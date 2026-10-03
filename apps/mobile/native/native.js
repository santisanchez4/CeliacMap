/* =====================================================================
   CeliacMap — native.js (Android app only; the website never loads it)
   The Back button closes what is open, in the order a person expects,
   before sending the app to the background. Nothing else is native:
   location, map and chat run the same code as the website.
   ===================================================================== */
(function () {
  "use strict";

  var app = window.Capacitor && window.Capacitor.Plugins && window.Capacitor.Plugins.App;
  if (!app) return;

  function clickIf(id, isOpen) {
    var el = document.getElementById(id);
    if (!el || !isOpen(el)) return false;
    el.click();
    return true;
  }

  function closeTopmost() {
    var chat = document.getElementById("chat-panel");
    if (chat && !chat.hidden && clickIf("chat-panel-close", function () { return true; })) return true;

    var place = document.getElementById("place-panel");
    if (place && place.classList.contains("is-open") && clickIf("place-panel-close", function () { return true; })) return true;

    return clickIf("map-expand", function (el) { return el.getAttribute("aria-expanded") === "true"; });
  }

  app.addListener("backButton", function () {
    if (!closeTopmost()) app.minimizeApp();
  });
})();
