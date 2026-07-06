from datetime import date, timedelta
from decimal import Decimal

from app.schemas import Category, Recurrence, Status


async def test_window_includes_boundaries_and_excludes_rest(client, make_obligation):
    today = date.today()
    inside_today = await make_obligation(title="Сегодня", next_payment_date=today)
    inside_edge = await make_obligation(title="Край окна", next_payment_date=today + timedelta(days=7))
    await make_obligation(title="За окном", next_payment_date=today + timedelta(days=8))

    response = await client.get("/obligations/upcoming")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["obligations"]}
    assert ids == {str(inside_today.id), str(inside_edge.id)}


async def test_days_parameter_widens_window(client, make_obligation):
    far = await make_obligation(
        title="Через месяц", next_payment_date=date.today() + timedelta(days=30)
    )
    response = await client.get("/obligations/upcoming", params={"days": 30})
    ids = {item["id"] for item in response.json()["obligations"]}
    assert str(far.id) in ids


async def test_totals_grouped_by_currency(client, make_obligation):
    await make_obligation(title="Кино", amount=Decimal("990.00"), currency="RUB")
    await make_obligation(title="Музыка", amount=Decimal("500.00"), currency="RUB")
    await make_obligation(title="Netflix", amount=Decimal("9.99"), currency="USD")

    totals = (await client.get("/obligations/upcoming")).json()["totals"]
    assert totals == {"RUB": 1490.0, "USD": 9.99}


async def test_renewal_alerts_only_recurring_subscriptions(client, make_obligation):
    subscription = await make_obligation(title="Netflix")
    await make_obligation(title="Разовая подписка", recurrence=None)
    await make_obligation(title="Страховка", category=Category.insurance, recurrence=Recurrence.yearly)

    body = (await client.get("/obligations/upcoming")).json()
    assert len(body["obligations"]) == 3
    assert [alert["id"] for alert in body["renewal_alerts"]] == [str(subscription.id)]
    alert = body["renewal_alerts"][0]
    assert set(alert) == {"id", "title", "next_payment_date", "amount", "currency"}


async def test_non_active_excluded(client, make_obligation):
    await make_obligation(title="Отменённая", status=Status.cancelled)
    await make_obligation(title="Истёкшая", status=Status.expired)

    body = (await client.get("/obligations/upcoming")).json()
    assert body["obligations"] == []
    assert body["totals"] == {}
    assert body["renewal_alerts"] == []
