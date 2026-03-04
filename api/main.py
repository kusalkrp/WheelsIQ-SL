"""
Prime Wheels SL — FastAPI application factory.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import health, query, search, vehicles, admin
from shared.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    setup_logging()
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Prime Wheels SL API",
        description="Production-grade RAG API for Sri Lankan used vehicles marketplace",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS — allow_credentials requires explicit origins (not "*")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    app.include_router(health.router, prefix="/api/v1", tags=["Health"])
    app.include_router(query.router, prefix="/api/v1", tags=["RAG Query"])
    app.include_router(search.router, prefix="/api/v1", tags=["Search"])
    app.include_router(vehicles.router, prefix="/api/v1", tags=["Vehicles"])
    app.include_router(admin.router, prefix="/api/v1", tags=["Admin"])

    return app


app = create_app()
