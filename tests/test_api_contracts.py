"""Frontend to Backend API Contract Tests.

Verifies that the exact HTTP method, path, query parameters, and JSON payload keys
sent by the frontend JavaScript controllers (movies.js, seats.js, bookings.js,
assistant.js, admin.js) are accepted by the backend routes and return 2xx status codes.
Prevents contract regressions such as 'payment_method' vs 'method'.
"""

from datetime import datetime, timedelta
import uuid
import pytest
from fastapi.testclient import TestClient


def test_contract_movies_page_requests(client: TestClient):
    """Verify contracts used by frontend/js/movies.js."""
    # 1. Catalog query with filters, pagination, and sort exactly as sent by fetchMovies() in movies.js:
    # /api/movies?page=1&page_size=8&sort_by=release_date_desc&search=Inception&genre=Sci-Fi&language=English
    res1 = client.get(
        "/api/movies?page=1&page_size=8&sort_by=release_date_desc&search=Inception&genre=Sci-Fi&language=English"
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert "items" in data1
    assert "total" in data1
    assert "page" in data1
    assert "page_size" in data1
    assert len(data1["items"]) >= 1

    # 2. Showtimes modal query by movie_id (openShowtimesModal() in movies.js)
    res2 = client.get("/api/shows?movie_id=1")
    assert res2.status_code == 200
    shows_data = res2.json()
    assert "items" in shows_data
    assert isinstance(shows_data["items"], list)


def test_contract_seats_page_requests(client: TestClient):
    """Verify contracts used by frontend/js/seats.js."""
    # 1. Fetch show metadata
    res1 = client.get("/api/shows/1")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["id"] == 1
    assert "base_price" in data1
    assert "start_time" in data1

    # 2. Fetch seat layout map
    res2 = client.get("/api/shows/1/seats")
    assert res2.status_code == 200
    seats = res2.json()
    assert isinstance(seats, list)
    assert len(seats) >= 2
    assert "seat_type" in seats[0]
    assert "price" in seats[0]
    assert "status" in seats[0]

    # 3. Hold seats payload as structured in frontend/js/seats.js (holdSelectedSeats):
    # apiClient("/api/bookings", { method: "POST", body: { user_id, show_id, seat_ids } })
    chosen_seat_ids = [seats[0]["id"], seats[1]["id"]]
    res3 = client.post(
        "/api/bookings",
        json={"user_id": 2, "show_id": 1, "seat_ids": chosen_seat_ids},
    )
    assert res3.status_code == 201
    hold_data = res3.json()
    assert "id" in hold_data
    assert hold_data["status"] == "pending"
    assert "expires_at" in hold_data
    assert "total_amount" in hold_data


def test_contract_bookings_page_checkout_and_cancellation(client: TestClient):
    """Verify contracts used by frontend/js/bookings.js.

    Specifically verifies that payment payload accepting 'payment_method' or 'method'
    and cancellation flow contract matches the frontend client exactly.
    """
    # 1. Get available seats for show 1
    seats_res = client.get("/api/shows/1/seats")
    assert seats_res.status_code == 200
    available_seats = [s["id"] for s in seats_res.json() if s["status"] == "available"]
    assert len(available_seats) >= 2
    hold_seats_list = available_seats[:2]

    # 2. Create a hold first via /api/bookings
    hold_res = client.post(
        "/api/bookings",
        json={"user_id": 2, "show_id": 1, "seat_ids": hold_seats_list},
    )
    assert hold_res.status_code == 201
    booking_id = hold_res.json()["id"]
    total = hold_res.json()["total_amount"]

    # 3. Get booking details (loadCheckoutBooking in bookings.js)
    get_res = client.get(f"/api/bookings/{booking_id}?user_id=2")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == booking_id

    # 4. Process payment with EXACT frontend payload keys from submitPayment() in bookings.js:
    # { booking_id: bookingId, user_id: activeUserId, amount: totalAmount, payment_method: selectedMethod, method: selectedMethod }
    pay_res = client.post(
        "/api/payments",
        json={
            "booking_id": booking_id,
            "user_id": 2,
            "amount": total,
            "payment_method": "card",
            "method": "card",
        },
    )
    assert pay_res.status_code == 200
    pay_data = pay_res.json()
    assert pay_data["status"] == "success"
    assert "txn_ref" in pay_data

    # 5. User booking history table (loadUserBookings in bookings.js)
    hist_res = client.get("/api/users/2/bookings?user_id=2")
    assert hist_res.status_code == 200
    assert isinstance(hist_res.json(), list)

    # 6. Cancel booking endpoint (confirmCancellation in bookings.js)
    cancel_res = client.post(f"/api/bookings/{booking_id}/cancel?user_id=2")
    assert cancel_res.status_code == 200
    cancel_data = cancel_res.json()
    assert cancel_data["status"] == "cancelled"
    assert "refund_amount" in cancel_data
    assert "refund_percentage" in cancel_data


def test_contract_assistant_page_requests(client: TestClient):
    """Verify contracts used by frontend/js/assistant.js."""
    session_id = f"contract-sess-{uuid.uuid4().hex[:8]}"

    # 1. GenAI mood recommendations (sendRecommendation in assistant.js)
    rec_res = client.post(
        "/api/ai/genai/recommend",
        json={"mood": "mind-bending thriller", "genre": "Sci-Fi"},
    )
    assert rec_res.status_code == 200
    assert "recommendations" in rec_res.json()

    # 2. Single-Agent chat endpoint (sendSingleAgentMessage in assistant.js)
    agent_res = client.post(
        "/api/ai/agent/chat",
        json={"user_id": 2, "message": "Search movies about dreams", "session_id": session_id},
    )
    assert agent_res.status_code == 200
    assert "reply" in agent_res.json()

    # 3. Multi-Agent chat endpoint (sendMultiAgentMessage in assistant.js)
    multi_res = client.post(
        "/api/ai/multi/chat",
        json={"user_id": 2, "message": "What sci-fi movies are playing?", "session_id": session_id},
    )
    assert multi_res.status_code == 200
    assert "agent_trace" in multi_res.json()

    # 4. Multi-Agent trace endpoint (loadMultiAgentTrace in assistant.js)
    trace_res = client.get(f"/api/ai/multi/trace/{session_id}")
    assert trace_res.status_code == 200
    assert "traces" in trace_res.json()


def test_contract_admin_page_requests(client: TestClient):
    """Verify contracts used by frontend/js/admin.js."""
    # 1. Fetch movie list for inventory
    res1 = client.get("/api/movies?page_size=100")
    assert res1.status_code == 200

    # 2. Add movie with admin header matching submitMovie() in admin.js:
    # { title, genre, language, duration_min, rating, poster_url, description, release_date }
    new_movie_payload = {
        "title": f"Contract Test Movie {uuid.uuid4().hex[:6]}",
        "genre": "Action",
        "duration_min": 125,
        "language": "English",
        "rating": "UA",
        "description": "Automated frontend contract test film description.",
        "poster_url": "https://example.com/poster.jpg",
        "release_date": "2026-10-15T00:00:00",
    }
    res2 = client.post("/api/movies", json=new_movie_payload, headers={"X-User-Id": "1"})
    assert res2.status_code == 201
    movie_id = res2.json()["id"]

    # 3. Fetch theatres for scheduling form (apiClient("/api/theatres") in admin.js)
    res3 = client.get("/api/theatres")
    assert res3.status_code == 200
    theatres_data = res3.json()
    theatres_list = theatres_data["items"]
    assert len(theatres_list) >= 1
    assert "screens" in theatres_list[0]
    assert len(theatres_list[0]["screens"]) >= 1

    # 4. Schedule show matching submitShow() in admin.js:
    # { movie_id, screen_id, start_time, end_time, base_price }
    future_start = datetime.utcnow() + timedelta(days=30)
    future_end = future_start + timedelta(hours=2, minutes=30)
    new_show_payload = {
        "movie_id": movie_id,
        "theatre_id": 1,
        "screen_id": 1,
        "start_time": future_start.isoformat(),
        "end_time": future_end.isoformat(),
        "base_price": 280.0,
    }
    res4 = client.post("/api/shows", json=new_show_payload, headers={"X-User-Id": "1"})
    assert res4.status_code == 201
    assert res4.json()["movie_id"] == movie_id

    # 5. Deactivate movie (deactivateMovie() in admin.js)
    res5 = client.delete(f"/api/movies/{movie_id}", headers={"X-User-Id": "1"})
    assert res5.status_code == 200
    assert res5.json()["id"] == movie_id
