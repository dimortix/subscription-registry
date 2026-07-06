import uuid
from datetime import date

from app.schemas import Category, Recurrence, Status


async def pay(client, obligation_id):
    return await client.post(f"/obligations/{obligation_id}/pay")


async def test_pay_monthly_shifts_one_month(client, make_obligation):
    obligation = await make_obligation(
        recurrence=Recurrence.monthly, next_payment_date=date(2026, 7, 15)
    )
    response = await pay(client, obligation.id)
    assert response.status_code == 200
    body = response.json()
    assert body["obligation"]["next_payment_date"] == "2026-08-15"
    assert body["obligation"]["status"] == "active"


async def test_pay_quarterly_shifts_three_months(client, make_obligation):
    obligation = await make_obligation(
        recurrence=Recurrence.quarterly, next_payment_date=date(2026, 7, 15)
    )
    body = (await pay(client, obligation.id)).json()
    assert body["obligation"]["next_payment_date"] == "2026-10-15"
    assert body["obligation"]["status"] == "active"


async def test_pay_yearly_shifts_one_year(client, make_obligation):
    obligation = await make_obligation(
        recurrence=Recurrence.yearly, next_payment_date=date(2026, 7, 15)
    )
    body = (await pay(client, obligation.id)).json()
    assert body["obligation"]["next_payment_date"] == "2027-07-15"
    assert body["obligation"]["status"] == "active"


async def test_pay_one_off_becomes_cancelled(client, make_obligation):
    obligation = await make_obligation(
        category=Category.bill, recurrence=None, next_payment_date=date(2026, 7, 15)
    )
    body = (await pay(client, obligation.id)).json()
    assert body["obligation"]["status"] == "cancelled"
    assert body["obligation"]["next_payment_date"] == "2026-07-15"


async def test_pay_jan_31_monthly_gives_feb_28(client, make_obligation):
    obligation = await make_obligation(
        recurrence=Recurrence.monthly, next_payment_date=date(2026, 1, 31)
    )
    body = (await pay(client, obligation.id)).json()
    assert body["obligation"]["next_payment_date"] == "2026-02-28"


async def test_pay_jan_31_monthly_leap_year_gives_feb_29(client, make_obligation):
    obligation = await make_obligation(
        recurrence=Recurrence.monthly, next_payment_date=date(2028, 1, 31)
    )
    body = (await pay(client, obligation.id)).json()
    assert body["obligation"]["next_payment_date"] == "2028-02-29"


async def test_pay_oct_31_quarterly_gives_jan_31(client, make_obligation):
    obligation = await make_obligation(
        recurrence=Recurrence.quarterly, next_payment_date=date(2026, 10, 31)
    )
    body = (await pay(client, obligation.id)).json()
    assert body["obligation"]["next_payment_date"] == "2027-01-31"


async def test_pay_feb_29_yearly_gives_feb_28(client, make_obligation):
    obligation = await make_obligation(
        recurrence=Recurrence.yearly, next_payment_date=date(2028, 2, 29)
    )
    body = (await pay(client, obligation.id)).json()
    assert body["obligation"]["next_payment_date"] == "2029-02-28"


async def test_shift_counts_from_next_payment_date_not_today(client, make_obligation):
    """Просроченная на два месяца подписка после оплаты сдвигается на месяц от старой даты."""
    obligation = await make_obligation(
        recurrence=Recurrence.monthly, next_payment_date=date(2026, 5, 10)
    )
    body = (await pay(client, obligation.id)).json()
    assert body["obligation"]["next_payment_date"] == "2026-06-10"


async def test_pay_creates_payment_record(client, make_obligation):
    obligation = await make_obligation()
    body = (await pay(client, obligation.id)).json()
    payment = body["payment"]
    assert payment["obligation_id"] == str(obligation.id)
    assert payment["amount"] == 9.99
    assert payment["currency"] == "USD"
    assert payment["paid_at"]


async def test_pay_expired_returns_422(client, make_obligation):
    obligation = await make_obligation(status=Status.expired)
    response = await pay(client, obligation.id)
    assert response.status_code == 422
    assert "active" in response.json()["detail"]


async def test_pay_cancelled_returns_422(client, make_obligation):
    obligation = await make_obligation(status=Status.cancelled)
    assert (await pay(client, obligation.id)).status_code == 422


async def test_pay_unknown_id_returns_404(client):
    assert (await pay(client, uuid.uuid4())).status_code == 404
