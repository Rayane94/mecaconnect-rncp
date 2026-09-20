// @ts-nocheck
const MC = {
  selectedServiceId: 0,
  garagePayment: null,
};

function mcMessage(text, type = "info") {
  const box = document.getElementById("message");
  if (!box) return;
  box.textContent = text;
  box.className = "message " + type;
  box.hidden = false;
  window.setTimeout(() => { box.hidden = true; }, 5000);
}

async function mcApi(url, options = {}) {
  const response = await fetch(url, {
    credentials: "include",
    headers: {"Content-Type": "application/json", ...(options.headers || {})},
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({detail: "Erreur serveur"}));
    throw new Error(body.detail || "Erreur serveur");
  }
  if (response.status === 204) return undefined;
  return response.json();
}

function mcStrongPassword(value) {
  if (value.length < 12) return false;
  const tests = [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/];
  return tests.filter((rule) => rule.test(value)).length >= 3;
}

function mcPasswordError(input, error) {
  if (!input || !error) return true;
  const ok = mcStrongPassword(input.value);
  error.textContent = ok ? "" : "Utilisez 12 caractères minimum et au moins 3 types parmi : majuscules, minuscules, chiffres et symboles.";
  error.hidden = ok;
  return ok;
}

function mcPlate(value) {
  const clean = value.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 7);
  return [clean.slice(0, 2), clean.slice(2, 5), clean.slice(5, 7)].filter(Boolean).join("-");
}

function mcPlateValid(value) {
  return !value || /^[A-Z]{2}-\d{3}-[A-Z]{2}$/.test(value);
}

function setupCityAutocomplete() {
  const select = document.getElementById("city");
  if (!select || select.dataset.enhanced === "1") return;
  select.dataset.enhanced = "1";
  const label = select.closest("label");
  if (!label) return;

  const input = document.createElement("input");
  input.id = "city-free";
  input.placeholder = "Paris, Montreuil, 93100...";
  input.autocomplete = "off";
  input.setAttribute("list", "city-suggestions");
  const list = document.createElement("datalist");
  list.id = "city-suggestions";
  select.hidden = true;
  label.insertBefore(input, select);
  label.appendChild(list);

  let timer = 0;
  input.addEventListener("input", () => {
    const city = input.value.trim();
    let option = Array.from(select.options).find((item) => item.value === city);
    if (!option && city) {
      option = new Option(city, city);
      select.add(option);
    }
    select.value = city;
    clearTimeout(timer);
    if (city.length < 2) {
      list.innerHTML = "";
      return;
    }
    timer = window.setTimeout(async () => {
      try {
        const results = await mcApi("/api/public/address-search?q=" + encodeURIComponent(city));
        list.innerHTML = results.map((item) =>
          '<option value="' + String(item.city).replace(/"/g, "&quot;") + '">' +
          String(item.postcode || "") + " · " + String(item.label || item.city) + "</option>"
        ).join("");
      } catch {
        list.innerHTML = "";
      }
    }, 250);
  });
}

function setupPasswordErrors() {
  const pairs = [
    ["reg-password", "reg-password-error"],
    ["pro-password", "pro-password-error"],
  ];
  pairs.forEach(([inputId, errorId]) => {
    const input = document.getElementById(inputId);
    const error = document.getElementById(errorId);
    if (!input || !error || input.dataset.inlineError === "1") return;
    input.dataset.inlineError = "1";
    input.addEventListener("input", () => mcPasswordError(input, error));
  });
}

async function checkProfessionalSiret() {
  const input = document.getElementById("pro-siret");
  const result = document.getElementById("pro-company-result");
  if (!input || !result) return;
  const siret = input.value.replace(/\D/g, "").slice(0, 14);
  input.value = siret;
  if (siret.length !== 14) {
    result.textContent = "Le SIRET doit contenir 14 chiffres.";
    result.className = "company-check error";
    return;
  }
  result.textContent = "Vérification dans le registre public...";
  result.className = "company-check";
  try {
    const company = await mcApi("/api/public/company/" + siret);
    result.textContent = "Entreprise trouvée : " + company.legal_name + (company.city ? " · " + company.city : "");
    result.className = "company-check success";
  } catch (error) {
    result.textContent = error.message;
    result.className = "company-check error";
  }
}

function setupProRegistration() {
  const form = document.getElementById("garage-register-form");
  if (!form || form.dataset.enhanced === "1") return;
  form.dataset.enhanced = "1";
  const siret = document.getElementById("pro-siret");
  siret?.addEventListener("blur", checkProfessionalSiret);
  siret?.addEventListener("input", () => { siret.value = siret.value.replace(/\D/g, "").slice(0, 14); });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const password = document.getElementById("pro-password");
    const error = document.getElementById("pro-password-error");
    if (!mcPasswordError(password, error)) {
      password.focus();
      return;
    }
    const result = document.getElementById("pro-company-result");
    try {
      const payload = await mcApi("/api/auth/register-garage", {
        method: "POST",
        body: JSON.stringify({
          email: document.getElementById("pro-email").value.trim(),
          password: password.value,
          full_name: document.getElementById("pro-name").value.trim(),
          phone: document.getElementById("pro-phone").value.trim() || null,
          siret: document.getElementById("pro-siret").value.trim(),
          garage_name: document.getElementById("pro-garage-name").value.trim(),
        }),
      });
      result.textContent = "SIRET vérifié. Votre espace professionnel est créé.";
      result.className = "company-check success";
      window.location.href = "/espace-garage";
    } catch (error) {
      result.textContent = error.message;
      result.className = "company-check error";
    }
  });
}

function setupClientRegisterGuard() {
  const form = document.getElementById("register-form");
  if (!form || form.dataset.inlineGuard === "1") return;
  form.dataset.inlineGuard = "1";
  form.addEventListener("submit", (event) => {
    const input = document.getElementById("reg-password");
    const error = document.getElementById("reg-password-error");
    if (!mcPasswordError(input, error)) {
      event.preventDefault();
      event.stopImmediatePropagation();
      input.focus();
    }
  }, true);
}

const VEHICLES = {
  "Audi":["A1","A3","A4","A5","Q2","Q3","Q5"],
  "BMW":["Série 1","Série 2","Série 3","Série 5","X1","X3","X5"],
  "Citroën":["C3","C4","C5 Aircross","Berlingo"],
  "Dacia":["Sandero","Duster","Jogger"],
  "Ford":["Fiesta","Focus","Puma","Kuga"],
  "Mercedes":["Classe A","Classe C","CLA","GLA","GLC"],
  "Peugeot":["208","308","2008","3008","5008"],
  "Renault":["Clio","Captur","Mégane","Arkana","Austral"],
  "Toyota":["Yaris","Corolla","C-HR","RAV4"],
  "Volkswagen":["Polo","Golf","T-Roc","Tiguan"]
};
const MOTORS = ["Essence","Diesel","Hybride","Hybride rechargeable","Électrique","GPL"];

function enhanceVehicleForm() {
  const form = document.getElementById("vehicle-form");
  if (!form || form.dataset.enhanced === "1") return;
  form.dataset.enhanced = "1";
  const make = document.getElementById("vehicle-make");
  const model = document.getElementById("vehicle-model");
  const plate = document.getElementById("vehicle-plate");
  if (!make || !model || !plate) return;

  let makes = document.getElementById("vehicle-makes");
  if (!makes) {
    makes = document.createElement("datalist");
    makes.id = "vehicle-makes";
    document.body.appendChild(makes);
  }
  makes.innerHTML = Object.keys(VEHICLES).map((item) => '<option value="' + item + '"></option>').join("");
  make.setAttribute("list", "vehicle-makes");

  let models = document.getElementById("vehicle-models");
  if (!models) {
    models = document.createElement("datalist");
    models.id = "vehicle-models";
    document.body.appendChild(models);
  }
  model.setAttribute("list", "vehicle-models");
  const refreshModels = () => {
    const key = Object.keys(VEHICLES).find((item) => item.toLowerCase() === make.value.trim().toLowerCase());
    models.innerHTML = (key ? VEHICLES[key] : []).map((item) => '<option value="' + item + '"></option>').join("");
  };
  make.addEventListener("input", refreshModels);
  refreshModels();

  if (!document.getElementById("vehicle-motorization")) {
    const label = document.createElement("label");
    label.innerHTML = 'Motorisation<select id="vehicle-motorization"><option value="">Non précisée</option>' +
      MOTORS.map((item) => '<option>' + item + '</option>').join("") + "</select>";
    model.closest("label")?.after(label);
  }

  plate.maxLength = 9;
  let error = document.getElementById("vehicle-plate-error");
  if (!error) {
    error = document.createElement("span");
    error.id = "vehicle-plate-error";
    error.className = "form-error";
    error.hidden = true;
    plate.closest("label")?.appendChild(error);
  }
  plate.addEventListener("input", () => {
    plate.value = mcPlate(plate.value);
    error.textContent = mcPlateValid(plate.value) ? "" : "Format attendu : AA-123-AA";
    error.hidden = mcPlateValid(plate.value);
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    event.stopImmediatePropagation();
    if (!mcPlateValid(plate.value)) {
      error.textContent = "Format attendu : AA-123-AA";
      error.hidden = false;
      plate.focus();
      return;
    }
    try {
      await mcApi("/api/vehicles", {
        method: "POST",
        body: JSON.stringify({
          make: make.value.trim(),
          model: model.value.trim(),
          year: Number(document.getElementById("vehicle-year").value),
          plate: plate.value || null,
          motorization: document.getElementById("vehicle-motorization")?.value || null,
        }),
      });
      mcMessage("Véhicule ajouté.", "success");
      window.location.reload();
    } catch (error) {
      mcMessage(error.message, "error");
    }
  }, true);
}

async function enhanceUserBookings() {
  if (!document.getElementById("vehicle-form")) return;
  let bookings;
  try { bookings = await mcApi("/api/bookings/me"); } catch { return; }
  document.querySelectorAll(".booking-card").forEach((card) => {
    if (card.dataset.actionsAdded === "1") return;
    const match = card.textContent.match(/#(\d+)/);
    if (!match) return;
    const id = Number(match[1]);
    const booking = bookings.find((item) => Number(item.id) === id);
    if (!booking || !["PENDING_PAYMENT","CONFIRMED"].includes(booking.status)) return;
    card.dataset.actionsAdded = "1";
    const actions = document.createElement("div");
    actions.className = "management-actions";
    actions.innerHTML = '<button class="btn small secondary" type="button" data-user-reschedule="' + id + '" data-garage-id="' + booking.garage_id + '">Modifier le créneau</button>' +
      '<button class="btn small danger-outline" type="button" data-user-cancel="' + id + '">Annuler</button>';
    card.appendChild(actions);
  });

  const shell = document.querySelector(".dashboard-shell");
  if (shell && !document.getElementById("privacy-actions")) {
    const panel = document.createElement("article");
    panel.id = "privacy-actions";
    panel.className = "panel privacy-actions";
    panel.innerHTML = '<div><span class="panel-label">CONFIDENTIALITÉ</span><h3>Mes données personnelles</h3><p>Exportez vos données ou supprimez votre compte directement depuis votre espace.</p></div><div class="management-actions"><a class="btn secondary" href="/api/privacy/export" target="_blank" rel="noopener">Exporter mes données</a><button class="btn danger-outline" type="button" id="delete-account">Supprimer mon compte</button></div>';
    shell.appendChild(panel);
  }
}

async function openReschedule(button) {
  const garageId = Number(button.dataset.garageId);
  const bookingId = Number(button.dataset.userReschedule);
  const slots = await mcApi("/api/availability?garage_id=" + garageId);
  if (!slots.length) {
    mcMessage("Aucun nouveau créneau disponible.", "warning");
    return;
  }
  const dialog = document.getElementById("reschedule-dialog");
  const select = document.getElementById("reschedule-slot");
  select.innerHTML = slots.map((slot) => '<option value="' + slot.id + '">' + new Date(slot.starts_at).toLocaleString("fr-FR") + "</option>").join("");
  dialog.dataset.bookingId = String(bookingId);
  dialog.showModal();
}

function setupRescheduleDialog() {
  const close = document.getElementById("close-reschedule");
  const form = document.getElementById("reschedule-form");
  if (!form || form.dataset.enhanced === "1") return;
  form.dataset.enhanced = "1";
  close?.addEventListener("click", () => document.getElementById("reschedule-dialog").close());
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const dialog = document.getElementById("reschedule-dialog");
    try {
      await mcApi("/api/bookings/" + dialog.dataset.bookingId + "/reschedule", {
        method: "PATCH",
        body: JSON.stringify({slot_id: Number(document.getElementById("reschedule-slot").value)}),
      });
      dialog.close();
      mcMessage("Créneau modifié.", "success");
      window.location.reload();
    } catch (error) {
      mcMessage(error.message, "error");
    }
  });
}

async function enhanceGarageProfile() {
  const forms = document.querySelectorAll("[data-garage-profile]");
  if (!forms.length) return;
  let data;
  try { data = await mcApi("/api/garage/dashboard"); } catch { return; }
  forms.forEach((form) => {
    if (form.dataset.legalEnhanced === "1") return;
    form.dataset.legalEnhanced = "1";
    const id = Number(form.dataset.garageProfile);
    const garage = data.garages.find((item) => Number(item.id) === id);
    if (!garage) return;
    const actions = form.querySelector(".management-actions");
    const block = document.createElement("div");
    block.className = "legal-company-card";
    block.innerHTML = '<strong>Identité professionnelle</strong><span>SIRET : ' + (garage.siret || "à renseigner") + '</span><span>SIREN : ' + (garage.siren || "à renseigner") + '</span><span>' + (garage.legal_name || "") + '</span>' +
      '<label class="check-row"><input name="payment_online_enabled" type="checkbox" ' + (garage.payment_online_enabled !== false ? "checked" : "") + '> Proposer un acompte en ligne</label>' +
      '<label>Pourcentage d\'acompte<select name="deposit_rate"><option value="0.1">10 %</option><option value="0.2">20 %</option><option value="0.3">30 %</option><option value="0.5">50 %</option><option value="1">100 %</option></select></label>';
    actions?.before(block);
    block.querySelector("select").value = String(garage.deposit_rate ?? 0.2);

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
      const fd = new FormData(form);
      const hourly = String(fd.get("hourly_rate") || "").trim();
      try {
        await mcApi("/api/garages/" + id, {
          method: "PATCH",
          body: JSON.stringify({
            name: String(fd.get("name") || "").trim(),
            city: String(fd.get("city") || "").trim(),
            address: String(fd.get("address") || "").trim(),
            description: String(fd.get("description") || "").trim(),
            specialties: String(fd.get("specialties") || "").trim(),
            brands: String(fd.get("brands") || "").trim(),
            hourly_rate: hourly ? Number(hourly) : null,
            payment_online_enabled: fd.get("payment_online_enabled") === "on",
            deposit_rate: Number(fd.get("deposit_rate") || 0.2),
          }),
        });
        mcMessage("Fiche garage et conditions de paiement mises à jour.", "success");
      } catch (error) {
        mcMessage(error.message, "error");
      }
    }, true);
  });
}

async function updateBookingPaymentDisplay() {
  const match = location.pathname.match(/^\/garages\/(\d+)$/);
  if (!match || !MC.selectedServiceId) return;
  try {
    const garage = await mcApi("/api/garages/" + match[1]);
    MC.garagePayment = garage;
    const service = garage.services.find((item) => Number(item.id) === Number(MC.selectedServiceId));
    if (!service) return;
    const online = garage.payment_online_enabled !== false;
    const rate = Number(garage.deposit_rate ?? 0.2);
    document.getElementById("booking-payment-label").textContent = online ? "Acompte à régler (" + Math.round(rate * 100) + " %)" : "Paiement";
    document.getElementById("booking-deposit").textContent = online ? new Intl.NumberFormat("fr-FR",{style:"currency",currency:"EUR"}).format(service.price * rate) : "Au garage";
    document.getElementById("booking-submit").textContent = online ? "Confirmer et payer l'acompte" : "Confirmer la réservation";
  } catch {}
}

function setupBookingOverride() {
  document.addEventListener("click", (event) => {
    const service = event.target.closest?.("[data-service]");
    if (service) {
      MC.selectedServiceId = Number(service.dataset.service);
      window.setTimeout(updateBookingPaymentDisplay, 150);
    }
  }, true);

  const form = document.getElementById("booking-form");
  if (!form || form.dataset.enhanced === "1") return;
  form.dataset.enhanced = "1";
  form.addEventListener("submit", async (event) => {
    if (!MC.selectedServiceId) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    try {
      const vehicle = document.getElementById("booking-vehicle").value;
      const booking = await mcApi("/api/bookings", {
        method: "POST",
        body: JSON.stringify({
          service_id: MC.selectedServiceId,
          slot_id: Number(document.getElementById("booking-slot").value),
          vehicle_id: vehicle ? Number(vehicle) : null,
        }),
      });
      if (booking.payment_required === false) {
        document.getElementById("booking-dialog").close();
        mcMessage("Réservation confirmée. Le règlement se fera directement au garage.", "success");
        window.location.href = "/mon-espace";
        return;
      }
      const payment = await mcApi("/api/payments/" + booking.id + "/session", {method:"POST"});
      if (payment.mode === "local-test") {
        await mcApi(payment.checkout_url, {method:"POST"});
        window.location.href = "/mon-espace";
      } else if (payment.checkout_url) {
        window.location.href = payment.checkout_url;
      }
    } catch (error) {
      mcMessage(error.message, "error");
    }
  }, true);
}

document.addEventListener("click", async (event) => {
  const cancel = event.target.closest?.("[data-user-cancel]");
  if (cancel) {
    if (!window.confirm("Annuler ce rendez-vous ?")) return;
    try {
      await mcApi("/api/bookings/" + cancel.dataset.userCancel + "/cancel", {method:"PATCH"});
      mcMessage("Rendez-vous annulé.", "success");
      window.location.reload();
    } catch (error) { mcMessage(error.message, "error"); }
    return;
  }
  const reschedule = event.target.closest?.("[data-user-reschedule]");
  if (reschedule) {
    try { await openReschedule(reschedule); } catch (error) { mcMessage(error.message, "error"); }
    return;
  }
  if (event.target.closest?.("#delete-account")) {
    if (!window.confirm("Supprimer votre compte ? Certaines réservations déjà réalisées peuvent être anonymisées plutôt que supprimées.")) return;
    try {
      await mcApi("/api/privacy/account", {method:"DELETE"});
      window.location.href = "/";
    } catch (error) { mcMessage(error.message, "error"); }
  }
});

function refreshDynamicEnhancements() {
  setupPasswordErrors();
  enhanceVehicleForm();
  enhanceUserBookings();
  enhanceGarageProfile();
}

window.addEventListener("load", () => {
  setupCityAutocomplete();
  setupPasswordErrors();
  setupClientRegisterGuard();
  setupProRegistration();
  setupRescheduleDialog();
  setupBookingOverride();
  refreshDynamicEnhancements();
  const target = document.getElementById("dashboard-content");
  if (target) {
    new MutationObserver(() => refreshDynamicEnhancements()).observe(target, {childList:true, subtree:true});
  }
});
