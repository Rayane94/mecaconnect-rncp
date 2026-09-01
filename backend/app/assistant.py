from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable

from . import models


@dataclass(frozen=True)
class IssueRule:
    key: str
    label: str
    keywords: tuple[str, ...]
    specialties: tuple[str, ...]
    service_terms: tuple[str, ...]
    min_cost: int
    max_cost: int
    urgency: str
    causes: tuple[str, ...]
    first_checks: tuple[str, ...]


ISSUE_RULES: tuple[IssueRule, ...] = (
    IssueRule(
        key="brakes",
        label="Freinage",
        keywords=("frein", "freine", "plaquette", "disque", "grince", "grincement", "pedale molle", "vibration frein"),
        specialties=("freinage",),
        service_terms=("frein", "plaquette", "disque"),
        min_cost=120,
        max_cost=750,
        urgency="HIGH",
        causes=("plaquettes usées", "disques marqués ou voilés", "étrier grippé", "liquide de frein à contrôler"),
        first_checks=("éviter les longs trajets si le freinage est dégradé", "faire contrôler l'épaisseur des plaquettes et l'état des disques"),
    ),
    IssueRule(
        key="battery",
        label="Batterie / démarrage",
        keywords=("batterie", "ne demarre", "ne démarre", "demarre mal", "démarre mal", "clic", "plus de courant", "voyants faibles"),
        specialties=("electricite", "diagnostic"),
        service_terms=("batterie", "diagnostic"),
        min_cost=90,
        max_cost=450,
        urgency="MEDIUM",
        causes=("batterie déchargée ou en fin de vie", "alternateur", "démarreur", "connexion électrique ou masse"),
        first_checks=("contrôler la tension de batterie", "vérifier si les voyants baissent fortement au démarrage"),
    ),
    IssueRule(
        key="engine_warning",
        label="Voyant moteur / diagnostic",
        keywords=("voyant moteur", "check engine", "voyant orange", "perte puissance", "mode degrade", "mode dégradé", "a-coup", "accoup", "raté moteur"),
        specialties=("diagnostic", "moteur", "injection"),
        service_terms=("diagnostic", "moteur", "injection"),
        min_cost=70,
        max_cost=900,
        urgency="MEDIUM",
        causes=("capteur moteur", "allumage ou injection", "admission d'air", "système antipollution"),
        first_checks=("effectuer une lecture des codes défaut", "noter si le voyant est fixe ou clignotant"),
    ),
    IssueRule(
        key="clutch",
        label="Embrayage",
        keywords=("embrayage", "patine", "pedale embrayage", "pédale embrayage", "vitesse passe mal", "vitesses passent mal"),
        specialties=("embrayage", "transmission"),
        service_terms=("embrayage",),
        min_cost=650,
        max_cost=1800,
        urgency="MEDIUM",
        causes=("disque d'embrayage usé", "butée", "volant moteur", "commande hydraulique"),
        first_checks=("éviter de faire patiner l'embrayage", "faire confirmer l'usure avant remplacement"),
    ),
    IssueRule(
        key="gearbox",
        label="Boîte de vitesses / transmission",
        keywords=("boite", "boîte", "bva", "boite auto", "boîte auto", "rapport", "vitesse saute", "vitesse craque", "transmission"),
        specialties=("transmission", "diagnostic"),
        service_terms=("boîte", "boite", "transmission", "diagnostic"),
        min_cost=180,
        max_cost=2800,
        urgency="HIGH",
        causes=("niveau ou qualité d'huile de boîte", "capteur ou électrovanne", "embrayage interne", "organe mécanique de transmission"),
        first_checks=("éviter de forcer les rapports", "faire contrôler rapidement si les rapports sautent ou si la voiture n'avance plus normalement"),
    ),
    IssueRule(
        key="tyres",
        label="Pneumatiques / géométrie",
        keywords=("pneu", "pneus", "crevaison", "hernie", "pression", "vibre volant", "tire a droite", "tire à droite", "geometrie", "géométrie"),
        specialties=("pneus", "geometrie"),
        service_terms=("pneu", "géométrie", "geometrie"),
        min_cost=60,
        max_cost=900,
        urgency="HIGH",
        causes=("pression incorrecte", "pneu endommagé ou usé", "équilibrage", "géométrie du train roulant"),
        first_checks=("contrôler immédiatement l'état visuel et la pression", "ne pas rouler avec une hernie ou une toile apparente"),
    ),
    IssueRule(
        key="ac",
        label="Climatisation",
        keywords=("clim", "climatisation", "air chaud", "ne refroidit", "compresseur clim", "odeur clim"),
        specialties=("climatisation",),
        service_terms=("clim", "climatisation"),
        min_cost=80,
        max_cost=1000,
        urgency="LOW",
        causes=("charge de fluide insuffisante", "fuite", "compresseur", "capteur ou commande de climatisation"),
        first_checks=("vérifier si le compresseur s'enclenche", "contrôler les pressions du circuit avant toute recharge"),
    ),
    IssueRule(
        key="suspension",
        label="Suspension / train roulant",
        keywords=("amortisseur", "suspension", "claquement", "clac", "biellette", "rotule", "silent bloc", "tenue de route"),
        specialties=("suspension", "geometrie"),
        service_terms=("amortisseur", "suspension", "rotule", "biellette"),
        min_cost=150,
        max_cost=1200,
        urgency="MEDIUM",
        causes=("biellette de barre stabilisatrice", "silentbloc", "rotule", "amortisseur ou coupelle"),
        first_checks=("faire contrôler le jeu du train roulant", "éviter les vitesses élevées si la tenue de route est anormale"),
    ),
    IssueRule(
        key="overheating",
        label="Surchauffe / refroidissement",
        keywords=("chauffe", "surchauffe", "temperature moteur", "température moteur", "liquide refroidissement", "fumee blanche", "fumée blanche"),
        specialties=("moteur", "refroidissement", "diagnostic"),
        service_terms=("refroidissement", "diagnostic", "moteur"),
        min_cost=120,
        max_cost=2200,
        urgency="CRITICAL",
        causes=("niveau ou fuite de liquide de refroidissement", "thermostat", "pompe à eau", "radiateur", "joint de culasse à exclure"),
        first_checks=("arrêter le moteur si la température passe en zone rouge", "ne jamais ouvrir le vase d'expansion moteur chaud"),
    ),
    IssueRule(
        key="timing",
        label="Distribution",
        keywords=("distribution", "courroie", "chaine distribution", "chaîne distribution", "bruit chaine", "bruit chaîne"),
        specialties=("distribution", "moteur"),
        service_terms=("distribution", "courroie", "chaîne", "chaine"),
        min_cost=500,
        max_cost=1700,
        urgency="HIGH",
        causes=("échéance de courroie atteinte", "galet ou tendeur", "chaîne détendue", "pompe à eau selon montage"),
        first_checks=("vérifier l'historique d'entretien", "faire contrôler rapidement tout bruit métallique inhabituel lié à la distribution"),
    ),
    IssueRule(
        key="diesel",
        label="Diesel / FAP / injection",
        keywords=("fap", "diesel", "injecteur", "injection", "adblue", "fumee noire", "fumée noire", "regeneration", "régénération"),
        specialties=("diesel", "fap", "injection", "diagnostic"),
        service_terms=("fap", "inject", "diagnostic", "diesel"),
        min_cost=90,
        max_cost=2000,
        urgency="MEDIUM",
        causes=("FAP chargé", "capteur de pression ou température", "injecteur", "vanne EGR", "circuit AdBlue selon véhicule"),
        first_checks=("lire les codes défaut avant remplacement de pièces", "contrôler la charge du FAP et les valeurs de capteurs"),
    ),
    IssueRule(
        key="exhaust",
        label="Échappement / antipollution",
        keywords=("echappement", "échappement", "catalyseur", "bruit pot", "odeur echappement", "odeur échappement"),
        specialties=("echappement", "diagnostic"),
        service_terms=("échappement", "echappement", "catalyseur", "diagnostic"),
        min_cost=120,
        max_cost=1500,
        urgency="MEDIUM",
        causes=("fuite sur la ligne", "silencieux", "catalyseur", "sonde lambda"),
        first_checks=("faire rechercher la fuite sur pont", "éviter un long trajet si des gaz d'échappement entrent dans l'habitacle"),
    ),
    IssueRule(
        key="service",
        label="Entretien courant",
        keywords=("vidange", "revision", "révision", "entretien", "filtre", "bougie", "bougies"),
        specialties=("entretien",),
        service_terms=("vidange", "révision", "revision", "filtre", "bougie"),
        min_cost=90,
        max_cost=550,
        urgency="LOW",
        causes=("entretien périodique arrivé à échéance", "consommables à remplacer selon kilométrage et préconisations"),
        first_checks=("consulter l'historique et le kilométrage", "regrouper les opérations arrivant à échéance pour éviter plusieurs immobilisations"),
    ),
    IssueRule(
        key="electric_hybrid",
        label="Électrique / hybride",
        keywords=("hybride", "electrique", "électrique", "batterie haute tension", "recharge", "systeme hybride", "système hybride"),
        specialties=("hybride", "electrique", "diagnostic"),
        service_terms=("hybride", "électrique", "electrique", "diagnostic"),
        min_cost=80,
        max_cost=1800,
        urgency="HIGH",
        causes=("batterie 12 V", "défaut de charge", "capteur ou électronique de puissance", "système haute tension à diagnostiquer"),
        first_checks=("ne pas intervenir soi-même sur le circuit haute tension", "faire contrôler le véhicule par un atelier habilité"),
    ),
)

PREMIUM_BRANDS = {
    "mercedes", "bmw", "audi", "porsche", "land rover", "jaguar", "lexus", "tesla", "volvo",
}

URGENCY_TEXT = {
    "LOW": ("Faible", "Vous pouvez généralement planifier un rendez-vous, sauf aggravation."),
    "MEDIUM": ("À contrôler", "Prenez rendez-vous prochainement et surveillez l'évolution des symptômes."),
    "HIGH": ("Rapide", "Évitez de prolonger l'utilisation sans contrôle, surtout si le comportement du véhicule change."),
    "CRITICAL": ("Urgent", "Immobilisez le véhicule si le symptôme persiste ou compromet la sécurité. Un dépannage peut être préférable."),
}


# MecaBot reste volontairement borné au domaine automobile.
# Ces listes servent de garde-fous avant toute tentative d'orientation mécanique.
AUTOMOTIVE_CONTEXT_TERMS = {
    "voiture", "vehicule", "auto", "moteur", "frein", "freins", "pneu", "pneus",
    "embrayage", "boite", "batterie", "demarrage", "voyant", "injecteur", "fap",
    "suspension", "amortisseur", "direction", "volant", "clim", "radiateur",
    "liquide", "huile", "roue", "echappement", "alternateur", "demarreur",
}

FOLLOW_UP_TERMS = {
    "depuis", "hier", "aujourd'hui", "chaud", "froid", "matin", "soir", "acceleration",
    "freinage", "demarrage", "tourne", "virage", "ralenti", "vitesse", "oui", "non",
}

OFF_TOPIC_PATTERNS = (
    r"\bmeteo\b", r"\bpolitique\b", r"\bre(cette|cette de)\b", r"\bcrepe(s)?\b",
    r"\bfootball\b", r"\bmatch\b", r"\bbitcoin\b", r"\btradu(is|ction)\b",
    r"\bdevoir\b", r"\bcode python\b", r"\bjavascript\b", r"\bemail\b",
)

PROMPT_INJECTION_PATTERNS = (
    r"ignore (les |toutes les )?(instructions|regles|règles)",
    r"system prompt", r"prompt systeme", r"jailbreak", r"developer message",
    r"tu es chatgpt", r"revele .*prompt", r"affiche .*instructions",
    r"reponds? (toujours|uniquement) ",
)

UNSAFE_TAMPERING_PATTERNS = (
    r"desactiv(e|er).*airbag", r"desactiv(e|er).*abs", r"desactiv(e|er).*frein",
    r"supprim(e|er).*fap", r"fap off", r"egr off", r"trafi(que|quer).*compteur",
    r"baisser .*kilometr", r"modifier .*kilometr", r"contourn(e|er).*securite",
)

CRITICAL_RED_FLAGS = (
    (r"(plus|pas|perdu).*frein|frein.*(plus|pas).*fonction", "Perte de freinage", "N'utilisez pas le véhicule. Immobilisez-le et faites intervenir un dépanneur ou un professionnel."),
    (r"direction.*(bloqu|dure|perdu)|volant.*bloqu", "Défaut de direction", "Arrêtez-vous en sécurité et n'utilisez plus le véhicule tant que la direction n'a pas été contrôlée."),
    (r"feu|flamme|fumee.*capot|odeur.*essence.*fort|fuite.*carburant", "Risque incendie / carburant", "Coupez le moteur, éloignez-vous du véhicule et contactez les secours ou l'assistance si nécessaire."),
    (r"temperature.*rouge|surchauffe.*rouge|moteur.*bouill", "Surchauffe sévère", "Coupez le moteur dès que vous pouvez le faire en sécurité. N'ouvrez pas le circuit de refroidissement à chaud."),
    (r"pression.*huile.*rouge|voyant.*huile.*rouge", "Pression d'huile critique", "Coupez le moteur et ne redémarrez pas avant contrôle afin d'éviter des dommages moteur importants."),
    (r"pneu.*eclat|pneu.*éclat|roue.*desserr|roue.*bouge", "Risque roue / pneumatique", "N'utilisez plus le véhicule avant contrôle du pneumatique et du serrage de la roue."),
)


def _contains_any_pattern(clean: str, patterns: Iterable[str]) -> bool:
    return any(re.search(pattern, clean) for pattern in patterns)


def _looks_like_gibberish(message: str) -> bool:
    raw = message.strip().lower()
    if re.search(r"(.)\1{7,}", raw):
        return True
    words = re.findall(r"[a-zA-ZÀ-ÿ]+", raw)
    if not words:
        return True
    joined = "".join(words)
    if len(joined) >= 12:
        vowels = sum(ch in "aeiouyàâäéèêëîïôöùûü" for ch in joined)
        # Une longue chaîne sans presque aucune voyelle ressemble davantage à du bruit qu'à une phrase.
        if vowels / len(joined) < 0.12:
            return True
    if len(words) == 1 and len(words[0]) >= 10 and not any(term in normalize(raw) for term in AUTOMOTIVE_CONTEXT_TERMS):
        common = {"bonjour", "bonsoir", "merci", "probleme", "voiture", "vehicule", "automobile"}
        if normalize(words[0]) not in common:
            return True
    return False


def _automotive_context(clean: str) -> bool:
    tokens = set(clean.split())
    return bool(tokens & AUTOMOTIVE_CONTEXT_TERMS) or bool(analyse_message(clean))


def _critical_safety_alert(clean: str) -> tuple[str, str] | None:
    for pattern, label, advice in CRITICAL_RED_FLAGS:
        if re.search(pattern, clean):
            return label, advice
    return None


def classify_input(message: str) -> tuple[str, str | None]:
    """Classe le message avant diagnostic afin d'éviter les réponses hors sujet ou trop affirmatives."""
    clean = normalize(message)
    if _contains_any_pattern(clean, PROMPT_INJECTION_PATTERNS):
        return "out_of_scope", "Je peux uniquement analyser des symptômes automobiles et orienter vers un garage adapté."
    if _contains_any_pattern(clean, UNSAFE_TAMPERING_PATTERNS):
        return "unsafe_request", "Je ne peux pas expliquer comment neutraliser un équipement de sécurité, antipollution ou falsifier un véhicule. Je peux en revanche vous orienter vers une réparation conforme."
    if _looks_like_gibberish(message):
        return "invalid_input", "Je n'ai pas compris la description. Reformulez avec un symptôme concret : bruit, voyant, vibration, fuite, démarrage, freinage ou perte de puissance."
    if _contains_any_pattern(clean, OFF_TOPIC_PATTERNS) and not _automotive_context(clean):
        return "out_of_scope", "MecaBot est spécialisé dans l'orientation automobile. Décrivez un problème rencontré sur votre véhicule."
    if not _automotive_context(clean):
        return "needs_context", None
    return "automotive", None


def _base_non_diagnostic_response(kind: str, summary: str, advice: str | None = None) -> dict:
    return {
        "response_type": kind,
        "summary": summary,
        "confidence": 0.0,
        "follow_up_question": advice,
        "urgency": {"level": "LOW", "label": "Information", "advice": "Aucune conclusion mécanique n'est tirée de ce message."},
        "estimated_cost": None,
        "possible_causes": [],
        "recommended_actions": [],
        "specialties": [],
        "garages": [],
        "disclaimer": "MecaBot reste limité à l'orientation automobile et ne remplace pas le diagnostic d'un professionnel.",
    }


def normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9 ]+", " ", normalized)


def split_values(value: str | None) -> set[str]:
    if not value:
        return set()
    return {normalize(item).strip() for item in value.split(",") if item.strip()}


def analyse_message(message: str) -> list[tuple[IssueRule, float]]:
    clean = normalize(message)
    tokens = set(clean.split())
    scored: list[tuple[IssueRule, float]] = []

    for rule in ISSUE_RULES:
        score = 0.0
        for keyword in rule.keywords:
            normalized_keyword = normalize(keyword)
            if normalized_keyword in clean:
                score += 2.3 if " " in normalized_keyword else 1.5
            elif normalized_keyword in tokens:
                score += 1.0

        if score:
            scored.append((rule, score))

    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:3]


def prepare_conversation_message(message: str, history: list[str] | None = None) -> str:
    """Réutilise un ancien symptôme seulement pour une vraie réponse de suivi courte.

    Un nouveau message automobile remplace le contexte précédent afin d'éviter qu'un
    ancien problème continue à influencer artificiellement les réponses.
    """
    history = history or []
    kind, _ = classify_input(message)
    if kind in {"out_of_scope", "unsafe_request", "invalid_input"}:
        return message
    if analyse_message(message):
        return message

    clean = normalize(message)
    tokens = set(clean.split())
    looks_like_follow_up = len(tokens) <= 12 or bool(tokens & FOLLOW_UP_TERMS)
    if not looks_like_follow_up:
        return message

    for previous in reversed(history[-4:]):
        previous_kind, _ = classify_input(previous)
        if previous_kind == "automotive" and analyse_message(previous):
            return f"{previous} {message}"
    return message


def adjusted_estimate(rule: IssueRule, make: str | None, year: int | None) -> tuple[int, int]:
    factor = 1.0
    if make and normalize(make) in PREMIUM_BRANDS:
        factor += 0.15
    if year and year <= 2012:
        factor += 0.08

    low = int(round(rule.min_cost * factor / 10.0) * 10)
    high = int(round(rule.max_cost * factor / 10.0) * 10)
    return low, high


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def matching_service(garage: models.Garage, terms: Iterable[str]):
    normalized_terms = [normalize(term) for term in terms]
    for service in garage.services:
        text = normalize(f"{service.name} {service.description or ''}")
        if any(term in text for term in normalized_terms):
            return service
    return None


def garage_score(
    garage: models.Garage,
    rule: IssueRule,
    make: str | None,
    user_lat: float | None,
    user_lng: float | None,
) -> tuple[float, float | None, list[str]]:
    garage_specialties = split_values(garage.specialties)
    garage_brands = split_values(garage.brands)
    requested_specialties = {normalize(item) for item in rule.specialties}

    score = 0.0
    reasons: list[str] = []

    overlap = garage_specialties & requested_specialties
    if overlap:
        score += 35 + min(9, len(overlap) * 3)
        reasons.append("spécialiste " + ", ".join(sorted(overlap)))

    if make:
        clean_make = normalize(make)
        if clean_make in garage_brands:
            score += 12
            reasons.append(f"spécialisation déclarée pour {make}")
        elif "multimarque" in garage_brands:
            score += 6
            reasons.append(f"atelier multimarque compatible avec {make}")

    score += min(18, max(0, garage.rating) * 3.6)
    if garage.verified:
        score += 3

    distance = None
    if user_lat is not None and user_lng is not None and garage.lat is not None and garage.lng is not None:
        distance = distance_km(user_lat, user_lng, garage.lat, garage.lng)
        proximity = max(0, 18 - min(18, distance * 0.9))
        score += proximity
        reasons.append(f"à environ {distance:.1f} km")

    return score, distance, reasons


def recommend_garages(
    garages: list[models.Garage],
    rule: IssueRule,
    make: str | None,
    user_lat: float | None,
    user_lng: float | None,
    location: str | None,
    limit: int = 5,
) -> list[dict]:
    ranked: list[tuple[float, dict]] = []
    clean_location = normalize(location or "")

    for garage in garages:
        garage_specialties = split_values(garage.specialties)
        requested_specialties = {normalize(item) for item in rule.specialties}
        specialty_match = bool(garage_specialties & requested_specialties)
        service = matching_service(garage, rule.service_terms)

        # Un garage n'est jamais proposé uniquement parce qu'il est bien noté.
        # Il doit avoir au moins une spécialité ou une prestation réellement liée au problème détecté.
        if not specialty_match and not service:
            continue

        score, distance, reasons = garage_score(garage, rule, make, user_lat, user_lng)

        if clean_location and clean_location in normalize(f"{garage.city} {garage.department or ''}"):
            score += 6
            reasons.append("dans votre zone de recherche")

        if service:
            score += 8
            reasons.append(f"prestation correspondante : {service.name}")

        ranked.append(
            (
                score,
                {
                    "id": garage.id,
                    "name": garage.name,
                    "city": garage.city,
                    "department": garage.department,
                    "address": garage.address,
                    "rating": garage.rating,
                    "verified": garage.verified,
                    "lat": garage.lat,
                    "lng": garage.lng,
                    "specialties": sorted(split_values(garage.specialties)),
                    "score": round(min(99, score), 1),
                    "distance_km": round(distance, 1) if distance is not None else None,
                    "reason": "; ".join(reasons[:3]) or "bon niveau général pour ce type d'intervention",
                    "service_hint": (
                        {
                            "id": service.id,
                            "name": service.name,
                            "price": service.price,
                            "duration_minutes": service.duration_minutes,
                        }
                        if service
                        else None
                    ),
                },
            )
        )

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in ranked[:limit]]


def build_diagnosis(
    message: str,
    garages: list[models.Garage],
    make: str | None = None,
    model: str | None = None,
    year: int | None = None,
    location: str | None = None,
    user_lat: float | None = None,
    user_lng: float | None = None,
) -> dict:
    current_message = message.strip()
    kind, boundary_message = classify_input(current_message)
    clean = normalize(current_message)

    if kind in {"out_of_scope", "unsafe_request", "invalid_input"}:
        return _base_non_diagnostic_response(kind, boundary_message or "Je ne peux pas analyser cette demande.")

    safety_alert = _critical_safety_alert(clean)
    if safety_alert:
        label, advice = safety_alert
        return {
            "response_type": "safety_stop",
            "summary": f"Le message décrit un risque potentiellement critique : {label.lower()}.",
            "confidence": 0.99,
            "follow_up_question": None,
            "urgency": {"level": "CRITICAL", "label": "Immobilisation recommandée", "advice": advice},
            "estimated_cost": None,
            "possible_causes": [],
            "recommended_actions": [advice, "privilégier l'assistance ou le remorquage plutôt qu'un trajet jusqu'au garage"],
            "specialties": ["diagnostic"],
            "garages": [],
            "disclaimer": "Priorité à la sécurité : MecaBot ne tente pas d'estimer une réparation lorsqu'un risque immédiat est détecté.",
        }

    matches = analyse_message(current_message)

    if not matches:
        if kind == "needs_context":
            return _base_non_diagnostic_response(
                "needs_context",
                "Je peux vous aider pour un problème automobile, mais votre message ne décrit pas encore de symptôme exploitable.",
                "Indiquez ce que fait la voiture : bruit, voyant, vibration, fuite, difficulté à démarrer, freinage, fumée ou perte de puissance, et à quel moment le symptôme apparaît.",
            )
        return {
            "response_type": "clarification",
            "summary": "Le sujet semble bien automobile, mais je n'ai pas assez d'éléments fiables pour proposer une panne ou un prix.",
            "confidence": 0.2,
            "follow_up_question": (
                "Quel est le symptôme principal et quand apparaît-il ? Par exemple : au démarrage, à chaud, "
                "au freinage, en accélérant, en tournant ou à une certaine vitesse."
            ),
            "urgency": {"level": "MEDIUM", "label": "À préciser", "advice": "En cas de voyant rouge ou de comportement dangereux, n'utilisez pas le véhicule avant contrôle."},
            "estimated_cost": None,
            "possible_causes": [],
            "recommended_actions": ["décrire le symptôme plus précisément", "indiquer la marque, le modèle et l'année si possible"],
            "specialties": ["diagnostic"],
            "garages": [],
            "disclaimer": "Aucune panne ni estimation n'est inventée lorsque les informations sont insuffisantes.",
        }

    rule, score = matches[0]
    second_score = matches[1][1] if len(matches) > 1 else 0.0
    max_score = max(1.0, sum(item[1] for item in matches))
    confidence = min(0.94, 0.48 + (score / max_score) * 0.42)

    # Un seul mot très général (ex. « frein », « batterie ») ne suffit pas pour chiffrer des travaux.
    if score < 2.3:
        return {
            "response_type": "clarification",
            "summary": f"Le message semble concerner {rule.label.lower()}, mais le symptôme est trop vague pour estimer des travaux sérieusement.",
            "confidence": round(min(confidence, 0.55), 2),
            "follow_up_question": "Que se passe-t-il exactement, depuis quand, et dans quelles conditions le problème apparaît-il ?",
            "urgency": {"level": rule.urgency, "label": "À préciser", "advice": URGENCY_TEXT[rule.urgency][1]},
            "estimated_cost": None,
            "possible_causes": [],
            "recommended_actions": list(rule.first_checks[:1]),
            "specialties": list(rule.specialties),
            "garages": [],
            "disclaimer": "MecaBot préfère poser une question supplémentaire plutôt que d'inventer une panne ou un devis.",
        }

    # Deux familles presque à égalité signifient que le récit est ambigu. On oriente, mais on ne chiffre pas encore.
    ambiguous = second_score >= score * 0.55
    secondary = [item[0].label for item in matches[1:] if item[1] >= score * 0.55]

    vehicle_text = ""
    if make or model or year:
        vehicle_text = " pour " + " ".join(str(item) for item in (make, model, year) if item)

    summary = f"Le symptôme évoque en priorité un problème de {rule.label.lower()}{vehicle_text}."
    if secondary:
        summary += " Une piste secondaire concerne aussi : " + ", ".join(secondary) + "."

    urgency_label, urgency_advice = URGENCY_TEXT[rule.urgency]

    if ambiguous:
        return {
            "response_type": "clarification",
            "summary": summary + " Les indices sont trop proches pour privilégier une seule famille de panne.",
            "confidence": round(min(confidence, 0.66), 2),
            "follow_up_question": "Quel symptôme est apparu en premier et lequel est le plus marqué ? Précisez aussi s'il apparaît à froid, à chaud, au freinage ou à l'accélération.",
            "urgency": {"level": rule.urgency, "label": urgency_label, "advice": urgency_advice},
            "estimated_cost": None,
            "possible_causes": [],
            "recommended_actions": list(rule.first_checks),
            "specialties": list(dict.fromkeys([*rule.specialties, *[s for item, _ in matches[1:] for s in item.specialties]])),
            "garages": [],
            "disclaimer": "L'estimation est volontairement suspendue tant que le symptôme principal n'est pas mieux identifié.",
        }

    low, high = adjusted_estimate(rule, make, year)
    follow_up = None
    if confidence < 0.72:
        follow_up = "Depuis quand le problème apparaît-il, et est-il présent à froid, à chaud, au freinage ou à l'accélération ?"

    recommendations = recommend_garages(garages, rule, make, user_lat, user_lng, location)

    return {
        "response_type": "diagnosis",
        "summary": summary,
        "confidence": round(confidence, 2),
        "follow_up_question": follow_up,
        "urgency": {"level": rule.urgency, "label": urgency_label, "advice": urgency_advice},
        "estimated_cost": {
            "min": low,
            "max": high,
            "label": f"environ {low} à {high} €",
            "basis": "fourchette indicative par famille d'intervention ; elle ne constitue pas un devis et peut varier après diagnostic, selon les pièces et le véhicule",
        },
        "possible_causes": list(rule.causes),
        "recommended_actions": list(rule.first_checks),
        "specialties": list(rule.specialties),
        "garages": recommendations,
        "disclaimer": "Pré-diagnostic indicatif : aucune panne n'est considérée comme certaine sans examen du véhicule par un professionnel.",
    }

