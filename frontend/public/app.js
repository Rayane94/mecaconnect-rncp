import { depositFor, filterGarages, formatPrice, isStrongPassword, safeText, sortSlots, } from "./lib.js";
const state = {
    garages: [],
    assistantHistory: [],
};
let garageMap = null;
let garageMarkers = [];
const pageTitles = {
    home: "MecaConnect - Réservez votre garage en ligne",
    assistant: "MecaBot - Assistant automobile | MecaConnect",
    garages: "Garages en Île-de-France | MecaConnect",
    "garage-detail": "Fiche garage | MecaConnect",
    auth: "Connexion | MecaConnect",
    dashboard: "Mon espace | MecaConnect",
    how: "Comment ça marche | MecaConnect",
    pro: "Espace professionnel | MecaConnect",
};
function element(id) {
    const node = document.getElementById(id);
    if (!node) {
        throw new Error(`Élément introuvable : ${id}`);
    }
    return node;
}
async function api(url, options = {}) {
    const response = await fetch(url, {
        credentials: "include",
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {}),
        },
        ...options,
    });
    if (!response.ok) {
        const body = await response
            .json()
            .catch(() => ({ detail: "Erreur serveur" }));
        throw new Error(body.detail || "Erreur serveur");
    }
    if (response.status === 204) {
        return undefined;
    }
    return response.json();
}
function showMessage(text, type = "info") {
    const box = element("message");
    box.textContent = text;
    box.className = `message ${type}`;
    box.hidden = false;
    window.setTimeout(() => {
        box.hidden = true;
    }, 5000);
}
function dashboardPath(user = state.user) {
    if (user?.role === "ADMIN")
        return "/admin";
    if (user?.role === "GARAGE")
        return "/espace-garage";
    return "/mon-espace";
}
function showPage(page) {
    document.querySelectorAll("[data-page]").forEach((section) => {
        section.hidden = section.dataset.page !== page;
    });
    document.title = pageTitles[page];
    document.querySelectorAll("[data-link]").forEach((link) => {
        const target = new URL(link.href, window.location.origin).pathname;
        const active = target === window.location.pathname;
        link.classList.toggle("active", active);
        if (active)
            link.setAttribute("aria-current", "page");
        else
            link.removeAttribute("aria-current");
    });
    window.scrollTo({ top: 0, behavior: "instant" });
}
async function renderRoute() {
    const path = window.location.pathname.replace(/\/+$/, "") || "/";
    const garageMatch = path.match(/^\/garages\/(\d+)$/);
    if (garageMatch) {
        showPage("garage-detail");
        await loadGarageDetail(Number(garageMatch[1]));
        return;
    }
    if (path === "/garages") {
        showPage("garages");
        window.requestAnimationFrame(() => initGarageMap());
        return;
    }
    if (path === "/mecabot") {
        showPage("assistant");
        return;
    }
    if (path === "/connexion") {
        if (state.user) {
            const requested = new URLSearchParams(window.location.search).get("next");
            if (requested === "/espace-garage" && !["GARAGE", "ADMIN"].includes(state.user.role)) {
                showMessage("L’espace garage est réservé aux comptes professionnels GARAGE.", "warning");
                await navigateTo("/professionnels", true);
                return;
            }
            await navigateTo(dashboardPath(), true);
            return;
        }
        showPage("auth");
        return;
    }
    if (path === "/fonctionnement") {
        showPage("how");
        return;
    }
    if (path === "/professionnels") {
        showPage("pro");
        return;
    }
    if (["/mon-espace", "/espace-garage", "/admin"].includes(path)) {
        if (!state.user) {
            const next = encodeURIComponent(path);
            await navigateTo(`/connexion?next=${next}`, true);
            return;
        }
        const expectedPath = dashboardPath();
        if (path !== expectedPath) {
            await navigateTo(expectedPath, true);
            return;
        }
        showPage("dashboard");
        await loadDashboard();
        return;
    }
    if (path !== "/") {
        await navigateTo("/", true);
        return;
    }
    showPage("home");
}
async function navigateTo(path, replace = false) {
    const target = new URL(path, window.location.origin);
    if (replace)
        window.history.replaceState({}, "", `${target.pathname}${target.search}`);
    else
        window.history.pushState({}, "", `${target.pathname}${target.search}`);
    await renderRoute();
}
function stars(rating) {
    const rounded = Math.round(rating);
    return "★".repeat(rounded) + "☆".repeat(Math.max(0, 5 - rounded));
}
function safeAttr(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}
function formatDateTime(value) {
    return new Date(value).toLocaleString("fr-FR", {
        weekday: "short",
        day: "2-digit",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
    });
}
function bookingStatusLabel(status) {
    const labels = {
        PENDING_PAYMENT: "En attente de paiement",
        CONFIRMED: "Confirmée",
        COMPLETED: "Terminée",
        CANCELLED: "Annulée",
    };
    return labels[status] || status;
}
function bookingStatusClass(status) {
    return `status-${status.toLowerCase().replace(/_/g, "-")}`;
}
function normalizeLocation(value) {
    return value
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .trim()
        .toLocaleLowerCase("fr-FR");
}
function coordinatesForLocation(location) {
    const query = normalizeLocation(location);
    if (!query)
        return null;
    const matches = state.garages.filter((garage) => {
        if (garage.lat == null || garage.lng == null)
            return false;
        const city = normalizeLocation(garage.city || "");
        const department = normalizeLocation(garage.department || "");
        const postalCode = normalizeLocation(garage.postal_code || "");
        return (query === city ||
            query === department ||
            query === postalCode ||
            query.includes(city) ||
            (!!department && query.includes(department)) ||
            (!!postalCode && query.includes(postalCode)));
    });
    if (!matches.length)
        return null;
    const lng = matches.reduce((sum, garage) => sum + Number(garage.lng), 0) / matches.length;
    const lat = matches.reduce((sum, garage) => sum + Number(garage.lat), 0) / matches.length;
    return [lng, lat];
}
function focusGarageOnMap(garage) {
    if (!garageMap || garage.lat == null || garage.lng == null) {
        return;
    }
    garageMap.flyTo({ center: [garage.lng, garage.lat], zoom: 13.5, essential: true });
}
function updateMapMarkers(garages) {
    if (!garageMap || typeof maplibregl === "undefined") {
        return;
    }
    garageMarkers.forEach((marker) => marker.remove());
    garageMarkers = [];
    const bounds = new maplibregl.LngLatBounds();
    for (const garage of garages) {
        if (garage.lat == null || garage.lng == null) {
            continue;
        }
        const popup = new maplibregl.Popup({ offset: 20 }).setHTML(`<strong>${safeText(garage.name)}</strong><br>${safeText(garage.city)}<br>` +
            `<small>${safeText((garage.specialties || []).slice(0, 3).join(" · "))}</small>`);
        const marker = new maplibregl.Marker({ color: "#e4461a" })
            .setLngLat([garage.lng, garage.lat])
            .setPopup(popup)
            .addTo(garageMap);
        garageMarkers.push(marker);
        bounds.extend([garage.lng, garage.lat]);
    }
    if (garageMarkers.length > 1) {
        garageMap.fitBounds(bounds, { padding: 45, maxZoom: 11.2, duration: 700 });
    }
}
function renderSchematicMap() {
    const container = element("garage-map");
    container.classList.add("map-placeholder");
    container.innerHTML = '<div class="schematic-label">Carte IDF de secours - affichage local des garages</div>';
    const points = state.garages.filter((garage) => garage.lat != null && garage.lng != null);
    if (!points.length)
        return;
    const minLat = Math.min(...points.map((garage) => garage.lat));
    const maxLat = Math.max(...points.map((garage) => garage.lat));
    const minLng = Math.min(...points.map((garage) => garage.lng));
    const maxLng = Math.max(...points.map((garage) => garage.lng));
    for (const garage of points) {
        const x = 7 + ((garage.lng - minLng) / Math.max(0.01, maxLng - minLng)) * 86;
        const y = 9 + (1 - (garage.lat - minLat) / Math.max(0.01, maxLat - minLat)) * 80;
        const point = document.createElement("button");
        point.type = "button";
        point.className = "schematic-point";
        point.style.left = `${x}%`;
        point.style.top = `${y}%`;
        point.title = `${garage.name} - ${garage.city}`;
        point.setAttribute("aria-label", `${garage.name}, ${garage.city}`);
        point.addEventListener("click", () => openGarage(garage.id));
        container.append(point);
    }
}
function initGarageMap() {
    const status = element("map-status");
    const container = element("garage-map");
    if (garageMap) {
        garageMap.resize();
        updateMapMarkers(state.garages);
        return;
    }
    if (typeof maplibregl === "undefined") {
        status.textContent = "La bibliothèque MapLibre n'a pas pu être chargée. La carte de secours reste disponible.";
        status.classList.add("map-error");
        renderSchematicMap();
        return;
    }
    try {
        container.classList.remove("map-placeholder");
        container.innerHTML = "";
        status.textContent = "Chargement de la carte libre…";
        garageMap = new maplibregl.Map({
            container,
            style: "https://tiles.openfreemap.org/styles/liberty",
            center: [2.35, 48.86],
            zoom: 8.5,
            attributionControl: true,
        });
        garageMap.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
        garageMap.on("load", () => {
            status.textContent = "Carte MapLibre / OpenFreeMap chargée. Sélectionnez un atelier pour afficher ses informations.";
            status.classList.remove("map-error");
            garageMap.resize();
            updateMapMarkers(state.garages);
        });
        garageMap.on("error", (event) => {
            const detail = event?.error?.message ? ` (${event.error.message})` : "";
            status.textContent = `La carte libre n'a pas pu charger toutes ses ressources${detail}.`;
            status.classList.add("map-error");
        });
    }
    catch (error) {
        garageMap = null;
        status.textContent = `Impossible d'initialiser MapLibre : ${error.message}`;
        status.classList.add("map-error");
        renderSchematicMap();
    }
}
function populateCities() {
    const select = element("city");
    const current = select.value;
    const cities = [...new Set(state.garages.map((garage) => garage.city))].sort((a, b) => a.localeCompare(b, "fr"));
    select.innerHTML = '<option value="">Toutes les villes</option>';
    cities.forEach((city) => select.add(new Option(city, city)));
    select.value = current;
}
function renderGarages(garages) {
    const grid = element("garage-grid");
    grid.innerHTML = "";
    if (!garages.length) {
        grid.innerHTML = '<p class="empty">Aucun garage ne correspond aux critères.</p>';
        return;
    }
    for (const garage of garages) {
        const card = document.createElement("article");
        card.className = "garage-card";
        card.innerHTML = `
      <div class="garage-badge">${garage.verified ? "✓ Vérifié" : "Partenaire"}</div>
      <h3>${safeText(garage.name)}</h3>
      <p class="rating" aria-label="Note ${garage.rating} sur 5">
        ${stars(garage.rating)} <span>${garage.rating.toFixed(1)}</span>
      </p>
      <p><strong>${safeText(garage.city)}</strong>${garage.department ? ` (${safeText(garage.department)})` : ""} · ${safeText(garage.address)}</p>
      <div class="specialty-list">${(garage.specialties || []).slice(0, 4).map((item) => `<span>${safeText(item)}</span>`).join("")}</div>
      <p>${safeText(garage.description)}</p>
      <div class="garage-actions">
        <button class="btn secondary" data-garage="${garage.id}">Voir les prestations</button>
        <button class="link-button map-link" type="button" data-map-garage="${garage.id}">Voir sur la carte</button>
      </div>
    `;
        grid.append(card);
    }
    grid.querySelectorAll("[data-garage]").forEach((button) => {
        button.addEventListener("click", () => {
            openGarage(Number(button.dataset.garage));
        });
    });
    grid.querySelectorAll("[data-map-garage]").forEach((button) => {
        button.addEventListener("click", () => {
            const garage = state.garages.find((item) => item.id === Number(button.dataset.mapGarage));
            if (garage) {
                focusGarageOnMap(garage);
                element("garage-map").scrollIntoView({ behavior: "smooth", block: "center" });
            }
        });
    });
    updateMapMarkers(garages);
}
async function loadGarages() {
    state.garages = await api("/api/garages");
    populateCities();
    renderGarages(state.garages);
}
async function loadGarageDetail(id) {
    const garage = await api(`/api/garages/${id}`);
    state.selectedGarage = garage;
    element("garage-name").textContent = garage.name;
    document.title = `${garage.name} | MecaConnect`;
    element("garage-address").textContent =
        `${garage.address} - ${garage.city}`;
    const list = element("service-list");
    list.innerHTML = "";
    for (const service of garage.services) {
        const row = document.createElement("div");
        row.className = "service-row";
        row.innerHTML = `
      <div>
        <strong>${safeText(service.name)}</strong>
        <small>${safeText(service.description || "")}</small>
      </div>
      <div>
        <strong>${formatPrice(service.price)}</strong>
        <button class="btn" data-service="${service.id}">Réserver</button>
      </div>
    `;
        list.append(row);
    }
    list.querySelectorAll("[data-service]").forEach((button) => {
        button.addEventListener("click", () => {
            startBooking(Number(button.dataset.service));
        });
    });
}
async function openGarage(id) {
    await navigateTo(`/garages/${id}`);
}
async function startBooking(serviceId) {
    try {
        if (!state.user) {
            showMessage("Connectez-vous avant de réserver.", "warning");
            await navigateTo(`/connexion?next=${encodeURIComponent(window.location.pathname)}`);
            return;
        }
        const service = state.selectedGarage?.services.find((item) => item.id === serviceId);
        if (!service || !state.selectedGarage) {
            throw new Error("Prestation introuvable");
        }
        state.selectedService = service;
        const slots = sortSlots(await api(`/api/availability?garage_id=${state.selectedGarage.id}`));
        if (!slots.length) {
            showMessage("Aucun créneau disponible actuellement.", "warning");
            return;
        }
        const vehicles = await api("/api/vehicles").catch(() => []);
        const vehicleSelect = element("booking-vehicle");
        vehicleSelect.innerHTML = '<option value="">Sans véhicule associé</option>';
        for (const vehicle of vehicles) {
            vehicleSelect.add(new Option(`${vehicle.make} ${vehicle.model} (${vehicle.year})`, String(vehicle.id)));
        }
        const slotSelect = element("booking-slot");
        slotSelect.innerHTML = "";
        for (const slot of slots) {
            slotSelect.add(new Option(new Date(slot.starts_at).toLocaleString("fr-FR"), String(slot.id)));
        }
        element("booking-title").textContent =
            `${service.name} - ${state.selectedGarage.name}`;
        element("booking-summary").textContent =
            `Prestation : ${formatPrice(service.price)}. ` +
                "Le créneau reste disponible jusqu'à la validation de la réservation.";
        element("booking-deposit").textContent = formatPrice(depositFor(service.price));
        element("booking-dialog").showModal();
    }
    catch (error) {
        showMessage(error.message, "error");
    }
}
function appendChatMessage(author, html) {
    const messages = element("assistant-messages");
    const bubble = document.createElement("div");
    bubble.className = `chat-message ${author}`;
    bubble.innerHTML = html;
    messages.append(bubble);
    messages.scrollTop = messages.scrollHeight;
}
function urgencyClass(level) {
    if (level === "CRITICAL")
        return "critical";
    if (level === "HIGH")
        return "high";
    if (level === "MEDIUM")
        return "medium";
    return "low";
}
function renderAssistantResponse(result) {
    const causes = result.possible_causes.length
        ? `<div><h4>Pistes possibles</h4><ul>${result.possible_causes.map((item) => `<li>${safeText(item)}</li>`).join("")}</ul></div>`
        : "";
    const actions = result.recommended_actions.length
        ? `<div><h4>À faire maintenant</h4><ul>${result.recommended_actions.map((item) => `<li>${safeText(item)}</li>`).join("")}</ul></div>`
        : "";
    const estimate = result.estimated_cost
        ? `<div class="assistant-estimate"><span>Estimation indicative</span><strong>${safeText(result.estimated_cost.label)}</strong><small>${safeText(result.estimated_cost.basis)}</small></div>`
        : "";
    const garages = result.garages.length
        ? `<div class="assistant-garages"><h4>Garages les plus adaptés</h4>${result.garages.map((garage, index) => `
        <article class="assistant-garage">
          <div><span class="rank">#${index + 1}</span><strong>${safeText(garage.name)}</strong> <small>${safeText(garage.city)}${garage.department ? ` (${safeText(garage.department)})` : ""}</small></div>
          <div class="match-score">${Math.round(garage.score)}% adapté</div>
          <p>${safeText(garage.reason)}</p>
          ${garage.service_hint ? `<small>Prestation repérée : ${safeText(garage.service_hint.name)} à partir de ${formatPrice(garage.service_hint.price)}</small>` : ""}
          <div class="garage-actions"><button class="btn secondary" type="button" data-chat-garage="${garage.id}">Voir le garage</button>${garage.distance_km != null ? `<span>${garage.distance_km.toFixed(1)} km env.</span>` : ""}</div>
        </article>`).join("")}</div>`
        : "";
    const confidence = result.response_type === "diagnosis"
        ? `<span>Confiance ${Math.round(result.confidence * 100)}%</span>`
        : result.response_type === "safety_stop"
            ? `<span>Priorité sécurité</span>`
            : `<span>Aucun diagnostic forcé</span>`;
    const engine = result.engine === "hybrid-groq"
        ? '<span class="ai-badge">IA Groq + garde-fous MecaConnect</span>'
        : '<span class="ai-badge local">Moteur sécurisé MecaConnect</span>';
    appendChatMessage("bot", `<strong>MecaBot</strong>
     <div class="assistant-engine">${engine}</div>
     <div class="assistant-result-head"><span class="urgency ${urgencyClass(result.urgency.level)}">${safeText(result.urgency.label)}</span>${confidence}</div>
     <p>${safeText(result.summary)}</p>
     ${estimate}
     <div class="assistant-columns">${causes}${actions}</div>
     <p><strong>Conseil :</strong> ${safeText(result.urgency.advice)}</p>
     ${result.follow_up_question ? `<p class="follow-up"><strong>Pour affiner :</strong> ${safeText(result.follow_up_question)}</p>` : ""}
     ${garages}
     <small class="assistant-disclaimer">${safeText(result.disclaimer)}</small>`);
    element("assistant-messages")
        .querySelectorAll("[data-chat-garage]")
        .forEach((button) => {
        if (button.dataset.bound === "1")
            return;
        button.dataset.bound = "1";
        button.addEventListener("click", async () => {
            const garageId = Number(button.dataset.chatGarage);
            const garage = state.garages.find((item) => item.id === garageId);
            await openGarage(garageId);
            if (garage)
                focusGarageOnMap(garage);
        });
    });
}
async function askAssistant(message) {
    const cleanMessage = message.trim();
    if (!cleanMessage)
        return;
    appendChatMessage("user", `<strong>Vous</strong><p>${safeText(cleanMessage)}</p>`);
    state.assistantHistory.push(cleanMessage);
    state.assistantHistory = state.assistantHistory.slice(-6);
    const sendButton = element("assistant-form").querySelector("button[type=submit]");
    if (sendButton) {
        sendButton.disabled = true;
        sendButton.textContent = "Analyse en cours...";
    }
    try {
        const location = element("assistant-location").value.trim();
        const coordinates = location ? coordinatesForLocation(location) : null;
        const yearValue = element("assistant-year").value;
        const result = await api("/api/assistant/diagnose", {
            method: "POST",
            body: JSON.stringify({
                message: cleanMessage,
                history: state.assistantHistory.slice(0, -1),
                location: location || null,
                vehicle_make: element("assistant-make").value.trim() || null,
                vehicle_model: element("assistant-model").value.trim() || null,
                vehicle_year: yearValue ? Number(yearValue) : null,
                lng: coordinates?.[0] ?? null,
                lat: coordinates?.[1] ?? null,
            }),
        });
        renderAssistantResponse(result);
        if (result.garages.length) {
            const recommendedIds = new Set(result.garages.map((garage) => garage.id));
            const recommended = state.garages.filter((garage) => recommendedIds.has(garage.id));
            updateMapMarkers(recommended);
        }
        else {
            updateMapMarkers(state.garages);
        }
    }
    catch (error) {
        appendChatMessage("bot", `<strong>MecaBot</strong><p>Je n'ai pas pu terminer l'analyse : ${safeText(error.message)}</p>`);
    }
    finally {
        if (sendButton) {
            sendButton.disabled = false;
            sendButton.textContent = "Analyser mon problème";
        }
    }
}
async function loadUserDashboard() {
    const [vehicles, bookings] = await Promise.all([
        api("/api/vehicles"),
        api("/api/bookings/me"),
    ]);
    const content = element("dashboard-content");
    const confirmed = bookings.filter((booking) => booking.status === "CONFIRMED").length;
    const completed = bookings.filter((booking) => booking.status === "COMPLETED").length;
    const deposits = bookings
        .filter((booking) => booking.payment_status === "SUCCEEDED")
        .reduce((sum, booking) => sum + Number(booking.deposit_amount || 0), 0);
    const nextBooking = [...bookings]
        .filter((booking) => booking.status === "CONFIRMED" && new Date(booking.starts_at).getTime() >= Date.now())
        .sort((a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime())[0];
    content.innerHTML = `
    <div class="dashboard-shell">
      <div class="dashboard-welcome user-dashboard-hero">
        <div>
          <span class="dashboard-kicker">ESPACE AUTOMOBILISTE</span>
          <h3>Bonjour ${safeText(state.user?.full_name || "")}</h3>
          <p>Gérez vos véhicules et retrouvez vos rendez-vous MecaConnect dans un espace unique.</p>
        </div>
        <a class="btn secondary" href="/garages" data-dashboard-link>Réserver une prestation</a>
      </div>

      <div class="dashboard-kpis">
        <article><span>Véhicules</span><strong>${vehicles.length}</strong><small>enregistré(s)</small></article>
        <article><span>À venir</span><strong>${confirmed}</strong><small>réservation(s) confirmée(s)</small></article>
        <article><span>Terminées</span><strong>${completed}</strong><small>intervention(s)</small></article>
        <article><span>Acomptes</span><strong>${formatPrice(deposits)}</strong><small>validés via Stripe</small></article>
      </div>

      ${nextBooking ? `
        <article class="next-appointment-card">
          <div><span class="panel-label">PROCHAIN RENDEZ-VOUS</span><h3>${safeText(nextBooking.garage)}</h3><p>${safeText(nextBooking.service)} · ${formatDateTime(nextBooking.starts_at)}</p></div>
          <span class="status-pill verified">Confirmée</span>
        </article>
      ` : ""}

      <div class="dashboard-grid user-dashboard-grid">
        <article class="panel dashboard-panel">
          <div class="panel-heading"><div><span class="panel-label">GARAGE PERSONNEL</span><h3>Mes véhicules</h3></div><span>${vehicles.length} véhicule(s)</span></div>
          <div class="vehicle-list">
            ${vehicles.length
        ? vehicles.map((vehicle) => `
                <div class="vehicle-card">
                  <div class="vehicle-icon">AUTO</div>
                  <div><strong>${safeText(vehicle.make)} ${safeText(vehicle.model)}</strong><small>${vehicle.year}${vehicle.plate ? ` · ${safeText(vehicle.plate)}` : ""}</small></div>
                </div>
              `).join("")
        : '<div class="empty-state"><strong>Aucun véhicule</strong><span>Ajoutez votre véhicule pour accélérer vos prochaines réservations.</span></div>'}
          </div>
          <form id="vehicle-form" class="management-form compact-form">
            <h4>Ajouter un véhicule</h4>
            <div class="form-grid two-cols">
              <label>Marque<input id="vehicle-make" required placeholder="Mercedes"></label>
              <label>Modèle<input id="vehicle-model" required placeholder="CLA 200"></label>
              <label>Année<input id="vehicle-year" type="number" min="1950" max="2100" required placeholder="2021"></label>
              <label>Immatriculation<input id="vehicle-plate" maxlength="24" placeholder="AA-123-AA"></label>
            </div>
            <button class="btn" type="submit">Ajouter le véhicule</button>
          </form>
        </article>

        <article class="panel dashboard-panel">
          <div class="panel-heading"><div><span class="panel-label">HISTORIQUE</span><h3>Mes réservations</h3></div><span>${bookings.length} réservation(s)</span></div>
          <div class="booking-list">
            ${bookings.length
        ? bookings.map((booking) => `
                <article class="booking-card ${bookingStatusClass(booking.status)}">
                  <div class="booking-card-head">
                    <div><strong>${safeText(booking.garage)}</strong><span>#${booking.id}</span></div>
                    <span class="status-pill ${booking.status === "CONFIRMED" ? "verified" : booking.status === "PENDING_PAYMENT" ? "pending" : ""}">${safeText(bookingStatusLabel(booking.status))}</span>
                  </div>
                  <h4>${safeText(booking.service)}</h4>
                  <p>${formatDateTime(booking.starts_at)}</p>
                  <div class="booking-money"><span>Acompte <strong>${formatPrice(booking.deposit_amount)}</strong></span><span>Paiement <strong>${booking.payment_status === "SUCCEEDED" ? "Validé" : "En attente"}</strong></span></div>
                </article>
              `).join("")
        : '<div class="empty-state"><strong>Aucune réservation</strong><span>Vos prochains rendez-vous apparaîtront ici.</span></div>'}
          </div>
        </article>
      </div>
    </div>
  `;
    content.querySelectorAll("[data-dashboard-link]").forEach((link) => {
        link.addEventListener("click", async (event) => {
            event.preventDefault();
            await navigateTo(new URL(link.href, window.location.origin).pathname);
        });
    });
    element("vehicle-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        try {
            await api("/api/vehicles", {
                method: "POST",
                body: JSON.stringify({
                    make: element("vehicle-make").value.trim(),
                    model: element("vehicle-model").value.trim(),
                    year: Number(element("vehicle-year").value),
                    plate: element("vehicle-plate").value.trim() || null,
                }),
            });
            showMessage("Véhicule ajouté.", "success");
            await loadDashboard();
        }
        catch (error) {
            showMessage(error.message, "error");
        }
    });
}
async function loadGarageDashboard(activeTab = "overview") {
    const data = await api("/api/garage/dashboard");
    const content = element("dashboard-content");
    const garages = data.garages || [];
    const bookings = data.bookings || [];
    const stats = data.stats || {};
    if (!garages.length) {
        content.innerHTML = `
      <div class="dashboard-shell">
        <div class="dashboard-welcome garage-dashboard-hero">
          <div><span class="dashboard-kicker">ESPACE PROFESSIONNEL</span><h3>Aucun garage associé</h3><p>Votre compte professionnel n'est encore rattaché à aucun établissement.</p></div>
        </div>
      </div>
    `;
        return;
    }
    const serviceOptions = garages
        .map((garage) => `<option value="${garage.id}">${safeText(garage.name)}</option>`)
        .join("");
    const allServices = garages.flatMap((garage) => (garage.service_items || []).map((service) => ({ ...service, garage_id: garage.id, garage_name: garage.name })));
    const allSlots = garages.flatMap((garage) => (garage.slot_items || []).map((slot) => ({ ...slot, garage_id: garage.id, garage_name: garage.name })));
    const nextBookings = [...bookings]
        .filter((booking) => booking.status === "CONFIRMED" && new Date(booking.starts_at).getTime() >= Date.now())
        .sort((a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime());
    content.innerHTML = `
    <div class="dashboard-shell garage-workspace">
      <div class="dashboard-welcome garage-dashboard-hero">
        <div>
          <span class="dashboard-kicker">PILOTAGE DE L'ATELIER</span>
          <h3>${safeText(garages[0].name)}</h3>
          <p>${safeText(garages[0].city)} · Gérez vos prestations, disponibilités et rendez-vous depuis un seul écran.</p>
        </div>
        <div class="garage-hero-status"><span class="status-pill ${garages[0].verified ? "verified" : "pending"}">${garages[0].verified ? "✓ Garage vérifié" : "Vérification en attente"}</span><small>${safeText(state.user?.email || "")}</small></div>
      </div>

      <div class="dashboard-kpis garage-kpis">
        <article><span>Rendez-vous</span><strong>${stats.upcoming || 0}</strong><small>à venir</small></article>
        <article><span>Prestations</span><strong>${stats.services || 0}</strong><small>au catalogue</small></article>
        <article><span>Créneaux</span><strong>${stats.available_slots || 0}</strong><small>encore disponibles</small></article>
        <article><span>Acomptes reçus</span><strong>${formatPrice(Number(stats.deposits_received || 0))}</strong><small>paiements validés</small></article>
      </div>

      <nav class="workspace-tabs" aria-label="Gestion du garage">
        <button type="button" data-dashboard-tab="overview">Vue d'ensemble</button>
        <button type="button" data-dashboard-tab="services">Prestations <span>${allServices.length}</span></button>
        <button type="button" data-dashboard-tab="slots">Créneaux <span>${allSlots.filter((slot) => !slot.is_booked).length}</span></button>
        <button type="button" data-dashboard-tab="bookings">Réservations <span>${bookings.length}</span></button>
        <button type="button" data-dashboard-tab="profile">Mon garage</button>
      </nav>

      <section class="workspace-panel" data-dashboard-panel="overview">
        <div class="dashboard-grid garage-overview-grid">
          <article class="panel dashboard-panel">
            <div class="panel-heading"><div><span class="panel-label">PROCHAINS RENDEZ-VOUS</span><h3>Planning à venir</h3></div><span>${nextBookings.length} rendez-vous</span></div>
            <div class="booking-list compact-booking-list">
              ${nextBookings.length
        ? nextBookings.slice(0, 6).map((booking) => `
                  <article class="booking-card status-confirmed">
                    <div class="booking-card-head"><div><strong>${safeText(booking.customer?.name || "Client")}</strong><span>#${booking.id}</span></div><span class="status-pill verified">Confirmée</span></div>
                    <h4>${safeText(booking.service)}</h4>
                    <p>${formatDateTime(booking.starts_at)} · ${booking.vehicle ? `${safeText(booking.vehicle.make)} ${safeText(booking.vehicle.model)}` : "Véhicule non renseigné"}</p>
                  </article>
                `).join("")
        : '<div class="empty-state"><strong>Aucun rendez-vous confirmé</strong><span>Les réservations payées apparaîtront automatiquement ici.</span></div>'}
            </div>
          </article>
          <article class="panel dashboard-panel activity-panel">
            <div class="panel-heading"><div><span class="panel-label">ACTIVITÉ</span><h3>Résumé de l'atelier</h3></div></div>
            <div class="activity-metrics">
              <div><span>Réservations totales</span><strong>${stats.bookings || 0}</strong></div>
              <div><span>Confirmées</span><strong>${stats.confirmed || 0}</strong></div>
              <div><span>Terminées</span><strong>${stats.completed || 0}</strong></div>
              <div><span>Garages gérés</span><strong>${garages.length}</strong></div>
            </div>
            <div class="activity-callout"><strong>Tout est synchronisé</strong><p>Une réservation payée côté client apparaît ici sans ressaisie. Le statut peut ensuite être clôturé par l'atelier.</p></div>
          </article>
        </div>
      </section>

      <section class="workspace-panel" data-dashboard-panel="services" hidden>
        <div class="management-layout">
          <article class="panel dashboard-panel management-create-card">
            <div class="panel-heading"><div><span class="panel-label">NOUVELLE PRESTATION</span><h3>Ajouter au catalogue</h3></div></div>
            <form id="service-create-form" class="management-form">
              ${garages.length > 1 ? `<label>Garage<select id="service-garage">${serviceOptions}</select></label>` : `<input id="service-garage" type="hidden" value="${garages[0].id}">`}
              <label>Nom<input id="service-name" required maxlength="120" placeholder="Diagnostic électronique"></label>
              <label>Description<textarea id="service-description" rows="4" maxlength="1000" placeholder="Décrivez clairement ce qui est inclus..."></textarea></label>
              <div class="form-grid two-cols"><label>Prix TTC (€)<input id="service-price" type="number" min="1" step="0.01" required></label><label>Durée (min)<input id="service-duration" type="number" min="15" max="1440" step="5" value="60" required></label></div>
              <button class="btn" type="submit">Ajouter la prestation</button>
            </form>
          </article>
          <div class="management-list service-management-list">
            ${allServices.length
        ? allServices.map((service) => `
                <form class="panel management-item service-edit-form" data-service-form="${service.id}">
                  <div class="management-item-head"><div><span class="panel-label">${safeText(service.garage_name)}</span><h3>${safeText(service.name)}</h3></div><strong>${formatPrice(service.price)}</strong></div>
                  <label>Nom<input name="name" value="${safeAttr(service.name)}" required maxlength="120"></label>
                  <label>Description<textarea name="description" rows="3" maxlength="1000">${safeText(service.description || "")}</textarea></label>
                  <div class="form-grid two-cols"><label>Prix (€)<input name="price" type="number" min="1" step="0.01" value="${Number(service.price)}" required></label><label>Durée (min)<input name="duration" type="number" min="15" max="1440" step="5" value="${Number(service.duration_minutes)}" required></label></div>
                  <div class="management-actions"><button class="btn" type="submit">Enregistrer</button><button class="btn danger-outline" type="button" data-delete-service="${service.id}">Supprimer</button></div>
                </form>
              `).join("")
        : '<div class="empty-state"><strong>Aucune prestation</strong><span>Ajoutez votre première prestation avec le formulaire.</span></div>'}
          </div>
        </div>
      </section>

      <section class="workspace-panel" data-dashboard-panel="slots" hidden>
        <div class="management-layout">
          <article class="panel dashboard-panel management-create-card">
            <div class="panel-heading"><div><span class="panel-label">PLANNING</span><h3>Ouvrir un créneau</h3></div></div>
            <form id="slot-create-form" class="management-form">
              ${garages.length > 1 ? `<label>Garage<select id="slot-garage">${serviceOptions}</select></label>` : `<input id="slot-garage" type="hidden" value="${garages[0].id}">`}
              <label>Date et heure<input id="slot-start" type="datetime-local" required></label>
              <label>Durée<select id="slot-duration"><option value="30">30 min</option><option value="45">45 min</option><option value="60" selected>1 h</option><option value="90">1 h 30</option><option value="120">2 h</option></select></label>
              <button class="btn" type="submit">Publier le créneau</button>
            </form>
          </article>
          <article class="panel dashboard-panel">
            <div class="panel-heading"><div><span class="panel-label">DISPONIBILITÉS</span><h3>Prochains créneaux</h3></div><span>${allSlots.length} affiché(s)</span></div>
            <div class="slot-list">
              ${allSlots.length
        ? allSlots.map((slot) => `
                  <div class="slot-management-row ${slot.is_booked ? "slot-booked" : ""}">
                    <div><strong>${formatDateTime(slot.starts_at)}</strong><small>${safeText(slot.garage_name)} · jusqu'à ${new Date(slot.ends_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}</small></div>
                    ${slot.is_booked ? '<span class="status-pill verified">Réservé</span>' : `<button class="btn small danger-outline" type="button" data-delete-slot="${slot.id}">Supprimer</button>`}
                  </div>
                `).join("")
        : '<div class="empty-state"><strong>Aucun créneau à venir</strong><span>Publiez une disponibilité pour recevoir de nouvelles réservations.</span></div>'}
            </div>
          </article>
        </div>
      </section>

      <section class="workspace-panel" data-dashboard-panel="bookings" hidden>
        <article class="panel dashboard-panel">
          <div class="panel-heading"><div><span class="panel-label">RENDEZ-VOUS</span><h3>Réservations clients</h3></div><span>${bookings.length} réservation(s)</span></div>
          <div class="booking-management-list">
            ${bookings.length
        ? bookings.map((booking) => `
                <article class="booking-management-card ${bookingStatusClass(booking.status)}">
                  <div class="booking-management-main">
                    <div class="booking-card-head"><div><strong>#${booking.id} · ${safeText(booking.service)}</strong><span>${safeText(booking.garage)}</span></div><span class="status-pill ${booking.status === "CONFIRMED" ? "verified" : booking.status === "PENDING_PAYMENT" ? "pending" : ""}">${safeText(bookingStatusLabel(booking.status))}</span></div>
                    <div class="booking-detail-grid">
                      <div><span>Client</span><strong>${safeText(booking.customer?.name || "-")}</strong><small>${safeText(booking.customer?.email || "")}</small></div>
                      <div><span>Véhicule</span><strong>${booking.vehicle ? `${safeText(booking.vehicle.make)} ${safeText(booking.vehicle.model)}` : "Non renseigné"}</strong><small>${booking.vehicle?.plate ? safeText(booking.vehicle.plate) : ""}</small></div>
                      <div><span>Rendez-vous</span><strong>${formatDateTime(booking.starts_at)}</strong><small>Acompte ${formatPrice(booking.deposit_amount)}</small></div>
                      <div><span>Paiement</span><strong>${booking.payment_status === "SUCCEEDED" ? "Validé" : "En attente"}</strong><small>Total prestation ${formatPrice(booking.total_amount)}</small></div>
                    </div>
                  </div>
                  <div class="booking-actions">
                    ${booking.status === "CONFIRMED" ? `<button class="btn small" type="button" data-booking-status="COMPLETED" data-booking-id="${booking.id}">Marquer terminée</button><button class="btn small danger-outline" type="button" data-booking-status="CANCELLED" data-booking-id="${booking.id}">Annuler</button>` : ""}
                    ${booking.status === "PENDING_PAYMENT" ? `<span class="waiting-note">En attente du paiement client</span><button class="btn small danger-outline" type="button" data-booking-status="CANCELLED" data-booking-id="${booking.id}">Annuler</button>` : ""}
                  </div>
                </article>
              `).join("")
        : '<div class="empty-state"><strong>Aucune réservation</strong><span>Les commandes clients apparaîtront ici.</span></div>'}
          </div>
        </article>
      </section>

      <section class="workspace-panel" data-dashboard-panel="profile" hidden>
        <div class="profile-management-grid">
          ${garages.map((garage) => `
            <form class="panel dashboard-panel garage-profile-form" data-garage-profile="${garage.id}">
              <div class="panel-heading"><div><span class="panel-label">FICHE PUBLIQUE</span><h3>${safeText(garage.name)}</h3></div><span class="status-pill ${garage.verified ? "verified" : "pending"}">${garage.verified ? "Vérifié" : "En attente"}</span></div>
              <div class="form-grid two-cols"><label>Nom du garage<input name="name" value="${safeAttr(garage.name)}" required></label><label>Ville<input name="city" value="${safeAttr(garage.city)}" required></label></div>
              <label>Adresse<input name="address" value="${safeAttr(garage.address)}" required></label>
              <label>Description<textarea name="description" rows="5" required>${safeText(garage.description || "")}</textarea></label>
              <label>Spécialités <small>séparées par des virgules</small><input name="specialties" value="${safeAttr(garage.specialties || "")}"></label>
              <label>Marques prises en charge <small>séparées par des virgules</small><input name="brands" value="${safeAttr(garage.brands || "")}"></label>
              <label>Taux horaire indicatif (€)<input name="hourly_rate" type="number" min="1" max="1000" step="0.01" value="${garage.hourly_rate ?? ""}"></label>
              <div class="management-actions"><button class="btn" type="submit">Enregistrer la fiche</button><a class="btn secondary" href="/garages/${garage.id}" data-dashboard-link>Voir la fiche publique</a></div>
            </form>
          `).join("")}
        </div>
      </section>
    </div>
  `;
    const activateTab = (tab) => {
        content.querySelectorAll("[data-dashboard-tab]").forEach((button) => {
            const selected = button.dataset.dashboardTab === tab;
            button.classList.toggle("active", selected);
            button.setAttribute("aria-selected", String(selected));
        });
        content.querySelectorAll("[data-dashboard-panel]").forEach((panel) => {
            panel.hidden = panel.dataset.dashboardPanel !== tab;
        });
    };
    activateTab(activeTab);
    content.querySelectorAll("[data-dashboard-tab]").forEach((button) => {
        button.addEventListener("click", () => activateTab(button.dataset.dashboardTab || "overview"));
    });
    content.querySelectorAll("[data-dashboard-link]").forEach((link) => {
        link.addEventListener("click", async (event) => {
            event.preventDefault();
            const target = new URL(link.href, window.location.origin);
            await navigateTo(target.pathname);
        });
    });
    element("service-create-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        try {
            await api("/api/services", {
                method: "POST",
                body: JSON.stringify({
                    garage_id: Number(element("service-garage").value),
                    name: element("service-name").value.trim(),
                    description: element("service-description").value.trim() || null,
                    price: Number(element("service-price").value),
                    duration_minutes: Number(element("service-duration").value),
                }),
            });
            showMessage("Prestation ajoutée au catalogue.", "success");
            await loadGarageDashboard("services");
        }
        catch (error) {
            showMessage(error.message, "error");
        }
    });
    content.querySelectorAll("[data-service-form]").forEach((form) => {
        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            const serviceId = Number(form.dataset.serviceForm);
            const formData = new FormData(form);
            try {
                await api(`/api/services/${serviceId}`, {
                    method: "PATCH",
                    body: JSON.stringify({
                        name: String(formData.get("name") || "").trim(),
                        description: String(formData.get("description") || "").trim() || null,
                        price: Number(formData.get("price")),
                        duration_minutes: Number(formData.get("duration")),
                    }),
                });
                showMessage("Prestation mise à jour.", "success");
                await loadGarageDashboard("services");
            }
            catch (error) {
                showMessage(error.message, "error");
            }
        });
    });
    content.querySelectorAll("[data-delete-service]").forEach((button) => {
        button.addEventListener("click", async () => {
            if (!window.confirm("Supprimer cette prestation ?"))
                return;
            try {
                await api(`/api/services/${Number(button.dataset.deleteService)}`, { method: "DELETE" });
                showMessage("Prestation supprimée.", "success");
                await loadGarageDashboard("services");
            }
            catch (error) {
                showMessage(error.message, "error");
            }
        });
    });
    element("slot-create-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const startsAt = element("slot-start").value;
        const duration = Number(element("slot-duration").value);
        if (!startsAt)
            return;
        const startDate = new Date(startsAt);
        const endDate = new Date(startDate.getTime() + duration * 60_000);
        const toLocalDateTime = (date) => {
            const pad = (value) => String(value).padStart(2, "0");
            return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:00`;
        };
        try {
            await api("/api/availability", {
                method: "POST",
                body: JSON.stringify({
                    garage_id: Number(element("slot-garage").value),
                    starts_at: `${startsAt}:00`,
                    ends_at: toLocalDateTime(endDate),
                }),
            });
            showMessage("Créneau publié.", "success");
            await loadGarageDashboard("slots");
        }
        catch (error) {
            showMessage(error.message, "error");
        }
    });
    content.querySelectorAll("[data-delete-slot]").forEach((button) => {
        button.addEventListener("click", async () => {
            if (!window.confirm("Supprimer ce créneau disponible ?"))
                return;
            try {
                await api(`/api/availability/${Number(button.dataset.deleteSlot)}`, { method: "DELETE" });
                showMessage("Créneau supprimé.", "success");
                await loadGarageDashboard("slots");
            }
            catch (error) {
                showMessage(error.message, "error");
            }
        });
    });
    content.querySelectorAll("[data-booking-status]").forEach((button) => {
        button.addEventListener("click", async () => {
            const bookingId = Number(button.dataset.bookingId);
            const status = button.dataset.bookingStatus || "";
            const confirmation = status === "COMPLETED"
                ? "Marquer cette intervention comme terminée ?"
                : "Annuler cette réservation ?";
            if (!window.confirm(confirmation))
                return;
            try {
                await api(`/api/bookings/${bookingId}/status`, {
                    method: "PATCH",
                    body: JSON.stringify({ status }),
                });
                showMessage(status === "COMPLETED" ? "Intervention terminée." : "Réservation annulée.", "success");
                await loadGarageDashboard("bookings");
            }
            catch (error) {
                showMessage(error.message, "error");
            }
        });
    });
    content.querySelectorAll("[data-garage-profile]").forEach((form) => {
        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            const garageId = Number(form.dataset.garageProfile);
            const formData = new FormData(form);
            const hourlyRate = String(formData.get("hourly_rate") || "").trim();
            try {
                await api(`/api/garages/${garageId}`, {
                    method: "PATCH",
                    body: JSON.stringify({
                        name: String(formData.get("name") || "").trim(),
                        city: String(formData.get("city") || "").trim(),
                        address: String(formData.get("address") || "").trim(),
                        description: String(formData.get("description") || "").trim(),
                        specialties: String(formData.get("specialties") || "").trim(),
                        brands: String(formData.get("brands") || "").trim(),
                        hourly_rate: hourlyRate ? Number(hourlyRate) : null,
                    }),
                });
                showMessage("Fiche garage mise à jour.", "success");
                await loadGarageDashboard("profile");
            }
            catch (error) {
                showMessage(error.message, "error");
            }
        });
    });
}
async function loadAdminDashboard() {
    const [stats, data] = await Promise.all([
        api("/api/admin/stats"),
        api("/api/garage/dashboard"),
    ]);
    const content = element("dashboard-content");
    content.innerHTML = `
    <div class="dashboard-shell admin-dashboard-shell">
    <div class="admin-intro panel">
      <div><span class="admin-kicker">SUPERVISION DE LA PLATEFORME</span><h3>Vue d'ensemble MecaConnect</h3><p>Suivez les comptes, les garages partenaires, les réservations et les paiements depuis cet espace sécurisé.</p></div>
      <a class="btn secondary" href="/api/docs">Ouvrir Swagger</a>
    </div>
    <div class="stats-grid">
      <article><strong>${stats.users}</strong><span>utilisateurs</span></article>
      <article><strong>${stats.garages}</strong><span>garages</span></article>
      <article><strong>${stats.bookings}</strong><span>réservations</span></article>
      <article><strong>${stats.payments_succeeded}</strong><span>paiements réussis</span></article>
      <article><strong>${stats.analytics_events}</strong><span>événements analytics consentis</span></article>
    </div>
    <div class="dashboard-grid admin-grid">
      <article class="panel">
        <div class="panel-heading"><div><span class="panel-label">RÉSEAU</span><h3>Garages suivis</h3></div><span>${data.garages.length} établissement(s)</span></div>
        <div class="admin-list">${data.garages.length
        ? data.garages.map((garage) => `<div class="admin-row"><div><strong>${safeText(garage.name)}</strong><small>${safeText(garage.city)} · ${garage.services} prestation(s)</small></div><span class="status-pill ${garage.verified ? "verified" : "pending"}">${garage.verified ? "Vérifié" : "À contrôler"}</span></div>`).join("")
        : "<p>Aucun garage enregistré.</p>"}</div>
      </article>
      <article class="panel">
        <div class="panel-heading"><div><span class="panel-label">ACTIVITÉ</span><h3>Réservations récentes</h3></div><span>${data.bookings.length} affichée(s)</span></div>
        <div class="admin-list">${data.bookings.length
        ? data.bookings.slice(0, 10).map((booking) => `<div class="admin-row"><div><strong>#${booking.id} · ${safeText(booking.service)}</strong><small>${safeText(booking.garage)} · ${new Date(booking.starts_at).toLocaleString("fr-FR")}</small></div><span class="status-pill">${safeText(booking.status)}</span></div>`).join("")
        : "<p>Aucune réservation récente.</p>"}</div>
      </article>
    </div>
    </div>
  `;
}
async function loadDashboard() {
    const section = element("dashboard");
    if (!state.user) {
        section.hidden = true;
        return;
    }
    section.hidden = false;
    element("dashboard-role").textContent = state.user.role;
    if (state.user.role === "USER") {
        element("dashboard-eyebrow").textContent = "ESPACE AUTOMOBILISTE";
        element("dashboard-title").textContent = "Mon espace";
        await loadUserDashboard();
    }
    else if (state.user.role === "GARAGE") {
        element("dashboard-eyebrow").textContent = "ESPACE PROFESSIONNEL";
        element("dashboard-title").textContent = "Tableau de bord garage";
        await loadGarageDashboard();
    }
    else {
        element("dashboard-eyebrow").textContent = "ADMINISTRATION";
        element("dashboard-title").textContent = "Tableau de bord administrateur";
        await loadAdminDashboard();
    }
}
async function updateSession() {
    try {
        state.user = await api("/api/auth/me");
        element("account-label").textContent = state.user.full_name;
        element("logout").hidden = false;
        element("dashboard-label").hidden = false;
    }
    catch {
        state.user = undefined;
        element("account-label").textContent = "Connexion";
        element("logout").hidden = true;
        element("dashboard-label").hidden = true;
        element("dashboard").hidden = true;
    }
}
function bindEvents() {
    document.querySelectorAll("a[data-link]").forEach((link) => {
        link.addEventListener("click", async (event) => {
            if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey)
                return;
            event.preventDefault();
            const target = new URL(link.href, window.location.origin);
            await navigateTo(`${target.pathname}${target.search}`);
        });
    });
    window.addEventListener("popstate", () => {
        renderRoute().catch((error) => showMessage(error.message, "error"));
    });
    element("search-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const city = element("city").value;
        const query = element("q").value;
        await navigateTo("/garages");
        const filtered = filterGarages(state.garages, query, city);
        renderGarages(filtered);
        try {
            const coordinates = coordinatesForLocation(city);
            if (coordinates && garageMap) {
                garageMap.flyTo({ center: coordinates, zoom: 11.5, essential: true });
            }
        }
        catch (error) {
            console.warn(error);
        }
    });
    element("assistant-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const input = element("assistant-message");
        const message = input.value;
        input.value = "";
        await askAssistant(message);
    });
    document.querySelectorAll("[data-assistant-prompt]").forEach((button) => {
        button.addEventListener("click", () => {
            const input = element("assistant-message");
            input.value = button.dataset.assistantPrompt || "";
            input.focus();
        });
    });
    element("account-label").addEventListener("click", () => {
        navigateTo(state.user ? dashboardPath() : "/connexion");
    });
    element("dashboard-label").addEventListener("click", () => {
        navigateTo(dashboardPath());
    });
    element("close-booking").addEventListener("click", () => {
        element("booking-dialog").close();
    });
    element("logout").addEventListener("click", async () => {
        await api("/api/auth/logout", { method: "POST" });
        await updateSession();
        await navigateTo("/");
        showMessage("Vous êtes déconnecté.", "success");
    });
    element("login-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        try {
            await api("/api/auth/login", {
                method: "POST",
                body: JSON.stringify({
                    email: element("login-email").value,
                    password: element("login-password").value,
                    totp_code: element("login-totp").value || null,
                }),
            });
            await updateSession();
            const next = new URLSearchParams(window.location.search).get("next");
            const destination = next?.startsWith("/") ? next : dashboardPath();
            await navigateTo(destination, true);
            showMessage("Connexion réussie.", "success");
        }
        catch (error) {
            showMessage(error.message, "error");
        }
    });
    element("register-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const password = element("reg-password").value;
        if (!isStrongPassword(password)) {
            showMessage("Mot de passe trop faible : 12 caractères et 3 catégories minimum.", "error");
            return;
        }
        try {
            await api("/api/auth/register", {
                method: "POST",
                body: JSON.stringify({
                    email: element("reg-email").value,
                    password,
                    full_name: element("reg-name").value,
                }),
            });
            await updateSession();
            await navigateTo("/mon-espace", true);
            showMessage("Compte créé.", "success");
        }
        catch (error) {
            showMessage(error.message, "error");
        }
    });
    element("booking-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!state.selectedService) {
            showMessage("Aucune prestation sélectionnée.", "error");
            return;
        }
        try {
            const vehicleValue = element("booking-vehicle").value;
            const booking = await api("/api/bookings", {
                method: "POST",
                body: JSON.stringify({
                    service_id: state.selectedService.id,
                    slot_id: Number(element("booking-slot").value),
                    vehicle_id: vehicleValue ? Number(vehicleValue) : null,
                }),
            });
            const payment = await api(`/api/payments/${booking.id}/session`, {
                method: "POST",
            });
            if (payment.mode === "local-test") {
                await api(payment.checkout_url, { method: "POST" });
                element("booking-dialog").close();
                showMessage(`Réservation confirmée. Acompte test : ${formatPrice(payment.amount)}.`, "success");
                await navigateTo(dashboardPath());
            }
            else if (payment.checkout_url) {
                window.location.href = payment.checkout_url;
            }
        }
        catch (error) {
            showMessage(error.message, "error");
        }
    });
    element("newsletter-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        try {
            const response = await api("/api/newsletter/request", {
                method: "POST",
                body: JSON.stringify({
                    email: element("newsletter-email").value,
                }),
            });
            showMessage("Un e-mail de confirmation est requis (double opt-in).", "success");
            console.info("Lien de confirmation en environnement local", response.confirmation_path);
        }
        catch (error) {
            showMessage(error.message, "error");
        }
    });
    element("cookie-settings").addEventListener("click", () => {
        element("cookie-dialog").showModal();
    });
    element("cookies-refuse").addEventListener("click", () => {
        localStorage.setItem("mc-consent", "necessary");
        element("cookie-dialog").close();
    });
    element("cookies-accept").addEventListener("click", async () => {
        localStorage.setItem("mc-consent", "analytics");
        element("cookie-dialog").close();
        await fetch("/api/analytics/event", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                event: "consent_analytics",
                path: location.pathname,
            }),
        });
        showMessage("Préférences enregistrées.", "success");
    });
}
async function start() {
    bindEvents();
    await Promise.all([loadGarages(), updateSession()]);
    await renderRoute();
    const consent = localStorage.getItem("mc-consent");
    if (!consent) {
        element("cookie-dialog").showModal();
    }
    else if (consent === "analytics") {
        fetch("/api/analytics/event", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ event: "page_view", path: location.pathname }),
        });
    }
}
start();
