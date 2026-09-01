import {
  Garage,
  depositFor,
  filterGarages,
  formatPrice,
  isStrongPassword,
  safeText,
  sortSlots,
} from "./lib.js";

type User = {
  id: number;
  email: string;
  full_name: string;
  role: "USER" | "GARAGE" | "ADMIN";
};

type Service = {
  id: number;
  name: string;
  description: string | null;
  price: number;
  duration_minutes: number;
};

type GarageDetail = Garage & {
  services: Service[];
};

type AssistantGarage = Garage & {
  score: number;
  distance_km: number | null;
  reason: string;
  service_hint: { id: number; name: string; price: number; duration_minutes: number } | null;
};

type AssistantResponse = {
  response_type: "diagnosis" | "clarification" | "needs_context" | "out_of_scope" | "unsafe_request" | "invalid_input" | "safety_stop";
  summary: string;
  confidence: number;
  follow_up_question: string | null;
  urgency: { level: string; label: string; advice: string };
  estimated_cost: { min: number; max: number; label: string; basis: string } | null;
  possible_causes: string[];
  recommended_actions: string[];
  specialties: string[];
  garages: AssistantGarage[];
  disclaimer: string;
  engine?: "rules" | "hybrid-openai";
};

declare const mapboxgl: any;

type AppState = {
  garages: Garage[];
  user?: User;
  selectedGarage?: GarageDetail;
  selectedService?: Service;
  assistantHistory: string[];
};

const state: AppState = {
  garages: [],
  assistantHistory: [],
};

let garageMap: any = null;
let garageMarkers: any[] = [];

type PageName = "home" | "assistant" | "garages" | "garage-detail" | "auth" | "dashboard" | "how" | "pro";

const pageTitles: Record<PageName, string> = {
  home: "MecaConnect - Réservez votre garage en ligne",
  assistant: "MecaBot - Assistant automobile | MecaConnect",
  garages: "Garages en Île-de-France | MecaConnect",
  "garage-detail": "Fiche garage | MecaConnect",
  auth: "Connexion | MecaConnect",
  dashboard: "Mon espace | MecaConnect",
  how: "Comment ça marche | MecaConnect",
  pro: "Espace professionnel | MecaConnect",
};

function element<T extends HTMLElement>(id: string): T {
  const node = document.getElementById(id);
  if (!node) {
    throw new Error(`Élément introuvable : ${id}`);
  }
  return node as T;
}

async function api<T>(url: string, options: RequestInit = {}): Promise<T> {
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
    return undefined as T;
  }

  return response.json();
}

function showMessage(text: string, type = "info"): void {
  const box = element<HTMLDivElement>("message");
  box.textContent = text;
  box.className = `message ${type}`;
  box.hidden = false;

  window.setTimeout(() => {
    box.hidden = true;
  }, 5000);
}

function dashboardPath(user = state.user): string {
  if (user?.role === "ADMIN") return "/admin";
  if (user?.role === "GARAGE") return "/espace-garage";
  return "/mon-espace";
}

function showPage(page: PageName): void {
  document.querySelectorAll<HTMLElement>("[data-page]").forEach((section) => {
    section.hidden = section.dataset.page !== page;
  });
  document.title = pageTitles[page];
  document.querySelectorAll<HTMLAnchorElement>("[data-link]").forEach((link) => {
    const target = new URL(link.href, window.location.origin).pathname;
    const active = target === window.location.pathname;
    link.classList.toggle("active", active);
    if (active) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  window.scrollTo({ top: 0, behavior: "instant" });
}

async function renderRoute(): Promise<void> {
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

async function navigateTo(path: string, replace = false): Promise<void> {
  const target = new URL(path, window.location.origin);
  if (replace) window.history.replaceState({}, "", `${target.pathname}${target.search}`);
  else window.history.pushState({}, "", `${target.pathname}${target.search}`);
  await renderRoute();
}

function stars(rating: number): string {
  const rounded = Math.round(rating);
  return "★".repeat(rounded) + "☆".repeat(Math.max(0, 5 - rounded));
}

async function geocodeCity(city: string): Promise<number[] | null> {
  const meta = document.querySelector<HTMLMetaElement>('meta[name="mapbox-token"]');
  const token = meta?.content || "";

  if (!city || !token.startsWith("pk.") || token.includes("replace_me")) {
    return null;
  }

  const url =
    `https://api.mapbox.com/geocoding/v5/mapbox.places/` +
    `${encodeURIComponent(city)}.json?access_token=${encodeURIComponent(token)}` +
    `&limit=1&language=fr`;

  const response = await fetch(url, {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error("Service cartographique indisponible");
  }

  const data = await response.json();
  return data.features?.[0]?.center || null;
}

function mapToken(): string {
  const meta = document.querySelector<HTMLMetaElement>('meta[name="mapbox-token"]');
  return meta?.content || "";
}

function focusGarageOnMap(garage: Garage): void {
  if (!garageMap || garage.lat == null || garage.lng == null) {
    return;
  }
  garageMap.flyTo({ center: [garage.lng, garage.lat], zoom: 13.5, essential: true });
}

function updateMapMarkers(garages: Garage[]): void {
  if (!garageMap || typeof mapboxgl === "undefined") {
    return;
  }

  garageMarkers.forEach((marker) => marker.remove());
  garageMarkers = [];

  const bounds = new mapboxgl.LngLatBounds();
  for (const garage of garages) {
    if (garage.lat == null || garage.lng == null) {
      continue;
    }

    const popup = new mapboxgl.Popup({ offset: 20 }).setHTML(
      `<strong>${safeText(garage.name)}</strong><br>${safeText(garage.city)}<br>` +
      `<small>${safeText((garage.specialties || []).slice(0, 3).join(" · "))}</small>`,
    );
    const marker = new mapboxgl.Marker({ color: "#e4461a" })
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

function renderSchematicMap(): void {
  const container = element<HTMLDivElement>("garage-map");
  container.classList.add("map-placeholder");
  container.innerHTML = '<div class="schematic-label">Carte IDF schématique - la version Mapbox s’active avec le token du projet</div>';

  const points = state.garages.filter((garage) => garage.lat != null && garage.lng != null);
  if (!points.length) return;

  const minLat = Math.min(...points.map((garage) => garage.lat as number));
  const maxLat = Math.max(...points.map((garage) => garage.lat as number));
  const minLng = Math.min(...points.map((garage) => garage.lng as number));
  const maxLng = Math.max(...points.map((garage) => garage.lng as number));

  for (const garage of points) {
    const x = 7 + (((garage.lng as number) - minLng) / Math.max(0.01, maxLng - minLng)) * 86;
    const y = 9 + (1 - ((garage.lat as number) - minLat) / Math.max(0.01, maxLat - minLat)) * 80;
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

function initGarageMap(): void {
  const token = mapToken();
  const status = element<HTMLParagraphElement>("map-status");
  const container = element<HTMLDivElement>("garage-map");

  if (garageMap) {
    garageMap.resize();
    updateMapMarkers(state.garages);
    return;
  }

  if (!token.startsWith("pk.") || token.includes("replace_me") || typeof mapboxgl === "undefined") {
    status.textContent = !token.startsWith("pk.")
      ? "Mapbox n'est pas configuré : ajoutez un MAPBOX_TOKEN public commençant par pk. dans Railway."
      : "La bibliothèque Mapbox n'a pas pu être chargée. Vérifiez le réseau et la politique CSP.";
    renderSchematicMap();
    return;
  }

  try {
    container.classList.remove("map-placeholder");
    container.innerHTML = "";
    status.textContent = "Chargement de la carte Mapbox…";
    mapboxgl.accessToken = token;
    garageMap = new mapboxgl.Map({
      container,
      style: "mapbox://styles/mapbox/streets-v12",
      center: [2.35, 48.86],
      zoom: 8.5,
      attributionControl: true,
    });
    garageMap.addControl(new mapboxgl.NavigationControl({ showCompass: false }), "top-right");
    garageMap.on("load", () => {
      status.textContent = "Carte interactive chargée. Sélectionnez un atelier pour afficher ses informations.";
      garageMap.resize();
      updateMapMarkers(state.garages);
    });
    garageMap.on("error", (event: any) => {
      const detail = event?.error?.message ? ` (${event.error.message})` : "";
      status.textContent = `Mapbox n'a pas pu afficher la carte${detail}. Vérifiez le token, ses restrictions d'URL et les requêtes réseau.`;
      status.classList.add("map-error");
    });
  } catch (error) {
    garageMap = null;
    status.textContent = `Impossible d'initialiser Mapbox : ${(error as Error).message}`;
    status.classList.add("map-error");
    renderSchematicMap();
  }
}

function populateCities(): void {
  const select = element<HTMLSelectElement>("city");
  const current = select.value;
  const cities = [...new Set(state.garages.map((garage) => garage.city))].sort((a, b) => a.localeCompare(b, "fr"));
  select.innerHTML = '<option value="">Toutes les villes</option>';
  cities.forEach((city) => select.add(new Option(city, city)));
  select.value = current;
}

function renderGarages(garages: Garage[]): void {
  const grid = element<HTMLDivElement>("garage-grid");
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

  grid.querySelectorAll<HTMLButtonElement>("[data-garage]").forEach((button) => {
    button.addEventListener("click", () => {
      openGarage(Number(button.dataset.garage));
    });
  });

  grid.querySelectorAll<HTMLButtonElement>("[data-map-garage]").forEach((button) => {
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

async function loadGarages(): Promise<void> {
  state.garages = await api<Garage[]>("/api/garages");
  populateCities();
  renderGarages(state.garages);
}

async function loadGarageDetail(id: number): Promise<void> {
  const garage = await api<GarageDetail>(`/api/garages/${id}`);
  state.selectedGarage = garage;

  element<HTMLHeadingElement>("garage-name").textContent = garage.name;
  document.title = `${garage.name} | MecaConnect`;
  element<HTMLParagraphElement>("garage-address").textContent =
    `${garage.address} - ${garage.city}`;

  const list = element<HTMLDivElement>("service-list");
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

  list.querySelectorAll<HTMLButtonElement>("[data-service]").forEach((button) => {
    button.addEventListener("click", () => {
      startBooking(Number(button.dataset.service));
    });
  });

}

async function openGarage(id: number): Promise<void> {
  await navigateTo(`/garages/${id}`);
}

async function startBooking(serviceId: number): Promise<void> {
  try {
    if (!state.user) {
      showMessage("Connectez-vous avant de réserver.", "warning");
      await navigateTo(`/connexion?next=${encodeURIComponent(window.location.pathname)}`);
      return;
    }

    const service = state.selectedGarage?.services.find(
      (item) => item.id === serviceId,
    );
    if (!service || !state.selectedGarage) {
      throw new Error("Prestation introuvable");
    }

    state.selectedService = service;

    const slots = sortSlots(
      await api<any[]>(`/api/availability?garage_id=${state.selectedGarage.id}`),
    );
    if (!slots.length) {
      showMessage("Aucun créneau disponible actuellement.", "warning");
      return;
    }

    const vehicles = await api<any[]>("/api/vehicles").catch(() => []);
    const vehicleSelect = element<HTMLSelectElement>("booking-vehicle");
    vehicleSelect.innerHTML = '<option value="">Sans véhicule associé</option>';

    for (const vehicle of vehicles) {
      vehicleSelect.add(
        new Option(
          `${vehicle.make} ${vehicle.model} (${vehicle.year})`,
          String(vehicle.id),
        ),
      );
    }

    const slotSelect = element<HTMLSelectElement>("booking-slot");
    slotSelect.innerHTML = "";
    for (const slot of slots) {
      slotSelect.add(
        new Option(
          new Date(slot.starts_at).toLocaleString("fr-FR"),
          String(slot.id),
        ),
      );
    }

    element("booking-title").textContent =
      `${service.name} - ${state.selectedGarage.name}`;
    element("booking-summary").textContent =
      `Prestation : ${formatPrice(service.price)}. ` +
      "Le créneau reste disponible jusqu'à la validation de la réservation.";
    element("booking-deposit").textContent = formatPrice(depositFor(service.price));
    element<HTMLDialogElement>("booking-dialog").showModal();
  } catch (error) {
    showMessage((error as Error).message, "error");
  }
}

function appendChatMessage(author: "user" | "bot", html: string): void {
  const messages = element<HTMLDivElement>("assistant-messages");
  const bubble = document.createElement("div");
  bubble.className = `chat-message ${author}`;
  bubble.innerHTML = html;
  messages.append(bubble);
  messages.scrollTop = messages.scrollHeight;
}

function urgencyClass(level: string): string {
  if (level === "CRITICAL") return "critical";
  if (level === "HIGH") return "high";
  if (level === "MEDIUM") return "medium";
  return "low";
}

function renderAssistantResponse(result: AssistantResponse): void {
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
  const engine = result.engine === "hybrid-openai"
    ? '<span class="ai-badge">IA OpenAI + garde-fous MecaConnect</span>'
    : '<span class="ai-badge local">Moteur sécurisé MecaConnect</span>';

  appendChatMessage(
    "bot",
    `<strong>MecaBot</strong>
     <div class="assistant-engine">${engine}</div>
     <div class="assistant-result-head"><span class="urgency ${urgencyClass(result.urgency.level)}">${safeText(result.urgency.label)}</span>${confidence}</div>
     <p>${safeText(result.summary)}</p>
     ${estimate}
     <div class="assistant-columns">${causes}${actions}</div>
     <p><strong>Conseil :</strong> ${safeText(result.urgency.advice)}</p>
     ${result.follow_up_question ? `<p class="follow-up"><strong>Pour affiner :</strong> ${safeText(result.follow_up_question)}</p>` : ""}
     ${garages}
     <small class="assistant-disclaimer">${safeText(result.disclaimer)}</small>`,
  );

  element<HTMLDivElement>("assistant-messages")
    .querySelectorAll<HTMLButtonElement>("[data-chat-garage]")
    .forEach((button) => {
      if (button.dataset.bound === "1") return;
      button.dataset.bound = "1";
      button.addEventListener("click", async () => {
        const garageId = Number(button.dataset.chatGarage);
        const garage = state.garages.find((item) => item.id === garageId);
        await openGarage(garageId);
        if (garage) focusGarageOnMap(garage);
      });
    });
}

async function askAssistant(message: string): Promise<void> {
  const cleanMessage = message.trim();
  if (!cleanMessage) return;

  appendChatMessage("user", `<strong>Vous</strong><p>${safeText(cleanMessage)}</p>`);
  state.assistantHistory.push(cleanMessage);
  state.assistantHistory = state.assistantHistory.slice(-6);

  const sendButton = element<HTMLFormElement>("assistant-form").querySelector<HTMLButtonElement>("button[type=submit]");
  if (sendButton) {
    sendButton.disabled = true;
    sendButton.textContent = "Analyse en cours...";
  }

  try {
    const location = element<HTMLInputElement>("assistant-location").value.trim();
    const coordinates = location ? await geocodeCity(location).catch(() => null) : null;
    const yearValue = element<HTMLInputElement>("assistant-year").value;
    const result = await api<AssistantResponse>("/api/assistant/diagnose", {
      method: "POST",
      body: JSON.stringify({
        message: cleanMessage,
        history: state.assistantHistory.slice(0, -1),
        location: location || null,
        vehicle_make: element<HTMLInputElement>("assistant-make").value.trim() || null,
        vehicle_model: element<HTMLInputElement>("assistant-model").value.trim() || null,
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
    } else {
      updateMapMarkers(state.garages);
    }
  } catch (error) {
    appendChatMessage("bot", `<strong>MecaBot</strong><p>Je n'ai pas pu terminer l'analyse : ${safeText((error as Error).message)}</p>`);
  } finally {
    if (sendButton) {
      sendButton.disabled = false;
      sendButton.textContent = "Analyser mon problème";
    }
  }
}

async function loadUserDashboard(): Promise<void> {
  const [vehicles, bookings] = await Promise.all([
    api<any[]>("/api/vehicles"),
    api<any[]>("/api/bookings/me"),
  ]);

  const content = element<HTMLDivElement>("dashboard-content");
  content.innerHTML = `
    <div class="dashboard-grid">
      <article class="panel">
        <h3>Mes véhicules</h3>
        <form id="vehicle-form" class="stack-form">
          <label>Marque<input id="vehicle-make" required></label>
          <label>Modèle<input id="vehicle-model" required></label>
          <label>Année<input id="vehicle-year" type="number" min="1950" max="2100" required></label>
          <button class="btn" type="submit">Ajouter</button>
        </form>
        <div>
          ${
            vehicles.length
              ? vehicles
                  .map(
                    (vehicle) =>
                      `<p><strong>${safeText(vehicle.make)} ${safeText(vehicle.model)}</strong> - ${vehicle.year}</p>`,
                  )
                  .join("")
              : "<p>Aucun véhicule enregistré.</p>"
          }
        </div>
      </article>
      <article class="panel">
        <h3>Mes réservations</h3>
        ${
          bookings.length
            ? bookings
                .map(
                  (booking) => `
                    <p>
                      <strong>${safeText(booking.garage)}</strong> - ${safeText(booking.service)}<br>
                      <small>
                        ${new Date(booking.starts_at).toLocaleString("fr-FR")} ·
                        ${safeText(booking.status)} ·
                        acompte ${formatPrice(booking.deposit_amount)}
                      </small>
                    </p>
                  `,
                )
                .join("")
            : "<p>Aucune réservation.</p>"
        }
      </article>
    </div>
  `;

  element<HTMLFormElement>("vehicle-form").addEventListener("submit", async (event) => {
    event.preventDefault();

    try {
      await api("/api/vehicles", {
        method: "POST",
        body: JSON.stringify({
          make: element<HTMLInputElement>("vehicle-make").value,
          model: element<HTMLInputElement>("vehicle-model").value,
          year: Number(element<HTMLInputElement>("vehicle-year").value),
          plate: null,
        }),
      });
      showMessage("Véhicule ajouté.", "success");
      await loadDashboard();
    } catch (error) {
      showMessage((error as Error).message, "error");
    }
  });
}

async function loadGarageDashboard(): Promise<void> {
  const data = await api<any>("/api/garage/dashboard");
  const content = element<HTMLDivElement>("dashboard-content");

  content.innerHTML = `
    <div class="dashboard-grid">
      <article class="panel">
        <h3>Mes garages</h3>
        ${
          data.garages.length
            ? data.garages
                .map(
                  (garage: any) => `
                    <p>
                      <strong>${safeText(garage.name)}</strong> - ${safeText(garage.city)}<br>
                      <small>${garage.services} prestation(s) · ${garage.verified ? "vérifié" : "en attente"}</small>
                    </p>
                  `,
                )
                .join("")
            : "<p>Aucun garage associé.</p>"
        }
      </article>
      <article class="panel">
        <h3>Réservations récentes</h3>
        ${
          data.bookings.length
            ? data.bookings
                .map(
                  (booking: any) => `
                    <p>
                      <strong>#${booking.id} ${safeText(booking.service)}</strong><br>
                      <small>${new Date(booking.starts_at).toLocaleString("fr-FR")} · ${safeText(booking.status)}</small>
                    </p>
                  `,
                )
                .join("")
            : "<p>Aucune réservation.</p>"
        }
      </article>
    </div>
  `;
}

async function loadAdminDashboard(): Promise<void> {
  const [stats, data] = await Promise.all([
    api<any>("/api/admin/stats"),
    api<any>("/api/garage/dashboard"),
  ]);

  const content = element<HTMLDivElement>("dashboard-content");
  content.innerHTML = `
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
          ? data.garages.map((garage: any) => `<div class="admin-row"><div><strong>${safeText(garage.name)}</strong><small>${safeText(garage.city)} · ${garage.services} prestation(s)</small></div><span class="status-pill ${garage.verified ? "verified" : "pending"}">${garage.verified ? "Vérifié" : "À contrôler"}</span></div>`).join("")
          : "<p>Aucun garage enregistré.</p>"}</div>
      </article>
      <article class="panel">
        <div class="panel-heading"><div><span class="panel-label">ACTIVITÉ</span><h3>Réservations récentes</h3></div><span>${data.bookings.length} affichée(s)</span></div>
        <div class="admin-list">${data.bookings.length
          ? data.bookings.slice(0, 10).map((booking: any) => `<div class="admin-row"><div><strong>#${booking.id} · ${safeText(booking.service)}</strong><small>${safeText(booking.garage)} · ${new Date(booking.starts_at).toLocaleString("fr-FR")}</small></div><span class="status-pill">${safeText(booking.status)}</span></div>`).join("")
          : "<p>Aucune réservation récente.</p>"}</div>
      </article>
    </div>
  `;
}

async function loadDashboard(): Promise<void> {
  const section = element<HTMLElement>("dashboard");

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
  } else if (state.user.role === "GARAGE") {
    element("dashboard-eyebrow").textContent = "ESPACE PROFESSIONNEL";
    element("dashboard-title").textContent = "Tableau de bord garage";
    await loadGarageDashboard();
  } else {
    element("dashboard-eyebrow").textContent = "ADMINISTRATION";
    element("dashboard-title").textContent = "Tableau de bord administrateur";
    await loadAdminDashboard();
  }
}

async function updateSession(): Promise<void> {
  try {
    state.user = await api<User>("/api/auth/me");
    element("account-label").textContent = state.user.full_name;
    element<HTMLButtonElement>("logout").hidden = false;
    element<HTMLButtonElement>("dashboard-label").hidden = false;
  } catch {
    state.user = undefined;
    element("account-label").textContent = "Connexion";
    element<HTMLButtonElement>("logout").hidden = true;
    element<HTMLButtonElement>("dashboard-label").hidden = true;
    element<HTMLElement>("dashboard").hidden = true;
  }
}

function bindEvents(): void {
  document.querySelectorAll<HTMLAnchorElement>("a[data-link]").forEach((link) => {
    link.addEventListener("click", async (event) => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      const target = new URL(link.href, window.location.origin);
      await navigateTo(`${target.pathname}${target.search}`);
    });
  });

  window.addEventListener("popstate", () => {
    renderRoute().catch((error) => showMessage((error as Error).message, "error"));
  });

  element<HTMLFormElement>("search-form").addEventListener("submit", async (event) => {
    event.preventDefault();

    const city = element<HTMLSelectElement>("city").value;
    const query = element<HTMLInputElement>("q").value;
    await navigateTo("/garages");
    const filtered = filterGarages(state.garages, query, city);
    renderGarages(filtered);

    try {
      const coordinates = await geocodeCity(city);
      if (coordinates && garageMap) {
        garageMap.flyTo({ center: coordinates, zoom: 11.5, essential: true });
      }
    } catch (error) {
      console.warn(error);
    }
  });

  element<HTMLFormElement>("assistant-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = element<HTMLTextAreaElement>("assistant-message");
    const message = input.value;
    input.value = "";
    await askAssistant(message);
  });

  document.querySelectorAll<HTMLButtonElement>("[data-assistant-prompt]").forEach((button) => {
    button.addEventListener("click", () => {
      const input = element<HTMLTextAreaElement>("assistant-message");
      input.value = button.dataset.assistantPrompt || "";
      input.focus();
    });
  });

  element<HTMLButtonElement>("account-label").addEventListener("click", () => {
    navigateTo(state.user ? dashboardPath() : "/connexion");
  });

  element<HTMLButtonElement>("dashboard-label").addEventListener("click", () => {
    navigateTo(dashboardPath());
  });

  element<HTMLButtonElement>("close-booking").addEventListener("click", () => {
    element<HTMLDialogElement>("booking-dialog").close();
  });

  element<HTMLButtonElement>("logout").addEventListener("click", async () => {
    await api("/api/auth/logout", { method: "POST" });
    await updateSession();
    await navigateTo("/");
    showMessage("Vous êtes déconnecté.", "success");
  });

  element<HTMLFormElement>("login-form").addEventListener("submit", async (event) => {
    event.preventDefault();

    try {
      await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({
          email: element<HTMLInputElement>("login-email").value,
          password: element<HTMLInputElement>("login-password").value,
          totp_code: element<HTMLInputElement>("login-totp").value || null,
        }),
      });

      await updateSession();
      const next = new URLSearchParams(window.location.search).get("next");
      const destination = next?.startsWith("/") ? next : dashboardPath();
      await navigateTo(destination, true);
      showMessage("Connexion réussie.", "success");
    } catch (error) {
      showMessage((error as Error).message, "error");
    }
  });

  element<HTMLFormElement>("register-form").addEventListener("submit", async (event) => {
    event.preventDefault();

    const password = element<HTMLInputElement>("reg-password").value;
    if (!isStrongPassword(password)) {
      showMessage(
        "Mot de passe trop faible : 12 caractères et 3 catégories minimum.",
        "error",
      );
      return;
    }

    try {
      await api("/api/auth/register", {
        method: "POST",
        body: JSON.stringify({
          email: element<HTMLInputElement>("reg-email").value,
          password,
          full_name: element<HTMLInputElement>("reg-name").value,
        }),
      });

      await updateSession();
      await navigateTo("/mon-espace", true);
      showMessage("Compte créé.", "success");
    } catch (error) {
      showMessage((error as Error).message, "error");
    }
  });

  element<HTMLFormElement>("booking-form").addEventListener("submit", async (event) => {
    event.preventDefault();

    if (!state.selectedService) {
      showMessage("Aucune prestation sélectionnée.", "error");
      return;
    }

    try {
      const vehicleValue = element<HTMLSelectElement>("booking-vehicle").value;
      const booking = await api<any>("/api/bookings", {
        method: "POST",
        body: JSON.stringify({
          service_id: state.selectedService.id,
          slot_id: Number(element<HTMLSelectElement>("booking-slot").value),
          vehicle_id: vehicleValue ? Number(vehicleValue) : null,
        }),
      });

      const payment = await api<any>(`/api/payments/${booking.id}/session`, {
        method: "POST",
      });

      if (payment.mode === "local-test") {
        await api(payment.checkout_url, { method: "POST" });
        element<HTMLDialogElement>("booking-dialog").close();
        showMessage(
          `Réservation confirmée. Acompte test : ${formatPrice(payment.amount)}.`,
          "success",
        );
        await navigateTo(dashboardPath());
      } else if (payment.checkout_url) {
        window.location.href = payment.checkout_url;
      }
    } catch (error) {
      showMessage((error as Error).message, "error");
    }
  });

  element<HTMLFormElement>("newsletter-form").addEventListener("submit", async (event) => {
    event.preventDefault();

    try {
      const response = await api<any>("/api/newsletter/request", {
        method: "POST",
        body: JSON.stringify({
          email: element<HTMLInputElement>("newsletter-email").value,
        }),
      });
      showMessage("Un e-mail de confirmation est requis (double opt-in).", "success");
      console.info("Lien de confirmation pour la démo", response.confirmation_path);
    } catch (error) {
      showMessage((error as Error).message, "error");
    }
  });

  element<HTMLButtonElement>("cookie-settings").addEventListener("click", () => {
    element<HTMLDialogElement>("cookie-dialog").showModal();
  });

  element<HTMLButtonElement>("cookies-refuse").addEventListener("click", () => {
    localStorage.setItem("mc-consent", "necessary");
    element<HTMLDialogElement>("cookie-dialog").close();
  });

  element<HTMLButtonElement>("cookies-accept").addEventListener("click", async () => {
    localStorage.setItem("mc-consent", "analytics");
    element<HTMLDialogElement>("cookie-dialog").close();
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

async function start(): Promise<void> {
  bindEvents();
  await Promise.all([loadGarages(), updateSession()]);
  await renderRoute();

  const consent = localStorage.getItem("mc-consent");
  if (!consent) {
    element<HTMLDialogElement>("cookie-dialog").showModal();
  } else if (consent === "analytics") {
    fetch("/api/analytics/event", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event: "page_view", path: location.pathname }),
    });
  }
}

start();
