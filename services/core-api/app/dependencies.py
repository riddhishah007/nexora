import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.security.tokens import TOKEN_TYPE_ACCESS, TokenError, decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token, expected_type=TOKEN_TYPE_ACCESS)
    except TokenError:
        raise credentials_exception from None

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise credentials_exception from None

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise credentials_exception
    return user


async def get_current_admin(
    user: User = Depends(get_current_user),
) -> User:
    from app.models.user import ROLE_ADMIN

    if user.role != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return user
