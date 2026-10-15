"""Single-Agent AI Booking Concierge with tool-calling ReAct loop and audit logging.

Coordinates between OpenAI-compatible function calling, security guardrails,
in-memory session state, and database audit logs.
"""

from collections import defaultdict
import json
import logging
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai.guardrails import (
    check_confirmation_guardrail,
    check_off_topic,
    check_rate_limit,
    sanitize_input,
    sanitize_output,
)
from app.ai.llm_client import llm_client
from app.ai.tools import TOOL_REGISTRY, TOOL_SCHEMAS
from app.models import AILog

logger = logging.getLogger("single_agent")

SINGLE_AGENT_SYSTEM_PROMPT = """You are Cineverse's AI Booking Assistant.
You help customers discover movies, view showtimes, choose and hold seats, calculate prices, and manage bookings.

Rules & Guardrails:
1. Always be polite, concise, and helpful.
2. When a customer wants to book tickets:
   - Help them select the movie and showtime.
   - Use `get_available_seats` to suggest seat IDs.
   - Use `calculate_price` to show the exact price breakdown.
   - Use `hold_seats` to hold the seats (which lasts 5 minutes).
   - CRITICAL GUARDRAIL: NEVER call `confirm_booking` without EXPLICIT customer confirmation of the exact seats and price.
3. When a customer wants to cancel:
   - Look up the booking with `get_my_bookings`.
   - Explain the refund policy (>24h = 100%, 2-24h = 50%, <2h = 0%).
   - NEVER call `cancel_booking` without explicit confirmation.
4. Keep answers brief and well-formatted. Never invent showtimes or seat IDs not returned by tools.
"""

# In-memory session store: session_id -> list of message dicts
_agent_sessions: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
MAX_ITERATIONS = 6


class AgentChatResponse(BaseModel):
    reply: str
    tool_calls_made: List[Dict[str, Any]]
    session_id: str
    mock: bool = False


def run_single_agent(
    db: Session,
    session_id: str,
    user_id: int,
    user_message: str,
) -> AgentChatResponse:
    """Execute the single-agent tool-calling loop with guardrails and audit logging."""
    start_turn = time.perf_counter()

    # 1. Rate Limiting Guardrail
    check_rate_limit(session_id)

    # 2. Prompt Injection Guardrail
    clean_message = sanitize_input(user_message)

    # 3. Off-Topic Refusal Guardrail
    off_topic_reply = check_off_topic(clean_message)
    if off_topic_reply:
        return AgentChatResponse(
            reply=off_topic_reply,
            tool_calls_made=[],
            session_id=session_id,
            mock=llm_client.is_mock,
        )

    # 4. Initialize Session History if New
    history = _agent_sessions[session_id]
    if not history:
        history.append({"role": "system", "content": SINGLE_AGENT_SYSTEM_PROMPT})

    # Append user turn
    history.append({
        "role": "user",
        "content": f"[User ID: {user_id}] {clean_message}",
    })

    tool_calls_executed = []
    current_iteration = 0
    final_reply = ""
    is_mock_run = llm_client.is_mock

    # 5. Tool-Calling ReAct Loop (Max 6 Iterations)
    while current_iteration < MAX_ITERATIONS:
        current_iteration += 1

        # Request completion from LLM or deterministic mock planner
        response = llm_client.chat_completion(
            messages=history,
            tools=TOOL_SCHEMAS,
            temperature=0.3,
        )
        if response.mock:
            is_mock_run = True

        # If LLM requested tool calls
        if response.tool_calls:
            for tc in response.tool_calls:
                tool_name = tc.name
                tool_args = tc.arguments or {}

                # Inject user_id if required by tool and missing
                if "user_id" in tool_args and not tool_args["user_id"]:
                    tool_args["user_id"] = user_id

                # Guardrail: Check explicit confirmation before executing confirm_booking or cancel_booking
                check_confirmation_guardrail(tool_name, history)

                tool_start = time.perf_counter()
                if tool_name in TOOL_REGISTRY:
                    tool_fn, _ = TOOL_REGISTRY[tool_name]
                    try:
                        tool_result = tool_fn(db, tool_args)
                    except Exception as err:
                        tool_result = {"error": str(err)}
                else:
                    tool_result = {"error": f"Unknown tool: {tool_name}"}

                tool_latency_ms = int((time.perf_counter() - tool_start) * 1000)

                # Persist tool execution audit log
                ai_log = AILog(
                    session_id=session_id,
                    agent_name="single_agent",
                    input=json.dumps({"tool": tool_name, "args": tool_args}),
                    output=json.dumps(tool_result),
                    tool_calls=[{"tool": tool_name, "args": tool_args}],
                    latency_ms=tool_latency_ms,
                )
                db.add(ai_log)
                db.commit()

                tool_calls_executed.append({
                    "tool": tool_name,
                    "arguments": tool_args,
                    "result": tool_result,
                    "latency_ms": tool_latency_ms,
                })

                # Append tool result to context for next iteration
                history.append({
                    "role": "assistant",
                    "content": f"Invoking tool {tool_name} with args {tool_args}",
                })
                history.append({
                    "role": "system",
                    "content": f"Tool '{tool_name}' result: {json.dumps(tool_result)}",
                })

            # In mock mode, synthesize human-friendly summary after tool execution
            if is_mock_run:
                final_reply = _format_mock_agent_reply(tool_calls_executed)
                break
        else:
            final_reply = response.content or "I have processed your request. How else may I assist you?"
            break

    # If loop ended via MAX_ITERATIONS limit
    if not final_reply:
        if tool_calls_executed:
            final_reply = (
                f"I have reached the maximum reasoning limit ({MAX_ITERATIONS} steps) while processing your request. "
                f"Actions executed: {len(tool_calls_executed)} tool calls completed."
            )
        else:
            final_reply = "I have reached the maximum conversation reasoning limit. How else may I assist you?"

    # Guardrail: Sanitize reply to prevent prompt leakage
    sanitized_reply = sanitize_output(final_reply)

    # Append assistant reply to session history
    history.append({"role": "assistant", "content": sanitized_reply})

    # Log turn to ai_logs
    turn_latency_ms = int((time.perf_counter() - start_turn) * 1000)
    summary_log = AILog(
        session_id=session_id,
        agent_name="single_agent",
        input=clean_message,
        output=sanitized_reply,
        tool_calls=tool_calls_executed,
        latency_ms=turn_latency_ms,
    )
    db.add(summary_log)
    db.commit()

    return AgentChatResponse(
        reply=sanitized_reply,
        tool_calls_made=tool_calls_executed,
        session_id=session_id,
        mock=is_mock_run,
    )


def _format_mock_agent_reply(tool_calls: List[Dict[str, Any]]) -> str:
    """Produce human-friendly natural language responses from tool execution results in mock mode."""
    if not tool_calls:
        return "I am here to assist with Cineverse movies, showtimes, seats, and bookings."

    last_call = tool_calls[-1]
    name = last_call["tool"]
    res = last_call["result"]

    if name == "search_movies":
        movies = res.get("movies", [])
        if not movies:
            return "No movies found matching your search criteria in our active catalog."
        titles = [f"• **{m['title']}** ({m['genre']}, {m['language']}) - {m['rating']}" for m in movies[:4]]
        return f"Here are the active movies currently screening at Cineverse:\n" + "\n".join(titles)

    if name == "get_showtimes":
        shows = res.get("showtimes", [])
        if not shows:
            return "No scheduled upcoming shows found for this selection."
        times = [f"• Show #{s['show_id']}: {s['start_time']} at {s['theatre']} ({s['screen']}) - ₹{s['base_price']:.2f}" for s in shows[:4]]
        return f"Here are the available showtimes:\n" + "\n".join(times) + "\n\nWould you like me to check available seats for one of these shows?"

    if name == "get_available_seats":
        recs = res.get("recommended_seats", [])
        seat_labels = ", ".join([f"{s['label']} (₹{s['price']:.2f})" for s in recs])
        return (
            f"There are {res.get('total_available', 0)} seats available. "
            f"Recommended seats for you: **{seat_labels}**.\n\n"
            f"Would you like me to calculate the total price or hold these seats?"
        )

    if name == "calculate_price":
        return (
            f"Ticket price breakdown for {res.get('seat_count')} seats:\n"
            f"• Subtotal: ₹{res.get('subtotal', 0):.2f}\n"
            f"• Convenience Fee (2%): ₹{res.get('convenience_fee', 0):.2f}\n"
            f"• **Total Payable**: ₹{res.get('total_amount', 0):.2f}\n\n"
            f"Please reply **'confirm'** or **'proceed'** if you would like me to hold and confirm these tickets."
        )

    if name == "hold_seats":
        if res.get("success"):
            return (
                f"Your seats have been temporarily reserved!\n"
                f"• Booking Reference: #{res.get('booking_id')}\n"
                f"• Total Amount: ₹{res.get('total_amount', 0):.2f}\n"
                f"• Expiry: {res.get('expires_at')} (5-minute hold)\n\n"
                f"Please reply with **'confirm and pay'** to complete your reservation."
            )
        return f"Could not reserve seats: {res.get('error', 'unknown error')}"

    if name == "confirm_booking":
        if res.get("success"):
            return (
                f"Congratulations! Your booking #{res.get('booking_id')} is confirmed!\n"
                f"• Transaction Reference: {res.get('txn_ref')}\n"
                f"• Total Paid: ₹{res.get('total_amount', 0):.2f}\n"
                f"An electronic ticket has been attached to your profile."
            )
        return f"Payment confirmation failed: {res.get('error')}"

    if name == "cancel_booking":
        if res.get("success"):
            return (
                f"Booking #{res.get('booking_id')} has been cancelled.\n"
                f"• Refund Tier: {res.get('refund_percentage')}%\n"
                f"• Refund Amount: ₹{res.get('refund_amount', 0):.2f}\n"
                f"{res.get('message')}"
            )
        return f"Cancellation failed: {res.get('error')}"

    if name == "get_my_bookings":
        bookings = res.get("bookings", [])
        if not bookings:
            return "You have no active bookings on record."
        lines = [f"• #{b['booking_id']} - {b['movie']} ({b['seats']}) on {b['showtime']} - Status: {b['status']}" for b in bookings]
        return f"Your bookings:\n" + "\n".join(lines)

    return "Operation completed. How else may I assist you?"
