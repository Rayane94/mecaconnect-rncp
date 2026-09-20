from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


def utc_now() -> datetime:
    """Retourne une date UTC sans timezone pour rester compatible SQLite/PostgreSQL."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(512), nullable=False)
    full_name = Column(String(120), nullable=False)
    role = Column(String(20), default="USER", nullable=False)
    phone_encrypted = Column(Text, nullable=True)
    totp_secret = Column(String(128), nullable=True)
    two_factor_enabled = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)

    vehicles = relationship(
        "Vehicle",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    bookings = relationship("Booking", back_populates="user")


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True)
    owner_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    make = Column(String(80), nullable=False)
    model = Column(String(80), nullable=False)
    year = Column(Integer, nullable=False)
    plate = Column(String(24), nullable=True)
    motorization = Column(String(80), nullable=True)

    owner = relationship("User", back_populates="vehicles")


class Garage(Base):
    __tablename__ = "garages"

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String(150), nullable=False, index=True)
    slug = Column(String(160), unique=True, index=True, nullable=False)
    city = Column(String(100), index=True, nullable=False)
    address = Column(String(255), nullable=False)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    description = Column(Text, nullable=False)
    verified = Column(Boolean, default=False)
    rating = Column(Float, default=0.0)
    department = Column(String(8), nullable=True, index=True)
    postal_code = Column(String(10), nullable=True)
    specialties = Column(Text, default="multimarque,entretien", nullable=False)
    brands = Column(Text, default="multimarque", nullable=False)
    hourly_rate = Column(Float, nullable=True)
    siret = Column(String(14), unique=True, index=True, nullable=True)
    siren = Column(String(9), index=True, nullable=True)
    legal_name = Column(String(180), nullable=True)
    verification_source = Column(String(80), nullable=True)
    payment_online_enabled = Column(Boolean, default=True, nullable=False)
    deposit_rate = Column(Float, default=0.20, nullable=False)
    phone = Column(String(40), nullable=True)
    website_url = Column(String(500), nullable=True)
    photo_url = Column(String(700), nullable=True)
    photo_source_url = Column(String(700), nullable=True)
    source_url = Column(String(700), nullable=True)
    source_label = Column(String(160), nullable=True)
    listing_status = Column(String(32), default="PUBLIC_REFERENCE", nullable=False)
    booking_enabled = Column(Boolean, default=False, nullable=False)
    is_public = Column(Boolean, default=True, nullable=False)
    source_verified_at = Column(DateTime, nullable=True)

    services = relationship(
        "Service",
        back_populates="garage",
        cascade="all, delete-orphan",
    )
    slots = relationship(
        "Availability",
        back_populates="garage",
        cascade="all, delete-orphan",
    )


class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True)
    garage_id = Column(
        Integer,
        ForeignKey("garages.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    duration_minutes = Column(Integer, default=60)
    price_label = Column(String(120), nullable=True)
    bookable = Column(Boolean, default=True, nullable=False)
    source_url = Column(String(700), nullable=True)

    garage = relationship("Garage", back_populates="services")


class Availability(Base):
    __tablename__ = "availability"

    id = Column(Integer, primary_key=True)
    garage_id = Column(
        Integer,
        ForeignKey("garages.id", ondelete="CASCADE"),
        nullable=False,
    )
    starts_at = Column(DateTime, index=True, nullable=False)
    ends_at = Column(DateTime, nullable=False)
    is_booked = Column(Boolean, default=False, nullable=False)

    garage = relationship("Garage", back_populates="slots")

    __table_args__ = (
        UniqueConstraint("garage_id", "starts_at", name="uq_garage_slot"),
    )


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    slot_id = Column(
        Integer,
        ForeignKey("availability.id"),
        nullable=False,
        unique=True,
    )
    status = Column(String(24), default="PENDING_PAYMENT", nullable=False)
    total_amount = Column(Float, nullable=False)
    deposit_amount = Column(Float, nullable=False)
    created_at = Column(DateTime, default=utc_now)

    user = relationship("User", back_populates="bookings")
    service = relationship("Service")
    slot = relationship("Availability")
    payment = relationship(
        "Payment",
        back_populates="booking",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    booking_id = Column(
        Integer,
        ForeignKey("bookings.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    provider = Column(String(30), default="STRIPE_TEST")
    provider_reference = Column(String(120), nullable=True)
    amount = Column(Float, nullable=False)
    status = Column(String(24), default="CREATED", nullable=False)
    created_at = Column(DateTime, default=utc_now)

    booking = relationship("Booking", back_populates="payment")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    garage_id = Column(Integer, ForeignKey("garages.id"), nullable=False)
    booking_id = Column(Integer, ForeignKey("bookings.id"), unique=True, nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)


class NewsletterSubscription(Base):
    __tablename__ = "newsletter_subscriptions"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    token = Column(String(128), unique=True, nullable=False)
    confirmed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=True)
    action = Column(String(120), nullable=False)
    resource = Column(String(120), nullable=True)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, index=True)


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id = Column(Integer, primary_key=True)
    event = Column(String(80), nullable=False, index=True)
    path = Column(String(255), nullable=True)
    user_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=utc_now, index=True)
