import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
from datetime import datetime, timedelta, timezone

import jwt
from cryptography.fernet import Fernet, InvalidToken


JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-change-me")
JWT_ALGORITHM = "HS256"

FERNET_KEY = os.getenv("FERNET_KEY") or Fernet.generate_key().decode()
fernet = Fernet(FERNET_KEY.encode())


def hash_password(password: str) -> str:
    """Hash le mot de passe avec Scrypt et un sel aléatoire."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=64,
    )
    salt_b64 = base64.b64encode(salt).decode()
    digest_b64 = base64.b64encode(digest).decode()
    return f"scrypt${salt_b64}${digest_b64}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        kind, salt_b64, digest_b64 = encoded.split("$", 2)
        if kind != "scrypt":
            return False

        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.scrypt(
            password.encode(),
            salt=salt,
            n=2**14,
            r=8,
            p=1,
            dklen=len(expected),
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: int, role: str, minutes: int = 60) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


def encrypt_text(value: str | None) -> str | None:
    if not value:
        return None
    return fernet.encrypt(value.encode()).decode()


def decrypt_text(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return fernet.decrypt(value.encode()).decode()
    except InvalidToken:
        return None


def generate_totp_secret() -> str:
    """Génère un secret TOTP compatible avec les applications d'authentification."""
    secret = base64.b32encode(secrets.token_bytes(20)).decode()
    return secret.rstrip("=")


def _totp(secret: str, counter: int, digits: int = 6) -> str:
    padded_secret = secret + "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(padded_secret, casefold=True)
    message = struct.pack(">Q", counter)
    digest = hmac.new(key, message, hashlib.sha1).digest()

    offset = digest[-1] & 0x0F
    binary_code = struct.unpack(">I", digest[offset : offset + 4])[0]
    code = (binary_code & 0x7FFFFFFF) % (10**digits)
    return str(code).zfill(digits)


def verify_totp(
    secret: str,
    code: str,
    now: int | None = None,
    window: int = 1,
) -> bool:
    if not code or not code.isdigit():
        return False

    current_time = int(now or time.time())
    counter = current_time // 30

    for step in range(-window, window + 1):
        if hmac.compare_digest(_totp(secret, counter + step), code):
            return True

    return False
