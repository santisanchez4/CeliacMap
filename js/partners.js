/* =====================================================================
   CeliacMap — js/partners.js
   Partner program «CeliacMap Aliado» (ADR-011, PLAN-partner-program.md
   §3). Renders nothing unless CELIACMAP_CONFIG.PARTNER_PROGRAM === true.
   With it on: the published partners (read from the `partners_public`
   view) and the «Plan Fundador» card with its request form, which INSERTs
   into `partner_applications` with the anon key (INSERT only, on the 11
   request columns). No payment link lives here: it goes by email once
   the request is eligible. Being a partner never touches the map.
   ===================================================================== */
(function () {
  "use strict";

  var PROGRAM = {
    price: 790,
    currency: "$U",
    consentVersion: "condiciones-aliados-1.0-borrador",
    privacyUrl: "privacidad.html",
    logoBucket: "partner-logos",
    text: {
      es: {
        label: "Aliado",
        chip: "Plan Fundador",
        title: "CeliacMap Aliado",
        subtitle: "Un patrocinio publicitario mensual que ayuda a sostener el proyecto.",
        per: "/ mes",
        terms: "Pago mensual recurrente · Cancelás cuando quieras · Sin permanencia",
        founder: "Quien se suma en esta etapa mantiene el precio durante 12 meses.",
        benefitsTitle: "Qué incluye",
        benefits: [
          "Un perfil destacado en la sección Aliados, con la etiqueta «Aliado».",
          "El logo, imágenes y datos comerciales de tu comercio.",
          "Enlaces directos a tu WhatsApp, tus redes o tu sitio web.",
          "Difusión en las publicaciones colectivas de aliados en las redes de CeliacMap."
        ],
        notice: "Ser aliado es publicidad. No significa que CeliacMap certifique la seguridad alimentaria del comercio ni cambia cómo aparece en el mapa.",
        open: "Quiero ser aliado",
        close: "Ocultar el formulario",
        formTitle: "Solicitud para ser aliado",
        formIntro: "No pagás nada ahora. Revisamos tu solicitud y te respondemos por email.",
        business: "Nombre del comercio *",
        city: "Ciudad *",
        country: "País *",
        countryPh: "Elegí un país",
        contactName: "Persona responsable *",
        email: "Email *",
        phone: "Teléfono o WhatsApp",
        links: "Web o redes",
        linksPh: "Ej: instagram.com/tucomercio",
        description: "Contanos brevemente qué ofrecés",
        onMap: "¿Ya está en el mapa de CeliacMap? *",
        onMapPh: "Elegí una opción",
        yes: "Sí",
        no: "No",
        unsure: "No sé",
        conditionsTitle: "Condiciones del Plan Fundador",
        conditions: [
          "Precio: {price} por mes, en pesos uruguayos.",
          "El cobro es mensual y recurrente, con Mercado Pago.",
          "Sin permanencia: cancelás cuando quieras. Al cancelar, la tarjeta sigue visible hasta el final del período ya pagado.",
          "Ser aliado es publicidad: no certifica la seguridad alimentaria ni cambia nada del comercio en el mapa.",
          "Te respondemos por email dentro de los 5 días hábiles.",
          "No se paga nada antes de esa respuesta: si tu comercio califica, te mandamos el link de pago por email."
        ],
        consentBefore: "Leí las condiciones del Plan Fundador y la ",
        consentLink: "política de privacidad",
        consentAfter: ", y acepto que CeliacMap use estos datos para responder a mi solicitud. *",
        honeypot: "No completar este campo",
        submit: "Enviar solicitud",
        doneTitle: "Recibimos tu solicitud",
        doneCode: "Tu código de solicitud es",
        doneKeep: "Guardalo: lo vas a necesitar en los próximos pasos.",
        doneSteps: [
          "Revisamos tu solicitud y te respondemos por email dentro de los 5 días hábiles.",
          "Si tu comercio califica, te mandamos por email el link de pago de Mercado Pago. No pagues nada antes de esa respuesta.",
          "Después de pagar, respondé ese email con tu código y el número de operación de Mercado Pago.",
          "Nos mandás el logo, el texto y los enlaces de tu tarjeta; los revisamos y la publicamos."
        ],
        faqTitle: "Preguntas frecuentes",
        faq: [
          ["¿Qué incluye?", "Un perfil destacado en esta sección con la etiqueta «Aliado», tu logo, imágenes y datos comerciales, enlaces directos a tu WhatsApp, redes o web, y la difusión en las publicaciones colectivas de aliados."],
          ["¿Cómo se paga?", "Con Mercado Pago, en un cobro mensual recurrente de {price}. El link de pago te llega por email solo si tu solicitud califica. CeliacMap no ve ni guarda los datos de tu tarjeta."],
          ["¿Cómo cancelo?", "Cuando quieras, desde tu cuenta de Mercado Pago o escribiendo a hola@celiacmap.org. No hay permanencia: la tarjeta sigue visible hasta el final del período ya pagado."],
          ["¿Mi comercio aparece más arriba en el mapa?", "No. Ser aliado no agrega ni saca a tu comercio del mapa, no cambia su etiqueta ni su lugar en el ranking, las búsquedas o el chat."],
          ["¿Quién puede ser aliado?", "Un lugar aprobado en el mapa, o un comercio de productos o servicios sin gluten relevantes para la comunidad celíaca. No pueden serlo las cadenas de supermercados, autoservicios o farmacias, ni quien prometa curas. Cada solicitud la revisa una persona."]
        ],
        msg: {
          missing: "Completá los campos marcados con * y aceptá las condiciones.",
          email: "Revisá el email: no parece válido.",
          phone: "El teléfono tiene que tener entre 6 y 40 caracteres.",
          cooldown: "Esperá un momento antes de enviar otra solicitud.",
          sending: "Enviando…",
          duplicate: "Ya tenemos una solicitud tuya para este comercio. Te escribimos por email; si tenés dudas, escribinos a hola@celiacmap.org.",
          error: "No se pudo enviar. Probá de nuevo en unos minutos.",
          config: "El formulario no está disponible en este momento."
        }
      },
      en: {
        label: "Partner",
        chip: "Founding Plan",
        title: "CeliacMap Partner",
        subtitle: "A monthly advertising sponsorship that helps keep the project going.",
        per: "/ month",
        terms: "Recurring monthly payment · Cancel anytime · No minimum term",
        founder: "Businesses that join at this stage keep the price for 12 months.",
        benefitsTitle: "What it includes",
        benefits: [
          "A featured profile in the Partners section, labeled \"Partner\".",
          "Your business's logo, images and business details.",
          "Direct links to your WhatsApp, social media or website.",
          "A mention in CeliacMap's joint partner posts on social media."
        ],
        notice: "Being a partner is advertising. It does not mean CeliacMap certifies the business's food safety, and it does not change how it appears on the map.",
        open: "I want to become a partner",
        close: "Hide the form",
        formTitle: "Partner request",
        formIntro: "You pay nothing now. We review your request and reply by email.",
        business: "Business name *",
        city: "City *",
        country: "Country *",
        countryPh: "Choose a country",
        contactName: "Contact person *",
        email: "Email *",
        phone: "Phone or WhatsApp",
        links: "Website or social media",
        linksPh: "E.g. instagram.com/yourbusiness",
        description: "Briefly tell us what you offer",
        onMap: "Is it already on the CeliacMap map? *",
        onMapPh: "Choose an option",
        yes: "Yes",
        no: "No",
        unsure: "I don't know",
        conditionsTitle: "Founding Plan terms",
        conditions: [
          "Price: {price} per month, in Uruguayan pesos.",
          "It is a recurring monthly charge, through Mercado Pago.",
          "No minimum term: cancel anytime. After you cancel, the card stays visible until the end of the period already paid.",
          "Being a partner is advertising: it does not certify food safety and changes nothing about the business on the map.",
          "We reply by email within 5 business days.",
          "You pay nothing before that reply: if your business qualifies, we email you the payment link."
        ],
        consentBefore: "I have read the Founding Plan terms and the ",
        consentLink: "privacy policy",
        consentAfter: ", and I agree that CeliacMap uses this data to reply to my request. *",
        honeypot: "Leave this field empty",
        submit: "Send request",
        doneTitle: "We received your request",
        doneCode: "Your request code is",
        doneKeep: "Keep it: you will need it in the next steps.",
        doneSteps: [
          "We review your request and reply by email within 5 business days.",
          "If your business qualifies, we email you the Mercado Pago payment link. Do not pay anything before that reply.",
          "After paying, reply to that email with your code and the Mercado Pago transaction number.",
          "You send us your card's logo, text and links; we review it and publish it."
        ],
        faqTitle: "Frequently asked questions",
        faq: [
          ["What does it include?", "A featured profile in this section labeled \"Partner\", your logo, images and business details, direct links to your WhatsApp, social media or website, and a mention in the joint partner posts."],
          ["How do I pay?", "Through Mercado Pago, as a recurring monthly charge of {price}. The payment link is emailed to you only if your request qualifies. CeliacMap never sees or stores your card details."],
          ["How do I cancel?", "Whenever you want, from your Mercado Pago account or by writing to hola@celiacmap.org. There is no minimum term: the card stays visible until the end of the period already paid."],
          ["Does my business rank higher on the map?", "No. Being a partner does not add your business to the map or remove it, and does not change its label or its place in the ranking, the searches or the chat."],
          ["Who can become a partner?", "A place approved on the map, or a business selling gluten-free products or services relevant to the celiac community. Supermarket, convenience-store and pharmacy chains cannot, nor can anyone promising cures. A person reviews every request."]
        ],
        msg: {
          missing: "Fill in the fields marked with * and accept the terms.",
          email: "Please check the email: it does not look valid.",
          phone: "The phone must be between 6 and 40 characters.",
          cooldown: "Please wait a moment before sending another request.",
          sending: "Sending…",
          duplicate: "We already have a request from you for this business. We will email you; if you have questions, write to hola@celiacmap.org.",
          error: "Could not send. Please try again in a few minutes.",
          config: "The form is not available right now."
        }
      }
    }
  };

  window.CeliacPartners = { PROGRAM: PROGRAM };

  var cfg = window.CELIACMAP_CONFIG || {};
  var mount = document.getElementById("partner-program");
  if (!mount || cfg.PARTNER_PROGRAM !== true) return;

  // Same spam guards as js/suggest.js.
  var MIN_FILL_MS = 3000;
  var COOLDOWN_MS = 60000;
  var COOLDOWN_KEY = "celiacmap-partner-last";
  var MAX_REF_RETRIES = 3;
  var REF_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
  var EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
  var renderedAt = Date.now();
  var statusKey = null;
  var statusKind = null;

  function lang() {
    return document.documentElement.getAttribute("lang") === "en" ? "en" : "es";
  }

  function priceLabel() {
    return PROGRAM.currency + " " + PROGRAM.price;
  }

  function lookup(path) {
    var node = PROGRAM.text[lang()];
    var parts = path.split(".");
    for (var i = 0; i < parts.length; i++) node = node == null ? null : node[parts[i]];
    return typeof node === "string" ? node.replace("{price}", priceLabel()) : "";
  }

  function apiBase() {
    return String(cfg.SUPABASE_URL || "").replace(/\/+$/, "");
  }

  function headers(extra) {
    var h = { apikey: cfg.SUPABASE_ANON_KEY, Authorization: "Bearer " + cfg.SUPABASE_ANON_KEY };
    for (var k in extra) if (Object.prototype.hasOwnProperty.call(extra, k)) h[k] = extra[k];
    return h;
  }

  /* ------------------------------ Markup ------------------------------ */

  var CHECK_ICON = '<svg class="pp-icon" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false">' +
    '<circle cx="12" cy="12" r="10" fill="currentColor" opacity="0.14"/>' +
    '<path d="M7.5 12.4l3 3 6-6.6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  function t(key, tag, attrs) {
    return "<" + tag + (attrs ? " " + attrs : "") + ' data-pp="' + key + '"></' + tag + ">";
  }

  function list(key, count, tag, itemAttrs, prefix) {
    var out = "";
    for (var i = 0; i < count; i++) out += "<li" + (itemAttrs ? " " + itemAttrs : "") + ">" + (prefix || "") + t(key + "." + i, "span") + "</li>";
    return "<" + tag + ">" + out + "</" + tag + ">";
  }

  function field(id, key, control, full) {
    return '<div class="field' + (full ? " field-full" : "") + '"><label for="' + id + '" data-pp="' + key + '"></label>' + control + "</div>";
  }

  function faq() {
    var out = "";
    for (var i = 0; i < PROGRAM.text.es.faq.length; i++) {
      out += '<details class="pp-faq-item">' + t("faq." + i + ".0", "summary") + t("faq." + i + ".1", "p") + "</details>";
    }
    return out;
  }

  function cardHtml() {
    var es = PROGRAM.text.es;
    return '<article class="partner-plan" aria-labelledby="pp-title">' +
      '<div class="pp-head">' + t("chip", "span", 'class="pp-chip"') + t("title", "h3", 'class="pp-title" id="pp-title"') +
        t("subtitle", "p", 'class="pp-subtitle"') + "</div>" +
      '<div class="pp-grid">' +
        '<div class="pp-price-block"><p class="pp-price"><span class="pp-amount">' + priceLabel() + "</span> " +
          t("per", "span", 'class="pp-per"') + "</p>" + t("terms", "p", 'class="pp-terms"') + t("founder", "p", 'class="pp-founder"') + "</div>" +
        '<div class="pp-benefits">' + t("benefitsTitle", "h4", 'class="pp-subhead"') +
          list("benefits", es.benefits.length, "ul", 'class="pp-benefit"', CHECK_ICON) + "</div>" +
      "</div>" +
      t("notice", "p", 'class="pp-notice" id="pp-notice"') +
      '<button class="btn btn-accent pp-toggle" type="button" id="pp-toggle" aria-expanded="false" aria-controls="pp-form" data-pp="open"></button>' +
      '<form class="pp-form" id="pp-form" novalidate hidden aria-labelledby="pp-form-title">' +
        t("formTitle", "h4", 'class="pp-form-title" id="pp-form-title"') + t("formIntro", "p", 'class="pp-form-intro"') +
        '<div class="suggest-grid">' +
          field("pp-business", "business", '<input id="pp-business" type="text" required minlength="2" maxlength="120" autocomplete="organization">') +
          field("pp-city", "city", '<input id="pp-city" type="text" required minlength="2" maxlength="80" autocomplete="address-level2">') +
          field("pp-country", "country", '<select id="pp-country" required>' + t("countryPh", "option", 'value=""') +
            '<option value="Uruguay">Uruguay</option><option value="Argentina">Argentina</option></select>') +
          field("pp-contact", "contactName", '<input id="pp-contact" type="text" required minlength="2" maxlength="120" autocomplete="name">') +
          field("pp-email", "email", '<input id="pp-email" type="email" required maxlength="254" autocomplete="email">') +
          field("pp-phone", "phone", '<input id="pp-phone" type="tel" maxlength="40" autocomplete="tel">') +
          field("pp-links", "links", '<input id="pp-links" type="text" maxlength="500" autocomplete="url" data-pp-ph="linksPh">', true) +
          field("pp-description", "description", '<textarea id="pp-description" maxlength="300" rows="3"></textarea>', true) +
          field("pp-onmap", "onMap", '<select id="pp-onmap" required>' + t("onMapPh", "option", 'value=""') +
            t("yes", "option", 'value="yes"') + t("no", "option", 'value="no"') + t("unsure", "option", 'value="unsure"') + "</select>", true) +
        "</div>" +
        '<div class="pp-recap"><p class="pp-price pp-price-small"><span class="pp-amount">' + priceLabel() + "</span> " +
          t("per", "span", 'class="pp-per"') + "</p>" +
          '<details class="pp-conditions" id="pp-conditions">' + t("conditionsTitle", "summary") +
            list("conditions", es.conditions.length, "ul") + "</details></div>" +
        '<label class="pp-consent"><input id="pp-consent" type="checkbox" required>' +
          "<span>" + t("consentBefore", "span") + '<a href="' + PROGRAM.privacyUrl + '" target="_blank" rel="noopener" data-pp="consentLink"></a>' +
          t("consentAfter", "span") + "</span></label>" +
        '<div class="suggest-hp" aria-hidden="true"><label for="pp-website" data-pp="honeypot"></label>' +
          '<input id="pp-website" type="text" tabindex="-1" autocomplete="off"></div>' +
        '<div class="suggest-actions"><button class="btn btn-accent" type="submit" id="pp-submit" aria-describedby="pp-notice" data-pp="submit"></button></div>' +
        '<p class="suggest-status" id="pp-status" role="status" aria-live="polite" hidden></p>' +
      "</form>" +
      '<div class="pp-done" id="pp-done" hidden>' +
        t("doneTitle", "h4", 'class="pp-form-title" id="pp-done-title" tabindex="-1"') +
        '<p class="pp-done-code">' + t("doneCode", "span") + ' <strong id="pp-code"></strong></p>' +
        t("doneKeep", "p", 'class="pp-form-intro"') +
        list("doneSteps", PROGRAM.text.es.doneSteps.length, "ol") +
      "</div>" +
      '<div class="pp-faq">' + t("faqTitle", "h4", 'class="pp-subhead"') + faq() + "</div>" +
      "</article>";
  }

  function translate(root) {
    var nodes = root.querySelectorAll("[data-pp]");
    for (var i = 0; i < nodes.length; i++) nodes[i].textContent = lookup(nodes[i].getAttribute("data-pp"));
    var ph = root.querySelectorAll("[data-pp-ph]");
    for (var j = 0; j < ph.length; j++) ph[j].setAttribute("placeholder", lookup(ph[j].getAttribute("data-pp-ph")));
  }

  mount.innerHTML = cardHtml();
  mount.hidden = false;

  var published = document.createElement("div");
  published.className = "partners-published";
  published.id = "partners-published";
  mount.parentNode.insertBefore(published, mount);

  var $ = function (id) { return document.getElementById(id); };
  var form = $("pp-form");
  var toggle = $("pp-toggle");
  var statusEl = $("pp-status");
  var submitBtn = $("pp-submit");
  var done = $("pp-done");

  function show(key, kind) {
    statusKey = key;
    statusKind = kind;
    statusEl.textContent = PROGRAM.text[lang()].msg[key];
    statusEl.classList.remove("is-success", "is-error");
    if (kind === "err") statusEl.classList.add("is-error");
    statusEl.hidden = false;
  }

  function refreshToggle() {
    var open = toggle.getAttribute("aria-expanded") === "true";
    toggle.textContent = lookup(open ? "close" : "open");
  }

  translate(mount);
  refreshToggle();

  toggle.addEventListener("click", function () {
    var open = toggle.getAttribute("aria-expanded") !== "true";
    toggle.setAttribute("aria-expanded", String(open));
    form.hidden = !open;
    refreshToggle();
    if (open) {
      renderedAt = Date.now();
      $("pp-business").focus();
    }
  });

  /* ------------------------------- Form ------------------------------- */

  function newRefCode() {
    var out = "";
    var bytes = new Uint8Array(1);
    while (out.length < 6) {
      window.crypto.getRandomValues(bytes);
      if (bytes[0] < 252) out += REF_ALPHABET[bytes[0] % 36];
    }
    return "CM-" + out;
  }

  function value(id) {
    return ($(id).value || "").trim();
  }

  function readForm() {
    return {
      business_name: value("pp-business"),
      city: value("pp-city"),
      country: $("pp-country").value || "",
      contact_name: value("pp-contact"),
      contact_email: value("pp-email"),
      contact_phone: value("pp-phone") || null,
      links: value("pp-links") || null,
      description: value("pp-description") || null,
      on_map_claim: $("pp-onmap").value || "",
      consent_version: PROGRAM.consentVersion
    };
  }

  function problem(data) {
    if (data.business_name.length < 2 || data.city.length < 2 || data.contact_name.length < 2 ||
        !data.country || !data.on_map_claim || !data.contact_email || !$("pp-consent").checked) return "missing";
    if (data.contact_email.length < 6 || !EMAIL_RE.test(data.contact_email)) return "email";
    if (data.contact_phone && data.contact_phone.length < 6) return "phone";
    return null;
  }

  function succeed(ref) {
    try { localStorage.setItem(COOLDOWN_KEY, String(Date.now())); } catch (e) {}
    form.reset();
    form.hidden = true;
    toggle.hidden = true;
    statusEl.hidden = true;
    statusKey = null;
    $("pp-code").textContent = ref;
    done.hidden = false;
    $("pp-done-title").focus();
  }

  function send(data, attempt) {
    var row = { ref_code: newRefCode() };
    for (var k in data) if (Object.prototype.hasOwnProperty.call(data, k)) row[k] = data[k];
    return fetch(apiBase() + "/rest/v1/partner_applications", {
      method: "POST",
      headers: headers({ "Content-Type": "application/json", Prefer: "return=minimal" }),
      body: JSON.stringify(row)
    }).then(function (res) {
      if (res.ok) return succeed(row.ref_code);
      if (res.status !== 409) throw new Error("HTTP " + res.status);
      return res.text().then(function (body) {
        if (body.indexOf("partner_applications_ref_code_key") !== -1 && attempt < MAX_REF_RETRIES) return send(data, attempt + 1);
        if (body.indexOf("partner_applications_open_request_idx") !== -1) return show("duplicate", "err");
        throw new Error("HTTP 409");
      });
    });
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();

    // Honeypot filled, or submitted implausibly fast: look accepted, send nothing.
    if (value("pp-website") || Date.now() - renderedAt < MIN_FILL_MS) {
      succeed(newRefCode());
      return;
    }
    if (!cfg.SUPABASE_URL || !cfg.SUPABASE_ANON_KEY) {
      show("config", "err");
      return;
    }
    var data = readForm();
    var bad = problem(data);
    if (bad) {
      show(bad, "err");
      return;
    }
    var last = 0;
    try { last = parseInt(localStorage.getItem(COOLDOWN_KEY), 10) || 0; } catch (e1) {}
    if (Date.now() - last < COOLDOWN_MS) {
      show("cooldown", "err");
      return;
    }

    submitBtn.disabled = true;
    form.setAttribute("aria-busy", "true");
    show("sending");
    send(data, 0)
      .catch(function () { show("error", "err"); })
      .then(function () {
        submitBtn.disabled = false;
        form.removeAttribute("aria-busy");
      });
  });

  /* ------------------------- Published partners ------------------------ */

  var partners = [];

  function logoUrl(path) {
    var segments = String(path).split("/").map(encodeURIComponent).join("/");
    return apiBase() + "/storage/v1/object/public/" + PROGRAM.logoBucket + "/" + segments;
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function partnerCard(p) {
    var card = el("article", "partner-card");
    if (p.logo_path) {
      var img = el("img", "partner-logo");
      img.setAttribute("src", logoUrl(p.logo_path));
      img.setAttribute("alt", (lang() === "en" ? "Logo of " : "Logo de ") + p.public_name);
      img.setAttribute("width", "192");
      img.setAttribute("height", "192");
      img.setAttribute("loading", "lazy");
      img.setAttribute("decoding", "async");
      card.appendChild(img);
    }
    var body = el("div", "partner-body");
    body.appendChild(el("span", "partner-label", lookup("label")));
    body.appendChild(el("h3", "partner-name", p.public_name));
    var copy = lang() === "en" ? p.public_text_en || p.public_text_es : p.public_text_es || p.public_text_en;
    if (copy) body.appendChild(el("p", "partner-text", copy));
    var links = el("div", "partner-links");
    var items = Array.isArray(p.public_links) ? p.public_links : [];
    for (var i = 0; i < items.length; i++) {
      var url = items[i] && typeof items[i].url === "string" ? items[i].url : "";
      if (!/^https:\/\//.test(url) || !items[i].label) continue;
      var a = el("a", null, String(items[i].label));
      a.setAttribute("href", url);
      a.setAttribute("target", "_blank");
      a.setAttribute("rel", "sponsored noopener");
      links.appendChild(a);
    }
    if (links.childNodes.length) body.appendChild(links);
    card.appendChild(body);
    return card;
  }

  function renderPartners() {
    while (published.firstChild) published.removeChild(published.firstChild);
    for (var i = 0; i < partners.length; i++) {
      if (partners[i] && partners[i].public_name) published.appendChild(partnerCard(partners[i]));
    }
  }

  if (cfg.SUPABASE_URL && cfg.SUPABASE_ANON_KEY) {
    fetch(apiBase() + "/rest/v1/partners_public?select=public_name,public_text_es,public_text_en,logo_path,public_links", {
      headers: headers({ Accept: "application/json" })
    })
      .then(function (res) { return res.ok ? res.json() : []; })
      .then(function (rows) {
        partners = Array.isArray(rows) ? rows : [];
        renderPartners();
      })
      .catch(function () {});
  }

  document.addEventListener("celiacmap:lang", function () {
    translate(mount);
    refreshToggle();
    if (statusKey) show(statusKey, statusKind);
    renderPartners();
  });
})();
