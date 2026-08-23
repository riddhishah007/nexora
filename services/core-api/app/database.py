from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings


def _create_engine():
    return create_async_engine(
        settings.database_url,
        echo=settings.environment == "development",
        pool_pre_ping=True,
    )


engine = _create_engine()

SessionFactory = async_sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
