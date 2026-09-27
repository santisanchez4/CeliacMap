# Runbook — evidence finder for the admin-pending 100% queue

Tool: `scripts/find_evidence.py` (read-only) + `scripts/review_queue.py --proposals / --accept-proposals` (the admin's decision).
Code: `agents/evidence_finder.py`. Design and the pilot's findings: `docs/DECISIONS.md`, "Evidence finder for the admin-pending 100% queue".

## What it is, and what it never does

The queue is every place carrying the flag `100% pendiente de confirmación del administrador` (271 on 2026-09-27; all `approved` and
all still published as "Espacio 100% sin gluten": the flag was added with `cap_unsupported_100 --flag-only`, which does not change the map).
For each one the finder looks for **public** evidence about **that** business and proposes `100`, `options` or `insuficiente`, with the quotes.

- **It never writes to the database.** `EvidenceFinder` receives no DB client; `find_evidence.py` only reads the queue and writes a
  local report under `db/checks/evidence-proposals/` (git-ignored: third-party text and place ids that go stale).
- **It never changes `safety_level`, `status`, `flags` or `verified`.** Only `review_queue --accept-proposals --apply`, run by the admin, writes.
- **`insuficiente` proposes nothing** (no discard, no downgrade). The admin decides those by hand.

## Evidence rules (same criterion as the Validator's RUBRIC)

- Only quotes: a literal sentence of text the code retrieved, with the URL the code got. The model never writes one.
- The source must be about THAT business, decided by the code and never by the name alone: its URL is the place's own `website` / `social_url`; or
  the whole name and the city appear together; or its title / URL holds every distinctive word of the name AND the city or `places.region` appears.
  A name made only of generic or place words ("Concepción sin TACC" in Concepción del Uruguay) identifies no business: it matches only by its full
  name plus the city, or by its own URL. The model can only veto a quote ("this sentence is about another place"), never accept one the code rejected.
- On a page matched to the business only by its text (its title does not name it), a quote counts only in the same sentence as the name or up to 400
  characters after it. A page that lists several businesses (a listing word in its title or address, a blog, a numbered list of 3+ entries) never supports
  a plain 100: at most "100 · verificar en la fuente" (the citation is labelled "guía de varios negocios" and never quoted in the public note).
- Nothing from the model's own knowledge: it sees numbered quotes and returns only enum values (scope, contradiction, "about this business").
- Nothing about the health of a person (an owner who is celiac...): those sentences are dropped, and the public note is refused if it matches.
- Google Places reviews are **not** used (ToS: they are purged after 30 days; `place_evidence` is permanent).
- `100` needs an explicit exclusivity phrase (`ValidatorAgent.has_exclusive_signal`) + scope "the whole establishment" + no contradicting quote.
  The model can only take a place out of `100`, never put it there.

## Tavily quota (shared with the Social agent)

Tavily's free plan gives 1000 searches a month and the Social agent uses the same account (≤ 25–30 per pipeline run). The finder spends
**2 searches per place** (open web + Instagram/Facebook), or 3 with `--queries 3` (adds ACELU / ACELA / ACA).

1. **Check the account before any run** (read-only; the key stays in `.env`):
   `curl -s -H "Authorization: Bearer $TAVILY_API_KEY" https://api.tavily.com/usage` → `account.plan_usage` / `plan_limit`.
   On 2026-09-27 it read 25 / 1000 (plan Researcher, no pay-as-you-go). The counter can lag a few minutes behind the searches:
   it still read 25 right after the 20-search pilot, so re-read it before relying on it.
2. **The pilot** (`--pilot`, 10 places, 20 searches) can run at any time.
3. **The full queue waits until the monthly pipeline of the 1st has run** (2026-10-01): it needs ~542 searches (2 per place) or ~813 (3),
   and the Social agent must not be left without quota. Leave `--max-searches` below `plan_limit − plan_usage − 30`.
4. `--max-searches N` is **required** above 20 places. The run stops before the place that would pass the cap and lists the rest as
   `skipped_by_cap`; a skipped place gets no proposal (it is never reported as `insuficiente`). Run the remainder next month, or in
   chunks with `--offset` / `--limit`.

## Order of operations

1. `python -m scripts.find_evidence --pilot` → `db/checks/evidence-proposals/evidence-pilot-*.md` (+ `.json`, `.frozen.json`). Read the citations and the URLs.
   (Done on 2026-09-27: `db/checks/2026-09-27-evidence-finder-pilot.md`.)
2. After 2026-10-01 (pipeline done, usage re-read): `python -m scripts.find_evidence --max-searches N` (add `--limit` / `--offset` to chunk it).
3. `python -m scripts.review_queue --proposals REPORT.json [--only 100|options|insuficiente]` → the counts, the citations and the ids to copy.
4. Dry run: `python -m scripts.review_queue --accept-proposals ID1 ID2 … --report REPORT.json` — shows, per place, the level change,
   the note that goes to the public `validation_notes` and how many `place_evidence` rows (source `web`) would be saved.
5. Same command with `--apply` once you have read it. Accepting `options` lowers the public label ("Espacio 100% sin gluten" →
   "Tiene opciones sin TACC"): the dry run says so. One `agent_log` row (`validator` / `accept_evidence_proposals`) per applied run.

`--accept-proposals` refuses (and says why, exit code 1, the rest still go through): an id not in the report, `insuficiente`, a place that
no longer exists / is no longer `approved` / left the queue, a place with a manual decision in `validation_notes`, a place that changed
after the report (`updated_at`), and a note that would carry health data. The quote in the public note is at most 160 characters.

## Verification labels and the "100 · verificar en la fuente" rule

Every citation carries a label: **verificada en la página** (the quote is literal in the page the code downloaded, or the page is the place's own
site), **solo snippet** (the page does not contain it or could not be downloaded) or **red social: no verificable** (Instagram / Facebook / link-in-bio
cannot be downloaded). A "100" backed by at least one verified exclusivity quote is accepted in bulk. A "100" that rests only on snippets or social
profiles is **"100 · verificar en la fuente"**: `--accept-proposals` refuses it in bulk; open the link and accept it alone with
`--accept-proposals ID --report REPORT --verified-source`. The public note quotes only a verified quote; otherwise it says "evidencia en redes del local
(URL)" / "evidencia en la web (URL)" without the snippet. `options` and `insuficiente` work as before. The report also lists the model's textual reason
when it vetoes or lowers a proposal (and the quote that caused it), the sources an `insuficiente` discarded and why, and the Haiku tokens.

## Freeze and replay

Every live run saves `<report>.frozen.json` next to its report: the search hits and the pages it downloaded. `--replay FROZEN` repeats the run on
those sources: no Tavily searches, no page downloads (only Haiku, cents), so a change of logic is compared on exactly the same sources. Whatever
the freeze lacks (a page the new logic wants and the old never downloaded) is counted as `freeze_misses` and read as empty. `--no-freeze` skips the file.

## Tavily's usage counter is not a reliable meter

`api.tavily.com/usage` read 25 / 1000 on 2026-09-27 before AND after 40 searches of the two pilots: it did not move. Do not size a run from it. Count
your own spend: every report records `searches_used`; add them up and check the Tavily dashboard by hand before the full run.

## Limits to keep in mind

- `has_exclusive_signal` is a regex (it is the Validator's gate and this tool does not change it): it can miss real exclusivity phrases such as
  "exclusivamente para celíacos", which then land in `options` (the safe side), and it can match a product line, which the model's scope check vetoes.
- A quote is literal in the snippet Tavily returned, which is not always literal on the page; verify with the URL. Instagram / Facebook pages
  cannot be downloaded, so those quotes cannot be checked against the page at all.
- Chains and branches: a quote about the brand may not apply to that branch. The report shows the text; the admin decides.
- Guides and listicles: the code cannot tell whose sentence it is on a page of several businesses; it keeps only what sits next to the name and never lets such a
  page support a plain 100 (found on 2026-09-27 with a Superprof guide: the sentence of the previous restaurant of the list).
