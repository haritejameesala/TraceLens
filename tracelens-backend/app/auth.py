"""OAuth identity helpers for TraceLens.

Provider secrets stay server-side. The browser receives only an HttpOnly signed session cookie.
Set AUTH_MODE=oauth and configure provider credentials before deploying.
"""
from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, HTTPException, Request
from authlib.integrations.starlette_client import OAuth
from app.config import settings
from app.db import db
from app.models import make_id

router = APIRouter(prefix="/api/auth", tags=["authentication"])
oauth = OAuth()
if settings.google_client_id and settings.google_client_secret:
    oauth.register(
        name="google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
if settings.github_client_id and settings.github_client_secret:
    oauth.register(
        name="github",
        client_id=settings.github_client_id,
        client_secret=settings.github_client_secret,
        access_token_url="https://github.com/login/oauth/access_token",
        authorize_url="https://github.com/login/oauth/authorize",
        api_base_url="https://api.github.com/",
        client_kwargs={"scope": "read:user user:email"},
    )

def configured_providers() -> list[str]:
    providers = []
    if settings.google_client_id and settings.google_client_secret: providers.append("google")
    if settings.github_client_id and settings.github_client_secret: providers.append("github")
    return providers

@router.get("/status")
async def auth_status():
    enabled = settings.auth_mode.lower() == "oauth"
    return {"mode": settings.auth_mode.lower(), "enabled": enabled, "providers": configured_providers()}

@router.get("/me")
async def current_user(request: Request):
    identity = request.session.get("user")
    if settings.auth_mode.lower() != "oauth":
        return {"authenticated": True, "mode": "local", "user": {"user_id": "local", "name": "Local developer", "email": None}}
    if not identity:
        return {"authenticated": False, "mode": "oauth", "user": None}
    return {"authenticated": True, "mode": "oauth", "user": identity}

@router.get("/login/{provider}")
async def login(provider: str, request: Request):
    if settings.auth_mode.lower() != "oauth":
        raise HTTPException(400, "OAuth mode is not enabled")
    if provider not in configured_providers():
        raise HTTPException(404, "This OAuth provider is not configured")
    client = oauth.create_client(provider)
    redirect_uri = request.url_for("oauth_callback", provider=provider)
    return await client.authorize_redirect(request, redirect_uri)

@router.get("/callback/{provider}", name="oauth_callback")
async def oauth_callback(provider: str, request: Request):
    if provider not in configured_providers():
        raise HTTPException(404, "This OAuth provider is not configured")
    client = oauth.create_client(provider)
    token = await client.authorize_access_token(request)
    if provider == "google":
        profile = token.get("userinfo")
        if not profile:
            profile = await client.parse_id_token(request, token)
        subject = str(profile.get("sub", ""))
        email = profile.get("email")
        name = profile.get("name") or email or "Google user"
        picture = profile.get("picture")
        email_verified = bool(profile.get("email_verified", False))
    else:
        response = await client.get("user", token=token)
        response.raise_for_status()
        profile = response.json()
        subject = str(profile.get("id", ""))
        email = profile.get("email")
        if not email:
            emails_response = await client.get("user/emails", token=token)
            emails_response.raise_for_status()
            emails = emails_response.json()
            primary = next((item for item in emails if item.get("primary") and item.get("verified")), None)
            email = primary.get("email") if primary else None
        name = profile.get("name") or profile.get("login") or "GitHub user"
        picture = profile.get("avatar_url")
        email_verified = bool(email)
    if not subject:
        raise HTTPException(400, "OAuth provider did not return a stable user identifier")
    now = datetime.now(timezone.utc)
    existing = await db.users.find_one({"provider": provider, "provider_subject": subject})
    if existing:
        user_id = existing["user_id"]
        await db.users.update_one({"user_id": user_id}, {"$set": {
            "name": name, "email": email, "email_verified": email_verified,
            "picture": picture, "last_login_at": now, "updated_at": now,
        }})
    else:
        user_id = make_id("usr")
        await db.users.insert_one({
            "user_id": user_id, "provider": provider, "provider_subject": subject,
            "name": name, "email": email, "email_verified": email_verified,
            "picture": picture, "created_at": now, "updated_at": now, "last_login_at": now,
        })
    request.session.clear()
    request.session["user"] = {
        "user_id": user_id, "name": name, "email": email,
        "picture": picture, "provider": provider,
    }
    return __import__("starlette.responses", fromlist=["RedirectResponse"]).RedirectResponse(settings.frontend_origin, status_code=303)

@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return {"status": "logged_out"}
