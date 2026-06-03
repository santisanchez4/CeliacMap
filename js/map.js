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
  var mapEl = document.getElementById("map");
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
      gluten_free_100: { es: "100% sin TACC", en: "100% gluten-free" },
      celiac_friendly: { es: "Apto celíacos", en: "Celiac-friendly" },
      options_available: { es: "Opciones aptas", en: "Options available" }
    },
    status: {
      loading: { es: "Cargando lugares…", en: "Loading places…" },
      empty: { es: "Todavía no hay lugares para mostrar.", en: "No places to show yet." },
      error: { es: "No se pudieron cargar los lugares.", en: "Couldn't load places." }
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

  function safetyClass(level) {
    return level === "gluten_free_100" ? "cm-marker--safe" : "cm-marker--mid";
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

  /* --------------------------- Markers ------------------------------ */
  var entries = [];                       // { marker, category }
  var visible = L.layerGroup().addTo(map);

  function applyFilter(category) {
    visible.clearLayers();
    var shown = [];
    entries.forEach(function (e) {
      if (category === "all" || e.category === category) {
        visible.addLayer(e.marker);
        shown.push(e.marker);
      }
    });
    if (shown.length) {
      map.fitBounds(L.featureGroup(shown).getBounds().pad(0.2), { maxZoom: 14 });
    }
  }

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
      applyFilter(chip.getAttribute("data-category") || "all");
    });
  });

  /* ----------------------------- Data ------------------------------- */
  if (!cfg.SUPABASE_URL || !cfg.SUPABASE_ANON_KEY) {
    setStatus("error");
    return;
  }

  setStatus("loading");

  var url =
    cfg.SUPABASE_URL.replace(/\/+$/, "") +
    "/rest/v1/places?select=id,name,lat,lng,category,city,safety_level,address" +
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
        marker.bindPopup(function () { return popupHtml(p); });
        entries.push({ marker: marker, category: p.category });
      });
      setStatus(null);
      applyFilter("all");
    })
    .catch(function () {
      setStatus("error");
    });
})();
