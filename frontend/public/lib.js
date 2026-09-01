export function normalize(value) {
    return value.trim().toLocaleLowerCase("fr-FR");
}
export function filterGarages(garages, query, city) {
    const normalizedQuery = normalize(query);
    const normalizedCity = normalize(city);
    return garages.filter((garage) => {
        const text = normalize(`${garage.name} ${garage.description}`);
        const queryMatches = !normalizedQuery || text.includes(normalizedQuery);
        const cityMatches = !normalizedCity || normalize(garage.city) === normalizedCity;
        return queryMatches && cityMatches;
    });
}
export function formatPrice(value) {
    return new Intl.NumberFormat("fr-FR", {
        style: "currency",
        currency: "EUR",
    }).format(value);
}
export function depositFor(price, rate = 0.2) {
    return Math.round(price * rate * 100) / 100;
}
export function isStrongPassword(value) {
    if (value.length < 12) {
        return false;
    }
    const rules = [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/];
    return rules.filter((rule) => rule.test(value)).length >= 3;
}
export function safeText(value) {
    if (typeof value !== "string") {
        return "";
    }
    return value.replace(/[<>]/g, "");
}
export function sortSlots(slots) {
    return [...slots].sort((a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime());
}
