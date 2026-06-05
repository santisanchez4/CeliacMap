/* =====================================================================
   CeliacMap — js/map.js
   Real interactive map (Leaflet) backed by Supabase.
   - Fetches APPROVED places via the Supabase REST API (anon key).
   - Renders brand-colored markers with bilingual popups.
   - Wires the category chips (Todos / Restaurantes / Cafés / Comercios).
   Degrades gracefully: if Leaflet/config/data are unavailable, the map
   container simply shows a status message and the rest of the page works.
   ===================================================================== */
(function () {
  "use strict";

  var cfg = window.CELIACMAP_CONFIG || {};
  // #cm-map, not #map: the <section id="map"> is the nav anchor; using #map here
  // returned the section (first match) and made Leaflet size/click the whole section.
  var mapEl = document.getElementById("cm-map");
  if (!mapEl || typeof L === "undefined") return;
  var statusEl = document.getElementById("map-status");

  /* --------------------------- i18n labels -------------------------- */
  var LABELS = {
    category: {
      restaurant: { es: "Restaurante", en: "Restaurant" },
      cafe: { es: "Café", en: "Café" },
      shop: { es: "Comercio", en: "Shop" }
    },
    safety: {
      // 2 levels (matches the map legend): gluten_free_100 + celiac_friendly
      // share "Sin TACC"; options_available is "Tiene opciones sin TACC".
      gluten_free_100: { es: "Sin TACC", en: "Gluten-free" },
      celiac_friendly: { es: "Sin TACC", en: "Gluten-free" },
      options_available: { es: "Tiene opciones sin TACC", en: "Has gluten-free options" }
    },
    status: {
      loading: { es: "Cargando lugares…", en: "Loading places…" },
      empty: { es: "Todavía no hay lugares para mostrar.", en: "No places to show yet." },
      error: { es: "No se pudieron cargar los lugares.", en: "Couldn't load places." }
    },
    panel: {
      address: { es: "Dirección", en: "Address" },
      phone: { es: "Teléfono", en: "Phone" },
      hours: { es: "Horarios", en: "Opening hours" },
      website: { es: "Sitio web", en: "Website" },
      social: { es: "Redes sociales", en: "Social media" },
      visit: { es: "Visitar sitio", en: "Visit website" },
      report: { es: "Reportar un error", en: "Report an error" },
      reviews: { es: "reseñas", en: "reviews" }
    },
    source: {
      google_places: { es: "Verificado por Google", en: "Verified by Google" },
      social: { es: "Encontrado en redes sociales", en: "Found on social media" },
      manual: { es: "Lugar curado", en: "Curated place" },
      user: { es: "Sugerido por la comunidad", en: "Community suggested" }
    },
    controls: {
      results: { es: "resultados", en: "results" },
      result: { es: "resultado", en: "result" },
      noResults: {
        es: "No encontramos lugares con ese nombre.",
        en: "No places match that name."
      }
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

  function setStatus(key) {
    if (!statusEl) return;
    if (!key) {
      statusEl.classList.remove("is-visible");
      statusEl.textContent = "";
      return;
    }
    statusEl.textContent = LABELS.status[key][lang()];
    statusEl.classList.add("is-visible");
  }

  /* ------------------------------ Map ------------------------------- */
  // Centered on the Río de la Plata to frame both Montevideo and Buenos Aires.
  var map = L.map(mapEl, { scrollWheelZoom: false }).setView([-34.75, -57.4], 6);

  // The two Phase-1 cities. The default view frames exactly these two, so
  // outlier places (Mar del Plata, Paysandú, …) don't blow out the zoom and
  // collapse the city clusters into unclickable blobs.
  var CITY_BOUNDS = L.latLngBounds([
    [-34.9011, -56.1645], // Montevideo
    [-34.6037, -58.3816]  // Buenos Aires
  ]);

  L.tileLayer(
    "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
    {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> ' +
        '&copy; <a href="https://carto.com/attributions">CARTO</a>',
      maxZoom: 19
    }
  ).addTo(map);

  // Don't hijack page scroll until the user interacts with the map.
  map.on("focus", function () { map.scrollWheelZoom.enable(); });
  map.on("blur", function () { map.scrollWheelZoom.disable(); });

  // 2 visual levels: gluten_free_100 + celiac_friendly share the dark "safe"
  // color; options_available is the light "options" color.
  function safetyClass(level) {
    if (level === "options_available") return "cm-marker--options";
    return "cm-marker--safe";
  }

  function safetyBadgeClass(level) {
    if (level === "options_available") return "pp-badge--options";
    return "pp-badge--safe";
  }

  function icon(level) {
    return L.divIcon({
      className: "",
      html: '<span class="cm-marker ' + safetyClass(level) + '"></span>',
      iconSize: [18, 18],
      iconAnchor: [9, 9],
      popupAnchor: [0, -10]
    });
  }

  function popupHtml(p) {
    var l = lang();
    var cat = (LABELS.category[p.category] && LABELS.category[p.category][l]) || p.category;
    var saf = (LABELS.safety[p.safety_level] && LABELS.safety[p.safety_level][l]) || p.safety_level;
    var meta = esc(cat) + (p.city ? " · " + esc(p.city) : "");
    var addr = p.address ? '<div class="cm-popup-addr">' + esc(p.address) + "</div>" : "";
    return (
      '<div class="cm-popup">' +
      '<div class="cm-popup-title">' + esc(p.name) + "</div>" +
      '<div class="cm-popup-meta">' + meta + "</div>" +
      '<span class="badge badge-safe">' + esc(saf) + "</span>" +
      addr +
      "</div>"
    );
  }

  /* --------------------------- Side panel --------------------------- */
  var panelEl = document.getElementById("place-panel");
  var panelBody = document.getElementById("place-panel-body");
  var panelClose = document.getElementById("place-panel-close");
  var panelAvailable = !!(panelEl && panelBody);

  function stars(rating) {
    var full = Math.max(0, Math.min(5, Math.round(rating)));
    return "★★★★★".slice(0, full) + "☆☆☆☆☆".slice(0, 5 - full);
  }

  // Inline SVGs (themeable via currentColor) — no icon library.
  var ICONS = {
    phone:
      '<svg class="pp-ico" viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">' +
      '<path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" ' +
      'd="M5 4h3l1.5 5-2 1.5a11 11 0 0 0 5 5l1.5-2 5 1.5v3a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"/></svg>',
    external:
      '<svg class="pp-ico" viewBox="0 0 24 24" width="13" height="13" aria-hidden="true">' +
      '<path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" ' +
      'd="M14 4h6v6M20 4l-9 9M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5"/></svg>',
    instagram:
      '<svg class="pp-ico" viewBox="0 0 24 24" width="15" height="15" aria-hidden="true">' +
      '<rect x="3" y="3" width="18" height="18" rx="5" fill="none" stroke="currentColor" stroke-width="2"/>' +
      '<circle cx="12" cy="12" r="4" fill="none" stroke="currentColor" stroke-width="2"/>' +
      '<circle cx="17.5" cy="6.5" r="1.2" fill="currentColor"/></svg>',
    facebook:
      '<svg class="pp-ico" viewBox="0 0 24 24" width="15" height="15" aria-hidden="true">' +
      '<path fill="currentColor" d="M14 9h3V6h-3c-1.7 0-3 1.3-3 3v2H9v3h2v6h3v-6h2.5l.5-3H14V9.5c0-.3.2-.5.5-.5Z"/></svg>'
  };

  function socialIcon(url) {
    var u = String(url).toLowerCase();
    if (u.indexOf("instagram") !== -1) return ICONS.instagram;
    if (u.indexOf("facebook") !== -1 || u.indexOf("fb.com") !== -1) return ICONS.facebook;
    return ICONS.external;
  }

  // Render Google's weekday_text (Monday-first) with today's line highlighted.
  function hoursHtml(h) {
    var weekday = Array.isArray(h) ? h : (h && h.weekday_text) || null;
    if (!weekday || !weekday.length) {
      return '<span class="pp-hours-line">' + esc(String(h)) + "</span>";
    }
    var todayIdx = (new Date().getDay() + 6) % 7; // JS Sun=0 -> Google Mon=0
    var items = weekday
      .map(function (line, i) {
        var cls = i === todayIdx ? ' class="pp-hours-today"' : "";
        return "<li" + cls + ">" + esc(line) + "</li>";
      })
      .join("");
    return '<ul class="pp-hours">' + items + "</ul>";
  }

  function field(label, valueHtml) {
    return (
      '<div class="pp-field"><span class="pp-field-label">' + esc(label) +
      '</span><span class="pp-field-value">' + valueHtml + "</span></div>"
    );
  }

  // Renders only the fields present on the row, so phone/hours/website/social/
  // rating light up automatically once those columns exist and are populated.
  function panelHtml(p) {
    var l = lang();
    var cat = (LABELS.category[p.category] && LABELS.category[p.category][l]) || p.category;
    var saf = (LABELS.safety[p.safety_level] && LABELS.safety[p.safety_level][l]) || p.safety_level;
    var P = LABELS.panel;
    var html = '<h3 class="pp-title">' + esc(p.name) + "</h3>";
    if (p.city) html += '<p class="pp-meta">' + esc(p.city) + "</p>";

    html += '<div class="pp-badges">' +
      '<span class="pp-badge pp-badge--cat">' + esc(cat) + "</span>" +
      '<span class="pp-badge ' + safetyBadgeClass(p.safety_level) + '">' + esc(saf) + "</span>" +
      "</div>";

    if (typeof p.rating === "number" && p.rating > 0) {
      var num = p.rating.toFixed(1);
      var count =
        typeof p.user_ratings_total === "number"
          ? ' <span class="pp-rating-count">(' + p.user_ratings_total + " " + esc(P.reviews[l]) + ")</span>"
          : "";
      html += '<div class="pp-rating" aria-label="' + num + '/5">' +
        '<span class="pp-stars">' + stars(p.rating) + "</span>" +
        '<span class="pp-rating-num">' + num + "</span>" + count + "</div>";
    }

    html += '<div class="pp-fields">';
    if (p.address) html += field(P.address[l], esc(p.address));
    if (p.phone) {
      var tel = String(p.phone).replace(/[^\d+]/g, "");
      html += field(
        P.phone[l],
        '<a class="pp-link" href="tel:' + esc(tel) + '">' + ICONS.phone + esc(p.phone) + "</a>"
      );
    }
    if (p.opening_hours) html += field(P.hours[l], hoursHtml(p.opening_hours));
    if (p.website) {
      html += field(
        P.website[l],
        '<a class="pp-link" href="' + esc(p.website) + '" target="_blank" rel="noopener">' +
          esc(P.visit[l]) + ICONS.external + "</a>"
      );
    }
    if (p.social_url) {
      var socialText = p.social_url.replace(/^https?:\/\//, "").replace(/\/+$/, "");
      html += field(
        P.social[l],
        '<a class="pp-link" href="' + esc(p.social_url) + '" target="_blank" rel="noopener">' +
          socialIcon(p.social_url) + esc(socialText) + "</a>"
      );
    }
    html += "</div>";

    var srcLabel = (LABELS.source[p.source] && LABELS.source[p.source][l]) || "";
    if (srcLabel) {
      html += '<div class="pp-badges"><span class="pp-badge pp-badge--source">' + esc(srcLabel) + "</span></div>";
    }

    html += '<div class="pp-footer"><a class="pp-report" href="#" data-pp-report>' + esc(P.report[l]) + "</a></div>";
    return html;
  }

  function openPanel(p) {
    panelBody.innerHTML = panelHtml(p);
    panelEl.classList.add("is-open");
    panelEl.setAttribute("aria-hidden", "false");
  }

  function closePanel() {
    if (!panelAvailable) return;
    panelEl.classList.remove("is-open");
    panelEl.setAttribute("aria-hidden", "true");
  }

  // Open the side panel; fall back to the Leaflet popup if anything fails.
  function showDetails(p, marker) {
    if (panelAvailable) {
      try {
        openPanel(p);
        return;
      } catch (e) {
        /* fall through to popup */
      }
    }
    if (!marker.getPopup()) marker.bindPopup(popupHtml(p));
    marker.openPopup();
  }

  if (panelAvailable) {
    panelClose.addEventListener("click", closePanel);
    // Close on background map click (Leaflet does not fire this for markers).
    map.on("click", closePanel);
    // Close on click anywhere outside the panel and outside the map.
    document.addEventListener("click", function (e) {
      if (!panelEl.classList.contains("is-open")) return;
      if (panelEl.contains(e.target) || mapEl.contains(e.target)) return;
      closePanel();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closePanel();
    });
    // "Reportar error" is a placeholder for now.
    panelBody.addEventListener("click", function (e) {
      var t = e.target;
      if (t && t.getAttribute && t.getAttribute("data-pp-report") !== null) {
        e.preventDefault();
      }
    });
  }

  /* --------------------------- Markers ------------------------------ */
  var entries = [];                       // { marker, category, name, city }
  var visible = L.layerGroup().addTo(map);
  var currentCategory = "all";
  var currentCity = "all";
  var currentQuery = "";

  var searchInput = document.getElementById("place-search");
  var searchClear = document.getElementById("search-clear");
  var citySelect = document.getElementById("city-select");
  var countEl = document.getElementById("map-result-count");

  // A marker passes when it satisfies all three filters at once.
  function matches(e) {
    if (currentCategory !== "all" && e.category !== currentCategory) return false;
    if (currentCity !== "all" && e.city !== currentCity) return false;
    if (currentQuery.length >= 2 && e.name.indexOf(currentQuery) === -1) return false;
    return true;
  }

  function shownMarkers() {
    var out = [];
    entries.forEach(function (e) { if (matches(e)) out.push(e.marker); });
    return out;
  }

  // The result count only surfaces while actively searching (>= 2 chars).
  function updateCount(n) {
    if (!countEl) return;
    if (currentQuery.length < 2) {
      countEl.hidden = true;
      countEl.textContent = "";
      countEl.classList.remove("is-empty");
      return;
    }
    var l = lang();
    countEl.hidden = false;
    if (n === 0) {
      countEl.textContent = LABELS.controls.noResults[l];
      countEl.classList.add("is-empty");
    } else {
      var word = n === 1 ? LABELS.controls.result[l] : LABELS.controls.results[l];
      countEl.textContent = n + " " + word;
      countEl.classList.remove("is-empty");
    }
  }

  // Re-apply category + city + search to the marker layer.
  function refresh() {
    visible.clearLayers();
    var n = 0;
    entries.forEach(function (e) {
      if (matches(e)) { visible.addLayer(e.marker); n += 1; }
    });
    updateCount(n);
    return n;
  }

  function frameVisible() {
    map.invalidateSize();
    var shown = shownMarkers();
    if (shown.length) {
      map.fitBounds(L.featureGroup(shown).getBounds().pad(0.2), { maxZoom: 14 });
    } else if (currentCity === "all") {
      map.fitBounds(CITY_BOUNDS, { padding: [40, 40] });
    }
  }

  // Reframe once when the map first scrolls into view (handles init-below-fold),
  // and keep the size correct on window resize.
  if ("IntersectionObserver" in window) {
    var framedOnce = false;
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (en) {
        if (en.isIntersecting && !framedOnce) {
          framedOnce = true;
          frameVisible();
          io.disconnect();
        }
      });
    }, { threshold: 0.15 });
    io.observe(mapEl);
  }
  var resizeTimer;
  window.addEventListener("resize", function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () { map.invalidateSize(); }, 200);
  });

  // Re-render the dynamic count text when the page language toggles.
  document.addEventListener("celiacmap:lang", function () {
    updateCount(shownMarkers().length);
  });

  /* ----------------------------- Chips ------------------------------ */
  var chips = Array.prototype.slice.call(document.querySelectorAll(".map-chips .chip"));
  chips.forEach(function (chip) {
    chip.addEventListener("click", function () {
      chips.forEach(function (c) {
        c.classList.remove("chip-active");
        c.setAttribute("aria-pressed", "false");
      });
      chip.classList.add("chip-active");
      chip.setAttribute("aria-pressed", "true");
      currentCategory = chip.getAttribute("data-category") || "all";
      refresh();
      frameVisible();
    });
  });

  /* ------------------------- City selector -------------------------- */
  if (citySelect) {
    citySelect.addEventListener("change", function () {
      currentCity = citySelect.value || "all";
      refresh();
      var opt = citySelect.options[citySelect.selectedIndex];
      var lat = opt ? parseFloat(opt.getAttribute("data-lat")) : NaN;
      var lng = opt ? parseFloat(opt.getAttribute("data-lng")) : NaN;
      var zoom = opt ? parseInt(opt.getAttribute("data-zoom"), 10) : NaN;
      map.invalidateSize();
      if (currentCity !== "all" && isFinite(lat) && isFinite(lng)) {
        map.flyTo([lat, lng], isFinite(zoom) ? zoom : 13, { duration: 0.8 });
      } else {
        frameVisible();
      }
    });
  }

  /* --------------------------- Search ------------------------------- */
  function onSearch() {
    currentQuery = (searchInput.value || "").trim().toLowerCase();
    if (searchClear) searchClear.hidden = currentQuery.length === 0;
    refresh();
  }
  if (searchInput) searchInput.addEventListener("input", onSearch);
  if (searchClear) {
    searchClear.addEventListener("click", function () {
      searchInput.value = "";
      currentQuery = "";
      searchClear.hidden = true;
      refresh();
      searchInput.focus();
    });
  }

  /* ----------------------------- Data ------------------------------- */
  if (!cfg.SUPABASE_URL || !cfg.SUPABASE_ANON_KEY) {
    setStatus("error");
    return;
  }

  setStatus("loading");

  var url =
    cfg.SUPABASE_URL.replace(/\/+$/, "") +
    "/rest/v1/places?select=id,name,lat,lng,category,city,safety_level,address,source," +
    "phone,website,opening_hours,social_url,rating,user_ratings_total" +
    "&status=eq.approved&limit=1000";

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
      if (!Array.isArray(rows) || rows.length === 0) {
        setStatus("empty");
        return;
      }
      rows.forEach(function (p) {
        if (typeof p.lat !== "number" || typeof p.lng !== "number") return;
        var marker = L.marker([p.lat, p.lng], { icon: icon(p.safety_level), title: p.name });
        if (panelAvailable) {
          marker.on("click", (function (place, mk) {
            return function () { showDetails(place, mk); };
          })(p, marker));
        } else {
          marker.bindPopup(function () { return popupHtml(p); });
        }
        entries.push({
          marker: marker,
          category: p.category,
          name: (p.name || "").toLowerCase(),
          city: p.city || ""
        });
      });
      setStatus(null);
      refresh();
      frameVisible();
    })
    .catch(function () {
      setStatus("error");
    });
})();
