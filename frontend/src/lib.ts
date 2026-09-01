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
    const cityMatches = !normalizedCity || normalize(garage.city) === normalizedCity;
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
