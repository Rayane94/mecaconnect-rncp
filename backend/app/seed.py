from datetime import datetime, timedelta, timezone
import os

from sqlalchemy import select

from .database import Base, SessionLocal, engine, ensure_schema_compatibility
from .models import Availability, Garage, Service, User
from .security import hash_password


GARAGES = [
    # Paris
    {"name":"Garage Berthier","slug":"garage-berthier","city":"Paris","department":"75","postal_code":"75017","address":"Secteur Porte de Champerret - Paris 17e","lat":48.8877,"lng":2.3024,"rating":4.8,"specialties":"entretien,freinage,diagnostic,pneus","brands":"multimarque,mercedes,bmw,audi,renault,peugeot","hourly_rate":92},
    {"name":"Atelier Bastille","slug":"atelier-bastille","city":"Paris","department":"75","postal_code":"75011","address":"Secteur Bastille - Paris 11e","lat":48.8530,"lng":2.3690,"rating":4.7,"specialties":"diagnostic,electricite,batterie,hybride","brands":"multimarque,renault,peugeot,citroen,toyota","hourly_rate":88},
    {"name":"Meca Montparnasse","slug":"meca-montparnasse","city":"Paris","department":"75","postal_code":"75014","address":"Secteur Montparnasse - Paris 14e","lat":48.8329,"lng":2.3250,"rating":4.6,"specialties":"pneus,geometrie,suspension,freinage","brands":"multimarque,volkswagen,seat,skoda,ford","hourly_rate":86},
    {"name":"Auto République","slug":"auto-republique","city":"Paris","department":"75","postal_code":"75010","address":"Secteur République - Paris 10e","lat":48.8675,"lng":2.3638,"rating":4.5,"specialties":"moteur,distribution,entretien,diagnostic","brands":"multimarque,renault,dacia,peugeot,citroen","hourly_rate":90},
    {"name":"Atelier Bercy","slug":"atelier-bercy","city":"Paris","department":"75","postal_code":"75012","address":"Secteur Bercy - Paris 12e","lat":48.8356,"lng":2.3841,"rating":4.7,"specialties":"climatisation,entretien,diagnostic,electricite","brands":"multimarque,toyota,lexus,hyundai,kia","hourly_rate":89},
    {"name":"Diesel Paris Nord","slug":"diesel-paris-nord","city":"Paris","department":"75","postal_code":"75018","address":"Secteur Porte de la Chapelle - Paris 18e","lat":48.8974,"lng":2.3595,"rating":4.6,"specialties":"diesel,fap,injection,diagnostic,moteur","brands":"multimarque,mercedes,bmw,audi,peugeot,citroen","hourly_rate":95},
    # Hauts-de-Seine
    {"name":"Seine Auto Boulogne","slug":"seine-auto-boulogne","city":"Boulogne-Billancourt","department":"92","postal_code":"92100","address":"Secteur Marcel Sembat - Boulogne-Billancourt","lat":48.8333,"lng":2.2430,"rating":4.8,"specialties":"entretien,freinage,climatisation,pneus","brands":"multimarque,renault,peugeot,citroen","hourly_rate":84},
    {"name":"Atelier Défense","slug":"atelier-defense","city":"Courbevoie","department":"92","postal_code":"92400","address":"Secteur La Défense - Courbevoie","lat":48.8970,"lng":2.2520,"rating":4.7,"specialties":"diagnostic,electricite,hybride,electrique","brands":"multimarque,tesla,mercedes,bmw,audi","hourly_rate":105},
    {"name":"Nanterre Transmission","slug":"nanterre-transmission","city":"Nanterre","department":"92","postal_code":"92000","address":"Secteur Nanterre Centre","lat":48.8924,"lng":2.2060,"rating":4.6,"specialties":"transmission,embrayage,diagnostic,moteur","brands":"multimarque,volkswagen,audi,bmw,mercedes","hourly_rate":98},
    {"name":"Levallois Premium Auto","slug":"levallois-premium-auto","city":"Levallois-Perret","department":"92","postal_code":"92300","address":"Secteur Louise Michel - Levallois-Perret","lat":48.8932,"lng":2.2870,"rating":4.9,"specialties":"diagnostic,moteur,entretien,freinage","brands":"mercedes,bmw,audi,volvo,lexus","hourly_rate":118},
    {"name":"Antony Auto Service","slug":"antony-auto-service","city":"Antony","department":"92","postal_code":"92160","address":"Secteur Antony Centre","lat":48.7535,"lng":2.2960,"rating":4.5,"specialties":"entretien,freinage,pneus,suspension","brands":"multimarque,renault,peugeot,citroen,dacia","hourly_rate":79},
    # Seine-Saint-Denis
    {"name":"Saint-Denis Diagnostic","slug":"saint-denis-diagnostic","city":"Saint-Denis","department":"93","postal_code":"93200","address":"Secteur Stade de France - Saint-Denis","lat":48.9302,"lng":2.3574,"rating":4.6,"specialties":"diagnostic,electricite,injection,diesel","brands":"multimarque,renault,peugeot,citroen,ford","hourly_rate":76},
    {"name":"Montreuil Meca","slug":"montreuil-meca","city":"Montreuil","department":"93","postal_code":"93100","address":"Secteur Croix de Chavaux - Montreuil","lat":48.8575,"lng":2.4355,"rating":4.7,"specialties":"entretien,distribution,moteur,freinage","brands":"multimarque,renault,dacia,peugeot,citroen","hourly_rate":78},
    {"name":"Aulnay Diesel Center","slug":"aulnay-diesel-center","city":"Aulnay-sous-Bois","department":"93","postal_code":"93600","address":"Secteur Aulnay Centre","lat":48.9380,"lng":2.4930,"rating":4.8,"specialties":"diesel,fap,injection,diagnostic","brands":"multimarque,peugeot,citroen,renault,mercedes","hourly_rate":82},
    {"name":"Noisy Auto Tech","slug":"noisy-auto-tech","city":"Noisy-le-Grand","department":"93","postal_code":"93160","address":"Secteur Mont d'Est - Noisy-le-Grand","lat":48.8404,"lng":2.5480,"rating":4.5,"specialties":"hybride,electrique,diagnostic,climatisation","brands":"multimarque,toyota,hyundai,kia,tesla","hourly_rate":86},
    # Val-de-Marne
    {"name":"Créteil Auto Pro","slug":"creteil-auto-pro","city":"Créteil","department":"94","postal_code":"94000","address":"Secteur Créteil Université","lat":48.7904,"lng":2.4556,"rating":4.7,"specialties":"entretien,freinage,diagnostic,pneus","brands":"multimarque,renault,peugeot,citroen,toyota","hourly_rate":82},
    {"name":"Vincennes Car Lab","slug":"vincennes-car-lab","city":"Vincennes","department":"94","postal_code":"94300","address":"Secteur Château de Vincennes","lat":48.8470,"lng":2.4370,"rating":4.8,"specialties":"diagnostic,electricite,hybride,climatisation","brands":"multimarque,toyota,lexus,volvo,volkswagen","hourly_rate":96},
    {"name":"Ivry Pneus & Freins","slug":"ivry-pneus-freins","city":"Ivry-sur-Seine","department":"94","postal_code":"94200","address":"Secteur Ivry Centre","lat":48.8134,"lng":2.3886,"rating":4.6,"specialties":"pneus,freinage,geometrie,suspension","brands":"multimarque","hourly_rate":74},
    {"name":"Vitry Moteur Service","slug":"vitry-moteur-service","city":"Vitry-sur-Seine","department":"94","postal_code":"94400","address":"Secteur Vitry Centre","lat":48.7872,"lng":2.3928,"rating":4.5,"specialties":"moteur,distribution,refroidissement,diagnostic","brands":"multimarque,renault,peugeot,citroen,ford","hourly_rate":80},
    # Yvelines
    {"name":"Versailles Auto Expert","slug":"versailles-auto-expert","city":"Versailles","department":"78","postal_code":"78000","address":"Secteur Versailles Chantiers","lat":48.7955,"lng":2.1355,"rating":4.9,"specialties":"diagnostic,entretien,freinage,transmission","brands":"multimarque,mercedes,bmw,audi,volvo","hourly_rate":102},
    {"name":"Saint-Germain Atelier","slug":"saint-germain-atelier","city":"Saint-Germain-en-Laye","department":"78","postal_code":"78100","address":"Secteur Saint-Germain Centre","lat":48.8989,"lng":2.0938,"rating":4.7,"specialties":"entretien,climatisation,pneus,suspension","brands":"multimarque,volkswagen,audi,skoda,seat","hourly_rate":91},
    {"name":"Montigny Transmission","slug":"montigny-transmission","city":"Montigny-le-Bretonneux","department":"78","postal_code":"78180","address":"Secteur Saint-Quentin-en-Yvelines","lat":48.7710,"lng":2.0340,"rating":4.6,"specialties":"transmission,embrayage,moteur,diagnostic","brands":"multimarque,ford,volkswagen,renault,peugeot","hourly_rate":88},
    # Essonne
    {"name":"Massy Hybrid Tech","slug":"massy-hybrid-tech","city":"Massy","department":"91","postal_code":"91300","address":"Secteur Massy-Palaiseau","lat":48.7252,"lng":2.2731,"rating":4.8,"specialties":"hybride,electrique,diagnostic,electricite","brands":"toyota,lexus,hyundai,kia,tesla,multimarque","hourly_rate":94},
    {"name":"Évry Auto Centre","slug":"evry-auto-centre","city":"Évry-Courcouronnes","department":"91","postal_code":"91000","address":"Secteur Évry Centre","lat":48.6298,"lng":2.4410,"rating":4.6,"specialties":"entretien,freinage,pneus,distribution","brands":"multimarque,renault,peugeot,citroen,dacia","hourly_rate":75},
    {"name":"Sainte-Geneviève Meca","slug":"sainte-genevieve-meca","city":"Sainte-Geneviève-des-Bois","department":"91","postal_code":"91700","address":"Secteur Sainte-Geneviève Centre","lat":48.6460,"lng":2.3190,"rating":4.5,"specialties":"moteur,refroidissement,diagnostic,climatisation","brands":"multimarque,ford,opel,renault,peugeot","hourly_rate":78},
    # Val-d'Oise
    {"name":"Cergy Auto Diagnostic","slug":"cergy-auto-diagnostic","city":"Cergy","department":"95","postal_code":"95000","address":"Secteur Cergy-Préfecture","lat":49.0369,"lng":2.0761,"rating":4.7,"specialties":"diagnostic,electricite,injection,entretien","brands":"multimarque,renault,peugeot,citroen,volkswagen","hourly_rate":82},
    {"name":"Argenteuil Freinage","slug":"argenteuil-freinage","city":"Argenteuil","department":"95","postal_code":"95100","address":"Secteur Argenteuil Centre","lat":48.9472,"lng":2.2467,"rating":4.6,"specialties":"freinage,pneus,suspension,geometrie","brands":"multimarque","hourly_rate":76},
    {"name":"Sarcelles Diesel & FAP","slug":"sarcelles-diesel-fap","city":"Sarcelles","department":"95","postal_code":"95200","address":"Secteur Sarcelles Centre","lat":48.9973,"lng":2.3784,"rating":4.5,"specialties":"diesel,fap,injection,echappement","brands":"multimarque,renault,peugeot,citroen,mercedes","hourly_rate":79},
    # Seine-et-Marne
    {"name":"Meaux Auto Service","slug":"meaux-auto-service","city":"Meaux","department":"77","postal_code":"77100","address":"Secteur Meaux Centre","lat":48.9601,"lng":2.8788,"rating":4.6,"specialties":"entretien,freinage,distribution,pneus","brands":"multimarque,renault,dacia,peugeot,citroen","hourly_rate":72},
    {"name":"Melun Meca Expert","slug":"melun-meca-expert","city":"Melun","department":"77","postal_code":"77000","address":"Secteur Melun Centre","lat":48.5404,"lng":2.6600,"rating":4.7,"specialties":"moteur,diagnostic,transmission,embrayage","brands":"multimarque,ford,volkswagen,renault,peugeot","hourly_rate":77},
    {"name":"Chelles Auto Tech","slug":"chelles-auto-tech","city":"Chelles","department":"77","postal_code":"77500","address":"Secteur Chelles-Gournay","lat":48.8774,"lng":2.5836,"rating":4.6,"specialties":"hybride,electrique,diagnostic,climatisation","brands":"multimarque,toyota,hyundai,kia,volkswagen","hourly_rate":83},
]

SERVICE_CATALOG = {
    "entretien": ("Révision / vidange", "Entretien périodique avec contrôles de niveaux et filtres selon besoin.", 129.0, 75),
    "freinage": ("Contrôle freinage", "Contrôle du système de freinage et estimation des éléments à remplacer.", 59.0, 35),
    "diagnostic": ("Diagnostic électronique", "Lecture des calculateurs et recherche initiale de panne.", 79.0, 45),
    "pneus": ("Pneumatiques / équilibrage", "Contrôle pneus, pression et équilibrage. Prix hors pneumatiques neufs.", 69.0, 45),
    "geometrie": ("Géométrie train roulant", "Contrôle et réglage de la géométrie lorsque possible.", 89.0, 60),
    "suspension": ("Diagnostic suspension", "Recherche de jeu, bruit ou usure du train roulant.", 75.0, 45),
    "electricite": ("Diagnostic électrique", "Contrôle batterie, charge, démarrage et alimentation électrique.", 85.0, 50),
    "batterie": ("Contrôle batterie", "Test de batterie et circuit de charge.", 39.0, 25),
    "hybride": ("Diagnostic hybride", "Diagnostic initial par atelier sensibilisé aux systèmes hybrides.", 99.0, 60),
    "electrique": ("Diagnostic véhicule électrique", "Diagnostic initial hors intervention sur batterie haute tension.", 109.0, 60),
    "moteur": ("Diagnostic moteur", "Contrôle mécanique et électronique initial du moteur.", 95.0, 60),
    "distribution": ("Contrôle distribution", "Contrôle historique, bruits et échéance de distribution.", 69.0, 40),
    "refroidissement": ("Contrôle refroidissement", "Recherche de fuite et contrôle du circuit de refroidissement.", 79.0, 45),
    "diesel": ("Diagnostic diesel", "Contrôle moteur diesel et paramètres antipollution.", 89.0, 50),
    "fap": ("Diagnostic FAP", "Mesure des paramètres FAP et recherche de cause avant régénération.", 99.0, 55),
    "injection": ("Diagnostic injection", "Contrôle des paramètres d'injection et recherche de panne.", 99.0, 55),
    "embrayage": ("Diagnostic embrayage", "Essai et contrôle initial de l'embrayage.", 79.0, 45),
    "transmission": ("Diagnostic transmission", "Contrôle initial boîte, transmission et comportement des rapports.", 119.0, 60),
    "climatisation": ("Diagnostic climatisation", "Contrôle de fonctionnement et pressions avant recharge ou réparation.", 69.0, 40),
    "echappement": ("Contrôle échappement", "Recherche de fuite et contrôle de la ligne d'échappement.", 59.0, 35),
}

SPECIALTY_LABELS = {
    "entretien": "l'entretien courant",
    "freinage": "le freinage",
    "diagnostic": "le diagnostic électronique",
    "pneus": "les pneumatiques",
    "geometrie": "la géométrie",
    "suspension": "les trains roulants",
    "electricite": "l'électricité automobile",
    "batterie": "les batteries et circuits de charge",
    "hybride": "les motorisations hybrides",
    "electrique": "les véhicules électriques",
    "moteur": "la mécanique moteur",
    "distribution": "la distribution",
    "refroidissement": "le refroidissement moteur",
    "diesel": "les motorisations diesel",
    "fap": "les systèmes FAP",
    "injection": "l'injection",
    "embrayage": "l'embrayage",
    "transmission": "la transmission",
    "climatisation": "la climatisation",
    "echappement": "l'échappement",
}


def garage_description(data: dict) -> str:
    specialties = [
        SPECIALTY_LABELS[item]
        for item in data["specialties"].split(",")[:3]
        if item in SPECIALTY_LABELS
    ]
    if len(specialties) > 1:
        expertise = ", ".join(specialties[:-1]) + f" et {specialties[-1]}"
    else:
        expertise = specialties[0] if specialties else "la mécanique automobile"
    return (
        f"Atelier situé à {data['city']}, spécialisé dans {expertise}. "
        "Consultez les prestations, les tarifs et les prochains créneaux disponibles en ligne."
    )


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


def add_services(db, garage: Garage) -> None:
    if garage.services:
        return

    selected = []
    for specialty in garage.specialties.split(","):
        specialty = specialty.strip()
        if specialty in SERVICE_CATALOG and specialty not in selected:
            selected.append(specialty)
        if len(selected) >= 4:
            break

    for specialty in selected:
        name, description, price, duration = SERVICE_CATALOG[specialty]
        # Un léger écart simule les différences de tarif entre ateliers sans prétendre à un devis réel.
        price_factor = max(0.88, min(1.18, (garage.hourly_rate or 80) / 85))
        db.add(
            Service(
                garage_id=garage.id,
                name=name,
                description=description,
                price=round(price * price_factor, 2),
                duration_minutes=duration,
            )
        )


def add_slots(db, garage: Garage) -> None:
    existing = db.scalar(select(Availability.id).where(Availability.garage_id == garage.id).limit(1))
    if existing:
        return

    tomorrow = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1)
    first_slot = tomorrow.replace(hour=8, minute=30, second=0, microsecond=0)

    for day in range(5):
        for hour_offset in (0, 2, 4, 6):
            starts_at = first_slot + timedelta(days=day, hours=hour_offset)
            db.add(
                Availability(
                    garage_id=garage.id,
                    starts_at=starts_at,
                    ends_at=starts_at + timedelta(minutes=60),
                )
            )


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
            "Garage Berthier",
            "GARAGE",
        )

        for data in GARAGES:
            garage = db.scalar(select(Garage).where(Garage.slug == data["slug"]))
            if not garage:
                garage = Garage(
                    owner_id=garage_user.id if data["slug"] == "garage-berthier" else None,
                    description=garage_description(data),
                    verified=False,
                    **data,
                )
                db.add(garage)
                db.flush()
            else:
                for key, value in data.items():
                    setattr(garage, key, value)
                garage.description = garage_description(data)

            add_services(db, garage)
            add_slots(db, garage)

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    run()
