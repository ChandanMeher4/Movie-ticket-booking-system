"""Tests for Users and Screens CRUD endpoints."""

from fastapi.testclient import TestClient


def test_list_users(client: TestClient):
    """Verify listing users returns seeded users."""
    response = client.get("/api/users")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 3
    emails = [u["email"] for u in data["items"]]
    assert "admin@cineverse.com" in emails
    assert "aarav.sharma@example.com" in emails


def test_create_user_success_and_duplicate_conflict(client: TestClient):
    """Verify user registration and unique email constraint check."""
    payload = {
        "name": "Rohan Gupta",
        "email": "rohan.gupta@example.com",
        "phone": "+91-9988776655",
        "role": "customer",
    }
    create_res = client.post("/api/users", json=payload)
    assert create_res.status_code == 201
    user = create_res.json()
    assert user["email"] == "rohan.gupta@example.com"

    # Duplicate creation should yield 409 Conflict
    dup_res = client.post("/api/users", json=payload)
    assert dup_res.status_code == 409
    assert dup_res.json()["error"]["code"] == "RESOURCE_CONFLICT"


def test_screen_seat_grid_generation(client: TestClient):
    """Verify creating a screen generates the appropriate seat grid."""
    payload = {
        "theatre_id": 1,
        "name": "Screen 3 (Gold Class)",
        "total_rows": 4,
        "seats_per_row": 8,
    }
    create_screen_res = client.post("/api/screens", json=payload)
    assert create_screen_res.status_code == 201
    screen = create_screen_res.json()
    screen_id = screen["id"]

    # Verify 4 * 8 = 32 seats were created
    seats_res = client.get(f"/api/screens/{screen_id}/seats")
    assert seats_res.status_code == 200
    seats = seats_res.json()
    assert len(seats) == 32
    row_labels = {s["row_label"] for s in seats}
    assert row_labels == {"A", "B", "C", "D"}
