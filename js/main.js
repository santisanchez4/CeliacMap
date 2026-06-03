/* =====================================================================
   CeliacMap — main.js
   Lightweight progressive enhancement: mobile nav, smooth-scroll active
   links, ES/EN language toggle, and scroll reveal. No dependencies.
   The page is fully usable with JavaScript disabled (Spanish default).
   ===================================================================== */
(function () {
  "use strict";

  /* --------------------------- Current year ------------------------- */
  var yearEl = document.getElementById("year");
  if (yearEl) yearEl.textContent = String(new Date().getFullYear());

  /* ----------------------------- Mobile nav ------------------------- */
  var navToggle = document.getElementById("nav-toggle");
  var mainNav = document.getElementById("main-nav");

  function closeNav() {
    if (!mainNav) return;
    mainNav.classList.remove("open");
    if (navToggle) navToggle.setAttribute("aria-expanded", "false");
  }

  if (navToggle && mainNav) {
    navToggle.addEventListener("click", function () {
      var open = mainNav.classList.toggle("open");
      navToggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
    // Close the menu after tapping a link (mobile).
    mainNav.addEventListener("click", function (e) {
      if (e.target.closest("a")) closeNav();
    });
  }

  /* --------------------- Active nav link on scroll ------------------ */
  var navLinks = Array.prototype.slice.call(
    document.querySelectorAll(".main-nav a[href^='#']")
  );
  var sections = navLinks
    .map(function (link) {
      return document.querySelector(link.getAttribute("href"));
    })
    .filter(Boolean);

  if ("IntersectionObserver" in window && sections.length) {
    var navObserver = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          var id = entry.target.id;
          navLinks.forEach(function (link) {
            link.classList.toggle(
              "active",
              link.getAttribute("href") === "#" + id
            );
          });
        });
      },
      { rootMargin: "-45% 0px -50% 0px" }
    );
    sections.forEach(function (s) { navObserver.observe(s); });
  }

  /* ---------------------------- Scroll reveal ----------------------- */
  var reveals = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window) {
    var revealObserver = new IntersectionObserver(
      function (entries, obs) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            obs.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12 }
    );
    reveals.forEach(function (el) { revealObserver.observe(el); });
  } else {
    reveals.forEach(function (el) { el.classList.add("is-visible"); });
  }

  /* ---------------------- Language toggle (ES/EN) ------------------- */
  // Spanish lives in the HTML and is the default. We snapshot it on load,
  // so the dictionary below only needs to hold the English strings.
  var EN = {
    "skip": "Skip to main content",

    "nav.problem": "Problem",
    "nav.solution": "Solution",
    "nav.features": "Features",
    "nav.map": "Map",
    "nav.roadmap": "Roadmap",
    "nav.about": "About",

    "lang.current": "EN",
    "lang.other": "ES",

    "hero.eyebrow": "Gluten-free community",
    "hero.title": "Eating out, without fear.",
    "hero.subtitle": "The map of gluten-free places the celiac community validates, looks after and grows.",
    "hero.ctaPrimary": "Explore the map",
    "hero.ctaSecondary": "How it works",
    "hero.stat1": "places in the vision",
    "hero.stat2": "community validated",
    "hero.stat3": "always-updated info",
    "hero.badge": "100% gluten-free",

    "problem.eyebrow": "The problem",
    "problem.title": "Eating out shouldn't be a risk",
    "problem.lead": "Every outing brings the same question: is this place really safe?",
    "problem.c1.title": "Constant uncertainty",
    "problem.c1.text": "Not knowing if a place is safe creates stress at every meal away from home.",
    "problem.c2.title": "Cross-contamination risk",
    "problem.c2.text": "A single cross-contamination can harm the health of a person with celiac disease.",
    "problem.c3.title": "Scattered information",
    "problem.c3.text": "Data is spread across groups, social media and loose recommendations.",

    "solution.eyebrow": "The solution",
    "solution.title": "One trusted place to find it all",
    "solution.lead": "Everything gluten-free, gathered on one clear map and looked after by the community.",
    "solution.s1.title": "Search",
    "solution.s1.text": "Find restaurants, cafés and shops that are safe near you in seconds.",
    "solution.s2.title": "Trust",
    "solution.s2.text": "Each place shows its safety level and reviews from the community.",
    "solution.s3.title": "Share",
    "solution.s3.text": "Add new places and help the network grow for everyone.",

    "features.eyebrow": "Features",
    "features.title": "Everything you need, in one platform",
    "features.lead": "Simple, clear and made for everyday life.",
    "features.f1.title": "Smart search",
    "features.f1.text": "Filter by location, type of place and safety level.",
    "features.f2.title": "Interactive map",
    "features.f2.text": "See all the safe places near you at a glance.",
    "features.f3.title": "Verified places",
    "features.f3.text": "Clear safety labels backed by the community.",
    "features.f4.title": "Real reviews",
    "features.f4.text": "Experiences from other celiac people who have been there.",

    "map.eyebrow": "Interactive map",
    "map.title": "The heart of CeliacMap",
    "map.lead": "Safe places, safety levels and quick filters. All at a glance.",
    "map.chip1": "All",
    "map.chip2": "Restaurants",
    "map.chip3": "Cafés",
    "map.chip4": "Shops",
    "map.popupBadge": "100% gluten-free",
    "map.legend1": "100% gluten-free",
    "map.legend2": "Safe options",

    "suggest.eyebrow": "Add a place",
    "suggest.title": "The community grows the map",
    "suggest.lead": "Know a safe place that isn't on the map yet? Adding it will be this simple.",
    "suggest.s1.title": "Pin the place",
    "suggest.s1.text": "Set the location and type of business on the map.",
    "suggest.s2.title": "Share your experience",
    "suggest.s2.text": "Add safety details, the gluten-free menu and a short review.",
    "suggest.s3.title": "Help the community",
    "suggest.s3.text": "Your contribution is validated and made available to everyone.",

    "reviews.eyebrow": "Reviews",
    "reviews.title": "The voice of the community",
    "reviews.lead": "Real experiences that build trust.",
    "reviews.r1.text": "“I can finally eat out without anxiety. I found three safe places just steps from home.”",
    "reviews.r1.role": "Celiac for 8 years",
    "reviews.r2.text": "“The safety labels give me peace of mind. Knowing other celiacs validated it changes everything.”",
    "reviews.r2.role": "Father of a celiac girl",
    "reviews.r3.text": "“I added my favorite café in a minute. I love helping more people discover it.”",
    "reviews.r3.role": "Part of the community",

    "ai.eyebrow": "Future vision · Roadmap",
    "ai.title": "Artificial intelligence at the service of the community",
    "ai.lead": "Agents that discover, validate and keep every place up to date. Automatically and reliably.",
    "ai.li1": "Automatically discover new safe places.",
    "ai.li2": "Validate and cross-check reviews to detect inconsistencies.",
    "ai.li3": "Keep menus and data always up to date.",
    "ai.note": "Note: AI is part of the product's future vision, not the current version.",

    "roadmap.eyebrow": "Roadmap",
    "roadmap.title": "How the product will grow",
    "roadmap.lead": "A phased plan, designed to grow alongside the community.",
    "roadmap.p1.phase": "Phase 1",
    "roadmap.p1.title": "Map MVP",
    "roadmap.p1.text": "Landing page and conceptual map with safe places and safety levels.",
    "roadmap.p2.phase": "Phase 2",
    "roadmap.p2.title": "Community",
    "roadmap.p2.text": "Place suggestions, reviews and collaborative validation.",
    "roadmap.p3.phase": "Phase 3",
    "roadmap.p3.title": "AI & agents",
    "roadmap.p3.text": "Automatic discovery and validation of information with AI.",
    "roadmap.p4.phase": "Phase 4",
    "roadmap.p4.title": "Expansion",
    "roadmap.p4.text": "Mobile app and growth into new cities and countries.",

    "about.eyebrow": "About the project",
    "about.title": "An idea with purpose",
    "about.lead": "CeliacMap started as an academic and portfolio project: the foundation for a future app so the celiac community can eat safely.",
    "about.role": "Developer · Project author",

    "cta.title": "Join a safer way to eat out",
    "cta.text": "Explore the map and join the community that makes eating gluten-free simple.",
    "cta.primary": "Explore the map",
    "cta.secondary": "View on GitHub",

    "footer.tagline": "Safe gluten-free places, mapped by the community.",
    "footer.credit": "Made by Santiago Sanchez"
  };

  var i18nNodes = Array.prototype.slice.call(
    document.querySelectorAll("[data-i18n]")
  );

  // Snapshot the Spanish defaults straight from the markup.
  var ES = {};
  i18nNodes.forEach(function (node) {
    ES[node.getAttribute("data-i18n")] = node.textContent;
  });

  function applyLang(lang) {
    var dict = lang === "en" ? EN : ES;
    i18nNodes.forEach(function (node) {
      var key = node.getAttribute("data-i18n");
      if (dict[key] != null) node.textContent = dict[key];
    });
    document.documentElement.setAttribute("lang", lang);
    try { localStorage.setItem("celiacmap-lang", lang); } catch (e) {}
  }

  var langToggle = document.getElementById("lang-toggle");
  var stored;
  try { stored = localStorage.getItem("celiacmap-lang"); } catch (e) {}
  if (stored === "en") applyLang("en");

  if (langToggle) {
    langToggle.addEventListener("click", function () {
      var next = document.documentElement.getAttribute("lang") === "en" ? "es" : "en";
      applyLang(next);
    });
  }
})();
