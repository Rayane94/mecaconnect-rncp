import logging
import os
import secrets
import time
import re
import unicodedata

import httpx
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models, schemas
from .assistant import build_diagnosis, prepare_conversation_message
from .ai_assistant import ai_is_configured, configured_model, enhance_diagnosis
from .database import Base, engine, ensure_schema_compatibility, get_db
from .payment import StripeHttpProvider, get_payment_provider
from .security import (
    create_access_token,
    decode_access_token,
    decrypt_text,
    encrypt_text,
    generate_totp_secret,
    hash_password,
    verify_password,
    verify_totp,
)

logger = logging.getLogger("mecaconnect")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

Base.metadata.create_all(bind=engine)

ensure_schema_compatibility()

app = FastAPI(
    title="MecaConnect API",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000").rstrip("/")

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:8000,http://localhost:3000",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

# Limitation applicative : 120 requêtes par minute et par adresse IP.
request_history: dict[str, deque[float]] = defaultdict(deque)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    ip_address = request.client.host if request.client else "unknown"
    now = time.time()
    history = request_history[ip_address]

    while history and history[0] < now - 60:
        history.popleft()

    if len(history) >= 120:
        return JSONResponse({"detail": "Trop de requêtes"}, status_code=429)

    history.append(now)
    response = await call_next(request)

    # Swagger UI initialise son interface avec un script intégré dans /api/docs.
    # L'exception reste limitée à cette page ; le site public conserve une CSP stricte.
    script_src = "'self' https://unpkg.com https://cdn.jsdelivr.net"
    if request.url.path == "/api/docs":
        script_src += " 'unsafe-inline'"

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(self), camera=(), microphone=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' data: https:; "
        "style-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.jsdelivr.net; "
        f"script-src {script_src}; "
        "connect-src 'self' https://tiles.openfreemap.org https://api.stripe.com; "
        "worker-src 'self' blob:; "
        "child-src blob:"
    )

    if COOKIE_SECURE:
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )

    return response


def add_audit_log(
    db: Session,
    user_id: int | None,
    action: str,
    resource: str | None = None,
    detail: str | None = None,
) -> None:
    """Enregistre une action utile pour les contrôles et le suivi de l'application."""
    db.add(
        models.AuditLog(
            user_id=user_id,
            action=action,
            resource=resource,
            detail=detail,
        )
    )
    db.commit()


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> models.User:
    token = request.cookies.get("mc_session")

    if not token:
        authorization = request.headers.get("Authorization", "")
        if authorization.startswith("Bearer "):
            token = authorization.removeprefix("Bearer ").strip()

    if not token:
        raise HTTPException(status_code=401, detail="Authentification requise")

    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except Exception as exc:
        logger.warning("Jeton de session invalide: %s", exc)
        raise HTTPException(
            status_code=401,
            detail="Session invalide ou expirée",
        ) from exc

    user = db.get(models.User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Compte inactif")

    return user


def require_roles(*roles: str):
    def dependency(user: models.User = Depends(get_current_user)) -> models.User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Droits insuffisants")
        return user

    return dependency


def garage_to_dict(garage: models.Garage) -> dict:
    return {
        "id": garage.id,
        "name": garage.name,
        "slug": garage.slug,
        "city": garage.city,
        "address": garage.address,
        "description": garage.description,
        "rating": garage.rating,
        "verified": garage.verified,
        "lat": garage.lat,
        "lng": garage.lng,
        "department": garage.department,
        "postal_code": garage.postal_code,
        "specialties": [item.strip() for item in (garage.specialties or "").split(",") if item.strip()],
        "brands": [item.strip() for item in (garage.brands or "").split(",") if item.strip()],
        "hourly_rate": garage.hourly_rate,
        "siret": garage.siret,
        "siren": garage.siren,
        "legal_name": garage.legal_name,
        "verification_source": garage.verification_source,
        "payment_online_enabled": garage.payment_online_enabled,
        "deposit_rate": garage.deposit_rate,
        "phone": garage.phone,
        "website_url": garage.website_url,
        "photo_url": garage.photo_url,
        "photo_source_url": garage.photo_source_url,
        "source_url": garage.source_url,
        "source_label": garage.source_label,
        "listing_status": garage.listing_status,
        "booking_enabled": garage.booking_enabled,
        "is_public": garage.is_public,
        "source_verified_at": garage.source_verified_at,
    }


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "mecaconnect-api",
        "time": datetime.now(timezone.utc).isoformat(),
    }




def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(char for char in normalized if not unicodedata.combining(char))
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")
    return slug[:120] or "garage"


async def lookup_company_by_siret(siret: str) -> dict:
    """Vérifie un SIRET avec l'API publique de recherche d'entreprises."""
    if not re.fullmatch(r"\d{14}", siret):
        raise HTTPException(status_code=422, detail="Le SIRET doit contenir 14 chiffres")

    url = "https://recherche-entreprises.api.gouv.fr/search"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(url, params={"q": siret, "per_page": 5})
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        logger.warning("Vérification SIRET indisponible: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="La vérification officielle du SIRET est momentanément indisponible",
        ) from exc

    for company in payload.get("results", []):
        establishments = [company.get("siege") or {}] + list(
            company.get("matching_etablissements") or []
        )
        establishment = next(
            (item for item in establishments if str(item.get("siret") or "") == siret),
            None,
        )
        if establishment:
            activity_value = (
                establishment.get("activite_principale")
                or company.get("activite_principale")
                or ""
            )
            activity_code = str(activity_value).replace(".", "")
            nature = str(activity_value).lower()
            if not activity_code.startswith("452"):
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Le SIRET existe, mais l'activité principale de cet établissement "
                        "ne correspond pas à l'entretien ou à la réparation automobile (NAF 45.20)."
                    ),
                )
            name = (
                company.get("nom_complet")
                or company.get("nom_raison_sociale")
                or company.get("sigle")
                or "Entreprise"
            )
            address = establishment.get("adresse") or ""
            city = establishment.get("libelle_commune") or establishment.get("commune") or ""
            postal_code = establishment.get("code_postal") or ""
            return {
                "siret": siret,
                "siren": str(company.get("siren") or siret[:9]),
                "legal_name": str(name),
                "address": str(address),
                "city": str(city),
                "postal_code": str(postal_code),
                "activity": nature,
            }

    raise HTTPException(
        status_code=404,
        detail="SIRET introuvable dans le registre public des entreprises",
    )


@app.get("/api/public/address-search")
async def address_search(q: str):
    query = q.strip()
    if len(query) < 2:
        return []

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                "https://data.geopf.fr/geocodage/search",
                params={
                    "q": query,
                    "type": "municipality",
                    "autocomplete": "true",
                    "limit": 7,
                },
            )
            response.raise_for_status()
            features = response.json().get("features", [])
    except Exception:
        return []

    results = []
    seen = set()
    for feature in features:
        props = feature.get("properties") or {}
        city = props.get("city") or props.get("name")
        postcode = props.get("postcode") or ""
        label = props.get("label") or city
        if not city or city in seen:
            continue
        seen.add(city)
        results.append({"city": city, "postcode": postcode, "label": label})
    return results


@app.get("/api/public/company/{siret}")
async def company_lookup(siret: str):
    return await lookup_company_by_siret(siret)


@app.post("/api/auth/register", status_code=201)
def register(
    payload: schemas.RegisterIn,
    response: Response,
    db: Session = Depends(get_db),
):
    email = payload.email.lower()
    existing_user = db.scalar(select(models.User).where(models.User.email == email))
    if existing_user:
        raise HTTPException(status_code=409, detail="Adresse e-mail déjà utilisée")

    user = models.User(
        email=email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        role="USER",
        phone_encrypted=encrypt_text(payload.phone),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.role)
    response.set_cookie(
        "mc_session",
        token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=3600,
    )

    add_audit_log(db, user.id, "REGISTER", "user")
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
    }




@app.post("/api/auth/register-garage", status_code=201)
async def register_garage(
    payload: schemas.RegisterGarageIn,
    response: Response,
    db: Session = Depends(get_db),
):
    email = payload.email.lower()
    if db.scalar(select(models.User).where(models.User.email == email)):
        raise HTTPException(status_code=409, detail="Adresse e-mail déjà utilisée")

    company = await lookup_company_by_siret(payload.siret)
    existing_garage = db.scalar(
        select(models.Garage).where(models.Garage.siret == payload.siret)
    )
    if existing_garage and existing_garage.owner_id:
        raise HTTPException(
            status_code=409,
            detail="Ce SIRET est déjà rattaché à un compte professionnel",
        )

    user = models.User(
        email=email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        role="GARAGE",
        phone_encrypted=encrypt_text(payload.phone),
    )
    db.add(user)
    db.flush()

    if existing_garage:
        garage = existing_garage
        garage.owner_id = user.id
        garage.verified = True
        garage.listing_status = "CLAIMED_PARTNER"
        garage.booking_enabled = True
        garage.is_public = True
        garage.payment_online_enabled = True
        garage.deposit_rate = float(garage.deposit_rate or 0.20)
        garage.siren = company["siren"]
        garage.legal_name = company["legal_name"]
        garage.verification_source = "Annuaire des Entreprises / API publique"
        if payload.garage_name.strip():
            garage.name = payload.garage_name.strip()
    else:
        base_slug = _slugify(payload.garage_name)
        slug = f"{base_slug}-{payload.siret[-5:]}"
        garage = models.Garage(
            owner_id=user.id,
            name=payload.garage_name.strip(),
            slug=slug,
            city=company["city"] or "À compléter",
            address=company["address"] or "Adresse à compléter",
            postal_code=company["postal_code"] or None,
            description=(
                f"{payload.garage_name.strip()} - établissement professionnel "
                "vérifié à partir de son SIRET. Complétez la fiche depuis l'espace garage."
            ),
            verified=True,
            siret=company["siret"],
            siren=company["siren"],
            legal_name=company["legal_name"],
            verification_source="Annuaire des Entreprises / API publique",
            listing_status="CLAIMED_PARTNER",
            booking_enabled=True,
            is_public=True,
            payment_online_enabled=True,
            deposit_rate=0.20,
        )
        db.add(garage)
    db.commit()
    db.refresh(user)
    db.refresh(garage)

    token = create_access_token(user.id, user.role)
    response.set_cookie(
        "mc_session",
        token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=3600,
    )
    add_audit_log(db, user.id, "REGISTER_GARAGE", "garage", str(garage.id))
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "garage_id": garage.id,
        "siret": garage.siret,
        "verified": garage.verified,
    }


@app.post("/api/auth/login")
def login(
    payload: schemas.LoginIn,
    response: Response,
    db: Session = Depends(get_db),
):
    user = db.scalar(
        select(models.User).where(models.User.email == payload.email.lower())
    )

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Identifiants invalides")

    if user.two_factor_enabled:
        code = payload.totp_code or ""
        if not user.totp_secret or not verify_totp(user.totp_secret, code):
            raise HTTPException(status_code=401, detail="Code 2FA requis ou invalide")

    token = create_access_token(user.id, user.role)
    response.set_cookie(
        "mc_session",
        token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=3600,
    )

    add_audit_log(db, user.id, "LOGIN", "user")
    return {
        "ok": True,
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
        },
    }


@app.post("/api/auth/logout")
def logout(
    response: Response,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    response.delete_cookie("mc_session")
    add_audit_log(db, user.id, "LOGOUT", "user")
    return {"ok": True}


@app.get("/api/auth/me")
def auth_me(user: models.User = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "phone": decrypt_text(user.phone_encrypted),
        "two_factor_enabled": user.two_factor_enabled,
    }


@app.post("/api/auth/2fa/setup")
def setup_2fa(
    user: models.User = Depends(require_roles("GARAGE", "ADMIN")),
    db: Session = Depends(get_db),
):
    user.totp_secret = generate_totp_secret()
    db.commit()

    uri = (
        f"otpauth://totp/MecaConnect:{user.email}"
        f"?secret={user.totp_secret}&issuer=MecaConnect"
    )
    return {"secret": user.totp_secret, "otpauth_uri": uri}


@app.post("/api/auth/2fa/enable")
def enable_2fa(
    code: str,
    user: models.User = Depends(require_roles("GARAGE", "ADMIN")),
    db: Session = Depends(get_db),
):
    if not user.totp_secret or not verify_totp(user.totp_secret, code):
        raise HTTPException(status_code=400, detail="Code TOTP invalide")

    user.two_factor_enabled = True
    db.commit()
    add_audit_log(db, user.id, "ENABLE_2FA", "user")
    return {"ok": True}


@app.post("/api/vehicles", status_code=201)
def create_vehicle(
    payload: schemas.VehicleIn,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vehicle = models.Vehicle(owner_id=user.id, **payload.model_dump())
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)

    add_audit_log(db, user.id, "CREATE", "vehicle", str(vehicle.id))
    return {"id": vehicle.id, **payload.model_dump()}


@app.get("/api/vehicles")
def list_vehicles(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vehicles = db.scalars(
        select(models.Vehicle).where(models.Vehicle.owner_id == user.id)
    ).all()

    return [
        {
            "id": vehicle.id,
            "make": vehicle.make,
            "model": vehicle.model,
            "year": vehicle.year,
            "plate": vehicle.plate,
            "motorization": vehicle.motorization,
        }
        for vehicle in vehicles
    ]


@app.get("/api/garages")
def list_garages(
    city: str | None = None,
    department: str | None = None,
    specialty: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
):
    query = select(models.Garage).where(models.Garage.is_public.is_(True))

    if city:
        query = query.where(func.lower(models.Garage.city) == city.lower())

    if department:
        query = query.where(models.Garage.department == department)

    if specialty:
        query = query.where(func.lower(models.Garage.specialties).contains(specialty.lower()))

    if q:
        search = q.lower()
        query = query.where(
            func.lower(models.Garage.name).contains(search)
            | func.lower(models.Garage.description).contains(search)
            | func.lower(models.Garage.specialties).contains(search)
            | func.lower(models.Garage.brands).contains(search)
        )

    garages = db.scalars(
        query.order_by(models.Garage.rating.desc(), models.Garage.name)
    ).all()
    return [garage_to_dict(garage) for garage in garages]


@app.post("/api/assistant/diagnose")
async def assistant_diagnose(
    payload: schemas.AssistantMessageIn,
    db: Session = Depends(get_db),
):
    # Un ancien symptôme n'est repris que lorsqu'il s'agit clairement d'une réponse
    # de suivi courte. Cela évite qu'un nouveau sujet hérite d'un diagnostic précédent.
    context = prepare_conversation_message(payload.message, payload.history)
    garages = db.scalars(
        select(models.Garage)
        .where(models.Garage.is_public.is_(True))
        .order_by(models.Garage.rating.desc())
    ).all()

    diagnosis = build_diagnosis(
        message=context,
        garages=list(garages),
        make=payload.vehicle_make,
        model=payload.vehicle_model,
        year=payload.vehicle_year,
        location=payload.location,
        user_lat=payload.lat,
        user_lng=payload.lng,
    )

    return await enhance_diagnosis(
        base=diagnosis,
        message=context,
        history=payload.history,
        make=payload.vehicle_make,
        model=payload.vehicle_model,
        year=payload.vehicle_year,
        location=payload.location,
    )


@app.get("/api/assistant/status")
def assistant_status():
    return {
        "mode": "hybrid-groq" if ai_is_configured() else "rules-fallback",
        "configured": ai_is_configured(),
        "model": configured_model() if ai_is_configured() else None,
        "guardrails": "deterministic",
    }


@app.get("/api/garages/{garage_id}")
def get_garage(garage_id: int, db: Session = Depends(get_db)):
    garage = db.get(models.Garage, garage_id)
    if not garage or not garage.is_public:
        raise HTTPException(status_code=404, detail="Garage introuvable")

    result = garage_to_dict(garage)
    result["services"] = [
        {
            "id": service.id,
            "name": service.name,
            "description": service.description,
            "price": service.price,
            "duration_minutes": service.duration_minutes,
            "price_label": service.price_label,
            "bookable": service.bookable,
            "source_url": service.source_url,
        }
        for service in garage.services
    ]
    return result


@app.post("/api/garages", status_code=201)
def create_garage(
    payload: schemas.GarageIn,
    user: models.User = Depends(require_roles("GARAGE", "ADMIN")),
    db: Session = Depends(get_db),
):
    existing = db.scalar(
        select(models.Garage).where(models.Garage.slug == payload.slug)
    )
    if existing:
        raise HTTPException(status_code=409, detail="Slug déjà utilisé")

    garage = models.Garage(
        owner_id=user.id,
        verified=user.role == "ADMIN",
        listing_status="CLAIMED_PARTNER" if user.role == "ADMIN" else "PENDING_VERIFICATION",
        booking_enabled=True,
        is_public=user.role == "ADMIN",
        **payload.model_dump(),
    )
    db.add(garage)
    db.commit()
    db.refresh(garage)

    add_audit_log(db, user.id, "CREATE", "garage", str(garage.id))
    return {"id": garage.id, "slug": garage.slug}


@app.patch("/api/garages/{garage_id}")
def update_garage(
    garage_id: int,
    payload: schemas.GarageUpdateIn,
    user: models.User = Depends(require_roles("GARAGE", "ADMIN")),
    db: Session = Depends(get_db),
):
    garage = db.get(models.Garage, garage_id)
    if not garage:
        raise HTTPException(status_code=404, detail="Garage introuvable")

    if user.role != "ADMIN" and garage.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Ce garage ne vous appartient pas")

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        if isinstance(value, str):
            value = value.strip()
        setattr(garage, field, value)

    db.commit()
    db.refresh(garage)
    add_audit_log(db, user.id, "UPDATE", "garage", str(garage.id))
    return garage_to_dict(garage)


@app.post("/api/services", status_code=201)
def create_service(
    payload: schemas.ServiceIn,
    user: models.User = Depends(require_roles("GARAGE", "ADMIN")),
    db: Session = Depends(get_db),
):
    garage = db.get(models.Garage, payload.garage_id)
    if not garage:
        raise HTTPException(status_code=404, detail="Garage introuvable")

    if user.role != "ADMIN" and garage.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Ce garage ne vous appartient pas")

    service = models.Service(**payload.model_dump())
    db.add(service)
    db.commit()
    db.refresh(service)

    add_audit_log(db, user.id, "CREATE", "service", str(service.id))
    return {"id": service.id}


@app.patch("/api/services/{service_id}")
def update_service(
    service_id: int,
    payload: schemas.ServiceUpdateIn,
    user: models.User = Depends(require_roles("GARAGE", "ADMIN")),
    db: Session = Depends(get_db),
):
    service = db.get(models.Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Prestation introuvable")

    if user.role != "ADMIN" and service.garage.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Cette prestation ne vous appartient pas")

    for field, value in payload.model_dump(exclude_unset=True).items():
        if isinstance(value, str):
            value = value.strip()
        setattr(service, field, value)

    db.commit()
    db.refresh(service)
    add_audit_log(db, user.id, "UPDATE", "service", str(service.id))
    return {
        "id": service.id,
        "name": service.name,
        "description": service.description,
        "price": service.price,
        "duration_minutes": service.duration_minutes,
    }


@app.delete("/api/services/{service_id}", status_code=204)
def delete_service(
    service_id: int,
    user: models.User = Depends(require_roles("GARAGE", "ADMIN")),
    db: Session = Depends(get_db),
):
    service = db.get(models.Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Prestation introuvable")

    if user.role != "ADMIN" and service.garage.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Cette prestation ne vous appartient pas")

    booking_count = db.scalar(
        select(func.count(models.Booking.id)).where(models.Booking.service_id == service.id)
    ) or 0
    if booking_count:
        raise HTTPException(
            status_code=409,
            detail="Cette prestation possède déjà des réservations et ne peut pas être supprimée",
        )

    db.delete(service)
    db.commit()
    add_audit_log(db, user.id, "DELETE", "service", str(service_id))
    return Response(status_code=204)


@app.post("/api/availability", status_code=201)
def create_availability(
    payload: schemas.SlotIn,
    user: models.User = Depends(require_roles("GARAGE", "ADMIN")),
    db: Session = Depends(get_db),
):
    garage = db.get(models.Garage, payload.garage_id)
    if not garage:
        raise HTTPException(status_code=404, detail="Garage introuvable")

    if user.role != "ADMIN" and garage.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Ce garage ne vous appartient pas")

    if payload.ends_at <= payload.starts_at:
        raise HTTPException(status_code=400, detail="Créneau invalide")

    slot = models.Availability(**payload.model_dump())
    db.add(slot)

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Créneau déjà existant") from exc

    db.refresh(slot)
    return {
        "id": slot.id,
        "starts_at": slot.starts_at,
        "ends_at": slot.ends_at,
    }


@app.delete("/api/availability/{slot_id}", status_code=204)
def delete_availability(
    slot_id: int,
    user: models.User = Depends(require_roles("GARAGE", "ADMIN")),
    db: Session = Depends(get_db),
):
    slot = db.get(models.Availability, slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Créneau introuvable")

    if user.role != "ADMIN" and slot.garage.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Ce créneau ne vous appartient pas")

    if slot.is_booked:
        raise HTTPException(
            status_code=409,
            detail="Un créneau réservé ne peut pas être supprimé",
        )

    db.delete(slot)
    db.commit()
    add_audit_log(db, user.id, "DELETE", "availability", str(slot_id))
    return Response(status_code=204)


@app.get("/api/availability")
def list_availability(garage_id: int, db: Session = Depends(get_db)):
    garage = db.get(models.Garage, garage_id)
    if not garage or not garage.booking_enabled:
        return []

    # Tolérance de cinq minutes pour éviter qu'un petit décalage d'horloge masque un créneau.
    now = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5)

    slots = db.scalars(
        select(models.Availability)
        .where(
            models.Availability.garage_id == garage_id,
            models.Availability.starts_at >= now,
            models.Availability.is_booked.is_(False),
        )
        .order_by(models.Availability.starts_at)
    ).all()

    return [
        {
            "id": slot.id,
            "starts_at": slot.starts_at,
            "ends_at": slot.ends_at,
        }
        for slot in slots
    ]


@app.post("/api/bookings", status_code=201)
def create_booking(
    payload: schemas.BookingIn,
    user: models.User = Depends(require_roles("USER", "ADMIN")),
    db: Session = Depends(get_db),
):
    slot = db.get(models.Availability, payload.slot_id)
    service = db.get(models.Service, payload.service_id)

    if not slot or not service:
        raise HTTPException(status_code=404, detail="Créneau ou prestation introuvable")

    if not service.bookable or not service.garage.booking_enabled:
        raise HTTPException(
            status_code=409,
            detail=(
                "Cette fiche est référencée publiquement mais ne prend pas encore "
                "de réservation directement sur MecaConnect"
            ),
        )

    if service.garage_id != slot.garage_id:
        raise HTTPException(
            status_code=400,
            detail="La prestation et le créneau ne correspondent pas",
        )

    if slot.is_booked:
        raise HTTPException(status_code=409, detail="Ce créneau n'est plus disponible")

    if payload.vehicle_id:
        vehicle = db.get(models.Vehicle, payload.vehicle_id)
        if not vehicle or vehicle.owner_id != user.id:
            raise HTTPException(status_code=403, detail="Véhicule invalide")

    slot.is_booked = True
    garage = service.garage
    payment_online_enabled = bool(garage.payment_online_enabled)
    deposit_rate = float(garage.deposit_rate or 0.20)
    deposit = round(service.price * deposit_rate, 2) if payment_online_enabled else 0.0

    booking = models.Booking(
        user_id=user.id,
        vehicle_id=payload.vehicle_id,
        service_id=service.id,
        slot_id=slot.id,
        total_amount=service.price,
        deposit_amount=deposit,
        status="PENDING_PAYMENT" if payment_online_enabled else "CONFIRMED",
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)

    add_audit_log(db, user.id, "CREATE", "booking", str(booking.id))
    return {
        "id": booking.id,
        "status": booking.status,
        "total_amount": booking.total_amount,
        "deposit_amount": booking.deposit_amount,
        "payment_required": payment_online_enabled,
        "deposit_rate": deposit_rate if payment_online_enabled else 0,
    }




@app.patch("/api/bookings/{booking_id}/cancel")
def cancel_own_booking(
    booking_id: int,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    booking = db.get(models.Booking, booking_id)
    if not booking or (booking.user_id != user.id and user.role != "ADMIN"):
        raise HTTPException(status_code=404, detail="Réservation introuvable")
    if booking.status in {"COMPLETED", "CANCELLED"}:
        raise HTTPException(status_code=409, detail="Cette réservation ne peut plus être annulée")
    booking.status = "CANCELLED"
    booking.slot.is_booked = False
    db.commit()
    add_audit_log(db, user.id, "CANCEL", "booking", str(booking.id))
    return {
        "id": booking.id,
        "status": booking.status,
        "refund_note": (
            "Si un acompte a déjà été payé, son éventuel remboursement doit être traité "
            "selon les conditions du garage et le moyen de paiement."
        ),
    }


@app.patch("/api/bookings/{booking_id}/reschedule")
def reschedule_own_booking(
    booking_id: int,
    payload: schemas.BookingRescheduleIn,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    booking = db.get(models.Booking, booking_id)
    if not booking or (booking.user_id != user.id and user.role != "ADMIN"):
        raise HTTPException(status_code=404, detail="Réservation introuvable")
    if booking.status not in {"PENDING_PAYMENT", "CONFIRMED"}:
        raise HTTPException(status_code=409, detail="Cette réservation ne peut plus être modifiée")

    new_slot = db.get(models.Availability, payload.slot_id)
    if not new_slot:
        raise HTTPException(status_code=404, detail="Nouveau créneau introuvable")
    if new_slot.garage_id != booking.service.garage_id:
        raise HTTPException(status_code=400, detail="Le créneau appartient à un autre garage")
    if new_slot.is_booked and new_slot.id != booking.slot_id:
        raise HTTPException(status_code=409, detail="Ce créneau n'est plus disponible")

    old_slot = booking.slot
    if new_slot.id != old_slot.id:
        old_slot.is_booked = False
        new_slot.is_booked = True
        booking.slot_id = new_slot.id
    db.commit()
    add_audit_log(db, user.id, "RESCHEDULE", "booking", str(booking.id))
    return {"id": booking.id, "status": booking.status, "starts_at": new_slot.starts_at}


@app.get("/api/bookings/me")
def my_bookings(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bookings = db.scalars(
        select(models.Booking)
        .where(models.Booking.user_id == user.id)
        .order_by(models.Booking.created_at.desc())
    ).all()

    return [
        {
            "id": booking.id,
            "status": booking.status,
            "total_amount": booking.total_amount,
            "deposit_amount": booking.deposit_amount,
            "service": booking.service.name,
            "garage": booking.service.garage.name,
            "garage_id": booking.service.garage.id,
            "starts_at": booking.slot.starts_at,
            "payment_status": booking.payment.status if booking.payment else None,
        }
        for booking in bookings
    ]


@app.patch("/api/bookings/{booking_id}/status")
def update_booking_status(
    booking_id: int,
    payload: schemas.BookingStatusIn,
    user: models.User = Depends(require_roles("GARAGE", "ADMIN")),
    db: Session = Depends(get_db),
):
    booking = db.get(models.Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Réservation introuvable")

    garage = booking.service.garage
    if user.role != "ADMIN" and garage.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Cette réservation ne vous appartient pas")

    requested = payload.status
    if requested == booking.status:
        return {"id": booking.id, "status": booking.status}

    allowed_transitions = {
        "PENDING_PAYMENT": {"CANCELLED"},
        "CONFIRMED": {"COMPLETED", "CANCELLED"},
        "COMPLETED": set(),
        "CANCELLED": set(),
    }
    allowed = allowed_transitions.get(booking.status, set())
    if requested not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Passage de {booking.status} vers {requested} non autorisé",
        )

    booking.status = requested
    db.commit()
    add_audit_log(db, user.id, "UPDATE_STATUS", "booking", f"{booking.id}:{requested}")
    return {"id": booking.id, "status": booking.status}


@app.get("/api/garage/dashboard")
def garage_dashboard(
    user: models.User = Depends(require_roles("GARAGE", "ADMIN")),
    db: Session = Depends(get_db),
):
    query = select(models.Garage)
    if user.role != "ADMIN":
        query = query.where(models.Garage.owner_id == user.id)

    garages = db.scalars(query.order_by(models.Garage.name)).all()
    garage_ids = [garage.id for garage in garages]
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    bookings: list[dict] = []
    all_bookings: list[models.Booking] = []
    if garage_ids:
        booking_query = (
            select(models.Booking)
            .join(models.Service)
            .where(models.Service.garage_id.in_(garage_ids))
            .order_by(models.Booking.created_at.desc())
            .limit(100)
        )
        all_bookings = list(db.scalars(booking_query).all())
        for booking in all_bookings:
            vehicle = db.get(models.Vehicle, booking.vehicle_id) if booking.vehicle_id else None
            bookings.append(
                {
                    "id": booking.id,
                    "garage_id": booking.service.garage_id,
                    "garage": booking.service.garage.name,
                    "service": booking.service.name,
                    "status": booking.status,
                    "starts_at": booking.slot.starts_at,
                    "total_amount": booking.total_amount,
                    "deposit_amount": booking.deposit_amount,
                    "payment_status": booking.payment.status if booking.payment else None,
                    "customer": {
                        "name": booking.user.full_name,
                        "email": booking.user.email,
                    },
                    "vehicle": (
                        {
                            "make": vehicle.make,
                            "model": vehicle.model,
                            "year": vehicle.year,
                            "plate": vehicle.plate,
                        }
                        if vehicle
                        else None
                    ),
                }
            )

    garage_payload = []
    available_slots = 0
    service_count = 0
    for garage in garages:
        service_items = [
            {
                "id": service.id,
                "name": service.name,
                "description": service.description,
                "price": service.price,
                "duration_minutes": service.duration_minutes,
            }
            for service in sorted(garage.services, key=lambda item: item.name.lower())
        ]
        slot_items = [
            {
                "id": slot.id,
                "starts_at": slot.starts_at,
                "ends_at": slot.ends_at,
                "is_booked": slot.is_booked,
            }
            for slot in sorted(
                (slot for slot in garage.slots if slot.starts_at >= now),
                key=lambda item: item.starts_at,
            )[:80]
        ]
        service_count += len(service_items)
        available_slots += sum(1 for slot in slot_items if not slot["is_booked"])
        garage_payload.append(
            {
                "id": garage.id,
                "name": garage.name,
                "city": garage.city,
                "address": garage.address,
                "description": garage.description,
                "verified": garage.verified,
                "rating": garage.rating,
                "specialties": garage.specialties,
                "brands": garage.brands,
                "hourly_rate": garage.hourly_rate,
                "siret": garage.siret,
                "siren": garage.siren,
                "legal_name": garage.legal_name,
                "payment_online_enabled": garage.payment_online_enabled,
                "deposit_rate": garage.deposit_rate,
                "listing_status": garage.listing_status,
                "booking_enabled": garage.booking_enabled,
                "source_url": garage.source_url,
                "source_label": garage.source_label,
                "services": len(service_items),
                "service_items": service_items,
                "slot_items": slot_items,
            }
        )

    confirmed = sum(1 for booking in all_bookings if booking.status == "CONFIRMED")
    completed = sum(1 for booking in all_bookings if booking.status == "COMPLETED")
    upcoming = sum(
        1
        for booking in all_bookings
        if booking.status == "CONFIRMED" and booking.slot.starts_at >= now
    )
    deposits_received = round(
        sum(
            booking.deposit_amount
            for booking in all_bookings
            if booking.payment and booking.payment.status == "SUCCEEDED"
        ),
        2,
    )

    return {
        "stats": {
            "bookings": len(all_bookings),
            "confirmed": confirmed,
            "upcoming": upcoming,
            "completed": completed,
            "services": service_count,
            "available_slots": available_slots,
            "deposits_received": deposits_received,
        },
        "garages": garage_payload,
        "bookings": bookings,
    }


@app.post("/api/payments/{booking_id}/session")
async def create_payment_session(
    booking_id: int,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    booking = db.get(models.Booking, booking_id)
    if not booking or (booking.user_id != user.id and user.role != "ADMIN"):
        raise HTTPException(status_code=404, detail="Réservation introuvable")

    if not booking.service.garage.payment_online_enabled:
        return {"mode": "pay-at-garage", "amount": 0, "status": "NOT_REQUIRED"}

    if booking.payment and booking.payment.status == "SUCCEEDED":
        return {"status": "SUCCEEDED"}

    provider = get_payment_provider()
    result = await provider.create_test_payment(booking.id, booking.deposit_amount)

    payment = booking.payment or models.Payment(
        booking_id=booking.id,
        amount=booking.deposit_amount,
    )
    payment.provider_reference = result.get("provider_reference")
    payment.status = "CREATED"
    payment.provider = "STRIPE_TEST"

    db.add(payment)
    db.commit()

    add_audit_log(db, user.id, "PAYMENT_SESSION", "booking", str(booking.id))
    return {
        "payment_id": payment.id,
        "amount": payment.amount,
        **result,
    }


@app.post("/api/payments/test/{booking_id}/confirm")
def confirm_local_test_payment(
    booking_id: int,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    booking = db.get(models.Booking, booking_id)
    if not booking or (booking.user_id != user.id and user.role != "ADMIN"):
        raise HTTPException(status_code=404, detail="Réservation introuvable")

    if not booking.payment:
        raise HTTPException(status_code=400, detail="Session de paiement absente")

    booking.payment.status = "SUCCEEDED"
    booking.status = "CONFIRMED"
    db.commit()

    add_audit_log(db, user.id, "PAYMENT_SUCCEEDED", "booking", str(booking.id))
    return {
        "ok": True,
        "booking_status": booking.status,
        "payment_status": booking.payment.status,
    }


@app.get(
    "/api/payments/stripe/confirm",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def confirm_stripe_payment(
    session_id: str,
    db: Session = Depends(get_db),
):
    provider = get_payment_provider()

    if not isinstance(provider, StripeHttpProvider):
        raise HTTPException(
            status_code=400,
            detail="Stripe Test n'est pas configuré",
        )

    session = await provider.retrieve_session(session_id)

    booking_id = int(
        session.get("metadata", {}).get("booking_id", 0) or 0
    )

    booking = db.get(models.Booking, booking_id)

    if (
        not booking
        or not booking.payment
        or booking.payment.provider_reference != session_id
    ):
        raise HTTPException(
            status_code=404,
            detail="Paiement ou réservation introuvable",
        )

    if session.get("payment_status") != "paid":
        raise HTTPException(
            status_code=400,
            detail="Le paiement Stripe n'est pas confirmé",
        )

    booking.payment.status = "SUCCEEDED"
    booking.status = "CONFIRMED"
    db.commit()

    add_audit_log(
        db,
        booking.user_id,
        "PAYMENT_SUCCEEDED",
        "booking",
        str(booking.id),
    )

    redirect_url = (
        f"/mon-espace?payment=confirmed&booking_id={booking.id}"
    )

    return HTMLResponse(
        f"""
        <!doctype html>
        <html lang="fr">
        <head>
            <meta charset="utf-8">
            <meta
                name="viewport"
                content="width=device-width, initial-scale=1"
            >

            <meta
                http-equiv="refresh"
                content="6;url={redirect_url}"
            >

            <title>Paiement confirmé - MecaConnect</title>

            <style>
                * {{
                    box-sizing: border-box;
                }}

                body {{
                    margin: 0;
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    padding: 24px;
                    font-family:
                        Inter,
                        -apple-system,
                        BlinkMacSystemFont,
                        "Segoe UI",
                        sans-serif;
                    background:
                        radial-gradient(
                            circle at top left,
                            rgba(244, 122, 86, 0.20),
                            transparent 35%
                        ),
                        linear-gradient(
                            135deg,
                            #f7f4ef 0%,
                            #eef4f5 100%
                        );
                    color: #173f52;
                }}

                .payment-card {{
                    width: min(100%, 620px);
                    padding: 48px;
                    text-align: center;
                    background: white;
                    border-radius: 28px;
                    box-shadow:
                        0 24px 70px
                        rgba(15, 46, 61, 0.14);
                }}

                .success-icon {{
                    width: 84px;
                    height: 84px;
                    margin: 0 auto 24px;
                    display: grid;
                    place-items: center;
                    border-radius: 50%;
                    background: #e9f8ef;
                    color: #18864b;
                    font-size: 44px;
                    font-weight: 900;
                }}

                .eyebrow {{
                    display: inline-block;
                    margin-bottom: 12px;
                    color: #f47a56;
                    font-size: 13px;
                    font-weight: 800;
                    letter-spacing: .12em;
                    text-transform: uppercase;
                }}

                h1 {{
                    margin: 0 0 14px;
                    font-size: 40px;
                    line-height: 1.1;
                }}

                .description {{
                    max-width: 490px;
                    margin: 0 auto 28px;
                    color: #63727a;
                    font-size: 17px;
                    line-height: 1.6;
                }}

                .booking {{
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    gap: 20px;
                    padding: 18px 20px;
                    margin-bottom: 28px;
                    text-align: left;
                    background: #f6f8f8;
                    border-radius: 16px;
                }}

                .booking-label {{
                    display: block;
                    margin-bottom: 4px;
                    color: #7b878d;
                    font-size: 13px;
                }}

                .booking-id {{
                    font-size: 19px;
                    font-weight: 800;
                }}

                .status {{
                    padding: 8px 13px;
                    color: #18864b;
                    background: #e9f8ef;
                    border-radius: 999px;
                    font-size: 12px;
                    font-weight: 900;
                }}

                .redirect-text {{
                    margin: 20px 0;
                    color: #63727a;
                }}

                .countdown {{
                    position: relative;
                    display: inline-block;
                    width: 25px;
                    height: 25px;
                    color: #173f52;
                    font-size: 20px;
                    font-weight: 900;
                    vertical-align: middle;
                }}

                .countdown span {{
                    position: absolute;
                    inset: 0;
                    opacity: 0;
                }}

                .n6 {{
                    animation: number 1s 0s linear;
                }}

                .n5 {{
                    animation: number 1s 1s linear;
                }}

                .n4 {{
                    animation: number 1s 2s linear;
                }}

                .n3 {{
                    animation: number 1s 3s linear;
                }}

                .n2 {{
                    animation: number 1s 4s linear;
                }}

                .n1 {{
                    animation: number 1s 5s linear;
                }}

                @keyframes number {{
                    0%, 99% {{
                        opacity: 1;
                    }}

                    100% {{
                        opacity: 0;
                    }}
                }}

                .button {{
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    min-height: 50px;
                    padding: 0 25px;
                    color: white;
                    background: #173f52;
                    border-radius: 13px;
                    text-decoration: none;
                    font-weight: 800;
                }}

                .button:hover {{
                    background: #102e3c;
                }}

                .secure {{
                    margin-top: 22px;
                    color: #899399;
                    font-size: 12px;
                }}

                @media (max-width: 600px) {{
                    .payment-card {{
                        padding: 34px 22px;
                    }}

                    .booking {{
                        align-items: flex-start;
                        flex-direction: column;
                    }}

                    h1 {{
                        font-size: 32px;
                    }}
                }}
            </style>
        </head>

        <body>
            <main class="payment-card">

                <div class="success-icon">
                    ✓
                </div>

                <div class="eyebrow">
                    Paiement sécurisé
                </div>

                <h1>
                    Paiement confirmé
                </h1>

                <p class="description">
                    Votre acompte a bien été validé.
                    Votre réservation est maintenant
                    confirmée auprès du garage.
                </p>

                <div class="booking">
                    <div>
                        <span class="booking-label">
                            Réservation
                        </span>

                        <span class="booking-id">
                            #{booking.id}
                        </span>
                    </div>

                    <span class="status">
                        CONFIRMÉE
                    </span>
                </div>

                <p class="redirect-text">
                    Redirection vers vos réservations dans

                    <span class="countdown">
                        <span class="n6">6</span>
                        <span class="n5">5</span>
                        <span class="n4">4</span>
                        <span class="n3">3</span>
                        <span class="n2">2</span>
                        <span class="n1">1</span>
                    </span>

                    secondes
                </p>

                <a
                    class="button"
                    href="{redirect_url}"
                >
                    Voir ma réservation
                </a>

                <p class="secure">
                    Paiement traité de manière sécurisée
                    par Stripe.
                </p>

            </main>
        </body>
        </html>
        """
    )

@app.post("/api/newsletter/request", status_code=201)
def newsletter_request(
    payload: schemas.NewsletterIn,
    db: Session = Depends(get_db),
):
    email = payload.email.lower()
    subscription = db.scalar(
        select(models.NewsletterSubscription).where(
            models.NewsletterSubscription.email == email
        )
    )

    if subscription and subscription.confirmed:
        return {"status": "already_confirmed"}

    token = secrets.token_urlsafe(24)
    if subscription:
        subscription.token = token
    else:
        db.add(models.NewsletterSubscription(email=email, token=token))

    db.commit()
    return {
        "status": "confirmation_required",
        # En production, ce lien serait envoyé par e-mail.
        "confirmation_path": f"/api/newsletter/confirm/{token}",
    }


@app.get("/api/newsletter/confirm/{token}")
def newsletter_confirm(token: str, db: Session = Depends(get_db)):
    subscription = db.scalar(
        select(models.NewsletterSubscription).where(
            models.NewsletterSubscription.token == token
        )
    )
    if not subscription:
        raise HTTPException(status_code=404, detail="Lien invalide")

    subscription.confirmed = True
    db.commit()
    return {"status": "confirmed"}


@app.get("/api/privacy/export")
def privacy_export(
    user: models.User = Depends(get_current_user),
):
    return {
        "profile": {
            "email": user.email,
            "full_name": user.full_name,
            "phone": decrypt_text(user.phone_encrypted),
            "role": user.role,
        },
        "vehicles": [
            {
                "make": vehicle.make,
                "model": vehicle.model,
                "year": vehicle.year,
                "plate": vehicle.plate,
            }
            for vehicle in user.vehicles
        ],
        "bookings": [
            {
                "id": booking.id,
                "status": booking.status,
                "total_amount": booking.total_amount,
                "created_at": booking.created_at.isoformat(),
            }
            for booking in user.bookings
        ],
    }


@app.delete("/api/privacy/account", status_code=204)
def privacy_delete_account(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    has_any_booking = bool(user.bookings)

    if has_any_booking:
        # Les réservations restent traçables mais le compte est anonymisé.
        user.full_name = "Compte supprimé"
        user.email = f"deleted-{user.id}-{secrets.token_hex(6)}@invalid.local"
        user.phone_encrypted = None
        user.password_hash = hash_password(secrets.token_urlsafe(32))
        user.is_active = False
    else:
        db.delete(user)

    db.commit()
    return Response(status_code=204)


@app.post("/api/analytics/event", status_code=204)
async def analytics_event(
    request: Request,
    db: Session = Depends(get_db),
):
    body = await request.json()
    event = str(body.get("event", ""))[:80]
    path = str(body.get("path", ""))[:255]

    if not event:
        raise HTTPException(status_code=400, detail="Événement manquant")

    db.add(models.AnalyticsEvent(event=event, path=path))
    db.commit()
    return Response(status_code=204)


@app.get("/api/admin/stats")
def admin_stats(
    user: models.User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
):
    return {
        "users": db.scalar(select(func.count()).select_from(models.User)),
        "garages": db.scalar(
            select(func.count())
            .select_from(models.Garage)
            .where(models.Garage.is_public.is_(True))
        ),
        "bookings": db.scalar(select(func.count()).select_from(models.Booking)),
        "payments_succeeded": db.scalar(
            select(func.count())
            .select_from(models.Payment)
            .where(models.Payment.status == "SUCCEEDED")
        ),
        "analytics_events": db.scalar(
            select(func.count()).select_from(models.AnalyticsEvent)
        ),
    }


LOCAL_FRONT_DIR = Path(__file__).resolve().parents[2] / "frontend" / "public"
DOCKER_FRONT_DIR = Path(__file__).resolve().parents[1] / "frontend" / "public"
FRONT_DIR = DOCKER_FRONT_DIR if DOCKER_FRONT_DIR.exists() else LOCAL_FRONT_DIR
if FRONT_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONT_DIR)), name="assets")


def render_frontend() -> HTMLResponse:
    index_file = FRONT_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h1>MecaConnect API</h1>")

    html = index_file.read_text(encoding="utf-8")
    html = html.replace("__APP_BASE_URL__", APP_BASE_URL)
    return HTMLResponse(html)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def frontend_root():
    return render_frontend()


@app.get("/mecabot", response_class=HTMLResponse, include_in_schema=False)
@app.get("/garages", response_class=HTMLResponse, include_in_schema=False)
@app.get("/garages/{garage_id:int}", response_class=HTMLResponse, include_in_schema=False)
@app.get("/connexion", response_class=HTMLResponse, include_in_schema=False)
@app.get("/mon-espace", response_class=HTMLResponse, include_in_schema=False)
@app.get("/espace-garage", response_class=HTMLResponse, include_in_schema=False)
@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
@app.get("/fonctionnement", response_class=HTMLResponse, include_in_schema=False)
@app.get("/professionnels", response_class=HTMLResponse, include_in_schema=False)
def frontend_page(garage_id: int | None = None):
    return render_frontend()


@app.get("/mentions-legales", response_class=HTMLResponse, include_in_schema=False)
def legal_notice():
    return HTMLResponse((FRONT_DIR / "legal.html").read_text(encoding="utf-8"))


@app.get("/confidentialite", response_class=HTMLResponse, include_in_schema=False)
def privacy_page():
    return HTMLResponse((FRONT_DIR / "privacy.html").read_text(encoding="utf-8"))


@app.get("/cgu", response_class=HTMLResponse, include_in_schema=False)
def terms_page():
    return HTMLResponse((FRONT_DIR / "terms.html").read_text(encoding="utf-8"))


@app.get("/cgv", response_class=HTMLResponse, include_in_schema=False)
def sales_terms_page():
    return HTMLResponse((FRONT_DIR / "sales-terms.html").read_text(encoding="utf-8"))


@app.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
def robots():
    return PlainTextResponse(
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        f"Sitemap: {APP_BASE_URL}/sitemap.xml\n"
    )


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap():
    public_paths = ("/", "/garages", "/mecabot", "/fonctionnement", "/professionnels")
    entries = "\n".join(
        f"  <url><loc>{APP_BASE_URL}{path}</loc><changefreq>weekly</changefreq>"
        f"<priority>{'1.0' if path == '/' else '0.8'}</priority></url>"
        for path in public_paths
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}\n"
        "</urlset>"
    )
    return Response(content=xml, media_type="application/xml")
