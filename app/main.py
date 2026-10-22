"""Main FastAPI application entrypoint.

Initializes middleware, exception handlers, API routers, static assets, and health checks.
"""

from contextlib import asynccontextmanager
import os
from typing import AsyncGenerator
from fastapi import FastAPI, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, SessionLocal, engine, get_db
from app.errors import setup_exception_handlers
from app.routers import (
    ai_agent,
    ai_genai,
    ai_multi_agent,
    bookings,
    movies,
    payments,
    screens,
    seats,
    shows,
    theatres,
    users,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle events."""
    try:
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            from app.services.seed import seed_database
            seed_database(db)
    except Exception:
        # Gracefully handle unconfigured MySQL engine during testing or offline runs
        pass
    yield


app = FastAPI(
    title="Cineverse Movie Ticket Booking System",
    description="Classroom case-study teaching Database + CRUD -> Validation -> GenAI -> Single-Agent -> Multi-Agent",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# 1. CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Standardized Exception Handlers
setup_exception_handlers(app)

# 3. Include Core CRUD and Booking Routers
app.include_router(movies.router)
app.include_router(theatres.router)
app.include_router(screens.router)
app.include_router(shows.router)
app.include_router(users.router)
app.include_router(seats.router)
app.include_router(bookings.router)
app.include_router(payments.router)
app.include_router(ai_genai.router)
app.include_router(ai_agent.router)
app.include_router(ai_multi_agent.router)

# 4. Health Check Endpoint
@app.get("/health", tags=["system"])
def health_check(db: Session = Depends(get_db)) -> dict:
    """System health check and database connectivity probe."""
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as exc:
        db_status = f"unhealthy: {exc}"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "mock_llm": settings.is_mock_llm,
        "llm_model": settings.llm_model,
        "environment": settings.app_env,
    }


# 5. Frontend Static Files and Route Handlers (HTML pages)
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/", include_in_schema=False)
    def serve_index() -> FileResponse:
        return FileResponse(os.path.join(frontend_dir, "index.html"))

    @app.get("/movies.html", include_in_schema=False)
    def serve_movies() -> FileResponse:
        return FileResponse(os.path.join(frontend_dir, "movies.html"))

    @app.get("/seats.html", include_in_schema=False)
    def serve_seats() -> FileResponse:
        return FileResponse(os.path.join(frontend_dir, "seats.html"))

    @app.get("/bookings.html", include_in_schema=False)
    def serve_bookings() -> FileResponse:
        return FileResponse(os.path.join(frontend_dir, "bookings.html"))

    @app.get("/admin.html", include_in_schema=False)
    def serve_admin() -> FileResponse:
        return FileResponse(os.path.join(frontend_dir, "admin.html"))

    @app.get("/assistant.html", include_in_schema=False)
    def serve_assistant() -> FileResponse:
        return FileResponse(os.path.join(frontend_dir, "assistant.html"))
