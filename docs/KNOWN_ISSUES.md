# Known Issues, Architectural Trade-offs & Limitations

This document maintains an honest, transparent record of deliberate pedagogical shortcuts, current limitations, and production hardening requirements.

## 1. Authentication & Authorization Model
- **Current State**: The system uses a simulated client-side user switcher (`user_id` passed in request payloads or query parameters).
- **Limitation**: There is no cryptographically signed session token (such as JWT bearer tokens in the `Authorization` header), and passwords are not stored or verified. Any client can pass any `user_id` unless explicit ownership checks are enforced in the service layer.
- **Production Roadmap**: Implement OAuth2 password/bearer flow, password hashing via `bcrypt` / `passlib`, and role-based access control (RBAC) dependencies checking `UserRole.ADMIN`.

## 2. In-Process State & Horizontal Scalability
- **Current State**: Conversation history (`_agent_sessions`), multi-agent session state (`SESSION_STATES`), execution traces (`SESSION_TRACES`), and the rate limiter (`_session_request_timestamps`) are stored in in-memory Python dictionaries and `defaultdict` structures.
- **Limitation**: While perfect for single-process development and classroom instruction, these structures are lost on server restart and are NOT shared across multiple Uvicorn worker processes (`--workers > 1`) or distributed Kubernetes replicas.
- **Production Roadmap**: Back session state, traces, and sliding-window rate limiters with a centralized Redis instance using `aioredis` or Redis key TTLs.

## 3. Mock Payment Processing
- **Current State**: Payment authorization generates a deterministic mock transaction reference (`TXN-CARD-...`) and immediately transitions bookings to `CONFIRMED`.
- **Limitation**: No actual financial interchange occurs. No webhooks, refund callbacks, or PCI-DSS card tokenization are implemented.
- **Production Roadmap**: Integrate a production payment gateway SDK (Stripe, Razorpay) with asynchronous webhook verification.

## 4. Lazy Seat Hold Expiry vs. Dedicated Daemon
- **Current State**: Expired 5-minute seat holds are cleared lazily whenever seat availability is inspected or a new hold is attempted via `release_expired_holds(db, show_id)`.
- **Limitation**: If no user queries a show for 20 minutes, expired held seats technically remain marked as pending in the database until the next access.
- **Production Roadmap**: Run a background periodic task (e.g. Celery beat, APScheduler, or an asynchronous FastAPI lifespan worker) scanning for `expires_at < NOW()` every 30 seconds.

## 5. LLM Fallback & Rule-Based Planner
- **Current State**: When `LLM_API_KEY` is not provided, AI features execute against an internal deterministic mock engine reporting `"mock": true`.
- **Limitation**: The mock planner uses regex and keyword heuristics. Complex, highly ambiguous, or multi-turn conversational edge cases that deviate from standard flows can fall back to default prompt guidance.
- **Production Roadmap**: Connect to OpenAI `gpt-4o-mini`, Anthropic Claude, or local Ollama instances for full semantic reasoning.
