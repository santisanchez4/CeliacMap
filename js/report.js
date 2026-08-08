/* =====================================================================
   CeliacMap — js/report.js
   "Recomendar / reportar" form (Form B). Autocompletes against already
   published places (status='approved') via the Supabase REST API (anon
   key, read-only), then — once a place is matched — inserts directly into
   `place_reports` (anon key, INSERT-only RLS from Fase 1). No coordinates,
   no geocoding: unlike js/suggest.js this never creates a place, it only
   attaches evidence to one that already exists. See
   docs/architecture/ADR-004-community-reports-evidence-not-direct-action.md
   and docs/plans/PLAN-community-reviews.md.
   ===================================================================== */
(function () {
  "use strict";

  var cfg = window.CELIACMAP_CONFIG || {};
  var form = document.getElementById("report-form");
  if (!form) return;

  var statusEl = document.getElementById("rp-status");
  var submitBtn = document.getElementById("rp-submit");
  var honeypot = document.getElementById("rp-website");
  var typeRadios = form.querySelectorAll('input[name="rp-type"]');
  var searchEl = document.getElementById("rp-search");
  var searchClearBtn = document.getElementById("rp-search-clear");
  var placeIdEl = document.getElementById("rp-place-id");
  var resultsEl = document.getElementById("rp-results");
  var noMatchPositiveEl = document.getElementById("rp-no-match-positive");
  var noMatchNegativeEl = document.getElementById("rp-no-match-negative");
  var gotoSuggestLink = document.getElementById("rp-goto-suggest");
  var detailsEl = document.getElementById("rp-details");
  var descriptionEl = document.getElementById("rp-description");

  // Spam guards: a too-fast submit and a per-browser cooldown are bot signals.
  // Independent from suggest.js's own cooldown — recommending/reporting is a
  // different action and shouldn't be rate-limited by the other form.
  var MIN_FILL_MS = 3000;
  var COOLDOWN_MS = 60000;
  var COOLDOWN_KEY = "celiacmap-report-last";
  var renderedAt = Date.now();

  var MIN_CHARS = 2;
  var DEBOUNCE_MS = 300;
  var MAX_RESULTS = 8;

  var MSG = {
    es: {
      searching: "Buscando…",
      missing: "Elegí un lugar de la lista y contanos qué pasó (5 a 2000 caracteres).",
      cooldown: "Esperá un momento antes de enviar otro reporte.",
      sending: "Enviando…",
      success: "¡Gracias! Tu aporte se revisará junto con la información del lugar.",
      error: "No se pudo enviar. Probá de nuevo en unos minutos.",
      config: "El formulario no está disponible en este momento."
    },
    en: {
      searching: "Searching…",
      missing: "Pick a place from the list and tell us what happened (5 to 2000 characters).",
      cooldown: "Please wait a moment before sending another report.",
      sending: "Sending…",
      success: "Thanks! Your contribution will be reviewed together with the place's information.",
      error: "Could not send. Please try again in a few minutes.",
      config: "The form is not available right now."
    }
  };

  function lang() {
    return document.documentElement.getAttribute("lang") === "en" ? "en" : "es";
  }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function show(key, kind) {
    statusEl.textContent = MSG[lang()][key];
    statusEl.classList.remove("is-success", "is-error");
    if (kind === "ok") statusEl.classList.add("is-success");
    else if (kind === "err") statusEl.classList.add("is-error");
    statusEl.hidden = false;
  }

  function hideStatus() {
    statusEl.hidden = true;
  }

  function currentType() {
    for (var i = 0; i < typeRadios.length; i++) {
      if (typeRadios[i].checked) return typeRadios[i].value;
    }
    return "positive";
  }

  /* ------------------------- Autocomplete state ---------------------- */
  // A monotonically increasing token per query: only the response whose
  // token still matches `searchToken` at resolve time is applied. Without
  // this, a slow response to an earlier keystroke could resolve AFTER a
  // faster response to a later one and clobber it with stale results.
  var searchToken = 0;
  var searchTimer = null;
  var resultItems = []; // [{ place, el }]
  var activeIdx = -1;
  var selectedPlace = null; // { id, name, city } once committed

  function closeResults() {
    resultsEl.hidden = true;
    resultsEl.innerHTML = "";
    resultItems = [];
    activeIdx = -1;
    searchEl.setAttribute("aria-expanded", "false");
    searchEl.removeAttribute("aria-activedescendant");
  }

  function hideNoMatch() {
    noMatchPositiveEl.hidden = true;
    noMatchNegativeEl.hidden = true;
  }

  function showNoMatch() {
    closeResults();
    hideNoMatch();
    if (currentType() === "positive") noMatchPositiveEl.hidden = false;
    else noMatchNegativeEl.hidden = false;
  }

  function setActive(idx) {
    if (!resultItems.length) return;
    if (idx < 0) idx = resultItems.length - 1;
    if (idx >= resultItems.length) idx = 0;
    resultItems.forEach(function (it, i) {
      var on = i === idx;
      it.el.classList.toggle("is-active", on);
      if (on) it.el.setAttribute("aria-selected", "true");
      else it.el.removeAttribute("aria-selected");
    });
    activeIdx = idx;
    searchEl.setAttribute("aria-activedescendant", resultItems[idx].el.id);
    if (resultItems[idx].el.scrollIntoView) {
      resultItems[idx].el.scrollIntoView({ block: "nearest" });
    }
  }

  function selectPlace(place) {
    clearTimeout(searchTimer);
    selectedPlace = place;
    placeIdEl.value = place.id;
    searchEl.value = place.name;
    searchEl.setAttribute("readonly", "true");
    closeResults();
    hideNoMatch();
    searchClearBtn.hidden = false;
    detailsEl.hidden = false;
  }

  function clearSelection(focusInput) {
    selectedPlace = null;
    placeIdEl.value = "";
    searchEl.value = "";
    searchEl.removeAttribute("readonly");
    searchClearBtn.hidden = true;
    detailsEl.hidden = true;
    descriptionEl.value = "";
    closeResults();
    hideNoMatch();
    if (focusInput) searchEl.focus();
  }

  function renderResults(places) {
    resultsEl.innerHTML = "";
    resultItems = places.map(function (place, idx) {
      var li = document.createElement("li");
      li.className = "map-suggest-item";
      li.id = "rp-result-" + idx;
      li.setAttribute("role", "option");
      li.innerHTML =
        '<span class="map-suggest-name">' + esc(place.name) + "</span>" +
        '<span class="map-suggest-meta">' + esc(place.city || "") + "</span>";
      li.addEventListener("click", function (e) {
        e.stopPropagation();
        selectPlace(place);
      });
      li.addEventListener("mouseenter", function () { setActive(idx); });
      resultsEl.appendChild(li);
      return { place: place, el: li };
    });
    activeIdx = -1;
    resultsEl.hidden = false;
    searchEl.setAttribute("aria-expanded", "true");
  }

  function renderSearching() {
    resultsEl.innerHTML = '<li class="map-suggest-item" aria-disabled="true">' +
      '<span class="map-suggest-name">' + esc(MSG[lang()].searching) + "</span></li>";
    resultItems = [];
    activeIdx = -1;
    resultsEl.hidden = false;
    searchEl.setAttribute("aria-expanded", "true");
  }

  function runSearch(term) {
    var token = ++searchToken;
    if (!cfg.SUPABASE_URL || !cfg.SUPABASE_ANON_KEY) return;

    renderSearching();

    var url = cfg.SUPABASE_URL.replace(/\/+$/, "") +
      "/rest/v1/places?select=id,name,city&status=eq.approved&name=ilike.*" +
      encodeURIComponent(term) + "*&limit=" + MAX_RESULTS;

    fetch(url, {
      headers: {
        apikey: cfg.SUPABASE_ANON_KEY,
        Authorization: "Bearer " + cfg.SUPABASE_ANON_KEY
      }
    })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(function (rows) {
        if (token !== searchToken) return; // a newer query already superseded this one
        if (rows && rows.length) renderResults(rows);
        else showNoMatch();
      })
      .catch(function () {
        if (token !== searchToken) return;
        closeResults();
        hideNoMatch();
      });
  }

  function onSearchInput() {
    if (selectedPlace) return; // input is readonly while a place is selected
    var term = searchEl.value.trim();
    hideNoMatch();
    clearTimeout(searchTimer);
    if (term.length < MIN_CHARS) {
      searchToken++; // invalidate any in-flight query
      closeResults();
      return;
    }
    searchTimer = setTimeout(function () { runSearch(term); }, DEBOUNCE_MS);
  }

  searchEl.addEventListener("input", onSearchInput);

  searchEl.addEventListener("keydown", function (e) {
    if (!resultsEl.hidden) {
      if (e.key === "ArrowDown") { e.preventDefault(); setActive(activeIdx + 1); return; }
      if (e.key === "ArrowUp") { e.preventDefault(); setActive(activeIdx - 1); return; }
      if (e.key === "Enter") {
        e.preventDefault();
        if (activeIdx >= 0 && resultItems[activeIdx]) selectPlace(resultItems[activeIdx].place);
        return;
      }
      if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); closeResults(); return; }
    } else if (e.key === "Enter") {
      // Never let a bare Enter in the search box submit the form early.
      e.preventDefault();
    }
  });

  document.addEventListener("click", function (e) {
    if (!resultsEl.hidden && !form.contains(e.target)) closeResults();
  });

  searchClearBtn.addEventListener("click", function () {
    clearSelection(true);
  });

  typeRadios.forEach(function (radio) {
    radio.addEventListener("change", function () {
      // Only the no-match panel depends on type; a selection or an open
      // results list is left untouched (ADR-004 doesn't care about type
      // for an already-matched place).
      if (!noMatchPositiveEl.hidden || !noMatchNegativeEl.hidden) showNoMatch();
    });
  });

  if (gotoSuggestLink) {
    gotoSuggestLink.addEventListener("click", function () {
      // Let the native #suggest-form anchor scroll happen first (smooth
      // scroll is CSS-driven), then move focus into Form A for keyboard /
      // screen-reader users landing there.
      setTimeout(function () {
        var nameEl = document.getElementById("sg-name");
        if (nameEl) nameEl.focus();
      }, 400);
    });
  }

  /* ------------------------------ Submit ------------------------------ */
  form.addEventListener("submit", function (e) {
    e.preventDefault();

    // Honeypot filled, or submitted implausibly fast => silently accept so a
    // bot gets no signal, but never send the junk to the database.
    if ((honeypot && honeypot.value) || Date.now() - renderedAt < MIN_FILL_MS) {
      form.reset();
      clearSelection(false);
      show("success", "ok");
      return;
    }

    if (!cfg.SUPABASE_URL || !cfg.SUPABASE_ANON_KEY) {
      show("config", "err");
      return;
    }

    var description = (descriptionEl.value || "").trim();
    var placeId = placeIdEl.value;
    if (!placeId || description.length < 5 || description.length > 2000) {
      show("missing", "err");
      return;
    }

    var last = 0;
    try { last = parseInt(localStorage.getItem(COOLDOWN_KEY), 10) || 0; } catch (e1) {}
    if (Date.now() - last < COOLDOWN_MS) {
      show("cooldown", "err");
      return;
    }

    var data = {
      place_id: placeId,
      report_type: currentType(),
      description: description
    };

    submitBtn.disabled = true;
    form.setAttribute("aria-busy", "true");
    show("sending");

    fetch(cfg.SUPABASE_URL.replace(/\/+$/, "") + "/rest/v1/place_reports", {
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
        clearSelection(false);
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

  // Typing again after an error should clear the stale status message.
  descriptionEl.addEventListener("input", hideStatus);
})();
