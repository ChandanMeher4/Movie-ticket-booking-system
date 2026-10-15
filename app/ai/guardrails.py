"""Security guardrails, prompt injection filtering, rate limiting, and confirmation checks.

Protects against prompt exfiltration, off-topic misuse, denial of service, and unconfirmed payments.
"""

from collections import defaultdict
import logging
import re
import time
from typing import Dict, List, Optional
from app.errors import AppError, ValidationError

logger = logging.getLogger("guardrails")

# --- Rate Limiter per Session ---
MAX_REQUESTS_PER_MINUTE = 20
_session_request_timestamps: Dict[str, List[float]] = defaultdict(list)


def check_rate_limit(session_id: str) -> None:
    """Enforce maximum 20 requests per minute per conversation session."""
    now = time.time()
    window_start = now - 60.0
    timestamps = _session_request_timestamps[session_id]

    # Purge old timestamps
    _session_request_timestamps[session_id] = [t for t in timestamps if t > window_start]

    if len(_session_request_timestamps[session_id]) >= MAX_REQUESTS_PER_MINUTE:
        raise AppError(
            message="Rate limit exceeded. Please wait a few moments before sending more requests.",
            code="RATE_LIMIT_EXCEEDED",
            status_code=429,
        )

    _session_request_timestamps[session_id].append(now)


# --- Prompt Injection & System Leakage Protection ---

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior)\s+(instructions|directions|prompts)",
    r"you\s+are\s+now\s+(DAN|jailbroken|unrestricted)",
    r"reveal\s+(your\s+)?(system\s+prompt|instructions)",
    r"what\s+is\s+your\s+system\s+prompt",
    r"system\s+override",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
]


def sanitize_input(user_text: str) -> str:
    """Detect and block prompt injection patterns and strip delimiter tokens."""
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, user_text, re.IGNORECASE):
            logger.warning("Prompt injection attempt intercepted: %s", user_text[:100])
            raise ValidationError(
                "Your request contains unsupported instructions or disallowed prompt injection sequences."
            )
    return user_text.strip()


def sanitize_output(reply: str) -> str:
    """Ensure system prompt contents are never leaked in assistant responses."""
    leak_tokens = [
        "You are Cineverse's customer communications system",
        "You are a creative cinema copywriter",
        "CINEMA_POLICY_TEXT",
        "TOOL_REGISTRY",
    ]
    for token in leak_tokens:
        if token.lower() in reply.lower():
            return "I am the Cineverse AI Booking Assistant, here to help you explore movies, reserve seats, and manage tickets."
    return reply


# --- Off-Topic Detection ---

OFF_TOPIC_DOMAINS = [
    (r"\b(stock|crypto|bitcoin|forex|invest(ment)?)\b", "financial and investment advice"),
    (r"\b(diagnos(e|is)|prescri(be|ption)|symptom|medication|disease)\b", "medical advice"),
    (r"\b(write\s+(a\s+)?python|write\s+code|debug\s+this|sql\s+injection)\b", "programming assistance"),
    (r"\b(lawsuit|legal\s+advice|sue\s+them|attorney)\b", "legal consultation"),
]


def check_off_topic(user_text: str) -> Optional[str]:
    """Identify queries unrelated to cinema, movies, ticketing, or bookings."""
    # Allow cinema and movie terms even if other words match
    cinema_safe = any(
        w in user_text.lower()
        for w in ["movie", "ticket", "seat", "show", "theatre", "cineverse", "cinema", "film", "booking"]
    )
    if cinema_safe:
        return None

    for pattern, domain in OFF_TOPIC_DOMAINS:
        if re.search(pattern, user_text, re.IGNORECASE):
            return (
                f"I specialize exclusively in movie discovery, showtimes, seat selections, and ticket bookings at Cineverse. "
                f"I cannot provide {domain}. How can I help with your movie plans today?"
            )
    return None


# --- Explicit Confirmation Guardrail ---

AFFIRMATIVE_PATTERN = r"\b(yes|confirm|proceed|approve|authorized|pay now|confirm and pay|book it now|proceed with payment)\b"
NEGATION_OR_HESITATION_PATTERN = r"\b(don'?t|not yet|wait|no|nope|never|stop|abort|hold on|hang on|thinking|maybe|pause|later|tomorrow|next week|why|how|who|should i|can i)\b|\bbut\b"


def check_confirmation_guardrail(
    tool_name: str, conversation_history: List[dict]
) -> None:
    """Strictly prevent booking confirmation or cancellations without affirmative user approval.

    Verifies:
    1. A previous assistant message presented a summary (booking reference, price, or seats).
    2. The user's most recent reply explicitly affirms consent.
    3. The user reply does NOT contain negations, hesitations, or conditionals ("don't pay", "yes but wait", "not yet").
    """
    if tool_name not in ("confirm_booking", "cancel_booking"):
        return

    # Check that the assistant has recently presented a booking or price summary
    assistant_messages = [m for m in conversation_history if m.get("role") == "assistant"]
    has_prior_summary = any(
        any(token in m.get("content", "").lower() for token in ["₹", "total", "booking", "seats", "held", "reference"])
        for m in assistant_messages
    )
    if not has_prior_summary:
        raise ValidationError(
            f"Safety Guardrail: '{tool_name}' cannot be executed because no booking or price summary was presented to the user."
        )

    # Find the most recent user message
    user_messages = [m for m in conversation_history if m.get("role") == "user"]
    if not user_messages:
        raise ValidationError(
            f"Action '{tool_name}' requires explicit user confirmation. No user message found."
        )

    last_user_message = user_messages[-1].get("content", "").lower()

    # Reject if message contains negations, hesitations, questions, or conditionals
    has_negation = bool(re.search(NEGATION_OR_HESITATION_PATTERN, last_user_message))
    is_question = "?" in last_user_message
    has_affirmation = bool(re.search(AFFIRMATIVE_PATTERN, last_user_message))

    if has_negation or is_question or not has_affirmation:
        raise ValidationError(
            f"Safety Guardrail: '{tool_name}' requires explicit affirmative user confirmation. "
            f"User message lacked affirmation or contained hesitation/negation ('{last_user_message.strip()}')."
        )
