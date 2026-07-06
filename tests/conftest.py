"""Тестовая инфраструктура: in-memory SQLite вместо PostgreSQL, ASGI-клиент без сети.

Внешних зависимостей нет: реальная БД подменяется через dependency override.
"""
from datetime import date
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base, get_session
from app.main import app
from app.models import Obligation
from app.schemas import Category, Recurrence, Status


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)

    # Приближаем SQLite к поведению PostgreSQL: встроенный lower() понимает
    # только ASCII (подменяем Unicode-версией для кириллицы в title), а проверка
    # внешних ключей по умолчанию выключена (включаем, чтобы FK-целостность
    # и ON DELETE CASCADE действовали и в тестах).
    @event.listens_for(engine.sync_engine, "connect")
    def configure_sqlite(dbapi_connection, _):
        dbapi_connection.create_function("lower", 1, lambda s: s.lower() if s else s)
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
async def client(session_factory):
    async def override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def make_obligation(session_factory):
    """Кладёт обязательство напрямую в БД, минуя правила POST /obligations."""

    async def _make(
        title: str = "Netflix",
        amount: Decimal = Decimal("9.99"),
        currency: str = "USD",
        category: Category = Category.subscription,
        recurrence: Recurrence | None = Recurrence.monthly,
        next_payment_date: date | None = None,
        status: Status = Status.active,
    ) -> Obligation:
        obligation = Obligation(
            title=title,
            amount=amount,
            currency=currency,
            category=category,
            recurrence=recurrence,
            next_payment_date=next_payment_date or date.today(),
            status=status,
        )
        async with session_factory() as session:
            session.add(obligation)
            await session.commit()
            await session.refresh(obligation)
        return obligation

    return _make
