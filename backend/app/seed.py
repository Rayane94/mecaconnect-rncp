from datetime import datetime, timedelta, timezone
import os
import re
import unicodedata

import httpx
from sqlalchemy import select

from .database import Base, SessionLocal, engine, ensure_schema_compatibility
from .models import Availability, Garage, Service, User
from .security import hash_password


# Catalogue public : uniquement des établissements réels et actifs vérifiés à partir
# de sources publiques (SIRENE/RNE) et, pour les prestations/photos, des sites
# officiels des garages/réseaux. Une fiche référencée n'implique aucun partenariat.
REAL_GARAGES = [
    {
        "name": "Midas Paris 04 - Célestins",
        "slug": "midas-paris-04-celestins",
        "legal_name": "DOM AUTO",
        "siret": "40308888300018",
        "siren": "403088883",
        "city": "Paris",
        "department": "75",
        "postal_code": "75004",
        "address": "24-26 quai des Célestins, 75004 Paris",
        "phone": "01 42 72 39 95",
        "rating": 4.6,
        "specialties": "entretien,freinage,diagnostic,pneus,climatisation,distribution,embrayage,electrique",
        "brands": "multimarque",
        "website_url": "https://www.midas.fr/centres-auto-midas/ile-de-france/paris/paris-04/paris-04-celestins_1289",
        "photo_url": "https://media.midas.fr/shops/team/Centres/1289_Paris04-Celestins.jpg",
        "source_url": "https://www.midas.fr/centres-auto-midas/ile-de-france/paris/paris-04/paris-04-celestins_1289",
        "services": ["Bilan sécurité", "Climatisation", "Courroie de distribution", "Transmission et embrayage", "Révision", "Entretien véhicule électrique"],
    },
    {
        "name": "Midas Montreuil",
        "slug": "midas-montreuil",
        "legal_name": "SERVICES AUTOS",
        "siret": "83209991500023",
        "siren": "832099915",
        "city": "Montreuil",
        "department": "93",
        "postal_code": "93100",
        "address": "4-6 avenue Gabriel Péri, 93100 Montreuil",
        "phone": "01 48 59 04 00",
        "rating": 4.5,
        "specialties": "entretien,freinage,diagnostic,pneus,climatisation,distribution,embrayage,electrique",
        "brands": "multimarque",
        "website_url": "https://www.midas.fr/centres-auto-midas/ile-de-france/seine-saint-denis/bobigny/montreuil_1031",
        "photo_url": "https://media.midas.fr/shops/team/Centres/1031_%2BMontreuil.jpg",
        "source_url": "https://www.midas.fr/centres-auto-midas/ile-de-france/seine-saint-denis/bobigny/montreuil_1031",
        "services": ["Bilan sécurité", "Climatisation", "Courroie de distribution", "Transmission et embrayage", "Révision", "Entretien véhicule électrique"],
    },
    {
        "name": "Midas Meaux",
        "slug": "midas-meaux",
        "legal_name": "AUTO-SERVICES MEAUX",
        "siret": "85346792600012",
        "siren": "853467926",
        "city": "Meaux",
        "department": "77",
        "postal_code": "77100",
        "address": "36 rue François de Tessan, 77100 Meaux",
        "phone": "01 60 09 80 91",
        "rating": 4.4,
        "specialties": "entretien,freinage,diagnostic,pneus,climatisation,distribution,embrayage,electrique",
        "brands": "multimarque",
        "website_url": "https://www.midas.fr/centres-auto-midas/ile-de-france/seine-et-marne/meaux/meaux_1168",
        "photo_url": "https://media.midas.fr/shops/team/Centres/1168_%2BMeaux.jpg",
        "source_url": "https://www.midas.fr/centres-auto-midas/ile-de-france/seine-et-marne/meaux/meaux_1168",
        "services": ["Bilan sécurité", "Climatisation", "Courroie de distribution", "Transmission et embrayage", "Révision", "Entretien véhicule électrique"],
    },
    {
        "name": "Midas Chelles",
        "slug": "midas-chelles",
        "legal_name": "JNL SERVICES",
        "siret": "90814361300028",
        "siren": "908143613",
        "city": "Chelles",
        "department": "77",
        "postal_code": "77500",
        "address": "105 avenue du Gendarme Castermant, 77500 Chelles",
        "phone": "01 64 26 65 67",
        "rating": 4.5,
        "specialties": "entretien,freinage,diagnostic,pneus,climatisation,distribution,embrayage,electrique",
        "brands": "multimarque",
        "website_url": "https://www.midas.fr/centres-auto-midas/ile-de-france/seine-et-marne/torcy/chelles_1340",
        "photo_url": "https://media.midas.fr/shops/team/Centres/1340_Chelles.jpg",
        "source_url": "https://www.midas.fr/centres-auto-midas/ile-de-france/seine-et-marne/torcy/chelles_1340",
        "services": ["Bilan sécurité", "Climatisation", "Courroie de distribution", "Transmission et embrayage", "Révision", "Entretien véhicule électrique", "MIDAS Glass"],
    },
    {
        "name": "Midas Versailles",
        "slug": "midas-versailles",
        "legal_name": "SAUSSEREAU MARTINS SOARES AUTOMOBILES",
        "siret": "53008423500023",
        "siren": "530084235",
        "city": "Jouy-en-Josas",
        "department": "78",
        "postal_code": "78350",
        "address": "48 rue du Pont Colbert, 78350 Jouy-en-Josas",
        "phone": "01 39 51 27 72",
        "rating": 4.7,
        "specialties": "entretien,freinage,diagnostic,pneus,climatisation,distribution,embrayage,electrique",
        "brands": "multimarque",
        "website_url": "https://www.midas.fr/centres-auto-midas/ile-de-france/yvelines/versailles/versailles_1061",
        "photo_url": "https://media.midas.fr/shops/team/Centres/1061_%2BVersailles.jpg",
        "source_url": "https://www.midas.fr/centres-auto-midas/ile-de-france/yvelines/versailles/versailles_1061",
        "services": ["Bilan sécurité", "Climatisation", "Courroie de distribution", "Transmission et embrayage", "Révision", "Entretien véhicule électrique"],
    },
    {
        "name": "Midas Deuil-la-Barre",
        "slug": "midas-deuil-la-barre",
        "legal_name": "3J3M",
        "siret": "10573498200017",
        "siren": "105734982",
        "city": "Deuil-la-Barre",
        "department": "95",
        "postal_code": "95170",
        "address": "18 avenue de la Division Leclerc, 95170 Deuil-la-Barre",
        "phone": "01 84 74 59 09",
        "rating": 4.9,
        "specialties": "entretien,freinage,diagnostic,climatisation,distribution,embrayage,electrique",
        "brands": "multimarque",
        "website_url": "https://www.midas.fr/centres-auto-midas/ile-de-france/val-d-oise/sarcelles/deuil-la-barre_1716",
        "photo_url": None,
        "source_url": "https://www.midas.fr/centres-auto-midas/ile-de-france/val-d-oise/sarcelles/deuil-la-barre_1716",
        "services": ["Bilan sécurité", "Climatisation", "Courroie de distribution", "Transmission et embrayage", "Révision", "Entretien véhicule électrique"],
    },
    {
        "name": "Midas Issy-les-Moulineaux",
        "slug": "midas-issy-les-moulineaux",
        "legal_name": "AUTO ISSY 92",
        "siret": "82858931700027",
        "siren": "828589317",
        "city": "Issy-les-Moulineaux",
        "department": "92",
        "postal_code": "92130",
        "address": "61 boulevard Rodin, 92130 Issy-les-Moulineaux",
        "phone": "01 85 74 08 05",
        "rating": 4.3,
        "specialties": "entretien,freinage,diagnostic,pneus,climatisation,distribution,embrayage,electrique",
        "brands": "multimarque",
        "website_url": "https://www.midas.fr/centres-auto-midas/ile-de-france/hauts-de-seine/boulogne-billancourt/issy-les-moulineaux_1599",
        "photo_url": "https://media.midas.fr/shops/team/Centres/1599_%2BIssy%2BLes%2BMoulineaux.jpg",
        "source_url": "https://www.midas.fr/centres-auto-midas/ile-de-france/hauts-de-seine/boulogne-billancourt/issy-les-moulineaux_1599",
        "services": ["Bilan sécurité", "Climatisation", "Courroie de distribution", "Transmission et embrayage", "Révision", "Entretien véhicule électrique"],
    },
    {
        "name": "Midas Argenteuil",
        "slug": "midas-argenteuil",
        "legal_name": "ANTOUN G.J.",
        "siret": "80201150200027",
        "siren": "802011502",
        "city": "Argenteuil",
        "department": "95",
        "postal_code": "95100",
        "address": "108-112 route de Pontoise, 95100 Argenteuil",
        "phone": "01 30 25 50 39",
        "rating": 4.5,
        "specialties": "entretien,freinage,diagnostic,pneus,climatisation,distribution,embrayage,electrique",
        "brands": "multimarque",
        "website_url": "https://www.midas.fr/centres-auto-midas/ile-de-france/val-d-oise/argenteuil/argenteuil_1452",
        "photo_url": "https://media.midas.fr/shops/team/Centres/1452_Argenteuil.jpeg",
        "source_url": "https://www.midas.fr/centres-auto-midas/ile-de-france/val-d-oise/argenteuil/argenteuil_1452",
        "services": ["Bilan sécurité", "Climatisation", "Courroie de distribution", "Transmission et embrayage", "Révision", "Entretien véhicule électrique"],
    },
    {
        "name": "Midas Vitry-sur-Seine",
        "slug": "midas-vitry-sur-seine",
        "legal_name": "POP'S",
        "siret": "84103585000020",
        "siren": "841035850",
        "city": "Vitry-sur-Seine",
        "department": "94",
        "postal_code": "94400",
        "address": "123 boulevard de Stalingrad, 94400 Vitry-sur-Seine",
        "phone": "01 46 72 35 35",
        "rating": 4.5,
        "specialties": "entretien,freinage,diagnostic,pneus,climatisation,distribution,embrayage,electrique",
        "brands": "multimarque",
        "website_url": "https://www.midas.fr/centres-auto-midas/ile-de-france/val-de-marne/l-hay-les-roses/vitry-sur-seine_1259",
        "photo_url": "https://media.midas.fr/shops/team/Centres/1259_%2BVitry%2BSur%2BSeine.jpg",
        "source_url": "https://www.midas.fr/centres-auto-midas/ile-de-france/val-de-marne/l-hay-les-roses/vitry-sur-seine_1259",
        "services": ["Bilan sécurité", "Climatisation", "Courroie de distribution", "Transmission et embrayage", "Révision", "Entretien véhicule électrique"],
    },
    {
        "name": "Midas Paris 17 - Rue de Rome",
        "slug": "midas-paris-17-rue-de-rome",
        "legal_name": "NAJIB'S SON",
        "siret": "52118323600020",
        "siren": "521183236",
        "city": "Paris",
        "department": "75",
        "postal_code": "75017",
        "address": "131 rue de Rome, 75017 Paris",
        "phone": "01 43 80 73 73",
        "rating": 4.4,
        "specialties": "entretien,freinage,diagnostic,pneus,climatisation,distribution,embrayage",
        "brands": "multimarque",
        "website_url": "https://www.midas.fr/centres-auto-midas/ile-de-france/paris/paris-17/paris-17-rue-de-rome_1135",
        "photo_url": "https://media.midas.fr/shops/team/Centres/1135_%2BParis%2B17%2B-%2BRue%2Bde%2BRome.jpg",
        "source_url": "https://www.midas.fr/centres-auto-midas/ile-de-france/paris/paris-17/paris-17-rue-de-rome_1135",
        "services": ["Bilan sécurité", "Climatisation", "Courroie de distribution", "Transmission et embrayage", "Révision"],
    },
    {
        "name": "Midas Paris 18 - La Fourche",
        "slug": "midas-paris-18-la-fourche",
        "legal_name": "THE NEW CENTER",
        "siret": "34092561900033",
        "siren": "340925619",
        "city": "Paris",
        "department": "75",
        "postal_code": "75018",
        "address": "40 avenue de Saint-Ouen, 75018 Paris",
        "phone": "01 46 27 51 52",
        "rating": 4.7,
        "specialties": "entretien,freinage,diagnostic,pneus,distribution,embrayage,electrique",
        "brands": "multimarque",
        "website_url": "https://www.midas.fr/centres-auto-midas/ile-de-france/paris/paris-18/paris-18-la-fourche_1078",
        "photo_url": "https://media.midas.fr/shops/team/Centres/1078_Paris-18-La-Fourche.jpg",
        "source_url": "https://www.midas.fr/centres-auto-midas/ile-de-france/paris/paris-18/paris-18-la-fourche_1078",
        "services": ["Bilan sécurité", "Courroie de distribution", "Transmission et embrayage", "Révision", "Entretien véhicule électrique"],
    },
    {
        "name": "Alisson Garage",
        "slug": "alisson-garage-boulogne",
        "legal_name": "ALISSON GARAGE",
        "siret": "83397857000020",
        "siren": "833978570",
        "city": "Boulogne-Billancourt",
        "department": "92",
        "postal_code": "92100",
        "address": "32 rue Gallieni, 92100 Boulogne-Billancourt",
        "phone": "09 81 21 56 48",
        "rating": 0.0,
        "specialties": "entretien,freinage,pneus,jantes,distribution,embrayage,suspension",
        "brands": "multimarque",
        "website_url": "https://www.alissongarage.fr/",
        "photo_url": None,
        "source_url": "https://www.alissongarage.fr/nos-services",
        "services": ["Pneus neufs et d'occasion", "Réparation de jantes", "Plaquettes de freins", "Courroie et embrayage", "Amortisseurs et triangles", "Montage et équilibrage", "Vidange", "Préparation au contrôle technique"],
    },
    {
        "name": "Garage des 3 Communes",
        "slug": "garage-des-3-communes",
        "legal_name": "GARAGE DES 3 COMMUNES",
        "siret": "40331528600019",
        "siren": "403315286",
        "city": "Montreuil",
        "department": "93",
        "postal_code": "93100",
        "address": "190 bis rue de Romainville, 93100 Montreuil",
        "phone": "01 42 87 97 16",
        "rating": 4.1,
        "specialties": "entretien,freinage,pneus,distribution,climatisation,carrosserie",
        "brands": "peugeot,multimarque",
        "website_url": "https://www.peugeotproximity.fr/garage/garage-des-3-communes",
        "photo_url": None,
        "source_url": "https://www.peugeotproximity.fr/garage/garage-des-3-communes/nous-contacter/choix-du-service",
        "services": ["Révision vidange", "Pneumatiques été/hiver", "Amortisseurs", "Courroie de distribution", "Climatisation entretien & réparation", "Freins", "Contrôle technique (sous-traitance)"],
    },
    {
        "name": "Midas Saint-Denis",
        "slug": "midas-saint-denis",
        "legal_name": "SMART GARAGE 2000",
        "siret": "83845747100012",
        "siren": "838457471",
        "city": "Saint-Denis",
        "department": "93",
        "postal_code": "93200",
        "address": "4 boulevard Marcel Sembat, 93200 Saint-Denis",
        "phone": "01 77 37 05 30",
        "rating": 4.6,
        "specialties": "entretien,freinage,diagnostic,climatisation,distribution,embrayage,electrique",
        "brands": "multimarque",
        "website_url": "https://www.midas.fr/centres-auto-midas/ile-de-france/seine-saint-denis/saint-denis/saint-denis_1605",
        "photo_url": "https://media.midas.fr/shops/team/Centres/1605_%2BSaint%2BDenis-Stade%2Bde%2BFrance.jpg",
        "source_url": "https://www.midas.fr/centres-auto-midas/ile-de-france/seine-saint-denis/saint-denis/saint-denis_1605",
        "services": ["Bilan sécurité", "Climatisation", "Courroie de distribution", "Transmission et embrayage", "Révision", "Entretien véhicule électrique"],
    },
    {
        "name": "Midas Vert-Saint-Denis",
        "slug": "midas-vert-saint-denis",
        "legal_name": "POMPADOUR AUTO SERVICES",
        "siret": "47815359600042",
        "siren": "478153596",
        "city": "Vert-Saint-Denis",
        "department": "77",
        "postal_code": "77240",
        "address": "120 route Départementale 306, 77240 Vert-Saint-Denis",
        "phone": "01 64 79 59 05",
        "rating": 4.6,
        "specialties": "entretien,freinage,diagnostic,pneus,climatisation,distribution,embrayage,electrique",
        "brands": "multimarque",
        "website_url": "https://www.midas.fr/centres-auto-midas/ile-de-france/seine-et-marne/melun/vert-saint-denis_1631",
        "photo_url": "https://media.midas.fr/shops/team/Centres/1631_Vert%2BSaint%2BDenis.jpg",
        "source_url": "https://www.midas.fr/centres-auto-midas/ile-de-france/seine-et-marne/melun/vert-saint-denis_1631",
        "services": ["Bilan sécurité", "Climatisation", "Courroie de distribution", "Transmission et embrayage", "Révision", "Entretien véhicule électrique"],
    },
    {
        "name": "Midas Viry-Châtillon",
        "slug": "midas-viry-chatillon",
        "legal_name": "CAREFUL SERVICES",
        "siret": "78894256300016",
        "siren": "788942563",
        "city": "Viry-Châtillon",
        "department": "91",
        "postal_code": "91170",
        "address": "96 bis avenue du Général de Gaulle, 91170 Viry-Châtillon",
        "phone": "01 69 00 66 36",
        "rating": 4.6,
        "specialties": "entretien,freinage,diagnostic,pneus,climatisation,distribution,embrayage,electrique",
        "brands": "multimarque",
        "website_url": "https://www.midas.fr/centres-auto-midas/ile-de-france/essonne/evry/viry-chatillon_1503",
        "photo_url": "https://media.midas.fr/shops/team/Centres/1503_Viry-Chatillon.jpg",
        "source_url": "https://www.midas.fr/centres-auto-midas/ile-de-france/essonne/evry/viry-chatillon_1503",
        "services": ["Bilan sécurité", "Climatisation", "Courroie de distribution", "Transmission et embrayage", "Révision", "Entretien véhicule électrique"],
    },
    {
        "name": "Garage de Normandie",
        "slug": "garage-de-normandie-nanterre",
        "legal_name": "GARAGE DE NORMANDIE",
        "siret": "34030305600022",
        "siren": "340303056",
        "city": "Nanterre",
        "department": "92",
        "postal_code": "92000",
        "address": "98 route des Fusillés de la Résistance, 92000 Nanterre",
        "phone": "01 47 32 15 16",
        "rating": 4.5,
        "specialties": "entretien,freinage,diagnostic,pneus,batterie,electricite,embrayage,carrosserie",
        "brands": "peugeot,multimarque",
        "website_url": "https://www.garagedenormandie.fr/",
        "photo_url": "https://www.garagedenormandie.fr/ressources/images/customImage_558b_lg.jpeg",
        "photo_source_url": "https://www.garagedenormandie.fr/",
        "source_url": "https://www.garagedenormandie.fr/garage.php",
        "services": ["Révision", "Vidange", "Diagnostic électronique", "Batterie", "Pneumatiques", "Freinage", "Embrayage", "Contrôle technique", "Réparation mécanique"],
    },
    {
        "name": "Garage Auto Jesus",
        "slug": "garage-auto-jesus-nanterre",
        "legal_name": "GARAGE AUTO JESUS",
        "siret": "52417469500014",
        "siren": "524174695",
        "city": "Nanterre",
        "department": "92",
        "postal_code": "92000",
        "address": "129 rue de Suresnes, 92000 Nanterre",
        "phone": None,
        "rating": 0.0,
        "specialties": "carrosserie,peinture,debosselage,optique,marbre",
        "brands": "multimarque",
        "website_url": None,
        "photo_url": "https://static.where-e.com/France/Garage-Auto-Jesus_0f35c1b517a7ddfa4f79ee96c92fde59.jpg",
        "photo_source_url": "https://garage-auto-jesus.wheree.com/",
        "source_url": "https://www.118712.fr/professionnels/WkBWX1FSHgE",
        "services": ["Carrosserie", "Peinture automobile", "Débosselage", "Rénovation optique", "Passage au marbre", "Véhicule de remplacement", "Voitures anciennes"],
    },
    {
        "name": "Garage James Autos",
        "slug": "garage-james-autos-creteil",
        "legal_name": "JAMES AUTOS",
        "siret": "40995469000023",
        "siren": "409954690",
        "city": "Créteil",
        "department": "94",
        "postal_code": "94000",
        "address": "5 rue Jean Jaurès, 94000 Créteil",
        "phone": None,
        "rating": 0.0,
        "specialties": "carrosserie,peinture,entretien,antipollution,depannage",
        "brands": "multimarque",
        "website_url": None,
        "photo_url": None,
        "source_url": "https://mes-commerces.ville-creteil.fr/professionnels/UkBXRlFfWFI",
        "services": ["Carrosserie", "Peinture", "Réparation toutes marques", "Contrôle anti-pollution", "Dépannage", "Véhicule de remplacement"],
    },
    {
        "name": "Audi Bauer Paris Roissy",
        "slug": "audi-bauer-paris-roissy",
        "legal_name": "BAUER PARIS",
        "siret": "77566940100082",
        "siren": "775669401",
        "city": "Roissy-en-France",
        "department": "95",
        "postal_code": "95700",
        "address": "1 rue des Marguilliers, 95700 Roissy-en-France",
        "phone": "01 85 74 30 00",
        "rating": 0.0,
        "specialties": "entretien,freinage,diagnostic,pneus,carrosserie,batterie,electricite",
        "brands": "audi",
        "website_url": "https://www.bauerparis.fr/concessions-audi-bauer-paris/roissy-95/",
        "photo_url": None,
        "source_url": "https://www.bauerparis.fr/audi-service-entretien-reparation/bauer-paris-roissy-95/",
        "services": ["Révision", "Freinage", "Batterie", "Pneumatiques", "Maintenance mécanique", "Carrosserie", "Pièces et accessoires d'origine"],
    },

]

PUBLIC_SOURCE_VERIFIED_AT = datetime(2026, 9, 20)

DEMO_GARAGE = {
    "name": "Atelier Démo MecaConnect",
    "slug": "atelier-demo-mecaconnect",
    "city": "Paris",
    "department": "75",
    "postal_code": "75017",
    "address": "Donnée de démonstration non publiée",
    "description": "Atelier fictif masqué du catalogue public, réservé aux tests de réservation et de paiement de certification.",
    "specialties": "entretien,freinage,diagnostic,pneus",
    "brands": "multimarque",
}


def ensure_user(db, email: str, password: str, full_name: str, role: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user:
        return user
    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        role=role,
    )
    db.add(user)
    db.flush()
    return user


def geocode_address(address: str) -> tuple[float | None, float | None]:
    """Géocode une adresse officielle via la Géoplateforme IGN/BAN.

    Les tests restent totalement hors-ligne. En production, un échec réseau ne
    bloque jamais le seed : le garage reste consultable sans point cartographique.
    """
    if "test_mecaconnect" in os.getenv("DATABASE_URL", ""):
        return None, None

    try:
        response = httpx.get(
            "https://data.geopf.fr/geocodage/search",
            params={"q": address, "limit": 1},
            timeout=4.0,
        )
        response.raise_for_status()
        features = response.json().get("features") or []
        if not features:
            return None, None
        coordinates = (features[0].get("geometry") or {}).get("coordinates") or []
        if len(coordinates) != 2:
            return None, None
        return float(coordinates[1]), float(coordinates[0])
    except Exception:
        return None, None


def public_description(data: dict) -> str:
    return (
        f"{data['name']} est un établissement réel référencé à partir de données "
        f"publiques et du site officiel indiqué sur la fiche. SIRET {data['siret']}. "
        "Cette présence dans MecaConnect n'implique pas un partenariat commercial. "
        "Les prestations affichées sont celles publiées par l'établissement ou son réseau ; "
        "les tarifs doivent être confirmés directement auprès du garage."
    )


def replace_sourced_services(db, garage: Garage, names: list[str], source_url: str) -> None:
    # Ces services sont purement informatifs : pas de prix inventé ni de réservation
    # MecaConnect tant que l'établissement n'a pas revendiqué/configuré sa fiche.
    for service in list(garage.services):
        if not service.bookable:
            db.delete(service)
    db.flush()

    existing_bookable = {service.name for service in garage.services if service.bookable}
    for name in names:
        if name in existing_bookable:
            continue
        db.add(
            Service(
                garage_id=garage.id,
                name=name,
                description="Prestation publiée par l'établissement ou son réseau officiel.",
                price=0.0,
                duration_minutes=60,
                price_label="Tarif sur devis - non publié par MecaConnect",
                bookable=False,
                source_url=source_url,
            )
        )


def upsert_real_garage(db, data: dict) -> Garage:
    garage = db.scalar(select(Garage).where(Garage.siret == data["siret"]))
    if not garage:
        garage = db.scalar(select(Garage).where(Garage.slug == data["slug"]))

    lat = garage.lat if garage and garage.lat is not None else None
    lng = garage.lng if garage and garage.lng is not None else None
    if lat is None or lng is None:
        lat, lng = geocode_address(data["address"])

    claimed = bool(garage and garage.owner_id)
    values = {
        "name": data["name"],
        "slug": data["slug"],
        "legal_name": data["legal_name"],
        "siret": data["siret"],
        "siren": data["siren"],
        "city": data["city"],
        "department": data["department"],
        "postal_code": data["postal_code"],
        "address": data["address"],
        "phone": data["phone"],
        "rating": data["rating"],
        "specialties": data["specialties"],
        "brands": data["brands"],
        "website_url": data["website_url"],
        "photo_url": data["photo_url"],
        "photo_source_url": data.get("photo_source_url") or (data["source_url"] if data.get("photo_url") else None),
        "source_url": data["source_url"],
        "source_label": "SIRENE/RNE + site officiel de l'établissement ou du réseau",
        "verification_source": "SIRENE/RNE",
        "source_verified_at": PUBLIC_SOURCE_VERIFIED_AT,
        "description": public_description(data),
        "verified": True,
        "listing_status": "CLAIMED_PARTNER" if claimed else "PUBLIC_REFERENCE",
        "booking_enabled": garage.booking_enabled if claimed else False,
        "payment_online_enabled": garage.payment_online_enabled if claimed else False,
        "deposit_rate": float(garage.deposit_rate or 0.20) if claimed else 0.20,
        "is_public": True,
        "lat": lat,
        "lng": lng,
    }

    if not garage:
        garage = Garage(**values)
        db.add(garage)
        db.flush()
    else:
        for key, value in values.items():
            setattr(garage, key, value)
        db.flush()

    replace_sourced_services(db, garage, data["services"], data["source_url"])
    return garage


def ensure_demo_garage(db, garage_user: User) -> Garage:
    garage = db.scalar(select(Garage).where(Garage.slug == DEMO_GARAGE["slug"]))
    if not garage:
        garage = Garage(
            owner_id=garage_user.id,
            verified=True,
            listing_status="DEMO_HIDDEN",
            booking_enabled=True,
            payment_online_enabled=True,
            deposit_rate=0.20,
            is_public=False,
            rating=0.0,
            source_label="Donnée interne de démonstration",
            **DEMO_GARAGE,
        )
        db.add(garage)
        db.flush()
    else:
        garage.owner_id = garage_user.id
        garage.is_public = False
        garage.booking_enabled = True
        garage.listing_status = "DEMO_HIDDEN"
        garage.payment_online_enabled = True
        db.flush()

    if not garage.services:
        for name, description, price, duration in (
            ("Révision / vidange - démo", "Prestation fictive utilisée pour tester le tunnel de réservation.", 120.0, 60),
            ("Contrôle freinage - démo", "Prestation fictive utilisée pour tester le tunnel de réservation.", 80.0, 45),
            ("Diagnostic électronique - démo", "Prestation fictive utilisée pour tester le tunnel de réservation.", 90.0, 45),
        ):
            db.add(
                Service(
                    garage_id=garage.id,
                    name=name,
                    description=description,
                    price=price,
                    duration_minutes=duration,
                    price_label=None,
                    bookable=True,
                )
            )
        db.flush()

    existing_slot = db.scalar(
        select(Availability.id).where(Availability.garage_id == garage.id).limit(1)
    )
    if not existing_slot:
        tomorrow = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1)
        first = tomorrow.replace(hour=8, minute=30, second=0, microsecond=0)
        for day in range(5):
            for offset in (0, 2, 4):
                start = first + timedelta(days=day, hours=offset)
                db.add(
                    Availability(
                        garage_id=garage.id,
                        starts_at=start,
                        ends_at=start + timedelta(minutes=60),
                    )
                )
    return garage


def run() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_schema_compatibility()
    db = SessionLocal()

    try:
        ensure_user(
            db,
            "admin@mecaconnect.example.com",
            os.getenv("ADMIN_SEED_PASSWORD", "Admin-ChangeMe-2026!"),
            "Administrateur MecaConnect",
            "ADMIN",
        )
        garage_user = ensure_user(
            db,
            "garage@mecaconnect.example.com",
            os.getenv("GARAGE_SEED_PASSWORD", "Garage-ChangeMe-2026!"),
            "Garage Démo MecaConnect",
            "GARAGE",
        )

        # Les anciens garages fictifs du prototype restent en base pour ne pas casser
        # d'éventuelles relations historiques, mais disparaissent immédiatement du
        # catalogue et de la carte publics.
        legacy = db.scalars(select(Garage).where(Garage.siret.is_(None))).all()
        for garage in legacy:
            garage.is_public = False
            if garage.slug != DEMO_GARAGE["slug"] and garage.owner_id == garage_user.id:
                garage.owner_id = None

        for data in REAL_GARAGES:
            upsert_real_garage(db, data)

        ensure_demo_garage(db, garage_user)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    run()
