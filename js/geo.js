/* =====================================================================
   CeliacMap — geo.js
   Pure distance helpers for «Cerca mío»: no DOM, no network, no storage.
   The device position only ever passes through these functions as an
   argument; nothing here keeps it.
   ===================================================================== */
(function (root) {
  "use strict";

  var EARTH_RADIUS_KM = 6371.0088;

  function toRad(deg) { return deg * Math.PI / 180; }

  function isCoord(lat, lng) {
    return typeof lat === "number" && typeof lng === "number" && isFinite(lat) && isFinite(lng) &&
      Math.abs(lat) <= 90 && Math.abs(lng) <= 180;
  }

  // Great-circle ("straight line") distance in km between two {lat, lng}.
  function distanceKm(a, b) {
    var dLat = toRad(b.lat - a.lat);
    var dLng = toRad(b.lng - a.lng);
    var h = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLng / 2) * Math.sin(dLng / 2);
    return 2 * EARTH_RADIUS_KM * Math.asin(Math.min(1, Math.sqrt(h)));
  }

  // A reading less precise than this many metres is shown as an approximate zone.
  var APPROXIMATE_M = 1000;

  function isApproximate(accuracyM) {
    return typeof accuracyM === "number" && accuracyM > APPROXIMATE_M;
  }

  function decimal(n, lang) {
    var s = n.toFixed(1);
    return lang === "en" ? s : s.replace(".", ",");
  }

  // "A 1,2 km en línea recta" / "1.2 km away in a straight line". Never more
  // precise than the reading: metres round to 50 (100 when accuracy > 100 m),
  // and an approximate reading only gives whole kilometres.
  function formatDistance(km, accuracyM, lang) {
    var en = lang === "en";
    var m = km * 1000;
    if (isApproximate(accuracyM)) {
      var whole = Math.max(1, Math.round(km));
      return en ? "About " + whole + " km away in a straight line" : "A unos " + whole + " km en línea recta";
    }
    var step = typeof accuracyM === "number" && accuracyM > 100 ? 100 : 50;
    if (m < step) {
      return en ? "Less than " + step + " m away in a straight line" : "A menos de " + step + " m en línea recta";
    }
    var value;
    if (m < 1000) {
      var rounded = Math.round(m / step) * step;
      value = rounded >= 1000 ? "1" + (en ? ".0" : ",0") + " km" : rounded + " m";
    } else if (km < 10) {
      value = decimal(Math.round(km * 10) / 10, lang) + " km";
    } else {
      value = Math.round(km) + " km";
    }
    return en ? value + " away in a straight line" : "A " + value + " en línea recta";
  }

  // Places within radiusKm of origin, nearest first (ties by name), at most `limit`.
  function nearest(items, origin, radiusKm, limit) {
    if (!origin || !isCoord(origin.lat, origin.lng)) return [];
    var out = [];
    for (var i = 0; i < items.length; i++) {
      var p = items[i].place || items[i];
      if (!isCoord(p.lat, p.lng)) continue;
      var km = distanceKm(origin, { lat: p.lat, lng: p.lng });
      if (km <= radiusKm) out.push({ item: items[i], km: km });
    }
    out.sort(function (a, b) {
      if (a.km !== b.km) return a.km - b.km;
      var an = String((a.item.place || a.item).name || ""), bn = String((b.item.place || b.item).name || "");
      return an < bn ? -1 : an > bn ? 1 : 0;
    });
    return out.slice(0, limit);
  }

  root.CeliacGeo = {
    distanceKm: distanceKm,
    formatDistance: formatDistance,
    isApproximate: isApproximate,
    nearest: nearest
  };
})(typeof window !== "undefined" ? window : this);
