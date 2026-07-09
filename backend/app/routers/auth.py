from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import User
from ..schemas import UserOut
from ..services import auth as auth_svc

router = APIRouter(prefix="/api/auth", tags=["auth"])

_secure_cookies = settings.backend_url.startswith("https://")


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        auth_svc.COOKIE_NAME,
        token,
        max_age=settings.session_days * 86400,
        httponly=True,
        samesite="lax",
        secure=_secure_cookies,
        path="/",
    )


@router.get("/google/login")
def google_login():
    if not auth_svc.auth_enabled():
        raise HTTPException(400, "Google auth is not configured (dev mode is active)")
    state = auth_svc.new_state()
    response = RedirectResponse(auth_svc.build_login_url(state), status_code=302)
    response.set_cookie(
        auth_svc.STATE_COOKIE, state,
        max_age=600, httponly=True, samesite="lax", secure=_secure_cookies, path="/",
    )
    return response


@router.get("/google/callback")
async def google_callback(
    code: str = "",
    state: str = "",
    neu_oauth_state: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    if not code:
        raise HTTPException(400, "Missing authorization code")
    if not state or state != neu_oauth_state:
        raise HTTPException(400, "Invalid OAuth state — try signing in again")

    info = await auth_svc.exchange_code(code)
    email = info.get("email")
    if not email or not info.get("email_verified", True):
        raise HTTPException(401, "Google account has no verified email")
    auth_svc.check_email_allowed(email)

    user = auth_svc.upsert_user(db, email, info.get("name", ""), info.get("picture"))
    token = auth_svc.issue_session_token(user)

    response = RedirectResponse(settings.frontend_url, status_code=302)
    _set_session_cookie(response, token)
    response.delete_cookie(auth_svc.STATE_COOKIE, path="/")
    return response


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(auth_svc.get_current_user)):
    return user


@router.post("/logout")
def logout():
    response = Response(status_code=204)
    response.delete_cookie(auth_svc.COOKIE_NAME, path="/")
    return response


@router.get("/config")
def auth_config():
    """Tells the frontend whether real sign-in is required."""
    return {"auth_enabled": auth_svc.auth_enabled()}
