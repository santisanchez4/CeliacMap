"""Outreach agent — Etapa 1 (``outreach_send``) of the Outreach Agent.

Closes the gap where places sit indefinitely in ``needs_review`` (the
Validator's evidence floor, ADR-001) by contacting the business directly to
ask for confirmation. Per
``docs/architecture/ADR-002-outreach-evidence-not-autoapproval.md``, this
agent never approves anything itself — it only gathers a new piece of
evidence (the business's reply, handled by a separate, not-yet-built
``outreach_reply_handler``) for the Validator to re-weigh later.

Before selecting candidates, ``_scrape_missing_emails`` best-effort scrapes
each not-yet-checked place's own (non-social) website for a contact email via
``WebsiteScraperClient`` and persists ``places.contact_email`` /
``contact_email_checked_at`` — the real contact-email source live mode
(below) sends to once enabled.

Approach, per candidate:

1. Select the oldest ``needs_review`` places that still have
   ``outreach_status='not_sent'`` and a ``phone`` or ``website`` on file (a
   place with neither is unlikely to be reachable at all).
2. Draft a short confirmation email with ``claude-haiku-4-5`` (same
   fixed-rubric + JSON-contract pattern as the Social agent's ``PARSE_RUBRIC``).
3. Send it via Resend. **Recipient (ADR-003):** by default (``live_mode``
   false) every email still goes to a fixed ``test_recipient``, regardless of
   the place's own contact info. With ``live_mode`` true, it goes to the
   place's real ``contact_email`` instead — never a mix of the two (see
   CLAUDE.md's Outreach agent design decisions).
4. On success, record the sent message in ``outreach_messages`` and flip
   ``places.outreach_status`` to ``'sent'`` (channel ``'email'``) so the place
   isn't re-contacted every run. On failure, nothing is written — the place
   stays ``'not_sent'`` and is naturally retried on a later run.

Every outcome and a final run summary are written to ``agent_log``.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from agents.base import BaseAgent
from agents.clients.llm import LLMClient
from agents.clients.resend_client import ResendClient
from agents.clients.supabase_client import SupabaseClient
from agents.clients.website_scraper import WebsiteScraperClient, is_social_url

logger = logging.getLogger("celiacmap.agent")

# Oldest-first batch fetched before the phone/website filter is applied in
# Python (no precedent for an OR-filter query string in supabase_client.py;
# needs_review volume has historically been small — tens, not thousands).
CANDIDATE_FETCH_LIMIT = 200

# Haiku rubric: draft a short, respectful sin-TACC confirmation email.
OUTREACH_RUBRIC = """\
Redactás un email breve y respetuoso en nombre de CeliacMap, un proyecto \
comunitario que mapea lugares gluten free / sin TACC en Uruguay y Argentina, \
dirigido a un comercio que aparece como candidato en el mapa pero todavía no \
tiene evidencia suficiente confirmada.

Se te da el nombre del comercio, su categoría y su ciudad. El email debe:
- Presentar brevemente a CeliacMap (un mapa comunitario, no una entidad oficial). \
Al hacerlo, mencionar naturalmente que pueden ver cómo funciona en \
https://celiacmap.org — integrado en la misma oración de presentación, nunca \
como un link suelto al final ni como firma separada.
- Pedir amablemente que confirmen si ofrecen opciones sin TACC y, si es \
posible, que describan su protocolo de contaminación cruzada.
- Ser breve (2-3 párrafos cortos), cordial, sin sonar a spam ni a exigencia.
- Firmarse como "Equipo de CeliacMap".

Respondé ÚNICAMENTE con un objeto JSON válido, sin texto adicional, exactamente \
con esta forma:
{"subject": "<asunto breve>", "body": "<cuerpo del email en texto plano>"}
"""

# Fixed, non-LLM-generated closing line appended to every drafted body — a
# literal opt-out instruction the model never sees or paraphrases, so its
# exact wording can be trusted verbatim by the Haiku classifier in
# outreach_reply_handler.py (ADR-003).
OPT_OUT_FOOTER = (
    "Si preferís no recibir más contactos de CeliacMap, respondé este email "
    "indicando que no querés ser contactado nuevamente."
)


class OutreachAgent(BaseAgent):
    name = "outreach"

    def __init__(
        self,
        db: SupabaseClient,
        llm: LLMClient,
        resend_client: ResendClient,
        scraper: WebsiteScraperClient,
        *,
        test_recipient: str,
        haiku_model: str | None = None,
        max_per_run: int = 20,
        max_scrapes_per_run: int = 30,
        inbound_domain: str = "",
        sender_email: str = "outreach@celiacmap.org",
        live_mode: bool = False,
    ):
        super().__init__(db)
        self.llm = llm
        self.resend = resend_client
        self.scraper = scraper
        self.test_recipient = test_recipient
        self.haiku_model = haiku_model
        self.max_per_run = max_per_run
        self.max_scrapes_per_run = max_scrapes_per_run
        self.inbound_domain = inbound_domain
        self.sender_email = sender_email
        self.live_mode = live_mode

    def _reply_to_for(self, place_id: str) -> str | None:
        """Unique outreach+<place_id>@<inbound domain> address (Etapa 2) so a
        business's reply can be matched back to its place by the reply
        webhook. None (no Reply-To header) if inbound_domain isn't configured."""
        return f"outreach+{place_id}@{self.inbound_domain}" if self.inbound_domain else None

    def _scrape_missing_emails(self) -> dict:
        """Best-effort contact_email discovery for eligible needs_review places.

        Eligible: a non-social website on file and never scraped before
        (contact_email_checked_at is null). Runs once per place regardless of
        outcome — contact_email_checked_at is always stamped so the same site
        isn't re-scraped every run.
        """
        candidates = self.db.fetch_needs_review_for_outreach(CANDIDATE_FETCH_LIMIT)
        eligible = [
            p
            for p in candidates
            if p.get("website")
            and not is_social_url(p["website"])
            and p.get("contact_email_checked_at") is None
        ][: self.max_scrapes_per_run]

        scraped = found = 0
        for place in eligible:
            place_id = place.get("id")
            email = self.scraper.find_email(place["website"])
            scraped += 1
            found += bool(email)
            try:
                self.db.update_place(
                    place_id,
                    {
                        "contact_email": email,
                        "contact_email_checked_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
            except Exception:  # noqa: BLE001 - persistence failure must not abort the run
                logger.exception("failed to persist scraped email for %s", place_id)
                continue

        summary = {"scraped": scraped, "found": found}
        self.log("contact_email_scrape_complete", summary, status="success")
        return summary

    def _select_candidates(self) -> list[dict]:
        candidates = self.db.fetch_needs_review_for_outreach(CANDIDATE_FETCH_LIMIT)
        reachable = [
            p
            for p in candidates
            if (p.get("phone") or p.get("website"))
            and not p.get("outreach_opt_out")
            and (not self.live_mode or p.get("contact_email"))
        ]
        return reachable[: self.max_per_run]

    def _draft(self, place: dict) -> dict | None:
        """Use Haiku to draft {subject, body}. Returns None if invalid."""
        user = (
            f"place_name: {place.get('name')}\n"
            f"category: {place.get('category')}\n"
            f"city: {place.get('city') or ''}"
        )
        try:
            draft = self.llm.complete_json(
                OUTREACH_RUBRIC, user, model=self.haiku_model, max_tokens=400
            )
        except Exception:  # noqa: BLE001
            logger.exception("Haiku draft failed for %r", place.get("name"))
            return None

        subject = (draft.get("subject") or "").strip()
        body = (draft.get("body") or "").strip()
        if not subject or not body:
            return None
        return {"subject": subject, "body": f"{body}\n\n{OPT_OUT_FOOTER}"}

    def run(self) -> dict:
        self._scrape_missing_emails()
        candidates = self._select_candidates()

        candidates_seen = len(candidates)
        drafted = 0
        sent = 0
        errors = 0

        for place in candidates:
            place_id = place.get("id")

            draft = self._draft(place)
            if not draft:
                errors += 1
                self.log(
                    "outreach_draft_failed",
                    {"place_id": place_id, "name": place.get("name")},
                    status="error",
                    place_id=place_id,
                )
                continue
            drafted += 1

            if self.live_mode:
                recipient = place.get("contact_email")
                if not recipient:
                    errors += 1
                    logger.error(
                        "live mode: place %s has no contact_email, skipping send", place_id
                    )
                    self.log(
                        "outreach_send_missing_contact_email",
                        {"place_id": place_id, "name": place.get("name")},
                        status="error",
                        place_id=place_id,
                    )
                    continue
            else:
                recipient = self.test_recipient

            try:
                self.resend.send(
                    to=recipient,
                    subject=draft["subject"],
                    text=draft["body"],
                    from_address=self.sender_email,
                    reply_to=self._reply_to_for(place_id),
                )
            except Exception as exc:  # noqa: BLE001
                errors += 1
                logger.exception("Resend send failed for place %s", place_id)
                self.log(
                    "outreach_send_failed",
                    {"place_id": place_id, "name": place.get("name"), "error": str(exc)},
                    status="error",
                    place_id=place_id,
                )
                continue

            try:
                self.db.insert_outreach_message(
                    place_id,
                    direction="sent",
                    channel="email",
                    content=f"{draft['subject']}\n\n{draft['body']}",
                )
                self.db.update_place(
                    place_id, {"outreach_status": "sent", "outreach_channel": "email"}
                )
            except Exception:  # noqa: BLE001
                errors += 1
                logger.exception("failed to persist outreach result for %s", place_id)
                self.log(
                    "outreach_persist_failed",
                    {"place_id": place_id, "name": place.get("name")},
                    status="error",
                    place_id=place_id,
                )
                continue

            sent += 1
            self.log(
                "outreach_sent",
                {"place_id": place_id, "name": place.get("name")},
                status="success",
                place_id=place_id,
            )

        summary = {
            "candidates_seen": candidates_seen,
            "drafted": drafted,
            "sent": sent,
            "errors": errors,
        }
        self.log(
            "outreach_run_complete",
            summary,
            status="error" if errors else "success",
        )
        return summary


def main() -> int:
    """Run the Outreach agent standalone (manual pipeline validation)."""
    from config.settings import get_settings

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    settings = get_settings()
    settings.require(
        "supabase_url",
        "supabase_service_role_key",
        "anthropic_api_key",
        "resend_api_key",
        "outreach_test_recipient",
    )

    db = SupabaseClient(settings.supabase_url, settings.supabase_service_role_key)
    llm = LLMClient(settings.anthropic_api_key, settings.haiku_model)
    resend_client = ResendClient(settings.resend_api_key)
    scraper = WebsiteScraperClient()
    agent = OutreachAgent(
        db,
        llm,
        resend_client,
        scraper,
        test_recipient=settings.outreach_test_recipient,
        haiku_model=settings.haiku_model,
        max_per_run=settings.outreach_monthly_limit,
        max_scrapes_per_run=settings.max_email_scrapes_per_run,
        inbound_domain=settings.outreach_inbound_domain,
        sender_email=settings.outreach_sender_email,
        live_mode=settings.outreach_live_mode,
    )

    summary = agent.run()
    print("Outreach run complete:", summary)
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
