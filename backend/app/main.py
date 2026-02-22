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

# In development, allow all localhost origins to avoid CORS issues
_cors_origins = settings.cors_origins_list or ["*"]
if settings.app_env == "development":
    _cors_origins = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:3000",
    ]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(router, prefix=settings.api_prefix)
