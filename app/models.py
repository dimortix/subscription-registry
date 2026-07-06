import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.schemas import Category, Recurrence, Status


def _values(enum_cls) -> list[str]:
    return [member.value for member in enum_cls]


class Obligation(Base):
    __tablename__ = "obligations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    category: Mapped[Category] = mapped_column(
        Enum(Category, name="category", values_callable=_values), nullable=False
    )
    recurrence: Mapped[Recurrence | None] = mapped_column(
        Enum(Recurrence, name="recurrence", values_callable=_values), nullable=True
    )
    next_payment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[Status] = mapped_column(
        Enum(Status, name="obligation_status", values_callable=_values),
        nullable=False,
        default=Status.active,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    payments: Mapped[list["Payment"]] = relationship(
        back_populates="obligation", cascade="all, delete-orphan", order_by="Payment.paid_at"
    )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    obligation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("obligations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    paid_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    obligation: Mapped[Obligation] = relationship(back_populates="payments")
