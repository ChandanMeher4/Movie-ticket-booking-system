"""Tests for Multi-Agent AI Orchestration, specialist delegation, CriticAgent verification, and execution tracing."""

import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def test_multi_agent_discovery_flow(client: TestClient):
    """Verify Orchestrator classifies search intent and delegates to DiscoveryAgent."""
    session_id = f"multi-disc-{uuid.uuid4().hex[:8]}"
    payload = {
        "session_id": session_id,
        "user_id": 2,
        "message": "Find action movies currently playing",
    }
    response = client.post("/api/ai/multi/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["mock"] is True
    assert "movies" in data["reply"].lower() or "cineverse" in data["reply"].lower()

    # Check agent trace
    trace = data["agent_trace"]
    assert len(trace) >= 2
    assert trace[0]["agent"] == "OrchestratorAgent"
    assert trace[1]["agent"] == "DiscoveryAgent"
    assert "search_movies" in trace[1]["tools_used"]


def test_multi_agent_showtimes_flow(client: TestClient):
    """Verify Orchestrator delegates showtime inquiries to DiscoveryAgent."""
    session_id = f"multi-show-{uuid.uuid4().hex[:8]}"
    payload = {
        "session_id": session_id,
        "user_id": 2,
        "message": "What are the showtimes for Interstellar?",
    }
    response = client.post("/api/ai/multi/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    trace = data["agent_trace"]
    assert any(t["agent"] == "DiscoveryAgent" for t in trace)
    assert any("get_showtimes" in t["tools_used"] for t in trace)


def test_multi_agent_booking_hold_flow(client: TestClient):
    """Verify BookingAgent checks seats, calculates price, and holds seats."""
    session_id = f"multi-book-{uuid.uuid4().hex[:8]}"
    payload = {
        "session_id": session_id,
        "user_id": 2,
        "message": "Hold seats 1 and 2 for show 1 please",
    }
    response = client.post("/api/ai/multi/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["state"]["held_booking_id"] is not None
    assert "held" in data["reply"].lower()
    trace = data["agent_trace"]
    assert any(t["agent"] == "BookingAgent" for t in trace)


def test_multi_agent_critic_blocks_unconfirmed_payment(client: TestClient):
    """Verify CriticAgent vetoes payment confirmation if user does not provide explicit affirmative confirmation."""
    session_id = f"multi-critic-block-{uuid.uuid4().hex[:8]}"

    # Step 1: Hold seats first to establish held_booking_id in state
    r1 = client.post("/api/ai/multi/chat", json={
        "session_id": session_id,
        "user_id": 2,
        "message": "Hold seats 1 and 2 for show 1",
    })
    assert r1.status_code == 200
    held_id = r1.json()["state"]["held_booking_id"]
    assert held_id is not None

    # Step 2: Attempt payment without explicit confirmation (e.g. hesitant or ambiguous statement)
    r2 = client.post("/api/ai/multi/chat", json={
        "session_id": session_id,
        "user_id": 2,
        "message": "I am thinking about paying maybe next week",
    })
    assert r2.status_code == 200
    data = r2.json()

    # CriticAgent must have rejected
    assert data["state"]["critic_approved"] is False
    assert "criticagent verification rejected" in data["reply"].lower()
    assert "explicit user confirmation" in data["reply"].lower()

    # PaymentAgent must NOT have run confirm_booking
    trace = data["agent_trace"]
    critic_steps = [t for t in trace if t["agent"] == "CriticAgent"]
    assert len(critic_steps) >= 1
    assert not any(t["agent"] == "PaymentAgent" for t in trace)


def test_multi_agent_critic_rejects_negations_and_questions(client: TestClient):
    """Verify CriticAgent explicitly rejects 'don't pay yet', 'yes but wait', and 'how do I pay?'."""
    session_id = f"multi-critic-neg-{uuid.uuid4().hex[:8]}"

    # Step 1: Hold seats
    client.post("/api/ai/multi/chat", json={
        "session_id": session_id,
        "user_id": 2,
        "message": "Hold seats 1 and 2 for show 1",
    })

    # Test Case 1: "don't pay yet"
    r_neg = client.post("/api/ai/multi/chat", json={
        "session_id": session_id,
        "user_id": 2,
        "message": "don't pay yet",
    })
    data_neg = r_neg.json()
    assert data_neg["state"]["critic_approved"] is False
    assert "criticagent verification rejected" in data_neg["reply"].lower()

    # Test Case 2: "yes but wait"
    r_wait = client.post("/api/ai/multi/chat", json={
        "session_id": session_id,
        "user_id": 2,
        "message": "yes but wait a second",
    })
    data_wait = r_wait.json()
    assert data_wait["state"]["critic_approved"] is False
    assert "criticagent verification rejected" in data_wait["reply"].lower()

    # Test Case 3: "how do I pay?" (question)
    r_q = client.post("/api/ai/multi/chat", json={
        "session_id": session_id,
        "user_id": 2,
        "message": "how do I pay for this?",
    })
    data_q = r_q.json()
    assert data_q["state"]["critic_approved"] is False
    assert "criticagent verification rejected" in data_q["reply"].lower()



def test_multi_agent_critic_approves_and_payment_finalizes(client: TestClient):
    """Verify CriticAgent approves and PaymentAgent finalizes booking when user explicitly confirms."""
    session_id = f"multi-confirm-{uuid.uuid4().hex[:8]}"

    # Step 1: Hold seats
    client.post("/api/ai/multi/chat", json={
        "session_id": session_id,
        "user_id": 2,
        "message": "Hold seats 1 and 2 for show 1",
    })

    # Step 2: Explicit affirmative confirmation
    r2 = client.post("/api/ai/multi/chat", json={
        "session_id": session_id,
        "user_id": 2,
        "message": "Yes, I confirm the booking and total amount, please proceed with payment now",
    })
    assert r2.status_code == 200
    data = r2.json()

    assert data["state"]["critic_approved"] is True
    assert data["state"]["booking_confirmed"] is True
    assert "payment authorized successfully" in data["reply"].lower()
    assert "notification summary" in data["reply"].lower()

    trace = data["agent_trace"]
    agents_involved = [t["agent"] for t in trace]
    assert "OrchestratorAgent" in agents_involved
    assert "CriticAgent" in agents_involved
    assert "PaymentAgent" in agents_involved
    assert "NotificationAgent" in agents_involved


def test_multi_agent_critic_approves_affirmation_phrases(client: TestClient):
    """Verify CriticAgent approves 'yes, proceed, no problem', 'ok', and 'sounds good'."""
    for phrase in ["yes, proceed, no problem", "ok", "sounds good", "do it"]:
        session_id = f"multi-phrase-{uuid.uuid4().hex[:8]}"
        # Step 1: Hold seats
        client.post("/api/ai/multi/chat", json={
            "session_id": session_id,
            "user_id": 2,
            "message": "Hold seats 1 and 2 for show 1",
        })
        # Step 2: Confirm with phrase
        r = client.post("/api/ai/multi/chat", json={
            "session_id": session_id,
            "user_id": 2,
            "message": phrase,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["state"]["critic_approved"] is True
        assert data["state"]["booking_confirmed"] is True


def test_multi_agent_support_policy_and_bookings(client: TestClient):
    """Verify SupportAgent provides cinema policy information and booking history."""
    session_id = f"multi-support-{uuid.uuid4().hex[:8]}"

    # Test policy question
    r1 = client.post("/api/ai/multi/chat", json={
        "session_id": session_id,
        "user_id": 2,
        "message": "What is your refund policy and cancellation rules?",
    })
    assert r1.status_code == 200
    assert "refund policy" in r1.json()["reply"].lower() or "cancellation" in r1.json()["reply"].lower()
    assert "2 hours" in r1.json()["reply"].lower()

    # Test booking history
    r2 = client.post("/api/ai/multi/chat", json={
        "session_id": session_id,
        "user_id": 2,
        "message": "Check my bookings history",
    })
    assert r2.status_code == 200
    assert any(t["agent"] == "SupportAgent" for t in r2.json()["agent_trace"])


def test_get_multi_agent_trace_endpoint(client: TestClient):
    """Verify GET /api/ai/multi/trace/{session_id} returns previous traces."""
    session_id = f"multi-trace-ep-{uuid.uuid4().hex[:8]}"
    client.post("/api/ai/multi/chat", json={
        "session_id": session_id,
        "user_id": 2,
        "message": "Show me comedy movies",
    })

    res = client.get(f"/api/ai/multi/trace/{session_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["session_id"] == session_id
    assert len(data["traces"]) >= 2
    assert data["traces"][0]["agent"] == "OrchestratorAgent"
