import uuid

from sqlalchemy import func, select

from app.models import Payment
from app.schemas import Status
from app.sse import broker


async def test_cancel_active(client, make_obligation):
    obligation = await make_obligation()
    response = await client.patch(f"/obligations/{obligation.id}/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


async def test_cancel_expired_returns_422(client, make_obligation):
    obligation = await make_obligation(status=Status.expired)
    response = await client.patch(f"/obligations/{obligation.id}/cancel")
    assert response.status_code == 422
    assert response.json()["detail"]


async def test_cancel_already_cancelled_returns_422(client, make_obligation):
    obligation = await make_obligation(status=Status.cancelled)
    assert (await client.patch(f"/obligations/{obligation.id}/cancel")).status_code == 422


async def test_cancel_unknown_id_returns_404(client):
    assert (await client.patch(f"/obligations/{uuid.uuid4()}/cancel")).status_code == 404


async def test_delete_returns_204_for_any_status(client, make_obligation):
    for status in (Status.active, Status.cancelled, Status.expired):
        obligation = await make_obligation(status=status)
        response = await client.delete(f"/obligations/{obligation.id}")
        assert response.status_code == 204


async def test_delete_cascades_payments(client, make_obligation, session_factory):
    obligation = await make_obligation()
    await client.post(f"/obligations/{obligation.id}/pay")

    assert (await client.delete(f"/obligations/{obligation.id}")).status_code == 204

    async with session_factory() as session:
        payments_left = await session.scalar(
            select(func.count()).select_from(Payment).where(Payment.obligation_id == obligation.id)
        )
    assert payments_left == 0


async def test_delete_publishes_sse_event(client, make_obligation):
    obligation = await make_obligation()
    queue = broker.subscribe()
    try:
        await client.delete(f"/obligations/{obligation.id}")
        event = queue.get_nowait()
    finally:
        broker.unsubscribe(queue)
    assert event == {"type": "obligation_deleted", "id": str(obligation.id)}


async def test_delete_unknown_id_returns_404(client):
    assert (await client.delete(f"/obligations/{uuid.uuid4()}")).status_code == 404
