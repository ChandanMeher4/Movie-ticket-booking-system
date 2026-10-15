# AI System Design

## 1. Generative AI Layer (Single Turn, No Tools)
Direct stateless completions using OpenAI-compatible client with deterministic fallback:
- **Movie Summary**: Produces targeted marketing blurbs in tones like `exciting`, `poetic`, `family-friendly`.
- **Mood Recommender**: Ingests active movie catalog + user prompt, returns ranked list of 3 movies with rationales.
- **Review Summarizer**: Ingests customer review excerpts, extracts structured JSON with `sentiment` (positive, mixed, negative), `pros`, `cons`, and `summary`.
- **Booking Email Generator**: Generates professional transaction confirmation emails with movie, showtime, and seat details.

## 2. Tools & Service Bindings
| Tool Name | Parameters | Side Effects | Requires User Confirmation |
|---|---|---|---|
| `search_movies` | `query: str`, `genre: str`, `language: str` | None (Read-only) | No |
| `get_showtimes` | `movie_id: int`, `date: str`, `city: str` | None (Read-only) | No |
| `get_available_seats` | `show_id: int`, `seat_type: str`, `count: int` | None (Read-only) | No |
| `calculate_price` | `show_id: int`, `seat_ids: list[int]` | None (Read-only) | No |
| `hold_seats` | `user_id: int`, `show_id: int`, `seat_ids: list[int]` | Writes pending booking & holds seats for 5 mins | No |
| `confirm_booking` | `booking_id: int`, `payment_method: str` | Changes booking to confirmed, records payment | **Yes (Explicit confirmation required)** |
| `cancel_booking` | `booking_id: int` | Cancels booking and triggers refund | **Yes (Explicit confirmation required)** |
| `get_my_bookings` | `user_id: int` | None (Read-only) | No |

## 3. Guardrails Specification (`app/ai/guardrails.py`)
1. **Explicit Confirmation**: The assistant will never call `confirm_booking` or `cancel_booking` unless the conversation history shows the user was presented with the exact items, seat numbers, price, and clearly affirmed.
2. **Schema Validation**: All tool arguments are parsed through Pydantic schemas before invocation.
3. **Prompt Injection & System Leakage Protection**: User messages and tool outputs are scanned for system prompt exfiltration tokens (`system prompt`, `ignore previous instructions`, `DAN`, `<|im_start|>`) and sanitized.
4. **Off-Topic Refusal**: Queries regarding medical, legal, political, or non-cinema domains receive a polite redirect.
5. **Rate Limiting & Audit Logging**: 20 requests per minute per session; every tool invocation is stored in the `ai_logs` table with execution latency in milliseconds.

## 4. Multi-Agent Orchestration Architecture
```
             +--------------------+
             | Orchestrator Agent |
             +---------+----------+
                       |
       +---------------+---------------+---------------+
       |               |               |               |
+------v-------+ +-----v------+ +------v-------+ +-----v-------+
|  Discovery   | |  Booking   | |   Payment    | |   Support   |
|    Agent     | |   Agent    | |    Agent     | |    Agent    |
+--------------+ +-----+------+ +--------------+ +-------------+
                       |
               +-------v--------+
               |  Critic Agent  | (State Verifier & Policy Check)
               +----------------+
```

### Specialist Agent Responsibilities
- **OrchestratorAgent**: Evaluates conversation context, selects appropriate specialist or synthesizes final response, coordinates execution flow.
- **DiscoveryAgent**: Specialized in catalog browsing, showtime discovery, and genre filtering. Allowed tools: `search_movies`, `get_showtimes`.
- **BookingAgent**: Guides seat selection, pricing breakdown, and initial seat hold. Allowed tools: `get_available_seats`, `calculate_price`, `hold_seats`.
- **PaymentAgent**: Handles payment confirmation and mock gateway errors. Allowed tools: `confirm_booking`.
- **SupportAgent**: Handles cancellations, policy inquiries, and refund calculations. Allowed tools: `cancel_booking`, `get_my_bookings`.
- **NotificationAgent**: Formats user confirmations and human-friendly receipts.
- **CriticAgent (Verifier)**: Pre-execution guard; verifies that seats belong to the target show, prices match the pricing engine, and user confirmation is present before releasing state-altering actions. Rejects invalid plans with explicit feedback.
