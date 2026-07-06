import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Obligation, Payment
from app.schemas import Category, ObligationCreate, Recurrence, Status

DUPLICATE_WARNING = "Активное обязательство с таким названием уже существует"

RECURRENCE_DELTA = {
    Recurrence.monthly: relativedelta(months=1),
    Recurrence.quarterly: relativedelta(months=3),
    Recurrence.yearly: relativedelta(years=1),
}


class NotActiveError(Exception):
    """Операция допустима только для обязательства в статусе active."""

    def __init__(self, obligation: Obligation, action: str) -> None:
        self.obligation = obligation
        super().__init__(
            f"Нельзя {action} обязательство в статусе «{obligation.status.value}» — "
            "допустимо только для статуса «active»"
        )


async def create_obligation(
    session: AsyncSession, data: ObligationCreate
) -> tuple[Obligation, str | None]:
    """Создаёт обязательство; дата в прошлом даёт статус expired, дубль по title — warning."""
    duplicate_exists = await session.scalar(
        select(
            select(Obligation)
            .where(
                Obligation.status == Status.active,
                func.lower(Obligation.title) == data.title.lower(),
            )
            .exists()
        )
    )

    status = Status.expired if data.next_payment_date < date.today() else Status.active
    obligation = Obligation(**data.model_dump(), status=status)
    session.add(obligation)
    await session.commit()
    await session.refresh(obligation)

    return obligation, DUPLICATE_WARNING if duplicate_exists else None


async def apply_lazy_expiry(session: AsyncSession) -> None:
    """Переводит просроченные разовые обязательства в expired.

    Рекуррентные (recurrence != null) не трогаем: просроченная дата означает лишь,
    что пользователь не отметил оплату, а подписка продолжает действовать.
    """
    await session.execute(
        update(Obligation)
        .where(
            Obligation.status == Status.active,
            Obligation.recurrence.is_(None),
            Obligation.next_payment_date < date.today(),
        )
        .values(status=Status.expired, updated_at=func.now())
    )
    await session.commit()


async def list_obligations(
    session: AsyncSession, category: Category | None, status: Status | None
) -> list[Obligation]:
    await apply_lazy_expiry(session)

    query = select(Obligation).order_by(Obligation.next_payment_date)
    if category is not None:
        query = query.where(Obligation.category == category)
    if status is not None:
        query = query.where(Obligation.status == status)
    return list((await session.scalars(query)).all())


async def get_upcoming(
    session: AsyncSession, days: int
) -> tuple[list[Obligation], dict[str, Decimal], list[Obligation]]:
    """Активные обязательства с датой платежа в окне [today, today + days]."""
    await apply_lazy_expiry(session)

    today = date.today()
    obligations = list(
        (
            await session.scalars(
                select(Obligation)
                .where(
                    Obligation.status == Status.active,
                    Obligation.next_payment_date >= today,
                    Obligation.next_payment_date <= today + relativedelta(days=days),
                )
                .order_by(Obligation.next_payment_date)
            )
        ).all()
    )

    totals: dict[str, Decimal] = {}
    for obligation in obligations:
        totals[obligation.currency] = totals.get(obligation.currency, Decimal(0)) + obligation.amount

    renewal_alerts = [
        o
        for o in obligations
        if o.category == Category.subscription and o.recurrence is not None
    ]
    return obligations, totals, renewal_alerts


async def get_obligation(session: AsyncSession, obligation_id: uuid.UUID) -> Obligation | None:
    """Загружает обязательство с блокировкой строки (SELECT ... FOR UPDATE).

    Используется write-эндпоинтами (/pay, /cancel, DELETE): конкурентные запросы
    сериализуются на уровне БД, иначе два параллельных /pay создали бы два платежа
    при одном сдвиге даты. SQLite в тестах игнорирует FOR UPDATE — это не мешает.
    """
    return await session.get(Obligation, obligation_id, with_for_update=True)


async def pay_obligation(session: AsyncSession, obligation: Obligation) -> Payment:
    """Фиксирует оплату и сдвигает дату следующего платежа по правилам рекуррентности.

    Сдвиг считается от текущего next_payment_date, а не от даты оплаты, чтобы при
    просрочке не накапливалось смещение. relativedelta корректно обрабатывает границы
    месяца: 31 января + 1 месяц = 28 (29 в високосный год) февраля.
    """
    if obligation.status != Status.active:
        raise NotActiveError(obligation, "оплатить")

    payment = Payment(
        obligation_id=obligation.id,
        amount=obligation.amount,
        currency=obligation.currency,
        paid_at=datetime.now(timezone.utc),
    )
    session.add(payment)

    if obligation.recurrence is None:
        obligation.status = Status.cancelled
    else:
        obligation.next_payment_date += RECURRENCE_DELTA[obligation.recurrence]

    await session.commit()
    await session.refresh(obligation)
    await session.refresh(payment)
    return payment


async def cancel_obligation(session: AsyncSession, obligation: Obligation) -> Obligation:
    if obligation.status != Status.active:
        raise NotActiveError(obligation, "отменить")

    obligation.status = Status.cancelled
    await session.commit()
    await session.refresh(obligation)
    return obligation


async def delete_obligation(session: AsyncSession, obligation: Obligation) -> None:
    """Удаляет обязательство вместе с историей оплат (каскад в БД и ORM)."""
    await session.delete(obligation)
    await session.commit()
