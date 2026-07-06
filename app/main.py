from fastapi import FastAPI

from app.api.obligations import events_router, router as obligations_router

app = FastAPI(
    title="Умный реестр подписок",
    description="Backend-ядро AI-платформы управления личными подписками и регулярными платежами",
    version="1.0.0",
)

app.include_router(obligations_router)
app.include_router(events_router)


@app.get("/health", tags=["service"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
