# Customer Service — FindWorker Backend

The **Customer Service** module provides the complete suite of backend APIs for customer-facing interactions on the FindWorker platform. FindWorker is an on-demand marketplace connecting customers with nearby skilled professionals (such as plumbers, electricians, carpenters, AC technicians, cleaners, and appliance repair specialists).

---

## 📋 Table of Contents

- [Architecture & Routing](#-architecture--routing)
- [Database Schema & Data Model](#-database-schema--data-model)
- [API Endpoints Overview](#-api-endpoints-overview)
- [Step-by-Step API Usage & Examples](#-step-by-step-api-usage--examples)
  - [1. Customer Registration & Login](#1-customer-registration--login)
  - [2. Customer Profile & Addresses](#2-customer-profile--addresses)
  - [3. Discovering Services & Nearby Workers](#3-discovering-services--nearby-workers)
  - [4. Booking a Service](#4-booking-a-service)
  - [5. Cancelling a Booking](#5-cancelling-a-booking)
  - [6. Leaving a Review & Rating](#6-leaving-a-review--rating)
- [Geospatial Proximity Search (Haversine Formula)](#-geospatial-proximity-search-haversine-formula)
- [Security & Compliance Highlights](#-security--compliance-highlights)
- [Running & Testing](#-running--testing)

---

## 🏛️ Architecture & Routing

In the AWS ECS + Application Load Balancer (ALB) infrastructure, all customer requests are routed using path pattern `/api/customer*`:

```
Client (Web / Mobile App)
          │
          ▼
ALB Path Rule: /api/customer*
          │
          ▼
FastAPI Customer Router (`app/modules/customer/router.py`)
  ├── /api/customer/auth       -> Customer Registration & Login
  ├── /api/customer/profile    -> Customer Profile Management
  ├── /api/customer/addresses  -> Saved Service Delivery Locations
  ├── /api/customer/services   -> Catalog & Nearby Geospatial Search
  └── /api/customer/bookings   -> Service Booking Lifecycle & Reviews
```

---

## 🗄️ Database Schema & Data Model

The Customer Service interacts with the following relational models defined in [`app/db/models.py`](file:///home/vishnu/socwhiz/findworker-backend/app/db/models.py):

| Entity | Table Name | Purpose |
| :--- | :--- | :--- |
| **`User`** | `users` | Core account credentials, role (`customer`), email, phone, hashed password. |
| **`CustomerAddress`** | `customer_addresses` | Saved customer addresses with GPS coordinates (`latitude`, `longitude`) for service location. |
| **`ServiceCategory`** | `service_categories` | Catalog of trade categories (Plumbing, Electrical, Carpentry, AC Repair, Cleaning, Painting). |
| **`WorkerProfile`** | `worker_profiles` | Trade professional details, hourly rate, rating, coordinates, and availability status. |
| **`Booking`** | `bookings` | Customer service appointment orders with status tracking (`PENDING`, `CONFIRMED`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED`, `REJECTED`). |
| **`Review`** | `reviews` | Customer feedback and 1-to-5 star ratings for completed service bookings. |
| **`Notification`** | `notifications` | In-app alerts for status updates (`REQUEST_CREATED`, `REQUEST_ACCEPTED`, `REQUEST_REJECTED`, `JOB_COMPLETED`). |

---

## 🚀 API Endpoints Overview

All endpoints are prefixed with `/api/customer`:

### 1. Authentication
| Method | Endpoint | Auth Required | Description |
| :--- | :--- | :---: | :--- |
| `POST` | `/api/customer/auth/register` | No | Register a new customer account |
| `POST` | `/api/customer/auth/login` | No | Authenticate credentials and receive Bearer JWT token |

### 2. Profile & Addresses
| Method | Endpoint | Auth Required | Description |
| :--- | :--- | :---: | :--- |
| `GET` | `/api/customer/profile` | **Yes** | Retrieve authenticated customer profile |
| `PUT` | `/api/customer/profile` | **Yes** | Update customer full name, phone number, or avatar URL |
| `GET` | `/api/customer/addresses` | **Yes** | List all saved service locations |
| `POST` | `/api/customer/addresses` | **Yes** | Add a new service address |
| `DELETE` | `/api/customer/addresses/{id}` | **Yes** | Delete a saved address (IDOR protected) |

### 3. Service Catalog & Nearby Worker Discovery
| Method | Endpoint | Auth Required | Description |
| :--- | :--- | :---: | :--- |
| `GET` | `/api/customer/services/categories` | No | List all active trade categories (Plumbing, Electrical, etc.) |
| `GET` | `/api/customer/services/nearby` | No | Search nearby workers using customer GPS `latitude` and `longitude` within radius |
| `GET` | `/api/customer/workers/{id}` | No | Get public worker profile details, experience, rates, and past reviews |

### 4. Service Requests & Bookings (Accept, Reject, Cancel, Review)
*Note: Both `/api/customer/requests` and `/api/customer/bookings` are supported identically.*

| Method | Endpoint | Auth Required | Description |
| :--- | :--- | :---: | :--- |
| `POST` | `/api/customer/requests` | **Yes** | Request a service with appointment schedule, location, and issue details |
| `GET` | `/api/customer/requests` | **Yes** | List customer service requests (filterable by status) |
| `GET` | `/api/customer/requests/{id}` | **Yes** | View single service request details (IDOR protected) |
| `POST` | `/api/customer/requests/{id}/accept` | **Yes** | Accept a service request, confirmed schedule, or worker quote |
| `POST` | `/api/customer/requests/{id}/reject` | **Yes** | Reject a proposal or unwanted request with a reason |
| `POST` | `/api/customer/requests/{id}/cancel` | **Yes** | Cancel a pending or confirmed service request |
| `POST` | `/api/customer/bookings/{id}/review` | **Yes** | Submit 1–5 star rating and feedback for a completed service |

### 5. In-App Notifications
| Method | Endpoint | Auth Required | Description |
| :--- | :--- | :---: | :--- |
| `GET` | `/api/customer/notifications` | **Yes** | List customer notifications (with unread count & pagination) |
| `GET` | `/api/customer/notifications/unread-count` | **Yes** | Quick count of unread notifications for UI bell badge |
| `PUT` | `/api/customer/notifications/{id}/read` | **Yes** | Mark a single notification as read |
| `PUT` | `/api/customer/notifications/read-all` | **Yes** | Mark all customer notifications as read |
| `POST` | `/api/customer/notifications/simulate` | **Yes** | Simulate incoming worker event (Accepted, Rejected, Job Started, Completed) |

---

## 📖 Step-by-Step API Usage & Examples

### 1. Customer Registration & Login

#### Register Customer:
```bash
curl -X POST "http://localhost:8000/api/customer/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Priya Sharma",
    "email": "priya.sharma@example.com",
    "phone": "+919876543210",
    "password": "SecurePassword123!"
  }'
```
**Response (201 Created):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in_minutes": 1440,
  "customer": {
    "id": 1,
    "full_name": "Priya Sharma",
    "email": "priya.sharma@example.com",
    "phone": "+919876543210",
    "role": "customer",
    "avatar_url": null,
    "created_at": "2026-11-17T08:30:00"
  }
}
```

#### Customer Login:
```bash
curl -X POST "http://localhost:8000/api/customer/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "priya.sharma@example.com",
    "password": "SecurePassword123!"
  }'
```

---

### 2. Customer Profile & Addresses

Pass the JWT token in the `Authorization: Bearer <TOKEN>` header.

#### View Profile:
```bash
curl -X GET "http://localhost:8000/api/customer/profile" \
  -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>"
```

#### Add a Saved Service Address:
```bash
curl -X POST "http://localhost:8000/api/customer/addresses" \
  -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Home",
    "street_address": "Flat 301, Palm Meadows, Whitefield",
    "city": "Bengaluru",
    "state": "Karnataka",
    "postal_code": "560066",
    "latitude": 12.9698,
    "longitude": 77.7500,
    "is_default": true
  }'
```

---

### 3. Discovering Services & Nearby Workers

#### Browse Service Categories:
```bash
curl -X GET "http://localhost:8000/api/customer/services/categories"
```

#### Search Nearby Workers by Coordinates:
Find service professionals within 15 km of the customer's coordinates (`latitude=12.9716`, `longitude=77.5946`):
```bash
curl -X GET "http://localhost:8000/api/customer/services/nearby?latitude=12.9716&longitude=77.5946&radius_km=15.0&category_id=1"
```
**Response (200 OK):**
```json
[
  {
    "id": 1,
    "user_id": 2,
    "full_name": "Ramesh Kumar",
    "business_name": "Ramesh Quick Plumbing Solutions",
    "category_id": 1,
    "category_name": "Plumbing",
    "hourly_rate": 45.0,
    "rating": 4.9,
    "review_count": 34,
    "years_of_experience": 8,
    "distance_km": 0.61,
    "is_available": true,
    "latitude": 12.9750,
    "longitude": 77.5990
  }
]
```

#### View Worker Detailed Profile:
```bash
curl -X GET "http://localhost:8000/api/customer/workers/1"
```

---

### 4. Booking a Service

```bash
curl -X POST "http://localhost:8000/api/customer/bookings" \
  -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "worker_id": 1,
    "service_category_id": 1,
    "scheduled_at": "2026-11-20T10:30:00",
    "service_address": "Flat 301, Palm Meadows, Whitefield, Bengaluru",
    "customer_latitude": 12.9698,
    "customer_longitude": 77.7500,
    "problem_description": "Water leaking from kitchen sink drain pipe joint.",
    "estimated_hours": 2.0
  }'
```
**Response (201 Created):**
```json
{
  "id": 1,
  "booking_reference": "BK-20261117-F8A2",
  "customer_id": 1,
  "worker_id": 1,
  "worker_name": "Ramesh Kumar",
  "worker_phone": "+919876543210",
  "service_category_id": 1,
  "category_name": "Plumbing",
  "status": "PENDING",
  "scheduled_at": "2026-11-20T10:30:00",
  "service_address": "Flat 301, Palm Meadows, Whitefield, Bengaluru",
  "problem_description": "Water leaking from kitchen sink drain pipe joint.",
  "estimated_hours": 2.0,
  "total_price": 90.0,
  "cancellation_reason": null,
  "created_at": "2026-11-17T08:35:00",
  "updated_at": "2026-11-17T08:35:00",
  "review": null
}
```

---

### 5. Cancelling a Booking

Customers can cancel pending or confirmed bookings:
```bash
curl -X POST "http://localhost:8000/api/customer/bookings/1/cancel" \
  -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "cancellation_reason": "Issue was resolved by the building maintenance supervisor."
  }'
```

---

### 6. Leaving a Review & Rating

Once a job has been completed by the worker (`status = "COMPLETED"`):
```bash
curl -X POST "http://localhost:8000/api/customer/bookings/1/review" \
  -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "rating": 5,
    "comment": "Punctual, professional, and solved the leak quickly. Highly recommended!"
  }'
```
*Note: Submitting a review automatically updates the worker's average rating and total review count in the database.*

---

## 🌐 Geospatial Proximity Search (Haversine Formula)

The search service computes real-time spherical distances in kilometers between the customer ($lat_1, lon_1$) and workers ($lat_2, lon_2$):

$$d = 2 R \cdot \arcsin\left(\sqrt{\sin^2\left(\frac{\Delta\phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta\lambda}{2}\right)}\right)$$

Where $R = 6371.0 \text{ km}$.

Benefits:
- Fast and accurate without requiring proprietary external geocoding API round-trips.
- Runs natively across both PostgreSQL/Aurora in production and SQLite in testing.

---

## 🔒 Security & Compliance Highlights

The implementation adheres to the mandatory web security standards:

1. **Password Protection**:
   - Minimum 8 characters with letter + digit validation enforced by Pydantic.
   - Salted hashing using **bcrypt** (cost factor 12). Plaintext passwords are never logged or stored.
2. **JWT Authentication**:
   - Hardcoded `HS256` signature algorithm (rejects unverified algorithms).
   - Validates `exp` (expiration) and `sub` claims on every request.
   - Nonce-backed 256-bit cryptographic secret loaded via AWS Secrets Manager or environment.
3. **IDOR (Insecure Direct Object Reference) Prevention**:
   - All booking lookups, cancellations, address deletions, and profile updates explicitly filter by `customer_id == current_customer.id`. Unauthorized access returns a `404 Not Found`.
4. **SQL Injection Defense**:
   - 100% parameterized SQLAlchemy 2.0 queries (`select()`, `where()`). Zero raw string concatenation.
5. **Security Response Headers**:
   - `X-Content-Type-Options: nosniff`
   - `X-Frame-Options: DENY` (anti-clickjacking)
   - `Permissions-Policy` restrictive policies

---

## 🧪 Running & Testing

### 1. Run the API Locally
```bash
cd findworker-backend

# Start FastAPI server on localhost:8000
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
- Interactive Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Interactive ReDoc: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

### 2. Run Automated Test Suite
```bash
pytest tests/test_customer_api.py -v
```
All 9 test scenarios validate registration, login, profile updates, addresses, categories, Haversine nearby worker search, booking lifecycle, review submission, and IDOR isolation.

