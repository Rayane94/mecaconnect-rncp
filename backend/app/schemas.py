from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=30)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        groups = [
            any(char.islower() for char in value),
            any(char.isupper() for char in value),
            any(char.isdigit() for char in value),
            any(not char.isalnum() for char in value),
        ]
        if sum(groups) < 3:
            raise ValueError(
                "Le mot de passe doit combiner au moins trois catégories de caractères"
            )
        return value


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    totp_code: str | None = None


class VehicleIn(BaseModel):
    make: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=80)
    year: int = Field(ge=1950, le=2100)
    plate: str | None = Field(default=None, max_length=24)


class GarageIn(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    slug: str = Field(pattern=r"^[a-z0-9-]+$")
    city: str = Field(min_length=2, max_length=100)
    address: str = Field(min_length=5, max_length=255)
    description: str = Field(min_length=20, max_length=2000)
    lat: float | None = None
    lng: float | None = None


class ServiceIn(BaseModel):
    garage_id: int
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    price: float = Field(gt=0, le=10000)
    duration_minutes: int = Field(ge=15, le=1440)


class SlotIn(BaseModel):
    garage_id: int
    starts_at: datetime
    ends_at: datetime


class BookingIn(BaseModel):
    service_id: int
    slot_id: int
    vehicle_id: int | None = None


class ReviewIn(BaseModel):
    booking_id: int
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1500)


class NewsletterIn(BaseModel):
    email: EmailStr


class AssistantMessageIn(BaseModel):
    message: str = Field(min_length=3, max_length=2000)
    location: str | None = Field(default=None, max_length=100)
    vehicle_make: str | None = Field(default=None, max_length=80)
    vehicle_model: str | None = Field(default=None, max_length=80)
    vehicle_year: int | None = Field(default=None, ge=1950, le=2100)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    history: list[str] = Field(default_factory=list, max_length=10)
