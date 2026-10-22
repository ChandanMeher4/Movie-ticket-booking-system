"""Multi-Agent AI Orchestration system for Cineverse.

Implements specialized agents with the principle of least privilege, coordinated
by an OrchestratorAgent and audited by a pre-execution verifier CriticAgent.
All agents share and mutate a typed Pydantic session state.
"""

from datetime import datetime, timedelta
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.guardrails import (
    AFFIRMATIVE_PATTERN,
    CANCEL_AFFIRMATIVE_PATTERN,
    NEGATION_OR_HESITATION_PATTERN,
    check_confirmation_guardrail,
    check_off_topic,
    check_rate_limit,
    sanitize_input,
)
from app.ai.llm_client import llm_client
from app.ai.prompts import (
    BOOKING_AGENT_SYSTEM_PROMPT,
    CINEMA_POLICY_TEXT,
    CRITIC_AGENT_SYSTEM_PROMPT,
    DISCOVERY_AGENT_SYSTEM_PROMPT,
    NOTIFICATION_AGENT_SYSTEM_PROMPT,
    ORCHESTRATOR_SYSTEM_PROMPT,
    PAYMENT_AGENT_SYSTEM_PROMPT,
    SUPPORT_AGENT_SYSTEM_PROMPT,
)
from app.ai.tools import TOOL_REGISTRY, TOOL_SCHEMAS
from app.config import settings
from app.errors import BadRequestError, ValidationError
from app.models import AILog, Booking, BookingStatus, Movie, Show, ShowStatus


# --- Shared Typed State ---

class AgentSessionState(BaseModel):
    """Shared typed state passed across specialized agents during orchestration."""
    session_id: str
    user_id: int
    current_intent: Optional[str] = None
    selected_movie_id: Optional[int] = None
    selected_movie_title: Optional[str] = None
    selected_show_id: Optional[int] = None
    selected_seat_ids: List[int] = Field(default_factory=list)
    calculated_price: Optional[float] = None
    held_booking_id: Optional[int] = None
    booking_confirmed: bool = False
    user_confirmed: bool = False
    critic_approved: bool = False
    critic_feedback: Optional[str] = None
    pending_action: Optional[str] = None
    last_tool_result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class AgentStepTrace(BaseModel):
    """Structured audit trace of an individual specialist agent's action."""
    agent: str
    input: str
    output: str
    tools_used: List[str] = Field(default_factory=list)
    duration_ms: int


class MultiAgentChatResponse(BaseModel):
    """Complete response envelope for multi-agent interactions."""
    reply: str
    agent_trace: List[AgentStepTrace]
    state: AgentSessionState
    mock: bool = True


# In-memory stores for session states and execution traces
SESSION_STATES: Dict[str, AgentSessionState] = {}
SESSION_TRACES: Dict[str, List[AgentStepTrace]] = {}


def get_or_create_state(session_id: str, user_id: int) -> AgentSessionState:
    """Retrieve existing state for a session or initialize a fresh typed state."""
    if session_id not in SESSION_STATES:
        SESSION_STATES[session_id] = AgentSessionState(session_id=session_id, user_id=user_id)
    return SESSION_STATES[session_id]


# --- Specialized Sub-Agents ---

class DiscoveryAgent:
    """Movie search, genre exploration, and showtime schedule specialist."""
    NAME = "DiscoveryAgent"
    ALLOWED_TOOLS = {"search_movies", "get_showtimes"}

    @classmethod
    def run(cls, db: Session, state: AgentSessionState, query: str) -> Tuple[str, List[str]]:
        tools_used = []
        msg_lower = query.lower()

        # Check for showtime inquiry (explicit showtimes, schedule, or timings)
        is_showtime_query = any(w in msg_lower for w in ["showtime", "show times", "timings", "schedule", "when is"]) or (
            "shows" in msg_lower and "movie" not in msg_lower and "search" not in msg_lower and "find" not in msg_lower
        )
        if is_showtime_query:
            movie_id = state.selected_movie_id or 1
            # Try to identify movie by title
            for m in db.scalars(select(Movie).where(Movie.is_active == True)).all():
                if m.title.lower() in msg_lower:
                    movie_id = m.id
                    state.selected_movie_id = m.id
                    state.selected_movie_title = m.title
                    break

            handler, _ = TOOL_REGISTRY["get_showtimes"]
            res = handler(db, {"movie_id": movie_id})
            tools_used.append("get_showtimes")
            state.last_tool_result = res

            count = res.get("count", 0)
            if count == 0:
                reply = f"Currently there are no scheduled upcoming showtimes for movie ID {movie_id}."
            else:
                shows = res.get("showtimes", [])[:3]
                lines = [f"- Show #{s['show_id']}: {s['theatre']} ({s['screen']}) at {s['start_time']} (Base: ₹{s['base_price']})" for s in shows]
                state.selected_show_id = shows[0]["show_id"]
                reply = f"Found {count} upcoming showtimes for '{shows[0]['movie_title']}':\n" + "\n".join(lines)
            return reply, tools_used

        # Default to movie search
        genre = None
        for g in ["action", "sci-fi", "animation", "drama", "comedy", "thriller", "horror"]:
            if g in msg_lower:
                genre = g
                break

        handler, _ = TOOL_REGISTRY["search_movies"]
        res = handler(db, {"query": query if not genre else "", "genre": genre})
        tools_used.append("search_movies")
        state.last_tool_result = res

        movies = res.get("movies", [])
        if not movies:
            return "No movies found matching your request. Try searching for 'sci-fi' or 'action'.", tools_used

        top = movies[0]
        state.selected_movie_id = top["id"]
        state.selected_movie_title = top["title"]
        titles = ", ".join([f"'{m['title']}' ({m['genre']})" for m in movies[:4]])
        reply = f"Here are active movies available in Cineverse: {titles}. Would you like to check showtimes for '{top['title']}'?"
        return reply, tools_used


class BookingAgent:
    """Seat availability, pricing calculation, and 5-minute hold specialist."""
    NAME = "BookingAgent"
    ALLOWED_TOOLS = {"get_available_seats", "calculate_price", "hold_seats"}

    @classmethod
    def run(cls, db: Session, state: AgentSessionState, query: str) -> Tuple[str, List[str]]:
        tools_used = []
        msg_lower = query.lower()

        # Resolve target show_id: from query or state or find next future show
        show_match = re.search(r"show\s*#?(\d+)", msg_lower)
        if show_match:
            show_id = int(show_match.group(1))
            state.selected_show_id = show_id
        elif state.selected_show_id:
            show_id = state.selected_show_id
        else:
            future_show_id = db.scalar(
                select(Show.id)
                .where(Show.status == ShowStatus.SCHEDULED, Show.start_time > datetime.utcnow())
                .order_by(Show.start_time.asc())
                .limit(1)
            )
            show_id = future_show_id or 1
            state.selected_show_id = show_id

        # Check for seat availability inquiry
        if "seat" in msg_lower and ("available" in msg_lower or "check" in msg_lower or "list" in msg_lower):
            handler, _ = TOOL_REGISTRY["get_available_seats"]
            res = handler(db, {"show_id": show_id, "count": 2})
            tools_used.append("get_available_seats")
            state.last_tool_result = res

            rec = res.get("recommended_seats", [])
            state.selected_seat_ids = [s["seat_id"] for s in rec]
            labels = ", ".join([f"{s['label']} ({s['seat_type']} ₹{s['price']})" for s in rec])
            reply = f"For Show #{show_id}, there are {res.get('total_available', 0)} seats available. Recommended seats: {labels}."
            return reply, tools_used

        # Check for price calculation inquiry
        if "price" in msg_lower or "cost" in msg_lower or "how much" in msg_lower:
            seats = state.selected_seat_ids if state.selected_seat_ids else [1, 2]
            handler, _ = TOOL_REGISTRY["calculate_price"]
            res = handler(db, {"show_id": show_id, "seat_ids": seats})
            tools_used.append("calculate_price")
            state.last_tool_result = res
            state.calculated_price = res.get("total_amount")

            reply = (
                f"Price breakdown for {res.get('seat_count')} seats in Show #{show_id}: "
                f"Subtotal: ₹{res.get('subtotal', 0):.2f}, "
                f"Convenience Fee (2%): ₹{res.get('convenience_fee', 0):.2f}, "
                f"Total Amount: ₹{res.get('total_amount', 0):.2f}."
            )
            return reply, tools_used

        # Hold seats action
        if "hold" in msg_lower or "reserve" in msg_lower or "book" in msg_lower:
            seats = state.selected_seat_ids if state.selected_seat_ids else [1, 2]
            handler, _ = TOOL_REGISTRY["hold_seats"]
            res = handler(db, {"user_id": state.user_id, "show_id": show_id, "seat_ids": seats})
            tools_used.append("hold_seats")
            state.last_tool_result = res

            if res.get("success"):
                state.held_booking_id = res.get("booking_id")
                state.calculated_price = res.get("total_amount")
                reply = (
                    f"Seats successfully held! Booking #{res.get('booking_id')}, "
                    f"Total: ₹{res.get('total_amount'):.2f}. "
                    f"These seats are locked for 5 minutes (expires at {res.get('expires_at')}). "
                    f"Please confirm: Do you want to proceed with payment to finalize your booking?"
                )
            else:
                reply = f"Unable to hold seats: {res.get('error')}. Let us select alternative available seats."
            return reply, tools_used

        return "Booking specialist ready. I can check available seats, calculate pricing, or hold seats for your show.", tools_used


class CriticAgent:
    """Pre-execution verifier ensuring all state-changing actions are authorized, validated, and confirmed."""
    NAME = "CriticAgent"

    @classmethod
    def evaluate(cls, state: AgentSessionState, proposed_action: str, user_message: str) -> Tuple[bool, str]:
        """Verify proposed state-changing actions against validation rules and user confirmation."""
        msg_lower = user_message.lower()

        # 1. Verification for Payment Confirmation
        if proposed_action == "confirm_booking":
            if not state.held_booking_id:
                return False, "No active held booking was found in session state. Please hold seats before payment."

            # Check for negation, hesitation, conditional, or questions
            has_negation = bool(re.search(NEGATION_OR_HESITATION_PATTERN, msg_lower))
            is_question = "?" in msg_lower
            has_affirmation = bool(re.search(AFFIRMATIVE_PATTERN, msg_lower))

            if has_negation or is_question or not has_affirmation:
                return False, (
                    f"CriticAgent verification rejected: Payment requires explicit user confirmation without hesitation or conditions. "
                    f"Please confirm affirmatively (e.g., 'Yes, pay now') that you want to pay ₹{state.calculated_price or 0:.2f} for Booking #{state.held_booking_id}."
                )

            # Check that price is valid and positive
            if state.calculated_price is not None and state.calculated_price <= 0:
                return False, "CriticAgent verification rejected: Calculated booking amount must be greater than zero."

            return True, f"CriticAgent approved: Explicit user confirmation verified for Booking #{state.held_booking_id}."

        # 2. Verification for Booking Cancellation
        if proposed_action == "cancel_booking":
            has_negation = bool(re.search(NEGATION_OR_HESITATION_PATTERN, msg_lower))
            is_question = "?" in msg_lower
            cancel_affirmative = bool(re.search(CANCEL_AFFIRMATIVE_PATTERN, msg_lower))
            if has_negation or is_question or not cancel_affirmative:
                return False, "CriticAgent verification rejected: Cancellation requires explicit user confirmation without questions or hesitation."
            return True, "CriticAgent approved: Cancellation request validated against cinema cutoff policy."

        # Default approval for non-critical/read actions
        return True, "CriticAgent approved: Action adheres to policy."


class PaymentAgent:
    """Payment processing and booking confirmation specialist."""
    NAME = "PaymentAgent"
    ALLOWED_TOOLS = {"confirm_booking"}

    @classmethod
    def run(cls, db: Session, state: AgentSessionState, query: str) -> Tuple[str, List[str]]:
        tools_used = []
        if not state.critic_approved:
            return (
                f"Payment blocked by CriticAgent: {state.critic_feedback or 'Awaiting user confirmation.'}",
                tools_used,
            )

        booking_id = state.held_booking_id or 1
        method = "card"
        if "upi" in query.lower():
            method = "upi"
        elif "wallet" in query.lower():
            method = "wallet"

        handler, _ = TOOL_REGISTRY["confirm_booking"]
        res = handler(db, {"booking_id": booking_id, "payment_method": method, "user_id": state.user_id})
        tools_used.append("confirm_booking")
        state.last_tool_result = res

        if res.get("success"):
            state.booking_confirmed = True
            reply = (
                f"Payment authorized successfully! Booking #{res.get('booking_id')} is confirmed. "
                f"Transaction Reference: {res.get('txn_ref')}, Total Paid: ₹{res.get('total_amount'):.2f}."
            )
        else:
            reply = f"Payment failed: {res.get('error')}. You can retry with another payment method (card, upi, wallet)."
        return reply, tools_used


class SupportAgent:
    """Customer support, cancellation, refund calculation, and policy explanation specialist."""
    NAME = "SupportAgent"
    ALLOWED_TOOLS = {"cancel_booking", "get_my_bookings"}

    @classmethod
    def run(cls, db: Session, state: AgentSessionState, query: str) -> Tuple[str, List[str]]:
        tools_used = []
        msg_lower = query.lower()

        # Policy questions
        if "policy" in msg_lower or "rules" in msg_lower or "refund tier" in msg_lower or "terms" in msg_lower:
            reply = (
                "Cineverse Cancellation & Refund Policy:\n"
                "1. Cancellation allowed up to 2 hours before scheduled showtime.\n"
                "2. >24 hours before showtime: 100% refund of ticket price (excluding 2% convenience fee).\n"
                "3. 2 to 24 hours before showtime: 50% refund of ticket price.\n"
                "4. <2 hours before showtime: Strictly non-refundable.\n"
                "5. Seats are held for 5 minutes maximum during booking."
            )
            return reply, tools_used

        # Booking history inquiry
        if "my booking" in msg_lower or "my tickets" in msg_lower or "history" in msg_lower:
            handler, _ = TOOL_REGISTRY["get_my_bookings"]
            res = handler(db, {"user_id": state.user_id})
            tools_used.append("get_my_bookings")
            state.last_tool_result = res

            bookings = res.get("bookings", [])
            if not bookings:
                return "You have no active or previous bookings recorded.", tools_used

            items = [f"- Booking #{b['booking_id']}: '{b['movie']}' at {b['theatre']} ({b['status'].upper()}) - ₹{b['total_amount']:.2f}" for b in bookings[:3]]
            reply = f"Found {len(bookings)} booking(s) for your account:\n" + "\n".join(items)
            return reply, tools_used

        # Cancellation request
        if "cancel" in msg_lower:
            match = re.search(r"booking\s*#?(\d+)", msg_lower)
            booking_id = int(match.group(1)) if match else (state.held_booking_id or 1)

            if not state.critic_approved:
                return (
                    f"Cancellation verification: {state.critic_feedback or 'Please confirm that you want to cancel Booking #' + str(booking_id)}.",
                    tools_used,
                )

            handler, _ = TOOL_REGISTRY["cancel_booking"]
            res = handler(db, {"booking_id": booking_id, "user_id": state.user_id})
            tools_used.append("cancel_booking")
            state.last_tool_result = res

            if res.get("success"):
                reply = (
                    f"Booking #{res.get('booking_id')} successfully cancelled. "
                    f"Refund tier: {res.get('refund_percentage')}%. "
                    f"Refund Amount: ₹{res.get('refund_amount'):.2f} credited back to original payment method."
                )
            else:
                reply = f"Cancellation rejected: {res.get('error')}"
            return reply, tools_used

        return "Support specialist here. I can explain cancellation policies, list your bookings, or process refund cancellations.", tools_used


class NotificationAgent:
    """Communication formatting specialist for receipts, confirmations, and reminders."""
    NAME = "NotificationAgent"

    @classmethod
    def run(cls, state: AgentSessionState, message_type: str = "confirmation") -> Tuple[str, List[str]]:
        if message_type == "confirmation" and state.booking_confirmed:
            notice = (
                f"\n\n[Notification Summary]:\n"
                f"Booking Reference: #{state.held_booking_id}\n"
                f"Amount Paid: ₹{state.calculated_price or 0:.2f}\n"
                f"Entry Guidelines: Please arrive at the cinema 15 minutes prior to showtime with a valid photo ID. Enjoy your show!"
            )
            return notice, []
        return "", []


# --- Orchestrator Engine ---

class OrchestratorEngine:
    """Coordinates intent routing, multi-step sub-agent execution, and audit tracing."""

    @classmethod
    def process_chat(
        cls,
        db: Session,
        session_id: str,
        user_id: int,
        message: str,
    ) -> MultiAgentChatResponse:
        start_time = time.time()

        # 1. Apply Guardrails
        check_rate_limit(session_id)
        sanitized_msg = sanitize_input(message)
        off_topic_refusal = check_off_topic(sanitized_msg)
        if off_topic_refusal:
            trace = AgentStepTrace(
                agent="OrchestratorAgent",
                input=message,
                output=off_topic_refusal,
                tools_used=[],
                duration_ms=int((time.time() - start_time) * 1000),
            )
            cls._record_trace(session_id, [trace])
            return MultiAgentChatResponse(
                reply=off_topic_refusal,
                agent_trace=[trace],
                state=get_or_create_state(session_id, user_id),
                mock=settings.is_mock_llm,
            )

        # 2. Retrieve or initialize shared session state
        state = get_or_create_state(session_id, user_id)
        traces: List[AgentStepTrace] = []
        msg_lower = sanitized_msg.lower()

        # 3. Classify intent
        intent = cls._classify_intent(msg_lower, state)
        state.current_intent = intent

        orchestrator_trace = AgentStepTrace(
            agent="OrchestratorAgent",
            input=sanitized_msg,
            output=f"Intent classified as '{intent}'. Routing to appropriate specialist sub-agents.",
            tools_used=[],
            duration_ms=int((time.time() - start_time) * 1000),
        )
        traces.append(orchestrator_trace)

        final_reply = ""

        # 4. Route and execute through specialists
        if intent == "discovery":
            step_start = time.time()
            reply, tools = DiscoveryAgent.run(db, state, sanitized_msg)
            traces.append(
                AgentStepTrace(
                    agent=DiscoveryAgent.NAME,
                    input=sanitized_msg,
                    output=reply,
                    tools_used=tools,
                    duration_ms=int((time.time() - step_start) * 1000),
                )
            )
            final_reply = reply

        elif intent == "booking":
            step_start = time.time()
            reply, tools = BookingAgent.run(db, state, sanitized_msg)
            traces.append(
                AgentStepTrace(
                    agent=BookingAgent.NAME,
                    input=sanitized_msg,
                    output=reply,
                    tools_used=tools,
                    duration_ms=int((time.time() - step_start) * 1000),
                )
            )
            final_reply = reply

        elif intent == "payment":
            # State-changing action: CriticAgent must inspect first
            step_start = time.time()
            critic_pass, critic_feedback = CriticAgent.evaluate(state, "confirm_booking", sanitized_msg)
            state.critic_approved = critic_pass
            state.critic_feedback = critic_feedback

            traces.append(
                AgentStepTrace(
                    agent=CriticAgent.NAME,
                    input=f"Verify confirm_booking for Booking #{state.held_booking_id}",
                    output=critic_feedback,
                    tools_used=[],
                    duration_ms=int((time.time() - step_start) * 1000),
                )
            )

            if not critic_pass:
                # Critic rejected plan: abort PaymentAgent execution
                final_reply = critic_feedback
            else:
                # Critic approved: PaymentAgent proceeds
                pay_start = time.time()
                reply, tools = PaymentAgent.run(db, state, sanitized_msg)
                traces.append(
                    AgentStepTrace(
                        agent=PaymentAgent.NAME,
                        input=sanitized_msg,
                        output=reply,
                        tools_used=tools,
                        duration_ms=int((time.time() - pay_start) * 1000),
                    )
                )

                # Append notification message if booking confirmed
                notif_start = time.time()
                notif_text, _ = NotificationAgent.run(state, "confirmation")
                traces.append(
                    AgentStepTrace(
                        agent=NotificationAgent.NAME,
                        input="Generate confirmation notification summary",
                        output=notif_text,
                        tools_used=[],
                        duration_ms=int((time.time() - notif_start) * 1000),
                    )
                )
                final_reply = reply + notif_text

        elif intent == "support":
            step_start = time.time()
            # If cancellation is requested, check CriticAgent first
            if "cancel" in msg_lower and ("confirm cancel" in msg_lower or "yes cancel" in msg_lower or "it" in msg_lower):
                c_pass, c_fb = CriticAgent.evaluate(state, "cancel_booking", sanitized_msg)
                state.critic_approved = c_pass
                state.critic_feedback = c_fb
                traces.append(
                    AgentStepTrace(
                        agent=CriticAgent.NAME,
                        input="Verify cancel_booking",
                        output=c_fb,
                        tools_used=[],
                        duration_ms=int((time.time() - step_start) * 1000),
                    )
                )

            reply, tools = SupportAgent.run(db, state, sanitized_msg)
            traces.append(
                AgentStepTrace(
                    agent=SupportAgent.NAME,
                    input=sanitized_msg,
                    output=reply,
                    tools_used=tools,
                    duration_ms=int((time.time() - step_start) * 1000),
                )
            )
            final_reply = reply

        else:
            final_reply = (
                "Hello! I am the Cineverse Multi-Agent AI Assistant. "
                "I can help you search movies, check schedules, hold seats, authorize payments, "
                "and explain our cancellation & refund policies."
            )

        # 5. Persist audit log in DB and store trace history in memory
        cls._record_trace(session_id, traces)
        cls._log_to_db(db, session_id, sanitized_msg, final_reply, traces, int((time.time() - start_time) * 1000))

        return MultiAgentChatResponse(
            reply=final_reply,
            agent_trace=traces,
            state=state,
            mock=settings.is_mock_llm,
        )

    @classmethod
    def _classify_intent(cls, msg_lower: str, state: AgentSessionState) -> str:
        """Classify user query into specialist domains."""
        # 1. Affirmation / payment confirmation check
        if state.held_booking_id and (
            re.search(AFFIRMATIVE_PATTERN, msg_lower)
            or re.search(NEGATION_OR_HESITATION_PATTERN, msg_lower)
            or any(kw in msg_lower for kw in ["confirm", "proceed", "pay", "yes", "sure", "approve", "ok", "okay", "yep", "yeah", "do it", "sounds good", "please do"])
        ):
            return "payment"
        # 2. Support / refund / policy check
        if any(kw in msg_lower for kw in ["cancel", "refund", "policy", "rules", "my bookings", "my tickets"]):
            return "support"
        # 3. Booking / hold / seat check
        if any(kw in msg_lower for kw in ["seat", "hold", "reserve", "price", "cost", "book"]):
            return "booking"
        # 4. Movie search / showtime discovery
        if any(kw in msg_lower for kw in ["movie", "search", "showtime", "show", "schedule", "playing", "recommend"]):
            return "discovery"
        # 5. Chitchat / general greeting
        return "general"

    @classmethod
    def _record_trace(cls, session_id: str, traces: List[AgentStepTrace]) -> None:
        """Store trace history in-memory for session inspection."""
        if session_id not in SESSION_TRACES:
            SESSION_TRACES[session_id] = []
        SESSION_TRACES[session_id].extend(traces)

    @classmethod
    def _log_to_db(
        cls,
        db: Session,
        session_id: str,
        user_input: str,
        output_text: str,
        traces: List[AgentStepTrace],
        duration_ms: int,
    ) -> None:
        """Persist structured audit record to ai_logs table."""
        try:
            tools_used = [tool for t in traces for tool in t.tools_used]
            log = AILog(
                session_id=session_id,
                agent_name="multi_agent_orchestrator",
                input=user_input,
                output=output_text[:2000],
                tool_calls=[{"agent": t.agent, "tools": t.tools_used} for t in traces if t.tools_used],
                latency_ms=duration_ms,
            )
            db.add(log)
            db.commit()
        except Exception:
            db.rollback()


def get_session_traces(session_id: str) -> List[AgentStepTrace]:
    """Retrieve full trace history for a given session ID."""
    return SESSION_TRACES.get(session_id, [])
