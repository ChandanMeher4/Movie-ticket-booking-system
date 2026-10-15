# Architectural Decision Records (ADR)

## ADR-001: SQLite In-Memory for Automated Testing vs MySQL
- **Date**: 2026-10-15
- **Status**: Accepted
- **Context**: The production database is MySQL 8 via PyMySQL. However, automated CI and classroom pytest suites need to run rapidly without requiring a live external MySQL daemon.
- **Decision**: Use an in-memory SQLite database (`sqlite:///:memory:`) for pytest test runs via FastAPI dependency override `get_db`. The production code targets MySQL 8 with standard ANSI SQL datatypes and SQLAlchemy 2.0 ORM expressions that are fully compatible with both dialects.
- **Alternatives Considered**: Requiring a local MySQL server (burdensome setup for quick tests) or Docker-in-Docker testcontainers (slow startup time).
- **Consequences**: Fast, zero-dependency testing. MySQL-specific JSON operations must use portable SQLAlchemy `JSON` types.

## ADR-002: Double-Booking Prevention Strategy
- **Date**: 2026-10-15
- **Status**: Accepted
- **Context**: High concurrency during popular movie releases can lead to two customers selecting and paying for the identical seat in the same show.
- **Decision**: Enforce double-booking prevention at two layers:
  1. Primary guarantee: Database-level composite unique constraint `UNIQUE KEY uq_show_seat (show_id, seat_id)` on the `booking_seats` table.
  2. Transactional locking: In `booking_service.py`, execute queries with row-level locks or transactional isolation (`with db.begin():`) so that any overlapping attempt triggers an immediate `IntegrityError`, caught and converted into a `409 Conflict` error.
- **Alternatives Considered**: In-memory Redis locks (adds external dependency) or optimistic version numbers (more complex schema without added benefit over DB constraint).
- **Consequences**: Zero chance of duplicate seat allocation even across horizontal app replicas.

## ADR-003: 5-Minute Seat Hold TTL and Expiration Cleanup
- **Date**: 2026-10-15
- **Status**: Accepted
- **Context**: When a user selects seats, they enter checkout. If they abandon checkout, seats must become available again for other users.
- **Decision**: Bookings are created with `status='pending'` and an `expires_at` timestamp set to `created_at + 300 seconds` (5 minutes). When seat availability is queried or a new booking is attempted, an automated cleanup query marks expired pending bookings as `cancelled` and removes or frees associated `booking_seats`.
- **Alternatives Considered**: Celery/Redis delayed tasks (requires background worker broker).
- **Consequences**: Completely self-contained within FastAPI and the relational database.

## ADR-004: Centralized Pricing Engine
- **Date**: 2026-10-15
- **Status**: Accepted
- **Context**: Ticket pricing depends on show base price, seat tier multipliers (regular 1.0, premium 1.4, recliner 1.8), day of week (10% weekend surcharge on Friday, Saturday, Sunday), and a fixed convenience fee (2%).
- **Decision**: Centralize all pricing calculation into `app/services/pricing.py`. All API routers, booking services, and AI tool handlers call this single pure function.
- **Alternatives Considered**: Ad-hoc price calculations in SQL views or frontend JavaScript.
- **Consequences**: Single source of truth; immune to client-side tampering.

## ADR-005: Deterministic LLM Mock Fallback
- **Date**: 2026-10-15
- **Status**: Accepted
- **Context**: Students and evaluators may not have an active OpenAI API key or budget when running the system locally.
- **Decision**: In `app/ai/llm_client.py`, check `LLM_API_KEY`. If absent or set to a placeholder, transparently switch to an internal deterministic rule-based engine. All AI responses include `"mock": true` (or `"mock": false` when live).
- **Alternatives Considered**: Failing startup with an exception (blocks classroom usage).
- **Consequences**: Entire system is 100% testable and runnable out-of-the-box offline.

## ADR-006: Multi-Agent Architecture via Typed State and Orchestrator
- **Date**: 2026-10-15
- **Status**: Accepted
- **Context**: Teaching multi-agent systems requires clear separation of duties and verifiable guardrails.
- **Decision**: Implement a hierarchical orchestrator pattern with specialized worker agents (Discovery, Booking, Payment, Support, Notification) and a dedicated `CriticAgent` verifier. Agents interact by mutating a shared Pydantic `AgentSessionState` record. The `CriticAgent` inspects any state-changing intent before execution and has veto authority.
- **Alternatives Considered**: Unstructured agent-to-agent peer messaging (hard to audit, prone to infinite loops).
- **Consequences**: Predictable execution, complete audit traces, and high classroom pedagogy value.
