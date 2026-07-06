import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, StringConstraints


class Category(str, Enum):
    subscription = "subscription"
    warranty = "warranty"
    bill = "bill"
    insurance = "insurance"


class Recurrence(str, Enum):
    monthly = "monthly"
    quarterly = "quarterly"
    yearly = "yearly"


class Status(str, Enum):
    active = "active"
    cancelled = "cancelled"
    expired = "expired"


# В JSON суммы отдаются числами (как в примерах ТЗ), а не строками,
# в которые pydantic сериализует Decimal по умолчанию.
Money = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]

Currency = Annotated[str, StringConstraints(to_upper=True, pattern=r"^[A-Z]{3}$")]


class ObligationCreate(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    amount: Money = Field(gt=0, max_digits=12, decimal_places=2)
    currency: Currency
    category: Category
    recurrence: Recurrence | None = None
    next_payment_date: date


class ObligationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    amount: Money
    currency: str
    category: Category
    recurrence: Recurrence | None
    next_payment_date: date
    status: Status
    created_at: datetime
    updated_at: datetime


class ObligationCreateResponse(BaseModel):
    obligation: ObligationOut
    warning: str | None = None


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    obligation_id: uuid.UUID
    amount: Money
    currency: str
    paid_at: datetime


class PayResponse(BaseModel):
    obligation: ObligationOut
    payment: PaymentOut


class RenewalAlert(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    next_payment_date: date
    amount: Money
    currency: str


class UpcomingResponse(BaseModel):
    obligations: list[ObligationOut]
    totals: dict[str, Money]
    renewal_alerts: list[RenewalAlert]
