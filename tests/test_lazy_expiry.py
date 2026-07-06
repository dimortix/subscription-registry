from datetime import date, timedelta

from app.schemas import Category, Status


async def test_overdue_one_off_becomes_expired(client, make_obligation):
    overdue = await make_obligation(
        title="Страховка ОСАГО",
        category=Category.insurance,
        recurrence=None,
        next_payment_date=date.today() - timedelta(days=1),
    )
    response = await client.get("/obligations")
    assert response.status_code == 200
    by_id = {item["id"]: item for item in response.json()}
    assert by_id[str(overdue.id)]["status"] == "expired"


async def test_overdue_recurring_stays_active(client, make_obligation):
    overdue_subscription = await make_obligation(
        title="Netflix",
        next_payment_date=date.today() - timedelta(days=10),
    )
    response = await client.get("/obligations")
    by_id = {item["id"]: item for item in response.json()}
    assert by_id[str(overdue_subscription.id)]["status"] == "active"


async def test_future_one_off_stays_active(client, make_obligation):
    future = await make_obligation(
        title="Гарантия на ноутбук",
        category=Category.warranty,
        recurrence=None,
        next_payment_date=date.today() + timedelta(days=30),
    )
    response = await client.get("/obligations")
    by_id = {item["id"]: item for item in response.json()}
    assert by_id[str(future.id)]["status"] == "active"


async def test_lazy_expiry_is_persisted(client, make_obligation, session_factory):
    from app.models import Obligation

    overdue = await make_obligation(
        title="Разовый счёт",
        category=Category.bill,
        recurrence=None,
        next_payment_date=date.today() - timedelta(days=1),
    )
    await client.get("/obligations")

    async with session_factory() as session:
        refreshed = await session.get(Obligation, overdue.id)
        assert refreshed.status == Status.expired


async def test_filters_by_category_and_status_together(client, make_obligation):
    await make_obligation(title="Netflix", category=Category.subscription)
    await make_obligation(title="Spotify", category=Category.subscription, status=Status.cancelled)
    await make_obligation(title="Электричество", category=Category.bill, recurrence=None)

    response = await client.get("/obligations", params={"category": "subscription", "status": "active"})
    items = response.json()
    assert [item["title"] for item in items] == ["Netflix"]


async def test_sorted_by_next_payment_date_ascending(client, make_obligation):
    await make_obligation(title="Later", next_payment_date=date.today() + timedelta(days=20))
    await make_obligation(title="Sooner", next_payment_date=date.today() + timedelta(days=5))

    response = await client.get("/obligations")
    dates = [item["next_payment_date"] for item in response.json()]
    assert dates == sorted(dates)
