"""Google sign-in + JWT session cookies.

Flow:
  GET /api/auth/google/login    -> 302 to Google's consent screen (state = CSRF token)
  GET /api/auth/google/callback -> code exchange, userinfo, upsert user,
                                   set httpOnly session cookie, 302 to frontend
  GET /api/auth/me              -> current user (or 401)
  POST /api/auth/logout         -> clear cookie

Dev mode: when GOOGLE_CLIENT_ID is not configured, every request is treated as
dev@localhost so local development and tests work without credentials.
"""

import logging
import secrets
import time

import httpx
import jwt
from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import User, Workspace, WorkspaceMember

logger = logging.getLogger("neu.auth")

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

COOKIE_NAME = "neu_session"
STATE_COOKIE = "neu_oauth_state"

DEV_EMAIL = "dev@localhost"


def auth_enabled() -> bool:
    return bool(settings.google_client_id)


def redirect_uri() -> str:
    return f"{settings.backend_url.rstrip('/')}/api/auth/google/callback"


def build_login_url(state: str) -> str:
    from urllib.parse import urlencode

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def new_state() -> str:
    return secrets.token_urlsafe(24)


async def exchange_code(code: str) -> dict:
    """Exchange the auth code for tokens, then fetch the user's profile."""
    async with httpx.AsyncClient(timeout=30) as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": redirect_uri(),
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            logger.warning("Google token exchange failed: %s", token_resp.text[:300])
            raise HTTPException(401, "Google sign-in failed (code exchange)")
        access_token = token_resp.json().get("access_token")

        info_resp = await client.get(
            GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
        )
        if info_resp.status_code != 200:
            raise HTTPException(401, "Google sign-in failed (userinfo)")
        return info_resp.json()


def check_email_allowed(email: str) -> None:
    allowed = [d.strip().lower() for d in settings.auth_allowed_email_domains.split(",") if d.strip()]
    if allowed and email.split("@")[-1].lower() not in allowed:
        raise HTTPException(403, f"Sign-ins from your email domain are not allowed")


def upsert_user(db: Session, email: str, name: str, picture: str | None) -> User:
    """Find or create the user; first login also creates a personal workspace."""
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(email=email, name=name or email.split("@")[0], picture=picture)
        db.add(user)
        db.flush()
        workspace = Workspace(name=f"{user.name}'s workspace")
        db.add(workspace)
        db.flush()
        db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
        db.commit()
    else:
        if name and user.name != name:
            user.name = name
        if picture and user.picture != picture:
            user.picture = picture
        db.commit()
    return user


def issue_session_token(user: User) -> str:
    now = int(time.time())
    payload = {
        "sub": user.id,
        "email": user.email,
        "iat": now,
        "exp": now + settings.session_days * 86400,
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_session_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def get_current_user(
    neu_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency: resolve the logged-in user, or auto-login the dev
    user when Google auth is not configured."""
    if not auth_enabled():
        return upsert_user(db, DEV_EMAIL, "Dev User", None)

    if not neu_session:
        raise HTTPException(401, "Not signed in")
    payload = decode_session_token(neu_session)
    if payload is None:
        raise HTTPException(401, "Session expired — sign in again")
    user = db.get(User, payload["sub"])
    if user is None:
        raise HTTPException(401, "Account no longer exists")
    return user


def get_membership(db: Session, user: User, workspace_id: str) -> WorkspaceMember:
    member = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user.id,
        )
        .first()
    )
    if member is None:
        raise HTTPException(403, "You are not a member of this workspace")
    return member


def require_role(member: WorkspaceMember, *roles: str) -> None:
    if member.role not in roles:
        raise HTTPException(403, f"Requires role: {' or '.join(roles)}")


def default_workspace_id(db: Session, user: User) -> str:
    member = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.user_id == user.id)
        .order_by(WorkspaceMember.created_at)
        .first()
    )
    if member is None:
        # Should not happen (created on signup) — self-heal
        workspace = Workspace(name=f"{user.name}'s workspace")
        db.add(workspace)
        db.flush()
        db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
        db.commit()
        return workspace.id
    return member.workspace_id
