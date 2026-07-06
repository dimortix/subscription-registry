import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Obligation
from app.schemas import (
    Category,
    ObligationCreate,
    ObligationCreateResponse,
    ObligationOut,
    PayResponse,
    RenewalAlert,
    Status,
    UpcomingResponse,
)
from app.services import obligations as service
from app.sse import broker

router = APIRouter(prefix="/obligations", tags=["obligations"])


async def get_obligation_or_404(
    obligation_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Obligation:
    obligation = await service.get_obligation(session, obligation_id)
    if obligation is None:
        raise HTTPException(status_code=404, detail="Обязательство не найдено")
    return obligation


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ObligationCreateResponse)
async def create_obligation(
    data: ObligationCreate, session: AsyncSession = Depends(get_session)
) -> ObligationCreateResponse:
    obligation, warning = await service.create_obligation(session, data)
    return ObligationCreateResponse(obligation=obligation, warning=warning)


@router.get("", response_model=list[ObligationOut])
async def list_obligations(
    category: Category | None = Query(default=None),
    status: Status | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[Obligation]:
    return await service.list_obligations(session, category, status)


@router.get("/upcoming", response_model=UpcomingResponse)
async def upcoming_obligations(
    days: int = Query(default=7, ge=0, le=3650),
    session: AsyncSession = Depends(get_session),
) -> UpcomingResponse:
    obligations, totals, renewal_alerts = await service.get_upcoming(session, days)
    return UpcomingResponse(
        obligations=obligations,
        totals=totals,
        renewal_alerts=[RenewalAlert.model_validate(o) for o in renewal_alerts],
    )


@router.post("/{obligation_id}/pay", response_model=PayResponse)
async def pay_obligation(
    obligation: Obligation = Depends(get_obligation_or_404),
    session: AsyncSession = Depends(get_session),
) -> PayResponse:
    try:
        payment = await service.pay_obligation(session, obligation)
    except service.NotActiveError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return PayResponse(obligation=obligation, payment=payment)


@router.patch("/{obligation_id}/cancel", response_model=ObligationOut)
async def cancel_obligation(
    obligation: Obligation = Depends(get_obligation_or_404),
    session: AsyncSession = Depends(get_session),
) -> Obligation:
    try:
        return await service.cancel_obligation(session, obligation)
    except service.NotActiveError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/{obligation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_obligation(
    obligation: Obligation = Depends(get_obligation_or_404),
    session: AsyncSession = Depends(get_session),
) -> Response:
    obligation_id = obligation.id
    await service.delete_obligation(session, obligation)
    broker.publish({"type": "obligation_deleted", "id": str(obligation_id)})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


events_router = APIRouter(tags=["events"])


@events_router.get("/events")
async def sse_events() -> StreamingResponse:
    """SSE-стрим событий реестра (obligation_deleted) для обновления UI в реальном времени."""

    async def stream():
        queue = broker.subscribe()
        try:
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            broker.unsubscribe(queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
