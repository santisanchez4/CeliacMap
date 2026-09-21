/* =====================================================================
   CeliacMap — js/ranking.js
   Community ranking (ADR-005). A "vote" is a single anonymous POST to the
   place_votes table (INSERT-only RLS; a duplicate returns 409/23505, which
   we treat as success — the server dedup). The list is read straight off
   the denormalized places.vote_count column via the same approved-places
   REST endpoint the map uses — no coordinates, no geocoding, no server
   code. Votes have NO authority over places.status; they only order places
   the Validator already approved. See
   docs/architecture/ADR-005-community-ranking.md and
   docs/plans/PLAN-community-ranking.md.
   ===================================================================== */
(function () {
  "use strict";

  var cfg = window.CELIACMAP_CONFIG || {};
  if (!cfg.SUPABASE_URL || !cfg.SUPABASE_ANON_KEY) return;

  var REST = cfg.SUPABASE_URL.replace(/\/+$/, "") + "/rest/v1";
  var AUTH = { apikey: cfg.SUPABASE_ANON_KEY, Authorization: "Bearer " + cfg.SUPABASE_ANON_KEY };

  var TOP_N = 12;
  var COOLDOWN_MS = 10000;
  var TOKEN_KEY = "celiacmap-voter-token";
  var VOTED_KEY = "celiacmap-voted";
  var LAST_KEY = "celiacmap-vote-last";
  var COUNTRY_KEY = "celiacmap-ranking-country";
  var DEFAULT_COUNTRY = "Argentina";

  var MSG = {
    es: {
      vote: "Votar",
      voted: "✓ Votado",
      one: "voto",
      many: "votos",
      empty: "Todavía no hay votos de la comunidad. Cuando la gente empiece a recomendar sus lugares seguros, el ranking aparece acá.",
      top3Empty: "Todavía no hay votos en este país.",
      country: "País del ranking",
      loadError: "No se pudo cargar el ranking.",
      voteError: "No se pudo votar. Probá de nuevo en un momento.",
      cooldown: "Esperá un momento antes de votar de nuevo."
    },
    en: {
      vote: "Vote",
      voted: "✓ Voted",
      one: "vote",
      many: "votes",
      empty: "No community votes yet. Once people start recommending their safe places, the ranking shows up here.",
      top3Empty: "No votes in this country yet.",
      country: "Ranking country",
      loadError: "Couldn't load the ranking.",
      voteError: "Couldn't vote. Try again in a moment.",
      cooldown: "Wait a moment before voting again."
    }
  };
  var SAFE = {
    // 2 public levels, same as js/map.js: celiac_friendly reads as "options".
    es: { gluten_free_100: "Espacio 100% sin gluten", celiac_friendly: "Tiene opciones sin TACC", options_available: "Tiene opciones sin TACC", dflt: "Información sin TACC" },
    en: { gluten_free_100: "100% gluten-free venue", celiac_friendly: "Has gluten-free options", options_available: "Has gluten-free options", dflt: "Gluten-free information" }
  };

  function lang() {
    return document.documentElement.getAttribute("lang") === "en" ? "en" : "es";
  }
  function t(k) { return MSG[lang()][k]; }
  function safeLabel(level) {
    var d = SAFE[lang()];
    return d[level] || d.dflt;
  }
  function badgeClass(level) {
    if (level === "gluten_free_100") return "pp-badge--dedicated";
    return level === "celiac_friendly" || level === "options_available" ? "pp-badge--options" : "pp-badge--source";
  }
  function votesLabel(n) { return n + " " + (n === 1 ? t("one") : t("many")); }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  /* --------------------------- localStorage ----------------------- */
  function lsGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function lsSet(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }

  function voterToken() {
    var tok = lsGet(TOKEN_KEY);
    if (tok && tok.length >= 8) return tok;
    tok = (window.crypto && crypto.randomUUID)
      ? crypto.randomUUID()
      : "v" + Date.now().toString(36) + Math.random().toString(36).slice(2, 12);
    lsSet(TOKEN_KEY, tok);
    return tok;
  }
  function votedSet() {
    try { return JSON.parse(lsGet(VOTED_KEY) || "[]") || []; } catch (e) { return []; }
  }
  function hasVoted(id) { return votedSet().indexOf(id) !== -1; }
  function markVoted(id) {
    var s = votedSet();
    if (s.indexOf(id) === -1) { s.push(id); lsSet(VOTED_KEY, JSON.stringify(s)); }
  }
  function coolingDown() {
    return Date.now() - (parseInt(lsGet(LAST_KEY), 10) || 0) < COOLDOWN_MS;
  }

  /* ---------------------------- Cast a vote ---------------------- */
  // Resolves to "ok" (new vote) | "already" | "cooldown" | "error".
  function castVote(placeId) {
    if (hasVoted(placeId)) return Promise.resolve("already");
    if (coolingDown()) return Promise.resolve("cooldown");
    return fetch(REST + "/place_votes", {
      method: "POST",
      headers: {
        apikey: cfg.SUPABASE_ANON_KEY,
        Authorization: "Bearer " + cfg.SUPABASE_ANON_KEY,
        "Content-Type": "application/json",
        Prefer: "return=minimal"
      },
      body: JSON.stringify({ place_id: placeId, voter_token: voterToken() })
    }).then(function (res) {
      // 2xx = new vote; 409 = duplicate (place_votes unique constraint) —
      // both mean "your vote is counted". Verified in Fase B.
      if (res.ok) { markVoted(placeId); lsSet(LAST_KEY, String(Date.now())); return "ok"; }
      if (res.status === 409) { markVoted(placeId); return "already"; }
      return "error";
    }).catch(function () { return "error"; });
  }

  function paintVoted(btn) {
    if (!btn) return;
    btn.textContent = t("voted");
    btn.classList.add("is-voted");
    btn.disabled = true;
  }

  // Wire one vote button (a fresh node — the panel rebuilds its button on
  // every open, the list rebuilds all of them on every render).
  function attachVote(btn, onResult) {
    btn.addEventListener("click", function () {
      var placeId = btn.getAttribute("data-place-id");
      if (!placeId || btn.disabled) return;
      if (hasVoted(placeId)) { paintVoted(btn); return; }
      btn.disabled = true;
      castVote(placeId).then(function (r) {
        if (r === "ok" || r === "already") paintVoted(btn);
        else btn.disabled = false;
        if (onResult) onResult(r, placeId);
      });
    });
  }

  /* --------------------------- Ranking list --------------------- */
  var listEl = document.getElementById("ranking-list");
  var statusEl = document.getElementById("ranking-status");
  // Both country selectors (the #ranking section's and the Top 3 card's) share
  // one state: picking a country in either one reloads both lists.
  var tabs = Array.prototype.slice.call(document.querySelectorAll(".ranking-tabs .chip, .map-top3-tabs .chip"));
  var tabGroups = Array.prototype.slice.call(document.querySelectorAll(".ranking-tabs, .map-top3-tabs"));
  // The "Top 3" widget next to the map — same data (rows.slice(0,3)), hidden
  // until data is ready / on error. A country with no votes keeps the card (and
  // its selector) visible so the other country stays one click away.
  var top3El = document.getElementById("map-top3");
  var top3ListEl = document.getElementById("map-top3-list");
  var country = lsGet(COUNTRY_KEY) || DEFAULT_COUNTRY;
  var rows = [];
  var loaded = false;   // true only after a successful fetch (gates the Top 3 card)
  var flashTimer;

  function metaText(p) {
    return (p.city ? esc(p.city) + " · " : "") + votesLabel(p.vote_count || 0);
  }

  function setStatus(msg) {
    if (!statusEl) return;
    statusEl.textContent = msg || "";
    statusEl.hidden = !msg;
  }
  function flash(key) {
    setStatus(t(key));
    clearTimeout(flashTimer);
    flashTimer = setTimeout(function () { setStatus(""); }, 3500);
  }

  function rowHtml(p, rank) {
    var voted = hasVoted(p.id);
    return (
      '<li class="ranking-item">' +
        '<span class="rk-rank">' + rank + "</span>" +
        '<div class="rk-info">' +
          '<span class="rk-name">' + esc(p.name) + "</span>" +
          (p.city ? '<span class="rk-city">' + esc(p.city) + "</span>" : "") +
          '<span class="pp-badge ' + badgeClass(p.safety_level) + '">' +
            esc(safeLabel(p.safety_level)) + "</span>" +
        "</div>" +
        '<div class="rk-actions">' +
          '<span class="rk-count" data-place-id="' + esc(p.id) + '">' +
            votesLabel(p.vote_count || 0) + "</span>" +
          '<button type="button" class="rk-vote' + (voted ? " is-voted" : "") +
            '" data-place-id="' + esc(p.id) + '"' + (voted ? " disabled" : "") + ">" +
            (voted ? t("voted") : t("vote")) + "</button>" +
        "</div>" +
      "</li>"
    );
  }

  function bumpCount(placeId) {
    for (var i = 0; i < rows.length; i++) {
      if (rows[i].id !== placeId) continue;
      rows[i].vote_count = (rows[i].vote_count || 0) + 1;
      if (listEl) {
        var c = listEl.querySelector('.rk-count[data-place-id="' + placeId + '"]');
        if (c) c.textContent = votesLabel(rows[i].vote_count);
        paintVoted(listEl.querySelector('.rk-vote[data-place-id="' + placeId + '"]'));
      }
      if (top3ListEl) {
        var m = top3ListEl.querySelector('.mt3-meta[data-place-id="' + placeId + '"]');
        if (m) m.textContent = metaText(rows[i]);
      }
      return;
    }
  }

  function top3RowHtml(p, rank) {
    return (
      '<li class="map-top3-item">' +
        '<span class="mt3-rank">' + rank + "</span>" +
        '<span class="mt3-name">' + esc(p.name) + "</span>" +
        '<span class="mt3-meta" data-place-id="' + esc(p.id) + '">' + metaText(p) + "</span>" +
      "</li>"
    );
  }

  function render() {
    renderList();
    renderTop3();
  }

  function renderList() {
    if (!listEl) return;
    if (!rows.length) {
      listEl.innerHTML = '<li class="ranking-empty">' + esc(t("empty")) + "</li>";
      return;
    }
    listEl.innerHTML = rows.map(function (p, i) { return rowHtml(p, i + 1); }).join("");
    Array.prototype.forEach.call(listEl.querySelectorAll(".rk-vote"), function (btn) {
      attachVote(btn, function (r, pid) {
        if (r === "ok") bumpCount(pid);
        else if (r === "cooldown") flash("cooldown");
        else if (r === "error") flash("voteError");
      });
    });
  }

  function renderTop3() {
    if (!top3ListEl || !loaded) return;
    top3ListEl.innerHTML = rows.length
      ? rows.slice(0, 3).map(function (p, i) { return top3RowHtml(p, i + 1); }).join("")
      : '<li class="map-top3-empty">' + esc(t("top3Empty")) + "</li>";
    if (top3El) top3El.hidden = false;
  }

  function load() {
    if (!listEl) return;
    loaded = false;
    setStatus("");
    var url = REST + "/places?select=id,name,city,country,category,safety_level,vote_count,rating" +
      "&status=eq.approved&country=eq." + encodeURIComponent(country) +
      "&vote_count=gt.0" +
      "&order=vote_count.desc,rating.desc.nullslast,name.asc&limit=" + TOP_N;
    fetch(url, { headers: AUTH })
      .then(function (res) { if (!res.ok) throw new Error("HTTP " + res.status); return res.json(); })
      .then(function (data) { rows = Array.isArray(data) ? data : []; loaded = true; render(); })
      .catch(function () {
        rows = [];
        if (listEl) listEl.innerHTML = "";
        if (top3El) top3El.hidden = true;   // no error clutter next to the map
        setStatus(t("loadError"));
      });
  }

  function selectCountry(c) {
    country = c;
    lsSet(COUNTRY_KEY, c);
    tabs.forEach(function (tb) {
      var on = tb.getAttribute("data-country") === c;
      tb.classList.toggle("chip-active", on);
      tb.setAttribute("aria-pressed", on ? "true" : "false");
    });
    load();
  }

  tabs.forEach(function (tb) {
    tb.addEventListener("click", function () { selectCountry(tb.getAttribute("data-country")); });
  });

  function labelTabGroups() {
    tabGroups.forEach(function (g) { g.setAttribute("aria-label", t("country")); });
  }
  document.addEventListener("celiacmap:lang", function () {
    labelTabGroups();
    if (listEl) render();
  });

  if (listEl) selectCountry(country);

  /* ----------------- Vote button inside the map panel ----------- */
  // js/map.js renders <button class="pp-vote" data-place-id> in .pp-footer
  // and dispatches "celiacmap:panel-open" with the place id after each
  // (re)build. All vote logic stays here.
  var panelEl = document.getElementById("place-panel");
  if (panelEl) {
    document.addEventListener("celiacmap:panel-open", function (e) {
      var id = e && e.detail;
      var btn = panelEl.querySelector(".pp-vote");
      if (!btn) return;
      if (id && hasVoted(id)) { paintVoted(btn); return; }
      attachVote(btn, function (r, pid) { if (r === "ok") bumpCount(pid); });
    });
  }
})();
