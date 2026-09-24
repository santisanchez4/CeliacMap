/* =====================================================================
   CeliacMap — js/kitchen.js
   Shared "Sobre la cocina" block used by the suggest and report forms.
   Three optional radio questions (is the kitchen exclusively gluten free?,
   how is celiac food prepared?, is the owner celiac?). read() returns ONLY
   the answered keys, so leaving everything on "No sé" produces a payload
   identical to the one sent before this block existed.
   See docs/superpowers/specs/2026-09-24-kitchen-info-design.md.
   ===================================================================== */
(function () {
  "use strict";

  var PREP_VALUES = ["separate_kitchen", "separate_prep", "shared_kitchen"];

  function radios(root, question) {
    return root.querySelectorAll('input[data-kitchen-q="' + question + '"]');
  }

  function checkedValue(root, question) {
    var list = radios(root, question);
    for (var i = 0; i < list.length; i++) {
      if (list[i].checked) return list[i].value;
    }
    return "unknown";
  }

  function setChecked(root, question, value) {
    var list = radios(root, question);
    for (var i = 0; i < list.length; i++) list[i].checked = list[i].value === value;
  }

  function attach(root) {
    var prepBox = root.querySelector("[data-kitchen-prep]");

    // Question 2 only exists when question 1 is "No".
    function sync() {
      var mixed = checkedValue(root, "exclusive") === "no";
      prepBox.hidden = !mixed;
      if (!mixed) setChecked(root, "prep", "unknown");
    }

    function reset() {
      setChecked(root, "exclusive", "unknown");
      setChecked(root, "prep", "unknown");
      setChecked(root, "owner", "unknown");
      sync();
    }

    function read() {
      var out = {};
      if (root.hidden) return out;
      var exclusive = checkedValue(root, "exclusive");
      if (exclusive === "yes") {
        out.kitchen_exclusive = true;
      } else if (exclusive === "no") {
        out.kitchen_exclusive = false;
        var prep = checkedValue(root, "prep");
        if (PREP_VALUES.indexOf(prep) !== -1) out.celiac_prep = prep;
      }
      var owner = checkedValue(root, "owner");
      if (owner === "yes") out.owner_celiac = true;
      else if (owner === "no") out.owner_celiac = false;
      return out;
    }

    function setVisible(visible) {
      root.hidden = !visible;
      if (!visible) reset();
    }

    root.addEventListener("change", sync);
    var form = root.closest ? root.closest("form") : null;
    if (form) form.addEventListener("reset", function () { setTimeout(sync, 0); });
    sync();

    return { read: read, reset: reset, setVisible: setVisible };
  }

  window.CeliacKitchen = { attach: attach };
})();
