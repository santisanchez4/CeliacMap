/* =====================================================================
   CeliacMap — js/suggest.js
   Public "Suggest a Place" form. Submits raw user input (no coordinates)
   to the `suggestions` table via the Supabase REST API using the public
   ANON key. RLS allows anon INSERT only (status forced to 'new'); the daily
   pipeline's Suggestion promoter geocodes + dedups + promotes each row into
   `places` (status 'pending') for the Validator to judge before it reaches
   the map. The service_role and Google keys never touch the browser.
   ===================================================================== */
(function () {
  "use strict";

  var cfg = window.CELIACMAP_CONFIG || {};
  var form = document.getElementById("suggest-form");
  if (!form) return;

  var statusEl = document.getElementById("sg-status");
  var submitBtn = document.getElementById("sg-submit");
  var honeypot = document.getElementById("sg-website");
  var nameEl = document.getElementById("sg-name");
  var addressEl = document.getElementById("sg-address");
  var cityEl = document.getElementById("sg-city");
  var countryEl = document.getElementById("sg-country");
  var categoryEl = document.getElementById("sg-category");
  var urlEl = document.getElementById("sg-url");
  var notesEl = document.getElementById("sg-notes");

  // Spam guards: a too-fast submit and a per-browser cooldown are bot signals.
  var MIN_FILL_MS = 3000;
  var COOLDOWN_MS = 60000;
  var COOLDOWN_KEY = "celiacmap-suggest-last";
  var renderedAt = Date.now();

  var MSG = {
    es: {
      missing: "Completá nombre, dirección, ciudad y país.",
      cooldown: "Esperá un momento antes de enviar otra sugerencia.",
      sending: "Enviando…",
      success: "¡Gracias! Tu sugerencia se revisará y, si se confirma, aparecerá en el mapa.",
      error: "No se pudo enviar. Probá de nuevo en unos minutos.",
      config: "El formulario no está disponible en este momento."
    },
    en: {
      missing: "Please fill in name, address, city and country.",
      cooldown: "Please wait a moment before sending another suggestion.",
      sending: "Sending…",
      success: "Thanks! Your suggestion will be reviewed and, if confirmed, it will appear on the map.",
      error: "Could not send. Please try again in a few minutes.",
      config: "The form is not available right now."
    }
  };

  function lang() {
    return document.documentElement.getAttribute("lang") === "en" ? "en" : "es";
  }

  function show(key, kind) {
    statusEl.textContent = MSG[lang()][key];
    statusEl.classList.remove("is-success", "is-error");
    if (kind === "ok") statusEl.classList.add("is-success");
    else if (kind === "err") statusEl.classList.add("is-error");
    statusEl.hidden = false;
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();

    // Honeypot filled, or submitted implausibly fast => silently accept so a bot
    // gets no signal, but never send the junk to the database.
    if ((honeypot && honeypot.value) || Date.now() - renderedAt < MIN_FILL_MS) {
      form.reset();
      show("success", "ok");
      return;
    }

    if (!cfg.SUPABASE_URL || !cfg.SUPABASE_ANON_KEY) {
      show("config", "err");
      return;
    }

    var data = {
      name: (nameEl.value || "").trim(),
      address: (addressEl.value || "").trim(),
      city: (cityEl.value || "").trim(),
      country: countryEl.value || "",
      category: categoryEl.value || null,
      evidence_url: (urlEl.value || "").trim() || null,
      notes: (notesEl.value || "").trim() || null
    };

    if (!data.name || !data.address || !data.city || !data.country) {
      show("missing", "err");
      return;
    }

    var last = 0;
    try { last = parseInt(localStorage.getItem(COOLDOWN_KEY), 10) || 0; } catch (e1) {}
    if (Date.now() - last < COOLDOWN_MS) {
      show("cooldown", "err");
      return;
    }

    submitBtn.disabled = true;
    form.setAttribute("aria-busy", "true");
    show("sending");

    fetch(cfg.SUPABASE_URL.replace(/\/+$/, "") + "/rest/v1/suggestions", {
      method: "POST",
      headers: {
        apikey: cfg.SUPABASE_ANON_KEY,
        Authorization: "Bearer " + cfg.SUPABASE_ANON_KEY,
        "Content-Type": "application/json",
        Prefer: "return=minimal"
      },
      body: JSON.stringify(data)
    })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        try { localStorage.setItem(COOLDOWN_KEY, String(Date.now())); } catch (e2) {}
        form.reset();
        renderedAt = Date.now();
        show("success", "ok");
      })
      .catch(function () {
        show("error", "err");
      })
      .then(function () {
        submitBtn.disabled = false;
        form.removeAttribute("aria-busy");
      });
  });
})();
