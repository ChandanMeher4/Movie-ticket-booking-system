# Project Implementation Plan

Status indicators:
- `[ ]` Todo
- `[~]` In Progress
- `[x]` Done
- `[!]` Blocked

## Phase 0: Foundations & Context Management
- [x] Create `docs/PROJECT_CONTEXT.md`
- [x] Create `docs/PLAN.md`
- [x] Create `docs/DECISIONS.md`
- [x] Create `docs/ARCHITECTURE.md`
- [x] Create `docs/API.md`
- [x] Create `docs/AI_DESIGN.md`
- [x] Create `docs/PROGRESS_LOG.md`
- [x] Create `docs/KNOWN_ISSUES.md`

## Phase 1: Database & Core CRUD
- [x] Create `requirements.txt` and `.env.example`
- [x] Create `sql/schema.sql` (MySQL 8 DDL with foreign keys, indexes, and unique constraints)
- [x] Create `sql/seed.sql` (8+ movies, 3 theatres, 6 screens, 30+ upcoming shows, 3 users)
- [x] Create `app/config.py` and `app/database.py` (engine, sessionmaker, get_db)
- [x] Create `app/models.py` (SQLAlchemy 2.0 mapped models for all 10 tables)
- [x] Create `app/errors.py` (standard error format and exception handlers)
- [x] Create `app/schemas.py` (core Pydantic models for movies, theatres, screens, shows, users)
- [x] Create `app/services/seed.py` (idempotent database seeder)
- [x] Create CRUD routers: `movies.py`, `theatres.py`, `screens.py`, `shows.py`, `users.py`
- [x] Create `app/main.py` baseline and verify CRUD endpoints & SQLite compatibility

## Phase 2: Validation, Pricing & Business Rules
- [x] Create `app/services/pricing.py` (base price, seat multipliers, weekend surcharge, convenience fee)
- [x] Create `app/services/booking_service.py` (seat hold with 5-min TTL, cleanup, confirm, cancel/refund tiers)
- [x] Create routers: `seats.py`, `bookings.py`, `payments.py`
- [x] Enhance `app/schemas.py` with strict Pydantic v2 validators (phone regex, future dates, seat limits)
- [x] Implement concurrency safety (database transaction and seat collision handling)
- [x] Add tests for pricing, validation, seat holds, and double-booking race conditions

## Phase 3: Generative AI (Direct LLM Calls)
- [x] Create `app/ai/llm_client.py` (OpenAI-compatible client with deterministic rule-based mock fallback)
- [x] Create `app/ai/prompts.py` (prompts for summary, recommendations, review sentiment, booking email)
- [x] Create `app/ai/genai_features.py` (structured generation with Pydantic validation and retry)
- [x] Create `app/routers/ai_genai.py` (endpoints: `/movie-summary`, `/recommend`, `/review-summarize`, `/booking-email`)
- [x] Write unit tests for GenAI endpoints in mock mode

## Phase 4: Single-Agent AI with Tools
- [x] Create `app/ai/tools.py` (tool functions hitting DB/services + strict JSON schemas)
- [x] Create `app/ai/guardrails.py` (injection detection, off-topic refusal, rate limiting, confirmation checks)
- [x] Create `app/ai/single_agent.py` (ReAct/tool-calling loop with max 6 turns and audit logging to `ai_logs`)
- [x] Create `app/routers/ai_agent.py` (endpoint `/api/ai/agent/chat`)
- [x] Add tests for single-agent tool execution and guardrails

## Phase 5: Multi-Agent AI Orchestration
- [x] Create `app/ai/multi_agent.py` (Orchestrator, Discovery, Booking, Payment, Support, Notification, Critic)
- [x] Implement shared typed state and verifier rejection logic in CriticAgent
- [x] Create `app/routers/ai_multi_agent.py` (endpoints `/api/ai/multi/chat` and `/api/ai/multi/trace/{session_id}`)
- [x] Add tests for multi-agent routing, trace generation, and Critic rejection

## Phase 6: Frontend Development
- [x] Create `frontend/css/styles.css` (modern cinematic dark theme, responsive grid/flex, CSS custom properties)
- [x] Create `frontend/js/api.js` (fetch wrapper, error handling, HTML escaping / XSS protection)
- [x] Create `frontend/index.html` & `frontend/movies.html` & `frontend/js/movies.js`
- [x] Create `frontend/seats.html` & `frontend/js/seats.js` (interactive seat map, live pricing, 5-min hold timer)
- [x] Create `frontend/bookings.html` & `frontend/js/bookings.js` (checkout, summary, cancellation & refunds)
- [x] Create `frontend/admin.html` & `frontend/js/admin.js` (movie/show CRUD, revenue stats)
- [x] Create `frontend/assistant.html` & `frontend/js/assistant.js` (chat UI, GenAI / Single / Multi-agent trace toggle)
- [x] Mount frontend static directory and HTML page routes in `app/main.py`

## Phase 7: Tests, Quality & Documentation
- [x] Complete full pytest suite in `tests/` (`test_movies.py`, `test_shows.py`, `test_booking.py`, `test_validation.py`, `test_ai.py`, `test_single_agent.py`, `test_multi_agent.py`, `test_frontend.py`)
- [x] Add `/health` endpoint and CORS configuration
- [x] Create `docker-compose.yml` for containerized MySQL 8 + FastAPI execution
- [x] Create comprehensive `README.md` with architecture diagrams, setup instructions, classroom exercises, and CLI examples
- [x] Run end-to-end verification and compile final acceptance report
