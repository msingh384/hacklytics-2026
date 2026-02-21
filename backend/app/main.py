from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings
from app.services.container import build_services


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    services = build_services(settings)
    app.state.services = services
    try:
        yield
    finally:
        services.vector_store.close()


settings = get_settings()
app = FastAPI(
    title="DirectorsCut API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix=settings.api_prefix)
