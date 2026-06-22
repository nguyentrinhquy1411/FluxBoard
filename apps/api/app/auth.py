from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import models
from app.database.session import get_db
from app.schemas.auth import LoginPayload, RegisterPayload, TokenResponse, UserRead
from app.security import (
    DUMMY_HASH,
    AuthError,
    decode_token,
    encode_token,
    hash_password,
    normalize_email,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

_INVALID_CREDS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid email or password",
    headers={"WWW-Authenticate": "Bearer"},
)
_MUST_LOGIN = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Authentication required",
    headers={"WWW-Authenticate": "Bearer"},
)


# ── FastAPI dependencies ──────────────────────────────────────────────────────


def _parse_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> models.User:
    token = _parse_bearer(authorization)
    if not token:
        raise _MUST_LOGIN
    settings = get_settings()
    try:
        payload = decode_token(token, settings.resolved_auth_secret)
    except AuthError:
        raise _MUST_LOGIN
    uid = payload.get("uid")
    if not isinstance(uid, int):
        raise _MUST_LOGIN
    user = db.get(models.User, uid)
    if user is None or not user.is_active:
        raise _MUST_LOGIN
    return user


def get_optional_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> models.User | None:
    token = _parse_bearer(authorization)
    if not token:
        return None
    settings = get_settings()
    try:
        payload = decode_token(token, settings.resolved_auth_secret)
    except AuthError:
        return None
    uid = payload.get("uid")
    if not isinstance(uid, int):
        return None
    user = db.get(models.User, uid)
    if user is None or not user.is_active:
        return None
    return user


def _mint_token(user: models.User) -> str:
    settings = get_settings()
    return encode_token(
        {"sub": user.email, "uid": user.id},
        settings.resolved_auth_secret,
        settings.auth_token_ttl_minutes,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(payload: RegisterPayload, db: Session = Depends(get_db)) -> TokenResponse:
    email = normalize_email(payload.email)
    existing = db.scalar(select(models.User).where(models.User.email == email))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = models.User(
        email=email,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.refresh(user)
    return TokenResponse(access_token=_mint_token(user), user=UserRead.model_validate(user))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginPayload, db: Session = Depends(get_db)) -> TokenResponse:
    email = normalize_email(payload.email)
    user = db.scalar(select(models.User).where(models.User.email == email))
    if user is None:
        # timing equalization — run a real scrypt verify so timing is consistent
        verify_password(payload.password, DUMMY_HASH)
        raise _INVALID_CREDS
    if not verify_password(payload.password, user.password_hash) or not user.is_active:
        raise _INVALID_CREDS
    return TokenResponse(access_token=_mint_token(user), user=UserRead.model_validate(user))


@router.get("/me", response_model=UserRead)
def me(user: models.User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(user)
