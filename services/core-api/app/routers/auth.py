import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.organization import Organization
from app.models.user import User, UserSession
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.security.passwords import hash_password, verify_password
from app.security.tokens import (
    TOKEN_TYPE_REFRESH,
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


async def _issue_tokens(
    db: AsyncSession,
    user: User,
    user_agent: str | None,
) -> TokenResponse:
    session_id = uuid.uuid4()
    refresh_token, expires_at = create_refresh_token(user.id, session_id)

    session = UserSession(
        id=session_id,
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(refresh_token),
        expires_at=expires_at,
        revoked_at=None,
        user_agent=user_agent,
    )
    db.add(session)

    access_token, expires_in = create_access_token(user.id, role=user.role)
    await db.commit()
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=expires_in,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    existing = await db.execute(
        select(User).where(User.email == payload.email.lower())
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    org = Organization(name=f"{payload.name or payload.email}'s workspace")
    db.add(org)
    await db.flush()

    user = User(
        org_id=org.id,
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        name=payload.name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    result = await db.execute(
        select(User).where(User.email == payload.email.lower())
    )
    user = result.scalar_one_or_none()

    if (
        user is None
        or not user.is_active
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_agent = request.headers.get("user-agent")
    return await _issue_tokens(db, user, user_agent)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        claims = decode_token(payload.refresh_token, TOKEN_TYPE_REFRESH)
    except TokenError:
        raise invalid from None

    try:
        session_id = uuid.UUID(claims["sid"])
        user_id = uuid.UUID(claims["sub"])
    except (KeyError, ValueError):
        raise invalid from None

    result = await db.execute(
        select(UserSession).where(UserSession.id == session_id)
    )
    session_row = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if (
        session_row is None
        or session_row.user_id != user_id
        or session_row.revoked_at is not None
        or session_row.expires_at <= now
        or session_row.refresh_token_hash != hash_refresh_token(payload.refresh_token)
    ):
        raise invalid

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise invalid

    session_row.revoked_at = now
    return await _issue_tokens(db, user, request.headers.get("user-agent"))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: LogoutRequest,
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        claims = decode_token(payload.refresh_token, TOKEN_TYPE_REFRESH)
        session_id = uuid.UUID(claims["sid"])
    except (TokenError, KeyError, ValueError):
        return None

    result = await db.execute(
        select(UserSession).where(UserSession.id == session_id)
    )
    session_row = result.scalar_one_or_none()
    if (
        session_row is not None
        and session_row.revoked_at is None
        and session_row.refresh_token_hash == hash_refresh_token(payload.refresh_token)
    ):
        session_row.revoked_at = datetime.now(timezone.utc)
        await db.commit()


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)
