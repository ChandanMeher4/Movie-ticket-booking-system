# Project Context: Movie Ticket Booking System

## Overview
A classroom case-study web application teaching progressive software and AI engineering:
1. Database + CRUD (MySQL 8, SQLAlchemy 2.0, FastAPI)
2. Validation & Concurrency Rules (Pydantic v2, transactions, seat locking, hold expiry, refund tiers)
3. Generative AI (OpenAI-compatible LLM client with deterministic mock fallback)
4. Single-Agent AI (tool-calling loop with guardrails and session persistence)
5. Multi-Agent AI Orchestration (specialist agents with least privilege + verifier CriticAgent)
6. Frontend & Visual Integration (Vanilla HTML/CSS/JS, responsive dark theme, seat map, agent traces)
7. Production Readiness (pytest suite, SQLite in-memory tests, Docker Compose, Swagger docs)

## Fixed Tech Stack
- **Frontend**: Plain HTML5, CSS3 (vanilla custom properties/grid/flexbox), Vanilla JavaScript (ES6+, no framework, no build tools). Served as static files by FastAPI under `/static` and HTML routes.
- **Backend**: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 ORM, PyMySQL.
- **Database**: MySQL 8 (production / local), SQLite in-memory (automated pytest suite via dependency override).
- **LLM**: Any OpenAI-compatible API (`openai` Python SDK). Configured via `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`. When `LLM_API_KEY` is missing/empty, the system operates in deterministic mock mode returning `"mock": true`.
- **Testing**: pytest + httpx TestClient, SQLite in-memory.

## Repository Layout
```
movie-ticket-booking/
  docs/                   # Single source of truth documentation
  sql/schema.sql          # MySQL 8 DDL with constraints and indexes
  sql/seed.sql            # Realistic sample data (8+ movies, 3 theatres, 6 screens, 30+ shows)
  app/
    main.py               # FastAPI entrypoint, router mounts, static files, CORS, exception handlers
    config.py             # Settings via pydantic-settings
    database.py           # Engine, SessionLocal, get_db dependency
    models.py             # SQLAlchemy 2.0 declarative models
    schemas.py            # Pydantic v2 validation and response schemas
    errors.py             # Standardized error responses and exception classes
    routers/              # Resource routers (CRUD, bookings, payments, AI)
    services/             # Business logic (booking_service, pricing, seed)
    ai/                   # LLM client, prompts, tools, single-agent, multi-agent, guardrails
  frontend/               # Static web UI (HTML, CSS, JS)
  tests/                  # Automated pytest suite
  requirements.txt        # Python dependencies
  .env.example            # Environment template
  docker-compose.yml      # MySQL 8 + FastAPI container orchestration
  README.md               # Setup, classroom guide, and verification
```

## Non-Negotiable Rules
1. Zero placeholder code: Every file must be complete, typed, documented, and runnable.
2. Standardized error envelope: `{"error": {"code": "...", "message": "...", "details": ...}}`.
3. Concurrency safety: Seat double-booking is strictly prevented by DB unique constraint `(show_id, seat_id)` and transactional locking.
4. Deterministic fallback: AI endpoints must never crash if no LLM API key is provided.
5. Anti-slop engineering: No marketing fluff, no unused imports, strict type hints, and honest test assertions.
