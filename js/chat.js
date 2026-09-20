/* =====================================================================
   CeliacMap — js/chat.js
   Floating assistant widget (ADR-006 decision 11). A thin client for the
   `chat` Edge Function: it keeps the conversation in memory (lost on
   reload, by design), echoes the server's `pending_submission` back on the
   next turn (Módulo 2's two-turn confirmation), and renders replies as
   plain text. All writes to place_reports / suggestions happen server-side
   inside the function — this file never touches the database. The chatbot
   has NO authority over places.status. See
   docs/architecture/ADR-006-chatbot-rag.md and docs/plans/PLAN-chatbot-rag.md.
   ===================================================================== */
(function () {
  "use strict";

  var cfg = window.CELIACMAP_CONFIG || {};
  var fab = document.getElementById("chat-fab");
  var panel = document.getElementById("chat-panel");
  var closeBtn = document.getElementById("chat-panel-close");
  var log = document.getElementById("chat-log");
  var form = document.getElementById("chat-form");
  var input = document.getElementById("chat-input");
  var sendBtn = document.getElementById("chat-send");
  var honeypot = document.getElementById("chat-hp");

  // The page works without the widget: no markup or no config => stay hidden.
  if (!fab || !panel || !closeBtn || !log || !form || !input || !sendBtn) return;
  if (!cfg.SUPABASE_URL || !cfg.SUPABASE_ANON_KEY) return;

  var ENDPOINT = cfg.SUPABASE_URL.replace(/\/+$/, "") + "/functions/v1/chat";

  // The server rejects any history entry over 2000 chars (400), so clamp on the
  // way in. 15 = 8 user turns + 7 assistant replies: matches the server's
  // CHAT_MAX_HISTORY_TURNS and keeps the slice starting on a user message.
  var MAX_MESSAGE_CHARS = 2000;
  var MAX_HISTORY_MESSAGES = 15;
  var REQUEST_TIMEOUT_MS = 30000;

  // Spam guards (own localStorage key — independent from report.js / suggest.js).
  // The three server-side caps are the real defence; these only trim noise.
  var MIN_FILL_MS = 2000;
  var COOLDOWN_MS = 1500;
  var COOLDOWN_KEY = "celiacmap-chat-last";
  var TOKEN_KEY = "celiacmap-chat-token";

  var MSG = {
    es: {
      title: "Asistente CeliacMap",
      open: "Abrir el asistente de CeliacMap",
      close: "Cerrar el asistente",
      inputLabel: "Tu mensaje",
      placeholder: "Preguntá por un lugar sin TACC…",
      send: "Enviar mensaje",
      intro: "Hola. Te ayudo a encontrar lugares sin TACC en Argentina y Uruguay, a dejar un comentario sobre un lugar o a sumar uno que conozcas. También respondo dudas generales sobre la celiaquía.",
      disclaimer: "El nivel de seguridad es una estimación de la comunidad y del sistema, no una garantía médica.",
      logNotice: "Las conversaciones marcadas como fuera de lo esperado pueden guardarse temporalmente (hasta 30 días) para mejorar la seguridad del servicio.",
      thinking: "Pensando…",
      error: "No pude responder ahora. Probá de nuevo en un momento.",
      wait: "Esperá un momento antes de enviar otro mensaje."
    },
    en: {
      title: "CeliacMap assistant",
      open: "Open the CeliacMap assistant",
      close: "Close the assistant",
      inputLabel: "Your message",
      placeholder: "Ask about a gluten-free place…",
      send: "Send message",
      intro: "Hi. I can help you find gluten-free places in Argentina and Uruguay, leave a comment about a place, or add one you know. I also answer general questions about celiac disease.",
      disclaimer: "The safety level is an estimate from the community and the system, not a medical guarantee.",
      logNotice: "Conversations flagged as unexpected may be stored temporarily (up to 30 days) to improve the safety of the service.",
      thinking: "Thinking…",
      error: "I couldn't answer right now. Try again in a moment.",
      wait: "Wait a moment before sending another message."
    }
  };

  function lang() {
    return document.documentElement.getAttribute("lang") === "en" ? "en" : "es";
  }
  function t(k) { return MSG[lang()][k]; }

  /* --------------------------- localStorage ----------------------- */
  function lsGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function lsSet(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }

  var memToken = null;
  function sessionToken() {
    if (memToken) return memToken;
    var tok = lsGet(TOKEN_KEY);
    if (!tok || tok.length < 8) {
      tok = (window.crypto && crypto.randomUUID)
        ? crypto.randomUUID()
        : "c" + Date.now().toString(36) + Math.random().toString(36).slice(2, 12);
      lsSet(TOKEN_KEY, tok);
    }
    memToken = tok;
    return tok;
  }

  /* ------------------------------ State --------------------------- */
  var turns = [];            // [{role, content}] — memory only, never persisted
  var pending = null;        // server's pending_submission, echoed on the next POST
  var busy = false;
  var isOpen = false;
  var openedAt = 0;          // first time the panel opened (MIN_FILL_MS clock)
  var introEl = null;
  var waitEl = null;
  var backgroundNodes = Array.prototype.map.call(document.querySelectorAll("main, .site-header, .site-footer"), function (node) {
    return { node: node, originallyInert: node.hasAttribute("inert") };
  });

  var mobileMq = window.matchMedia ? window.matchMedia("(max-width: 767px)") : null;
  function isMobile() { return !!(mobileMq && mobileMq.matches); }

  function clamp(s) {
    return s.length > MAX_MESSAGE_CHARS ? s.slice(0, MAX_MESSAGE_CHARS) : s;
  }

  /* ----------------------------- Chrome i18n ---------------------- */
  function eachNode(selector, fn) {
    Array.prototype.forEach.call(document.querySelectorAll(selector), fn);
  }
  function syncFab() {
    var label = t(isOpen ? "close" : "open");
    fab.setAttribute("aria-label", label);
    fab.setAttribute("title", label);
  }
  function applyChrome() {
    eachNode("[data-chat-text]", function (n) { n.textContent = t(n.getAttribute("data-chat-text")); });
    eachNode("[data-chat-aria]", function (n) { n.setAttribute("aria-label", t(n.getAttribute("data-chat-aria"))); });
    eachNode("[data-chat-placeholder]", function (n) { n.setAttribute("placeholder", t(n.getAttribute("data-chat-placeholder"))); });
    if (introEl) introEl.firstChild.textContent = t("intro");
    renderPrompts();
    syncFab();
  }

  /* ------------------------------ Rendering ----------------------- */
  // Replies are model output: always textContent, never innerHTML.
  function scrollToEnd() { log.scrollTop = log.scrollHeight; }

  // The REDACTOR is told to answer in plain text, but Haiku still wraps place
  // names in **bold** now and then. Render just that marker, as DOM nodes.
  function appendRich(parent, text) {
    text.split(/\*\*([^*\n]+?)\*\*/).forEach(function (part, i) {
      if (!part) return;
      if (i % 2 === 1) {
        var b = document.createElement("strong");
        b.textContent = part;
        parent.appendChild(b);
      } else {
        parent.appendChild(document.createTextNode(part));
      }
    });
  }

  function addMessage(kind, text, modifiers) {
    var el = document.createElement("div");
    el.className = "chat-msg chat-msg--" + kind;
    (modifiers || []).forEach(function (m) { el.classList.add("chat-msg--" + m); });
    var span = document.createElement("span");
    span.className = "chat-msg-text";
    if (kind === "bot") appendRich(span, text);
    else span.textContent = text;
    el.appendChild(span);
    log.appendChild(el);
    scrollToEnd();
    return el;
  }

  function addPlaceReferences(parent, places) {
    if (!parent || !Array.isArray(places) || !places.length) return;
    var list = document.createElement("div");
    list.className = "chat-place-links";
    places.slice(0, 8).forEach(function (place) {
      if (!place || typeof place.id !== "string" || typeof place.name !== "string") return;
      var button = document.createElement("button");
      button.type = "button";
      button.className = "chat-place-link";
      button.textContent = place.name + (place.city ? " · " + place.city : "");
      button.addEventListener("click", function (event) {
        event.stopPropagation();
        try { document.dispatchEvent(new CustomEvent("celiacmap:open-place", { detail: { id: place.id } })); } catch (e) {}
        if (isMobile()) setOpen(false, false);
      });
      list.appendChild(button);
    });
    if (list.childNodes.length) parent.appendChild(list);
    scrollToEnd();
  }

  function showThinking() {
    var el = document.createElement("div");
    el.className = "chat-thinking";
    for (var i = 0; i < 3; i++) {
      var dot = document.createElement("span");
      dot.className = "chat-thinking-dot";
      dot.setAttribute("aria-hidden", "true");
      el.appendChild(dot);
    }
    var sr = document.createElement("span");
    sr.className = "chat-sr-only";
    sr.textContent = t("thinking");
    el.appendChild(sr);
    log.appendChild(el);
    scrollToEnd();
    return el;
  }

  function removeNode(n) { if (n && n.parentNode) n.parentNode.removeChild(n); }

  function autosize() {
    input.style.height = "auto";
    var border = input.offsetHeight - input.clientHeight;
    input.style.height = Math.min(input.scrollHeight + border, 120) + "px";
  }
  function updateSendState() {
    sendBtn.disabled = busy || !input.value.trim();
  }
  function setBusy(v) {
    busy = v;
    panel.classList.toggle("is-busy", v);
    log.setAttribute("aria-busy", v ? "true" : "false");
    updateSendState();
  }

  /* ---------------------------- Open / close ---------------------- */
  function setOpen(open, returnFocus) {
    isOpen = open;
    panel.hidden = !open;
    fab.setAttribute("aria-expanded", open ? "true" : "false");
    syncFab();
    syncViewport();
    if (open) {
      document.dispatchEvent(new CustomEvent("celiacmap:chat-open"));
      if (!openedAt) openedAt = Date.now();
      scrollToEnd();
      // On a phone, opening a conversation should not immediately cover the
      // map with the virtual keyboard. The user can opt into typing naturally.
      if (!isMobile()) input.focus({ preventScroll: true });
      else closeBtn.focus({ preventScroll: true });
    } else if (returnFocus) {
      fab.focus();
    }
  }

  function syncViewport() {
    document.body.classList.toggle("chat-mobile-open", isOpen && isMobile());
    backgroundNodes.forEach(function (entry) {
      if (isOpen && isMobile()) entry.node.setAttribute("inert", "");
      else if (!entry.originallyInert) entry.node.removeAttribute("inert");
    });
    panel.setAttribute("aria-modal", String(isMobile()));
    if (window.visualViewport) {
      panel.style.setProperty("--chat-viewport-height", window.visualViewport.height + "px");
      panel.style.setProperty("--chat-viewport-top", window.visualViewport.offsetTop + "px");
    }
  }
  window.addEventListener("resize", syncViewport);
  if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", syncViewport);
    window.visualViewport.addEventListener("scroll", syncViewport);
  }
  panel.addEventListener("keydown", function (event) {
    if (event.key !== "Tab" || !isMobile()) return;
    var nodes = Array.prototype.filter.call(panel.querySelectorAll("button, textarea, a[href]"), function (node) {
      return !node.disabled && node.getClientRects().length;
    });
    var first = nodes[0], last = nodes[nodes.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });

  fab.addEventListener("click", function () { setOpen(!isOpen, true); });
  closeBtn.addEventListener("click", function () { setOpen(false, true); });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && isOpen) setOpen(false, true);
  });

  // The map's bottom-sheet (mobile) owns the bottom of the screen: the FAB steps
  // aside while it is open (the CSS only acts on it at ≤640px) and an open chat
  // sheet closes rather than stacking under it. State stays in memory.
  document.addEventListener("celiacmap:panel-open", function () {
    fab.classList.add("is-suppressed");
    if (isOpen && isMobile()) setOpen(false, false);
  });
  document.addEventListener("celiacmap:panel-close", function () {
    fab.classList.remove("is-suppressed");
  });

  /* ------------------------------ Sending ------------------------- */
  function request() {
    var ctrl = typeof AbortController === "function" ? new AbortController() : null;
    var timer = ctrl ? setTimeout(function () { ctrl.abort(); }, REQUEST_TIMEOUT_MS) : null;
    return fetch(ENDPOINT, {
      method: "POST",
      headers: {
        apikey: cfg.SUPABASE_ANON_KEY,
        Authorization: "Bearer " + cfg.SUPABASE_ANON_KEY,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        messages: turns.slice(-MAX_HISTORY_MESSAGES),
        session_token: sessionToken(),
        pending_submission: pending
      }),
      signal: ctrl ? ctrl.signal : undefined
    }).then(function (res) {
      clearTimeout(timer);
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    }, function (err) {
      clearTimeout(timer);
      throw err;
    });
  }

  function onReply(data) {
    if (!data || typeof data.reply !== "string" || !data.reply.trim()) {
      throw new Error("empty reply");
    }
    // Overwrite unconditionally: the server owns the draft. It echoes it back
    // unchanged on a rate-limited turn and clears it after a submission.
    pending = data.pending_submission || null;
    var kind = "bot";
    var mods = [];
    if (data.rate_limited) {
      kind = "notice";
    } else if (data.action &&
        (data.action.type === "report_submitted" || data.action.type === "suggestion_submitted")) {
      mods.push("sent");
    }
    var replyEl = addMessage(kind, data.reply, mods);
    if (!data.rate_limited) addPlaceReferences(replyEl, data.places);
    turns.push({ role: "assistant", content: clamp(data.reply) });
  }

  function send() {
    if (busy) return;

    // Honeypot filled: a bot. Drop silently, send nothing.
    if (honeypot && honeypot.value) {
      input.value = "";
      autosize();
      updateSendState();
      return;
    }

    var text = input.value.trim();
    if (!text) return;

    var now = Date.now();
    var last = parseInt(lsGet(COOLDOWN_KEY), 10) || 0;
    if (now - openedAt < MIN_FILL_MS || now - last < COOLDOWN_MS) {
      if (!waitEl || !waitEl.parentNode) waitEl = addMessage("notice", t("wait"));
      return;   // the text stays in the box
    }

    // Clear any previous transient bubble (wait notice / earlier error).
    removeNode(waitEl);
    waitEl = null;
    eachNode(".chat-msg--error", removeNode);

    turns.push({ role: "user", content: clamp(text) });
    renderPrompts();
    var userEl = addMessage("user", text);
    input.value = "";
    autosize();
    lsSet(COOLDOWN_KEY, String(now));
    setBusy(true);
    var thinkingEl = showThinking();

    request()
      .then(onReply)
      .catch(function () {
        // Roll the failed turn back so the history keeps alternating, and hand
        // the text back to the person. Never surface technical detail.
        turns.pop();
        removeNode(userEl);
        if (!input.value) { input.value = text; autosize(); }
        addMessage("error", t("error"));
      })
      .then(function () {
        removeNode(thinkingEl);
        setBusy(false);
        if (isOpen && !isMobile()) input.focus({ preventScroll: true });
      });
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    send();
  });
  input.addEventListener("input", function () {
    autosize();
    updateSendState();
  });
  input.addEventListener("keydown", function (e) {
    // Enter sends, Shift+Enter is a newline; never mid-IME-composition.
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      send();
    }
  });

  /* -------------------------------- Init -------------------------- */
  var promptsEl = document.createElement("div");
  promptsEl.className = "chat-prompts";
  function renderPrompts() {
    if (!promptsEl) return;
    promptsEl.hidden = turns.length > 0;
    promptsEl.innerHTML = "";
    var prompts = lang() === "en" ? ["Gluten-free cafés in Montevideo", "Places in Buenos Aires", "How can I suggest a place?"] : ["Cafés sin TACC en Montevideo", "Lugares en Buenos Aires", "¿Cómo sugiero un lugar?"];
    prompts.forEach(function (prompt) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "chat-place-link";
      button.textContent = prompt;
      button.addEventListener("click", function () {
        input.value = prompt;
        autosize();
        updateSendState();
        input.focus({ preventScroll: true });
      });
      promptsEl.appendChild(button);
    });
  }
  introEl = addMessage("intro", t("intro"));
  log.appendChild(promptsEl);
  document.addEventListener("celiacmap:lang", applyChrome);
  applyChrome();
  updateSendState();
  fab.hidden = false;
})();
