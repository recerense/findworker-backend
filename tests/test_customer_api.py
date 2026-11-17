"""
Comprehensive test suite for FindWorker Customer Service APIs.
Tests:
- Authentication & JWT issuance (Register, Login, Password strength)
- Customer Profile & Address management (CRUD & IDOR verification)
- Nearby Services & Worker Discovery (Geospatial search, distance calculation)
- Booking creation, status tracking, and cancellation
- Review submission on completed services
"""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Booking, BookingStatus, User, UserRole, WorkerProfile
from app.db.seed import seed_database
from app.db.session import get_db
from app.main import app

# Test SQLite in-memory database
TEST_DB_URL = "sqlite:///./test_findworker.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

# Initialize test database
Base.metadata.drop_all(bind=test_engine)
Base.metadata.create_all(bind=test_engine)
db = TestingSessionLocal()
seed_database(db)
db.close()

client = TestClient(app)


def test_health_and_root():
    """Verify health check and root endpoints."""
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"

    res = client.get("/")
    assert res.status_code == 200
    assert "FindWorker" in res.json()["message"]


def test_customer_registration_success():
    """Test successful customer registration with strong password."""
    payload = {
        "full_name": "Priya Sharma",
        "email": "priya.sharma@example.com",
        "phone": "+919988776655",
        "password": "StrongPassword123!",
    }
    res = client.post("/api/customer/auth/register", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["customer"]["full_name"] == "Priya Sharma"
    assert data["customer"]["email"] == "priya.sharma@example.com"


def test_customer_registration_duplicate_email():
    """Test registration fails when email already exists."""
    payload = {
        "full_name": "Priya Duplicate",
        "email": "priya.sharma@example.com",
        "phone": "+919988776656",
        "password": "AnotherPassword123!",
    }
    res = client.post("/api/customer/auth/register", json=payload)
    assert res.status_code == 400
    assert "already exists" in res.json()["detail"]


def test_customer_registration_weak_password():
    """Test registration rejects weak password."""
    payload = {
        "full_name": "Weak Pass User",
        "email": "weak@example.com",
        "phone": "+919988776657",
        "password": "short",
    }
    res = client.post("/api/customer/auth/register", json=payload)
    assert res.status_code == 422  # Pydantic validation error


def test_customer_login_success_and_failure():
    """Test customer login with correct and incorrect credentials."""
    # Correct login
    res = client.post(
        "/api/customer/auth/login",
        json={"email": "priya.sharma@example.com", "password": "StrongPassword123!"},
    )
    assert res.status_code == 200
    assert "access_token" in res.json()

    # Incorrect password
    res = client.post(
        "/api/customer/auth/login",
        json={"email": "priya.sharma@example.com", "password": "WrongPassword123!"},
    )
    assert res.status_code == 401
    assert "Incorrect email or password" in res.json()["detail"]


def test_customer_profile_and_addresses():
    """Test profile retrieval, profile update, and address management."""
    # Login to get token
    login_res = client.post(
        "/api/customer/auth/login",
        json={"email": "priya.sharma@example.com", "password": "StrongPassword123!"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Get profile
    res = client.get("/api/customer/profile", headers=headers)
    assert res.status_code == 200
    assert res.json()["full_name"] == "Priya Sharma"

    # 2. Update profile
    res = client.put(
        "/api/customer/profile",
        headers=headers,
        json={"full_name": "Priya S. Kumar", "phone": "+919988776600"},
    )
    assert res.status_code == 200
    assert res.json()["full_name"] == "Priya S. Kumar"

    # 3. Add address
    addr_payload = {
        "title": "Home",
        "street_address": "Flat 402, Green Glen Layout, Bellandur",
        "city": "Bengaluru",
        "state": "Karnataka",
        "postal_code": "560103",
        "latitude": 12.9260,
        "longitude": 77.6762,
        "is_default": True,
    }
    res = client.post("/api/customer/addresses", headers=headers, json=addr_payload)
    assert res.status_code == 201
    address_id = res.json()["id"]
    assert res.json()["title"] == "Home"
    assert res.json()["is_default"] is True

    # 4. List addresses
    res = client.get("/api/customer/addresses", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) >= 1

    # 5. Delete address
    res = client.delete(f"/api/customer/addresses/{address_id}", headers=headers)
    assert res.status_code == 204


def test_categories_and_nearby_worker_search():
    """Test browsing categories and searching nearby workers with coordinates."""
    # 1. List categories
    res = client.get("/api/customer/services/categories")
    assert res.status_code == 200
    categories = res.json()
    assert len(categories) >= 4
    category_names = [c["name"] for c in categories]
    assert "Plumbing" in category_names
    assert "Electrical" in category_names

    plumbing_cat = next(c for c in categories if c["name"] == "Plumbing")

    # 2. Search nearby workers around Central Bangalore coordinates (12.9716, 77.5946)
    res = client.get(
        "/api/customer/services/nearby",
        params={
            "latitude": 12.9716,
            "longitude": 77.5946,
            "radius_km": 20.0,
        },
    )
    assert res.status_code == 200
    workers = res.json()
    assert len(workers) >= 1
    # Verify distance was calculated
    assert workers[0]["distance_km"] is not None
    # Verify sorted by proximity
    if len(workers) > 1:
        assert workers[0]["distance_km"] <= workers[1]["distance_km"]

    # 3. Filter by category
    res = client.get(
        "/api/customer/services/nearby",
        params={
            "latitude": 12.9716,
            "longitude": 77.5946,
            "category_id": plumbing_cat["id"],
        },
    )
    assert res.status_code == 200
    plumbers = res.json()
    assert len(plumbers) >= 1
    assert plumbers[0]["category_name"] == "Plumbing"

    # 4. View worker details
    worker_id = plumbers[0]["id"]
    res = client.get(f"/api/customer/workers/{worker_id}")
    assert res.status_code == 200
    detail = res.json()
    assert detail["id"] == worker_id
    assert "bio" in detail
    assert detail["hourly_rate"] > 0


def test_booking_lifecycle_and_review():
    """Test creating a booking, tracking, cancelling, and submitting a review."""
    # Login
    login_res = client.post(
        "/api/customer/auth/login",
        json={"email": "priya.sharma@example.com", "password": "StrongPassword123!"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Get a worker ID
    workers_res = client.get(
        "/api/customer/services/nearby",
        params={"latitude": 12.9716, "longitude": 77.5946},
    )
    worker = workers_res.json()[0]

    # 1. Create a booking
    scheduled_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    booking_payload = {
        "worker_id": worker["id"],
        "service_category_id": worker["category_id"],
        "scheduled_at": scheduled_time,
        "service_address": "123 MG Road, Bengaluru, 560001",
        "customer_latitude": 12.9716,
        "customer_longitude": 77.5946,
        "problem_description": "Water leaking from master bathroom sink pipe valve.",
        "estimated_hours": 2.0,
    }
    res = client.post("/api/customer/bookings", headers=headers, json=booking_payload)
    assert res.status_code == 201
    booking = res.json()
    assert booking["status"] == "PENDING"
    assert booking["total_price"] == worker["hourly_rate"] * 2.0
    assert booking["booking_reference"].startswith("BK-")
    booking_id = booking["id"]

    # 2. List bookings
    res = client.get("/api/customer/bookings", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) >= 1
    assert any(b["id"] == booking_id for b in res.json())

    # 3. Get booking detail
    res = client.get(f"/api/customer/bookings/{booking_id}", headers=headers)
    assert res.status_code == 200
    assert res.json()["id"] == booking_id

    # 4. Cancel booking
    res = client.post(
        f"/api/customer/bookings/{booking_id}/cancel",
        headers=headers,
        json={"cancellation_reason": "Issue was fixed by apartment maintenance."},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "CANCELLED"
    assert res.json()["cancellation_reason"] == "Issue was fixed by apartment maintenance."

    # 5. Review completed booking:
    # Create another booking and mark it COMPLETED directly in DB to test review endpoint
    res2 = client.post("/api/customer/bookings", headers=headers, json=booking_payload)
    booking2_id = res2.json()["id"]

    db_session = TestingSessionLocal()
    b2 = db_session.get(Booking, booking2_id)
    b2.status = BookingStatus.COMPLETED.value
    db_session.commit()
    db_session.close()

    # Submit review
    review_payload = {
        "rating": 5,
        "comment": "Excellent plumbing work! Fixed the leak in under 45 minutes.",
    }
    res = client.post(
        f"/api/customer/bookings/{booking2_id}/review",
        headers=headers,
        json=review_payload,
    )
    assert res.status_code == 201
    assert res.json()["rating"] == 5
    assert res.json()["comment"] == review_payload["comment"]


def test_idor_protection_between_customers():
    """Verify customer A cannot view or manipulate customer B's bookings or addresses."""
    # Register Customer A
    client.post(
        "/api/customer/auth/register",
        json={
            "full_name": "Customer A",
            "email": "customer.a@example.com",
            "phone": "+919111111111",
            "password": "CustomerPass123!",
        },
    )
    res_a = client.post(
        "/api/customer/auth/login",
        json={"email": "customer.a@example.com", "password": "CustomerPass123!"},
    )
    token_a = res_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Register Customer B
    client.post(
        "/api/customer/auth/register",
        json={
            "full_name": "Customer B",
            "email": "customer.b@example.com",
            "phone": "+919222222222",
            "password": "CustomerPass123!",
        },
    )
    res_b = client.post(
        "/api/customer/auth/login",
        json={"email": "customer.b@example.com", "password": "CustomerPass123!"},
    )
    token_b = res_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Customer A creates an address
    addr_res = client.post(
        "/api/customer/addresses",
        headers=headers_a,
        json={
            "title": "Private Residence A",
            "street_address": "Secret St 1",
            "city": "Bengaluru",
            "state": "Karnataka",
            "postal_code": "560001",
        },
    )
    address_id_a = addr_res.json()["id"]

    # Customer B attempts to delete Customer A's address -> MUST BE REJECTED 404
    hack_res = client.delete(f"/api/customer/addresses/{address_id_a}", headers=headers_b)
    assert hack_res.status_code == 404
