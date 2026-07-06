from datetime import date, timedelta

from app.schemas import Status

PAYLOAD = {
    "title": "Яндекс.Плюс",
    "amount": "399.00",
    "currency": "RUB",
    "category": "subscription",
    "recurrence": "monthly",
    "next_payment_date": str(date.today() + timedelta(days=10)),
}


async def test_create_active(client):
    response = await client.post("/obligations", json=PAYLOAD)
    assert response.status_code == 201
    body = response.json()
    assert body["obligation"]["status"] == "active"
    assert body["obligation"]["id"]
    assert body["obligation"]["created_at"]
    assert body["obligation"]["amount"] == 399.0
    assert body["warning"] is None


async def test_create_with_past_date_becomes_expired(client):
    payload = {**PAYLOAD, "next_payment_date": str(date.today() - timedelta(days=30))}
    response = await client.post("/obligations", json=payload)
    assert response.status_code == 201
    assert response.json()["obligation"]["status"] == "expired"
    assert response.json()["warning"] is None


async def test_duplicate_active_title_returns_warning(client, make_obligation):
    await make_obligation(title="Яндекс.Плюс")
    response = await client.post("/obligations", json=PAYLOAD)
    assert response.status_code == 201
    body = response.json()
    assert body["obligation"]["status"] == "active"
    assert body["warning"] is not None


async def test_duplicate_check_is_case_insensitive(client, make_obligation):
    await make_obligation(title="яндекс.плюс")
    response = await client.post("/obligations", json=PAYLOAD)
    assert response.status_code == 201
    assert response.json()["warning"] is not None


async def test_non_active_duplicate_does_not_trigger_warning(client, make_obligation):
    await make_obligation(title="Яндекс.Плюс", status=Status.cancelled)
    await make_obligation(title="Яндекс.Плюс", status=Status.expired)
    response = await client.post("/obligations", json=PAYLOAD)
    assert response.status_code == 201
    assert response.json()["warning"] is None


async def test_invalid_currency_rejected(client):
    response = await client.post("/obligations", json={**PAYLOAD, "currency": "RUBLES"})
    assert response.status_code == 422


async def test_negative_amount_rejected(client):
    response = await client.post("/obligations", json={**PAYLOAD, "amount": "-1"})
    assert response.status_code == 422
