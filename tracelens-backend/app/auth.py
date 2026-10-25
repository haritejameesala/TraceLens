"""Email/password authentication and signed bearer tokens for TraceLens."""
import base64, hashlib, hmac, json, os, secrets, time
from app.config import settings
from fastapi import HTTPException

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

def password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310000)
    return f"{_b64(salt)}${_b64(digest)}"

def verify_password(password: str, encoded: str) -> bool:
    try:
        salt_s, digest_s = encoded.split("$", 1)
        expected = _unb64(digest_s)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), _unb64(salt_s), 310000)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False

def _secret() -> bytes:
    value = settings.auth_secret or os.getenv("TRACELENS_AUTH_SECRET", "")
    if len(value) < 32:
        raise HTTPException(503, "Authentication is not configured: set TRACELENS_AUTH_SECRET to a random secret of at least 32 characters.")
    return value.encode()

def issue_token(user: dict) -> str:
    now = int(time.time())
    payload = {"sub": user["user_id"], "email": user["email"], "iat": now, "exp": now + 60*60*24*7}
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
    return body + "." + sig

def read_token(token: str) -> dict:
    try:
        body, signature = token.split(".", 1)
        expected = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("signature")
        payload = json.loads(_unb64(body))
        if int(payload["exp"]) < int(time.time()):
            raise ValueError("expired")
        return payload
    except Exception:
        raise HTTPException(401, "Invalid or expired session. Please sign in again.")
