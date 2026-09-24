/* =====================================================================
   CeliacMap — js/opinions.js
   "La voz de la comunidad": shows the positive recommendations the admin
   approved, read from the public view community_opinions (anon key,
   read-only; the closed place_reports table is never touched). Every piece
   of people's text goes in through textContent — never as HTML. Cards are
   built here, so they must not use .reveal (the observer in main.js ran
   at load). See docs/superpowers/specs/2026-09-24-community-opinions-design.md.
   ===================================================================== */
(function () {
  "use strict";

  var cfg = window.CELIACMAP_CONFIG || {};
  var grid = document.getElementById("opinions-grid");
  if (!grid) return;

  var LIMIT = 6;
  var MAX_CHARS = 280;
  var ENOUGH = 3; // with this many opinions the invitation card is not needed

  var MSG = {
    es: {
      anonymous: "Anónimo",
      about: "sobre",
      emptyTitle: "Todavía no hay comentarios publicados",
      emptyText: "Sé la primera persona en contar cómo te fue.",
      moreTitle: "¿Fuiste a un lugar del mapa?",
      moreText: "Contanos cómo te fue.",
      cta: "Contanos tu experiencia"
    },
    en: {
      anonymous: "Anonymous",
      about: "about",
      emptyTitle: "No comments published yet",
      emptyText: "Be the first to tell us how it went.",
      moreTitle: "Been to a place on the map?",
      moreText: "Tell us how it went.",
      cta: "Tell us about your experience"
    }
  };

  var items = [];
  var loaded = false;

  function lang() {
    return document.documentElement.getAttribute("lang") === "en" ? "en" : "es";
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  // Cut at a whole word so the card never ends mid-word.
  function clip(text) {
    text = String(text || "").replace(/\s+/g, " ").trim();
    if (text.length <= MAX_CHARS) return text;
    var cut = text.slice(0, MAX_CHARS);
    var space = cut.lastIndexOf(" ");
    if (space > MAX_CHARS * 0.6) cut = cut.slice(0, space);
    return cut.replace(/[\s.,;:!?-]+$/, "") + "…";
  }

  function firstLetter(name) {
    var chars = Array.from(name);
    return chars.length ? chars[0].toUpperCase() : "";
  }

  function valid(row) {
    return row && typeof row.description === "string" && row.description.trim() &&
      typeof row.place_name === "string" && row.place_name && row.place_id;
  }

  function card(item) {
    var m = MSG[lang()];
    var name = (item.author_name || "").trim();
    var anonymous = !name;
    var article = el("article", "review");
    article.appendChild(el("p", "review-text", "“" + clip(item.description) + "”"));

    var author = el("div", "review-author");
    var avatar = el("span", "avatar" + (anonymous ? " avatar--anon" : ""), anonymous ? "" : firstLetter(name));
    avatar.setAttribute("aria-hidden", "true");
    author.appendChild(avatar);

    var who = el("div");
    who.appendChild(el("strong", null, anonymous ? m.anonymous : name));
    var place = el("button", "review-place", m.about + " " + item.place_name + (item.city ? " · " + item.city : ""));
    place.type = "button";
    place.setAttribute("data-place-id", item.place_id);
    who.appendChild(place);
    author.appendChild(who);
    article.appendChild(author);
    return article;
  }

  function inviteCard(hasItems) {
    var m = MSG[lang()];
    var box = el("article", "review review-cta");
    box.appendChild(el("p", "review-cta-title", hasItems ? m.moreTitle : m.emptyTitle));
    box.appendChild(el("p", "review-cta-text", hasItems ? m.moreText : m.emptyText));
    var link = el("a", "btn btn-outline", m.cta);
    link.setAttribute("href", "#report-form");
    box.appendChild(link);
    return box;
  }

  function render() {
    if (!loaded) return;
    while (grid.firstChild) grid.removeChild(grid.firstChild);
    items.forEach(function (item) { grid.appendChild(card(item)); });
    if (items.length < ENOUGH) grid.appendChild(inviteCard(items.length > 0));
  }

  grid.addEventListener("click", function (e) {
    var target = e.target && e.target.closest ? e.target.closest("[data-place-id]") : null;
    if (!target) return;
    try {
      document.dispatchEvent(new CustomEvent("celiacmap:open-place", { detail: { id: target.getAttribute("data-place-id") } }));
    } catch (err) {}
  });

  document.addEventListener("celiacmap:lang", render);

  function load() {
    if (!cfg.SUPABASE_URL || !cfg.SUPABASE_ANON_KEY) {
      loaded = true;
      render();
      return;
    }
    var url = cfg.SUPABASE_URL.replace(/\/+$/, "") +
      "/rest/v1/community_opinions?select=id,description,author_name,place_id,place_name,city,country" +
      "&order=published_at.desc&limit=" + LIMIT;
    fetch(url, { headers: { apikey: cfg.SUPABASE_ANON_KEY, Authorization: "Bearer " + cfg.SUPABASE_ANON_KEY } })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(function (rows) { items = Array.isArray(rows) ? rows.filter(valid) : []; })
      .catch(function () { items = []; })
      .then(function () { loaded = true; render(); });
  }

  load();
})();
