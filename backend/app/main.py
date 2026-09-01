import logging
import os
import secrets
import time
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
from .database import Base, engine, get_db
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

# Limiteur volontairement simple pour le prototype : 120 requêtes par minute et par IP.
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

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(self), camera=(), microphone=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' data: https:; "
        "style-src 'self' 'unsafe-inline' https://api.mapbox.com; "
        "script-src 'self' https://api.mapbox.com; "
        "connect-src 'self' https://*.mapbox.com https://api.stripe.com; "
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
    """Enregistre une action utile pour les contrôles et le suivi du prototype."""
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
    }


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "mecaconnect-api",
        "time": datetime.now(timezone.utc).isoformat(),
    }


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
    query = select(models.Garage)

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
    garages = db.scalars(select(models.Garage).order_by(models.Garage.rating.desc())).all()

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
        "mode": "hybrid-openai" if ai_is_configured() else "rules-fallback",
        "configured": ai_is_configured(),
        "model": configured_model() if ai_is_configured() else None,
        "guardrails": "deterministic",
    }


@app.get("/api/garages/{garage_id}")
def get_garage(garage_id: int, db: Session = Depends(get_db)):
    garage = db.get(models.Garage, garage_id)
    if not garage:
        raise HTTPException(status_code=404, detail="Garage introuvable")

    result = garage_to_dict(garage)
    result["services"] = [
        {
            "id": service.id,
            "name": service.name,
            "description": service.description,
            "price": service.price,
            "duration_minutes": service.duration_minutes,
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
        **payload.model_dump(),
    )
    db.add(garage)
    db.commit()
    db.refresh(garage)

    add_audit_log(db, user.id, "CREATE", "garage", str(garage.id))
    return {"id": garage.id, "slug": garage.slug}


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


@app.get("/api/availability")
def list_availability(garage_id: int, db: Session = Depends(get_db)):
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
    deposit = round(service.price * 0.20, 2)

    booking = models.Booking(
        user_id=user.id,
        vehicle_id=payload.vehicle_id,
        service_id=service.id,
        slot_id=slot.id,
        total_amount=service.price,
        deposit_amount=deposit,
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
    }


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
            "starts_at": booking.slot.starts_at,
            "payment_status": booking.payment.status if booking.payment else None,
        }
        for booking in bookings
    ]


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

    bookings = []
    if garage_ids:
        booking_query = (
            select(models.Booking)
            .join(models.Service)
            .where(models.Service.garage_id.in_(garage_ids))
            .order_by(models.Booking.created_at.desc())
            .limit(25)
        )
        for booking in db.scalars(booking_query).all():
            bookings.append(
                {
                    "id": booking.id,
                    "garage": booking.service.garage.name,
                    "service": booking.service.name,
                    "status": booking.status,
                    "starts_at": booking.slot.starts_at,
                    "deposit_amount": booking.deposit_amount,
                }
            )

    return {
        "garages": [
            {
                "id": garage.id,
                "name": garage.name,
                "city": garage.city,
                "verified": garage.verified,
                "services": len(garage.services),
            }
            for garage in garages
        ],
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
        raise HTTPException(status_code=400, detail="Stripe Test n'est pas configuré")

    session = await provider.retrieve_session(session_id)
    booking_id = int(session.get("metadata", {}).get("booking_id", 0) or 0)
    booking = db.get(models.Booking, booking_id)

    if (
        not booking
        or not booking.payment
        or booking.payment.provider_reference != session_id
    ):
        raise HTTPException(status_code=404, detail="Paiement ou réservation introuvable")

    if session.get("payment_status") != "paid":
        raise HTTPException(status_code=400, detail="Le paiement Stripe n'est pas confirmé")

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

    return HTMLResponse(
        """
        <!doctype html>
        <html lang="fr">
          <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width,initial-scale=1">
            <title>Paiement confirmé - MecaConnect</title>
          </head>
          <body>
            <main>
              <h1>Paiement confirmé</h1>
              <p>Votre acompte a été validé et la réservation est confirmée.</p>
              <p><a href="/">Retour à MecaConnect</a></p>
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
    has_completed_booking = any(
        booking.status in {"CONFIRMED", "COMPLETED"}
        for booking in user.bookings
    )

    if has_completed_booking:
        # On conserve les réservations nécessaires au suivi tout en anonymisant le compte.
        user.full_name = "Compte supprimé"
        user.phone_encrypted = None
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
        "garages": db.scalar(select(func.count()).select_from(models.Garage)),
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
    html = html.replace("__MAPBOX_TOKEN__", os.getenv("MAPBOX_TOKEN", ""))
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
