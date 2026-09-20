export type Garage = {
  id: number;
  name: string;
  city: string;
  address: string;
  description: string;
  rating: number;
  verified: boolean;
  lat?: number | null;
  lng?: number | null;
  department?: string | null;
  postal_code?: string | null;
  specialties?: string[];
  brands?: string[];
  hourly_rate?: number | null;
  siret?: string | null;
  siren?: string | null;
  legal_name?: string | null;
  payment_online_enabled?: boolean;
  deposit_rate?: number;
  phone?: string | null;
  website_url?: string | null;
  photo_url?: string | null;
  source_url?: string | null;
  source_label?: string | null;
  listing_status?: "PUBLIC_REFERENCE" | "CLAIMED_PARTNER" | "PENDING_VERIFICATION" | "DEMO_HIDDEN" | string;
  booking_enabled?: boolean;
  is_public?: boolean;
  source_verified_at?: string | null;
};

export type Slot = {
  id: number;
  starts_at: string;
  ends_at: string;
};

export function normalize(value: string): string {
  return value.trim().toLocaleLowerCase("fr-FR");
}

export function filterGarages(
  garages: Garage[],
  query: string,
  city: string,
): Garage[] {
  const normalizedQuery = normalize(query);
  const normalizedCity = normalize(city);

  return garages.filter((garage) => {
    const text = normalize(`${garage.name} ${garage.description}`);
    const queryMatches = !normalizedQuery || text.includes(normalizedQuery);
    const cityValue = normalize(garage.city);
    const postalValue = normalize(garage.postal_code || "");
    const cityMatches =
      !normalizedCity ||
      cityValue.includes(normalizedCity) ||
      normalizedCity.includes(cityValue) ||
      (!!postalValue && normalizedCity.includes(postalValue));
    return queryMatches && cityMatches;
  });
}

export function formatPrice(value: number): string {
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: "EUR",
  }).format(value);
}

export function depositFor(price: number, rate = 0.2): number {
  return Math.round(price * rate * 100) / 100;
}

export function isStrongPassword(value: string): boolean {
  if (value.length < 12) {
    return false;
  }

  const rules = [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/];
  return rules.filter((rule) => rule.test(value)).length >= 3;
}

export function formatFrenchPlate(value: string): string {
  const clean = value.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 7);
  const first = clean.slice(0, 2);
  const digits = clean.slice(2, 5);
  const last = clean.slice(5, 7);
  return [first, digits, last].filter(Boolean).join("-");
}

export function isFrenchPlate(value: string): boolean {
  return /^[A-Z]{2}-\d{3}-[A-Z]{2}$/.test(value);
}

export function safeText(value: unknown): string {
  if (typeof value !== "string") {
    return "";
  }
  return value.replace(/[<>]/g, "");
}

export function sortSlots(slots: Slot[]): Slot[] {
  return [...slots].sort(
    (a, b) =>
      new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime(),
  );
}
