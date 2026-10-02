/* =====================================================================
   CeliacMap — pwa.js
   Registers the app-shell service worker and shows an accessible notice
   while the device is offline. Nothing is queued or sent offline: the map,
   the assistant and the forms simply need a connection.
   ===================================================================== */
(function () {
  "use strict";

  var notice = document.getElementById("offline-notice");

  function updateNotice() {
    if (notice) notice.hidden = navigator.onLine !== false;
  }

  window.addEventListener("online", updateNotice);
  window.addEventListener("offline", updateNotice);
  updateNotice();

  if (!("serviceWorker" in navigator)) return;
  window.addEventListener("load", function () {
    navigator.serviceWorker.register("service-worker.js").catch(function () {});
  });
})();
