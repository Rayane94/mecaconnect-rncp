import time
from app.security import create_access_token, decode_access_token, generate_totp_secret, hash_password, verify_password, verify_totp, _totp

def test_password_hash_roundtrip():
    encoded=hash_password("StrongPassword-2026!"); assert "StrongPassword" not in encoded; assert verify_password("StrongPassword-2026!",encoded); assert not verify_password("wrong",encoded)

def test_jwt_roundtrip():
    token=create_access_token(42,"USER",minutes=5); payload=decode_access_token(token); assert payload["sub"]=="42"; assert payload["role"]=="USER"

def test_totp_roundtrip():
    secret=generate_totp_secret(); now=int(time.time()); code=_totp(secret,now//30); assert verify_totp(secret,code,now=now)
