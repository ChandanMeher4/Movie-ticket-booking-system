# Cineverse - Complete End-to-End Engineering Report
### Comprehensive Classroom Case Study Build: Database + CRUD -> Validation -> GenAI -> Single-Agent AI -> Multi-Agent Orchestration

**Author:** Senior Full-Stack & AI Systems Engineer  
**Date:** 2026-10-15  
**Project:** Cineverse Movie Ticket Booking System  
**Repository Location:** `c:\Users\mchan\OneDrive\Desktop\movie ticket booking system`

---

## 1. Executive Summary & Pedagogical Ladder

The Cineverse project was designed and implemented as an end-to-end, runnable reference application and teaching curriculum. It bridges traditional enterprise backend engineering with modern generative AI and multi-agent systems.

The core architectural philosophy is **progressive complexity**:
1. **Database & Relational CRUD**: Establishing strict relational integrity, composite primary/foreign keys, and REST standards.
2. **Business Rules, Validation & Concurrency**: Preventing race conditions at the database level, enforcing atomic 5-minute seat holds, calculating tiered cancellation refunds, and isolating pricing logic.
3. **Generative AI (Stateless)**: Invoking LLMs for copywriting, recommendation, and sentiment analysis with deterministic mock fallbacks and structured Pydantic schema validation.
4. **Single-Agent AI with Tools (ReAct Loop)**: Autonomous tool execution in an iterative feedback loop with security guardrails (prompt-injection defense, off-topic filtering, confirmation checks).
5. **Multi-Agent Orchestration**: Domain-specialized worker agents operating under the Principle of Least Privilege, governed by a pre-execution `CriticAgent` verifier and coordinated through typed Pydantic state.
6. **Frontend Experience**: Vanilla HTML5, CSS3, and JavaScript with a cinematic dark theme, interactive curved seat matrix, 5-minute countdown banner, mock checkout, and real-time agent execution traces.
7. **Production Quality & DevOps**: 67 automated pytest tests (100% passing across 9 test suites), Docker Compose containerization, OpenAPI documentation, and a health monitoring probe.

---

## 2. System Architecture & Component Interactions

```mermaid
graph TD
    UserClient[Vanilla HTML/CSS/JS Client] -->|HTTP / JSON| Gateway[FastAPI REST API Gateway]
    
    subgraph Core Services Layer
        Gateway --> MovieService[Movie / Theatre Catalog Service]
        Gateway --> BookingService[Booking & Concurrency Service]
        Gateway --> PricingEngine[Centralized Pricing Engine]
    end

    subgraph Relational Persistence
        BookingService -->|Atomic Lock & UNIQUE show_id, seat_id| MySQL[(MySQL 8 / In-Memory SQLite)]
        MovieService --> MySQL
    end

    subgraph Multi-Agent AI Orchestration
        Gateway --> OrchestratorEngine[Orchestrator Engine]
        OrchestratorEngine --> DiscoveryAgent[Discovery Agent]
        OrchestratorEngine --> BookingAgent[Booking Agent]
        OrchestratorEngine --> PaymentAgent[Payment Agent]
        OrchestratorEngine --> SupportAgent[Support Agent]
        OrchestratorEngine --> NotificationAgent[Notification Agent]
        
        BookingAgent -.-> CriticAgent{CriticAgent Verifier}
        PaymentAgent -.-> CriticAgent
        SupportAgent -.-> CriticAgent
        
        CriticAgent -->|Approved| BookingService
        CriticAgent -->|Approved| MockGateway[Mock Payment Processor]
        CriticAgent -->|Veto / Reject| OrchestratorEngine
        
        DiscoveryAgent --> Tools[Database Tool Registry]
        BookingAgent --> Tools
        PaymentAgent --> Tools
        SupportAgent --> Tools
        Tools --> BookingService
        
        OrchestratorEngine --> LLMClient[OpenAI SDK Client / Deterministic Mock]
    end
```

---

## 3. Phase-by-Phase Implementation Details: What, How, and Why

### Phase 0: Foundations, Architecture & Context Management
- **What Was Done**:
  - Initialized the mandatory `/docs` repository documentation suite:
    - `PROJECT_CONTEXT.md`: Defined fixed constraints (Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0, PyMySQL, MySQL 8, vanilla HTML/CSS/JS, OpenAI SDK).
    - `PLAN.md`: Phase checklists tracking task states (`[x]`).
    - `DECISIONS.md`: Architectural Decision Records (ADR-001 to ADR-006).
    - `ARCHITECTURE.md`: Component topology and sequence diagrams.
    - `API.md`: Complete OpenAPI endpoint contracts.
    - `AI_DESIGN.md`: Agent privileges, tool schemas, and security guardrails.
    - `PROGRESS_LOG.md`: Append-only audit log with verified test outputs.
    - `KNOWN_ISSUES.md`: Explicit catalogue of technical limits and future extensions.
- **How It Was Done**:
  - Maintained as living documentation updated at the beginning and end of each phase before marking milestones complete.
- **Why It Was Done**:
  - Long engineering builds suffer from context drift. The `/docs` folder serves as the single source of truth, preventing silent scope changes, maintaining strict naming consistency, and enforcing anti-slop rules.

---

### Phase 1: Database Architecture & Core CRUD
- **What Was Done**:
  - Implemented 10 relational tables in `sql/schema.sql`:
    1. `users`: Customer and admin profiles with unique email validation.
    2. `movies`: Title, genre, language, duration, certification rating (`U`, `UA`, `A`), release date, poster URL, active status.
    3. `theatres`: Multiplex properties with city and street address.
    4. `screens`: Auditoriums tied to theatres with seating grid dimensions.
    5. `seats`: Individual seat coordinates (`row_label`, `seat_number`), tier (`regular`, `premium`, `recliner`), unique per screen.
    6. `shows`: Screenings linking movie, screen, start/end timestamps, base price, and status.
    7. `bookings`: Reservation records with customer ID, show ID, status (`pending`, `confirmed`, `cancelled`), total amount, and 5-minute hold timestamp (`expires_at`).
    8. `booking_seats`: Bridge table linking booking, show, and seat with the critical `UNIQUE(show_id, seat_id)` constraint.
    9. `payments`: Financial transactions with booking ID, amount, payment method (`card`, `upi`, `wallet`), transaction reference, and status.
    10. `ai_logs`: Complete audit trail of AI agent sessions, inputs, outputs, tool invocations, and latencies.
  - Built `sql/seed.sql` and idempotent seeder `app/services/seed.py`: 8 blockbuster movies, 3 theatres, 6 screens, 240 seats, 35 scheduled shows over 7 future days, and 3 demo users.
  - Implemented CRUD REST endpoints in `app/routers/` for movies, theatres, screens, shows, and users with pagination, sorting, and multi-field filtering.
- **How It Was Done**:
  - SQLAlchemy 2.0 declarative models (`Mapped[...]`) with strict relationships (`relationship(lazy="selectin")`).
  - Standardized error envelope in `app/errors.py`:
    ```json
    {
      "error": {
        "code": "RESOURCE_NOT_FOUND",
        "message": "Movie with ID 999 was not found",
        "details": null
      }
    }
    ```
- **Why It Was Done**:
  - Establishes relational integrity at the schema level rather than relying solely on application code. Seed data ensures immediate local runnability.

---

### Phase 2: Validation, Pricing Engine & Concurrency Safety
- **What Was Done**:
  - Implemented centralized pricing engine in `app/services/pricing.py`:
    - Base price * seat tier multiplier (`regular`: 1.0x, `premium`: 1.4x, `recliner`: 1.8x).
    - Weekend surcharge: 10% on Friday, Saturday, and Sunday screenings.
    - Convenience fee: 2% platform fee.
    - Currency rounding to 2 decimal places.
  - Implemented booking lifecycle rules in `app/services/booking_service.py`:
    - Maximum 6 seats per transaction.
    - 5-minute seat hold TTL (`expires_at = created_at + 300s`).
    - Automatic lazy release of expired holds (`release_expired_holds`).
    - Screen validation ensuring selected seats belong to the show's screen.
    - Cancellation cutoff: strictly non-refundable within 2 hours of showtime.
    - Tiered refund calculation: 100% refund if >24h prior, 50% refund if between 2h and 24h prior.
  - Concurrency defense: Prevention of double-booking under race conditions.
- **How It Was Done**:
  - Two-tier concurrency safety:
    1. Pre-check: In-transaction query verifying seat availability.
    2. Primary guarantee: Composite database constraint `UNIQUE KEY uq_show_seat (show_id, seat_id)`. Any overlapping insert immediately raises a database `IntegrityError` (or SQLAlchemy `FlushError`), intercepted and converted into a clean `409 Conflict` (`RESOURCE_CONFLICT`).
- **Why It Was Done**:
  - Distributed systems cannot rely on in-memory locks or client-side checks for ticketing. Database-level constraints guarantee zero double-booking even across horizontal app replicas without external cache/broker dependencies.

---

### Phase 3: Generative AI (Stateless Direct Completions)
- **What Was Done**:
  - Built 4 specialized GenAI endpoints under `/api/ai/genai`:
    1. `POST /movie-summary`: Generates spoiler-free marketing blurbs tailored to a chosen tone (`exciting`, `poetic`, `dramatic`, `family-friendly`).
    2. `POST /recommend`: Ingests active movie catalog and user mood, returning top 3 ranked recommendations with match scores and rationales.
    3. `POST /review-summarize`: Analyzes unstructured user reviews, outputting structured JSON with overall sentiment, summary, pros, and cons.
    4. `POST /booking-email`: Generates formal customer booking confirmation emails with venue instructions.
- **How It Was Done**:
  - Unified client wrapper `app/ai/llm_client.py` using `openai` Python SDK.
  - Centralized prompts in `app/ai/prompts.py`.
  - Pydantic schema validation on structured JSON outputs with automated single-turn retry on parse errors.
  - **Deterministic Mock Fallback**: When `LLM_API_KEY` is empty, unset, or invalid, the client automatically routes to an internal rule-based mock engine that generates consistent structured responses and sets `"mock": true`.
- **Why It Was Done**:
  - Guarantees that classroom students, automated CI pipelines, and evaluators can execute the full suite offline with zero API keys and zero cost.

---

### Phase 4: Single-Agent AI with Tools (ReAct Tool-Calling Loop)
- **What Was Done**:
  - Created single-agent assistant under `/api/ai/agent/chat` running an autonomous ReAct loop (up to 6 iterations).
  - Implemented 8 database tools with strict JSON schemas in `app/ai/tools.py`:
    1. `search_movies(query, genre, language)`
    2. `get_showtimes(movie_id, date, city)`
    3. `get_available_seats(show_id, seat_type, count)`
    4. `calculate_price(show_id, seat_ids)`
    5. `hold_seats(user_id, show_id, seat_ids)`
    6. `confirm_booking(booking_id, payment_method)`
    7. `cancel_booking(booking_id)`
    8. `get_my_bookings(user_id)`
  - Implemented security guardrails in `app/ai/guardrails.py`:
    - Rate limiter: 20 requests/minute per conversation session.
    - Prompt injection detector: Rejects jailbreak patterns (`ignore previous instructions`, `DAN`, `system override`) with `422 Unprocessable Entity`.
    - Off-topic detector: Intercepts medical, legal, or coding questions and politely redirects to cinema ticketing.
    - Explicit confirmation guardrail: Refuses to execute `confirm_booking` or `cancel_booking` without explicit user affirmation in conversation history.
  - Audit logging: Persists every tool call, arguments, and execution latency (ms) into `ai_logs`.
- **How It Was Done**:
  - Implemented a tool-calling dispatcher in `app/ai/single_agent.py` that formats OpenAI function-calling messages and feeds tool outputs back to the model turn-by-turn until completion.
- **Why It Was Done**:
  - Teaches students how autonomous tool-augmented LLMs operate, why conversational memory is required, and how state-changing mutations must be safeguarded against hallucinations.

---

### Phase 5: Multi-Agent AI Orchestration
- **What Was Done**:
  - Architected a multi-agent system in `app/ai/multi_agent.py` decomposing the application into 7 specialized agent roles (1 Orchestrator + 5 Domain Specialists + 1 Critic Verifier):
    1. `OrchestratorEngine`: Classifies user intent, creates an execution plan, and coordinates sub-agents.
    2. `DiscoveryAgent`: Catalog search and showtimes (`search_movies`, `get_showtimes`).
    3. `BookingAgent`: Seat availability, price calculation, and 5-minute holds (`get_available_seats`, `calculate_price`, `hold_seats`).
    4. `PaymentAgent`: Payment authorization and booking confirmation (`confirm_booking`).
    5. `SupportAgent`: Policy explanations, booking history, and refund cancellations (`cancel_booking`, `get_my_bookings`).
    6. `NotificationAgent`: Communication formatting (receipts, venue arrival rules).
    7. `CriticAgent` (Verifier): Evaluates proposed plans before ANY state-changing action is released.
  - Built endpoints `POST /api/ai/multi/chat` and `GET /api/ai/multi/trace/{session_id}`.
- **How It Was Done**:
  - **Shared Typed State**: Defined `AgentSessionState` (Pydantic model) passed across all agents containing `session_id`, `user_id`, `held_booking_id`, `selected_seat_ids`, `calculated_price`, `critic_approved`, `critic_feedback`, etc.
  - **Principle of Least Privilege**: Each agent only receives tools strictly required for its domain. `DiscoveryAgent` cannot confirm bookings; `BookingAgent` cannot authorize payments.
  - **Authoritative Gatekeeping**: When payment or cancellation is requested, `CriticAgent` inspects the state. If the user was hesitant or did not provide explicit affirmation ("yes", "confirm", "proceed", "pay"), the Critic rejects the plan, setting `critic_approved = False` and aborting payment.
  - **Execution Trace**: Every agent step records an `AgentStepTrace` with agent name, input, output, tools used, and latency in milliseconds.
- **Why It Was Done**:
  - Solves the primary weaknesses of monolithic single agents: security blast radius, prompt pollution, and lack of deterministic pre-execution validation.

---

### Phase 6: Frontend Development (Vanilla HTML5, CSS3, ES6 JavaScript)
- **What Was Done**:
  - Built a responsive, modern web UI served as static files by FastAPI under `/static` and page routes:
    - `index.html`: Hero section, architecture value props, dynamic "Now Showing" movie cards.
    - `movies.html` & `movies.js`: Catalog browsing, search query input, genre & language filters, sort dropdown, pagination, and showtimes modal grouped by theatre.
    - `seats.html` & `seats.js`: Visual curved cinema screen, alphabetical row matrix (`A`, `B`, `C`...), color-coded seat tiers (Regular 1.0x, Premium 1.4x, Recliner 1.8x), live price calculator (subtotal, 10% weekend surcharge, 2% fee), max-6 seats rule, and active 5-minute atomic hold countdown banner.
    - `bookings.html` & `bookings.js`: Checkout view with mock payment gateway (Card, UPI, Wallet), ticket confirmation voucher with transaction reference, user bookings history table, and cancellation with refund preview modal (>24h = 100%, 2-24h = 50%, <2h = non-refundable).
    - `admin.html` & `admin.js`: Studio operations portal with box office revenue metrics, confirmed bookings counter, movie inventory CRUD (add, deactivate), and show scheduling with conflict validation.
    - `assistant.html` & `assistant.js`: Cinema AI Concierge with 3-way toggle (GenAI features, Single Agent tool caller, Multi-Agent Orchestrator with collapsible step trace panel and CriticAgent verification feedback).
  - Created global cinematic CSS design system `frontend/css/styles.css` (custom properties, responsive flex/grid, dark theme, seat map colors, agent trace badges).
  - Created unified API client `frontend/js/api.js` (fetch wrapper, error extraction, toast alerts, demo user switcher, strict HTML escaping for XSS prevention).
- **How It Was Done**:
  - Zero build step, zero npm bundles, plain standard Web APIs.
  - Dynamic user switching (`localStorage`) between Admin (User 1), Customer 1 (Aarav Sharma, User 2), and Customer 2 (Diya Patel, User 3).
  - Strict input sanitization via `escapeHtml()` on all dynamic user, API, and agent content before DOM insertion.
- **Why It Was Done**:
  - Ensures simplicity and longevity in classroom settings: no broken npm dependencies, instant loading, and transparent inspection of DOM and network events.

---

### Phase 7: Tests, Quality, DevOps & Classroom Documentation
- **What Was Done**:
  - Built automated test suite across 11 test modules in `tests/`:
    1. `test_movies.py`: Pagination, genre/language filtering, search, CRUD operations, 404/422 errors.
    2. `test_shows.py`: Theatre listing, show filtering, screen conflict detection (409).
    3. `test_users_screens.py`: User retrieval, duplicate email rejection (409), seat grid generation.
    4. `test_pricing.py`: Multipliers, weekend detection, subtotal, convenience fees.
    5. `test_booking.py`: Seat map queries, hold & confirm lifecycle, 5-minute hold expiry seat release, cancellation refund tiers, booking history.
    6. `test_concurrency.py`: Concurrent seat booking race condition (201 vs 409), DB unique constraint violation assertion.
    7. `test_validation.py`: Max 6 seats limit, empty seat selection, wrong-screen seat validation, past show rejection, phone regex, positive base price.
    8. `test_ai.py`: Movie summary, recommendation structured JSON, review sentiment, booking email.
    9. `test_single_agent.py`: Tool flows, off-topic refusal, prompt injection interception, unconfirmed booking blockage, end-to-end booking journey.
    10. `test_multi_agent.py`: Discovery delegation, showtimes delegation, BookingAgent hold, CriticAgent unconfirmed payment veto, CriticAgent approval & payment finalization, SupportAgent policy, trace retrieval.
    11. `test_frontend.py`: All HTML routes and static JS/CSS assets return HTTP 200 OK.
  - Created `Dockerfile` and `docker-compose.yml` linking MySQL 8 with automated healthcheck and FastAPI web app.
  - Implemented `/health` probe verifying database connectivity, LLM mode, and environment status.
  - Authored comprehensive `README.md` with setup guides, curl examples, multi-agent trade-off analysis, and 5 progressive classroom exercises.
- **How It Was Done**:
  - In-memory SQLite database configured with `StaticPool` used during test execution via FastAPI `get_db` dependency override.
- **Why It Was Done**:
  - Guarantees immediate zero-setup automated CI verification without requiring an external MySQL daemon or API keys.

---

## 4. Verification Evidence & Test Execution Results

### Automated Pytest Suite Run
```bash
pytest -v
```
**Output:**
```
============================= test session starts =============================
platform win32 -- Python 3.12.8, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\mchan\OneDrive\Desktop\movie ticket booking system
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.12.0, langsmith-0.4.56
collected 67 items

tests/test_ai.py::test_genai_movie_summary PASSED                        [  1%]
tests/test_ai.py::test_genai_movie_summary_not_found PASSED              [  2%]
tests/test_ai.py::test_genai_recommendations_structured_output PASSED    [  4%]
tests/test_ai.py::test_genai_review_summarize_positive PASSED            [  5%]
tests/test_ai.py::test_genai_review_summarize_empty_error PASSED         [  7%]
tests/test_ai.py::test_genai_booking_email PASSED                        [  8%]
tests/test_ai_llm_path.py::test_live_llm_tool_calling_loop_execution PASSED [ 10%]
tests/test_ai_llm_path.py::test_live_llm_invalid_json_arguments_handled_gracefully PASSED [ 11%]
tests/test_ai_llm_path.py::test_live_llm_iteration_limit_enforced PASSED [ 13%]
tests/test_ai_llm_path.py::test_structured_json_retry_mechanism PASSED   [ 14%]
tests/test_booking.py::test_get_show_seat_map PASSED                     [ 16%]
tests/test_booking.py::test_hold_and_confirm_booking_flow PASSED         [ 17%]
tests/test_booking.py::test_hold_expiry_releases_seats PASSED            [ 19%]
tests/test_booking.py::test_cancellation_and_refund_tiers PASSED         [ 20%]
tests/test_booking.py::test_user_bookings_history PASSED                 [ 22%]
tests/test_booking.py::test_cross_user_authorization_rejected PASSED     [ 23%]
tests/test_concurrency.py::test_concurrent_seat_booking_race_condition PASSED [ 25%]
tests/test_concurrency.py::test_db_unique_constraint_prevents_duplicate_booking_seats PASSED [ 26%]
tests/test_concurrency.py::test_concurrent_threads_ten_users_same_seat_race_condition PASSED [ 28%]
tests/test_frontend.py::test_serve_html_pages PASSED                     [ 29%]
tests/test_frontend.py::test_serve_static_assets PASSED                  [ 31%]
tests/test_movies.py::test_list_movies_pagination PASSED                 [ 32%]
tests/test_movies.py::test_filter_movies_by_genre PASSED                 [ 34%]
tests/test_movies.py::test_filter_movies_by_language PASSED              [ 35%]
tests/test_movies.py::test_search_movies_by_title PASSED                 [ 37%]
tests/test_movies.py::test_get_movie_by_id PASSED                        [ 38%]
tests/test_movies.py::test_get_movie_not_found PASSED                    [ 40%]
tests/test_movies.py::test_create_movie_success PASSED                   [ 41%]
tests/test_movies.py::test_create_movie_forbidden_for_non_admin PASSED   [ 43%]
tests/test_movies.py::test_create_movie_invalid_payload PASSED           [ 44%]
tests/test_movies.py::test_update_movie PASSED                           [ 46%]
tests/test_movies.py::test_delete_movie PASSED                           [ 47%]
tests/test_multi_agent.py::test_multi_agent_discovery_flow PASSED        [ 49%]
tests/test_multi_agent.py::test_multi_agent_showtimes_flow PASSED        [ 50%]
tests/test_multi_agent.py::test_multi_agent_booking_hold_flow PASSED     [ 52%]
tests/test_multi_agent.py::test_multi_agent_critic_blocks_unconfirmed_payment PASSED [ 53%]
tests/test_multi_agent.py::test_multi_agent_critic_rejects_negations_and_questions PASSED [ 55%]
tests/test_multi_agent.py::test_multi_agent_critic_approves_and_payment_finalizes PASSED [ 56%]
tests/test_multi_agent.py::test_multi_agent_support_policy_and_bookings PASSED [ 58%]
tests/test_multi_agent.py::test_get_multi_agent_trace_endpoint PASSED    [ 59%]
tests/test_pricing.py::test_seat_multipliers PASSED                      [ 61%]
tests/test_pricing.py::test_weekend_detection PASSED                     [ 62%]
tests/test_pricing.py::test_calculate_seat_price_weekday PASSED          [ 64%]
tests/test_pricing.py::test_calculate_seat_price_weekend PASSED          [ 65%]
tests/test_pricing.py::test_calculate_booking_totals_with_convenience_fee PASSED [ 67%]
tests/test_shows.py::test_list_theatres PASSED                           [ 68%]
tests/test_shows.py::test_list_shows_filtering PASSED                    [ 70%]
tests/test_shows.py::test_show_conflict_detection PASSED                 [ 71%]
tests/test_shows.py::test_create_show_forbidden_for_non_admin PASSED     [ 73%]
tests/test_shows.py::test_create_show_invalid_times PASSED               [ 74%]
tests/test_single_agent.py::test_agent_search_movies_tool_flow PASSED    [ 76%]
tests/test_single_agent.py::test_agent_get_showtimes_tool_flow PASSED    [ 77%]
tests/test_single_agent.py::test_agent_off_topic_guardrail PASSED        [ 79%]
tests/test_single_agent.py::test_agent_prompt_injection_guardrail PASSED [ 80%]
tests/test_single_agent.py::test_confirmation_guardrail_blocks_unconfirmed_booking PASSED [ 82%]
tests/test_single_agent.py::test_confirmation_guardrail_negations_and_affirmations PASSED [ 83%]
tests/test_single_agent.py::test_single_agent_complete_booking_journey PASSED [ 85%]
tests/test_users_screens.py::test_list_users PASSED                      [ 86%]
tests/test_users_screens.py::test_create_user_success_and_duplicate_conflict PASSED [ 88%]
tests/test_users_screens.py::test_screen_seat_grid_generation PASSED     [ 89%]
tests/test_validation.py::test_max_six_seats_limit PASSED                [ 91%]
tests/test_validation.py::test_empty_seats_list PASSED                   [ 92%]
tests/test_validation.py::test_seat_from_different_screen PASSED         [ 94%]
tests/test_validation.py::test_cannot_book_past_show PASSED              [ 95%]
tests/test_validation.py::test_cannot_book_cancelled_show PASSED         [ 97%]
tests/test_validation.py::test_phone_validation_regex PASSED             [ 98%]
tests/test_validation.py::test_show_base_price_must_be_positive PASSED   [100%]

============================= 67 passed in 3.12s ==============================
```

---

## 5. Architectural Decision Records (ADRs) Summary

| ADR | Decision | Context & Rationale | Alternatives Considered |
|---|---|---|---|
| **ADR-001** | SQLite In-Memory for Automated Tests | Enables zero-dependency local testing without requiring a live external MySQL daemon. | External MySQL server (burdensome CI setup), Docker-in-Docker testcontainers (slow startup). |
| **ADR-002** | Double-Booking Prevention via Composite DB Unique Constraint | Primary guarantee enforced by `UNIQUE KEY uq_show_seat (show_id, seat_id)` on `booking_seats`. Overlapping attempts trigger immediate DB `IntegrityError` converted into HTTP 409. | In-memory Redis lock (extra dependency), optimistic locking with version columns (more complex without extra safety). |
| **ADR-003** | 5-Minute Seat Hold TTL with Lazy Expiration | Holds seats with `expires_at = created_at + 300s`. Lazy evaluation triggers `release_expired_holds` whenever seats or bookings are accessed. | Redis/Celery delayed tasks (requires worker queue infrastructure). |
| **ADR-004** | Centralized Pure Pricing Engine | Pure functions in `app/services/pricing.py` calculate tier multipliers, weekend 10% surcharges, and 2% convenience fees across all API routers and AI tools. | Ad-hoc calculations in SQL queries or client-side JavaScript (vulnerable to client tampering). |
| **ADR-005** | Deterministic LLM Mock Fallback | Inspects `LLM_API_KEY`. If missing, switches to rule-based mock engine reporting `"mock": true`, making all AI endpoints testable offline. | Crashing on startup (blocks students and automated evaluation). |
| **ADR-006** | Multi-Agent Orchestration via Typed State & CriticAgent | Specialized worker agents communicate through a typed Pydantic state. `CriticAgent` validates all state changes prior to execution. | Unstructured agent-to-agent peer messaging (hard to audit, prone to loops). |

---

## 6. Project File Inventory

```
movie-ticket-booking/
├── .env.example                     # Environment variable template
├── Dockerfile                       # Python 3.12 container definition
├── docker-compose.yml               # MySQL 8 + FastAPI multi-container orchestration
├── pytest.ini                       # Test configuration
├── README.md                        # Master documentation, architecture & exercises
├── requirements.txt                 # Frozen production dependencies
├── app/
│   ├── config.py                    # Pydantic Settings configuration
│   ├── database.py                  # SQLAlchemy engine, sessionmaker, get_db dependency
│   ├── errors.py                    # Custom AppError hierarchy & standard JSON handlers
│   ├── main.py                      # FastAPI app, static mounts, CORS, health probe
│   ├── models.py                    # SQLAlchemy 2.0 ORM mapped entities (10 tables)
│   ├── schemas.py                   # Pydantic v2 schemas for all requests and responses
│   ├── ai/
│   │   ├── genai_features.py        # Stateless GenAI functions (summary, recommend, reviews, email)
│   │   ├── guardrails.py            # Rate limiter, injection detector, off-topic & confirmation checks
│   │   ├── llm_client.py            # OpenAI SDK wrapper with deterministic mock fallback
│   │   ├── multi_agent.py           # Orchestrator, Discovery, Booking, Payment, Support, Critic agents
│   │   ├── prompts.py               # Centralized prompt templates & cinema policy reference
│   │   ├── single_agent.py          # ReAct tool-calling loop (max 6 turns) with audit logging
│   │   └── tools.py                 # 8 database tools with strict Pydantic schemas & registry
│   ├── routers/
│   │   ├── ai_agent.py              # Single-agent chat endpoint (/api/ai/agent/chat)
│   │   ├── ai_genai.py              # GenAI endpoints (/api/ai/genai/*)
│   │   ├── ai_multi_agent.py        # Multi-agent chat & trace endpoints (/api/ai/multi/*)
│   │   ├── bookings.py              # Seat hold, booking inspection, cancellation
│   │   ├── movies.py                # Movies CRUD with pagination and filtering
│   │   ├── payments.py              # Payment confirmation gateway
│   │   ├── screens.py               # Screens inspection & seat grid generation
│   │   ├── seats.py                 # Real-time seat availability map
│   │   ├── shows.py                 # Show scheduling with screen collision checks
│   │   ├── theatres.py              # Theatre multiplexes
│   │   └── users.py                 # User profile management
│   └── services/
│       ├── booking_service.py       # Seat locking, 5-min holds, cancellation refund tiers
│       ├── pricing.py               # Tier multipliers, weekend surcharge, convenience fee
│       └── seed.py                  # Idempotent database seeder (movies, theatres, shows, users)
├── docs/
│   ├── AI_DESIGN.md                 # Agent tool access matrix & guardrail specifications
│   ├── API.md                       # Comprehensive API specification with curl examples
│   ├── ARCHITECTURE.md              # Mermaid component, ER, and sequence diagrams
│   ├── COMPLETE_PROJECT_REPORT.md   # This comprehensive end-to-end report
│   ├── DECISIONS.md                 # Architectural Decision Records (ADR-001 to ADR-006)
│   ├── KNOWN_ISSUES.md              # Technical limitations & roadmap items
│   ├── PLAN.md                      # Phase-by-phase task checklist
│   ├── PROGRESS_LOG.md              # Historical progress audit log & final verification report
│   └── PROJECT_CONTEXT.md           # Project rules, tech stack & context protocol
├── frontend/
│   ├── admin.html                   # Studio admin portal (movies, shows, revenue metrics)
│   ├── assistant.html               # AI Concierge with 3-mode switcher & agent step trace
│   ├── bookings.html                # Checkout, payment gateway, voucher, cancellations
│   ├── index.html                   # Landing page, value props, now-showing grid
│   ├── movies.html                  # Catalog browsing, filtering, search, showtimes modal
│   ├── seats.html                   # Interactive curved seat matrix & 5-minute hold timer
│   ├── css/
│   │   └── styles.css               # Cinematic dark theme, responsive grid/flex, badges
│   └── js/
│       ├── admin.js                 # Admin dashboard & show scheduling controller
│       ├── api.js                   # Unified fetch client, XSS escaping, user switcher
│       ├── assistant.js             # AI Concierge chat & multi-agent trace controller
│       ├── bookings.js              # Checkout payment & booking history controller
│       ├── movies.js                # Movie catalog, filters & showtimes modal controller
│       └── seats.js                 # Seat selection, live pricing & hold timer controller
├── sql/
│   ├── schema.sql                   # MySQL 8 DDL with FKs, indexes & unique constraints
│   └── seed.sql                     # Raw SQL seed records
└── tests/
    ├── conftest.py                  # Pytest fixtures, in-memory SQLite DB & client
    ├── test_ai.py                   # GenAI endpoint tests (summary, recommend, reviews, email)
    ├── test_booking.py              # Booking lifecycle, hold TTL, cancellation refund tiers
    ├── test_concurrency.py          # Simultaneous seat booking race conditions (201 vs 409)
    ├── test_frontend.py             # Static HTML page routing & asset delivery
    ├── test_movies.py               # Movies CRUD, filtering, pagination, sorting
    ├── test_multi_agent.py          # Multi-agent delegation, Critic rejection & trace logs
    ├── test_pricing.py              # Pricing engine unit tests
    ├── test_shows.py                # Shows scheduling, collision checks, theatre list
    ├── test_single_agent.py         # Single-agent ReAct loop, guardrails & journey
    ├── test_users_screens.py        # Users CRUD & screen seat grid layout
    └── test_validation.py           # Pydantic v2 validation rules & edge cases
```

---

## 7. How to Run and Verify the System

### Turnkey Native Execution
```bash
# 1. Initialize and seed database
python -m app.services.seed

# 2. Run the FastAPI dev server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Navigate in your browser to:
- **Web App**: [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **System Health Endpoint**: [http://localhost:8000/health](http://localhost:8000/health)

### Docker Compose Execution
```bash
docker compose up --build
```

### Automated Testing Suite
```bash
# Run full suite (defaults to in-memory SQLite with QueuePool)
pytest -v

# Or run against live MySQL 8 instance
TEST_DATABASE_URL="mysql+pymysql://cineverse:cineverse_secret@localhost:3306/movie_ticket_booking" pytest -v
```
All **67 automated tests** pass synchronously in **~3.1 seconds**.
