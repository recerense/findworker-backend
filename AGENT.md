# AGENT.md — FindWorker Backend Memory & Architecture Guide

This document preserves the project context, service boundaries, architecture, database schemas, and implementation details for future AI agents and developers.

---

## 🧭 Team Ownership & Service Boundaries

FindWorker is an on-demand marketplace connecting customers with nearby skilled workers (plumbers, electricians, carpenters, AC technicians, painters, cleaners).

### 👥 Division of Work
- **Customer Service (`app/modules/customer/`)**: **OUR RESPONSIBILITY**. Fully built, tested, and maintained here.
- **Worker Service (`app/modules/worker/`)**: **Managed by other developers**. Do not modify unless requested.
- **Standalone Auth & Admin (`app/modules/auth/`, `app/modules/admin/`, `app/modules/locations/`)**: **Managed by other developers**.

---

## 🏗️ Customer Service API Inventory

All customer endpoints are mounted under `/api/customer`:

### 1. Authentication (`/api/customer/auth`)
- `POST /api/customer/auth/register` — Customer registration (email/phone uniqueness check, strong password validation, bcrypt hashing, returns JWT session).
- `POST /api/customer/auth/login` — Customer login (constant-time password verification, returns HS256 Bearer JWT token).

### 2. Profile & Saved Addresses (`/api/customer/profile` & `/api/customer/addresses`)
- `GET /api/customer/profile` — View authenticated customer profile.
- `PUT /api/customer/profile` — Update customer name, phone, avatar.
- `GET /api/customer/addresses` — List saved customer delivery/service addresses.
- `POST /api/customer/addresses` — Add a new address with GPS coordinates (`latitude`, `longitude`).
- `DELETE /api/customer/addresses/{address_id}` — Delete a saved address (IDOR protected).

### 3. Service Discovery & Nearby Search (`/api/customer/services`)
- `GET /api/customer/services/categories` — Browse active trade catalog categories (Plumbing, Electrical, etc.).
- `GET /api/customer/services/nearby` — Real-time GPS search for nearby workers using customer `latitude`, `longitude`, `radius_km`, and optional `category_id`. Calculates distance using the **Haversine formula** and sorts closest first.
- `GET /api/customer/workers/{worker_id}` — View detailed public worker profile, experience, hourly rate, coverage radius, and reviews.

### 4. Service Requests & Bookings (`/api/customer/requests` & `/api/customer/bookings`)
*Note: `/api/customer/requests` and `/api/customer/bookings` are unified and work interchangeably.*
- `POST /api/customer/requests` (or `/bookings`) — Submit a new service request with appointment time, location, and problem description. Status begins at `PENDING`.
- `GET /api/customer/requests` (or `/bookings`) — List customer's service requests (filterable by status: `PENDING`, `CONFIRMED`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED`, `REJECTED`).
- `GET /api/customer/requests/{id}` (or `/bookings/{id}`) — View full details of a specific request.
- `POST /api/customer/requests/{id}/accept` — Customer accepts a worker's proposal, quote, or confirmed schedule. Transitions status to `CONFIRMED`.
- `POST /api/customer/requests/{id}/reject` — Customer rejects an incoming proposal or unwanted request with a reason. Transitions status to `REJECTED`.
- `POST /api/customer/requests/{id}/cancel` — Customer cancels an upcoming request. Transitions status to `CANCELLED`.
- `POST /api/customer/bookings/{id}/review` — Submit a 1-to-5 star rating and feedback for completed jobs. Automatically updates the worker's average rating and total review count.

### 5. In-App Notifications (`/api/customer/notifications`)
- `GET /api/customer/notifications` — List customer notifications (supports `unread_only=true/false` and pagination).
- `GET /api/customer/notifications/unread-count` — Returns `{ "unread_count": int }` for frontend notification badge.
- `PUT /api/customer/notifications/{id}/read` — Mark a single notification as read (IDOR protected).
- `PUT /api/customer/notifications/read-all` — Mark all customer notifications as read.
- `POST /api/customer/notifications/simulate` — Utility to push simulated worker events (`REQUEST_ACCEPTED`, `REQUEST_REJECTED`, `JOB_IN_PROGRESS`, `JOB_COMPLETED`) to test customer notifications independently.

---

## 🗄️ Database Architecture & Models

Defined in [`app/db/models.py`](file:///home/vishnu/socwhiz/findworker-backend/app/db/models.py):

```
┌─────────────┐       1:N       ┌─────────────────────┐
│    User     │────────────────>│   CustomerAddress   │
│             │                 └─────────────────────┘
│             │       1:N       ┌─────────────────────┐
│             │────────────────>│    Notification     │
│             │                 └─────────────────────┘
│             │       1:1       ┌─────────────────────┐
│             │────────────────>│    WorkerProfile    │
│             │                 └──────────┬──────────┘
│             │                            │
│             │       1:N                  │ 1:N
│             │─────────────┐              │
└─────────────┘             │              │
                            ▼              ▼
                     ┌────────────────────────────┐
                     │          Booking           │
                     └─────────────┬──────────────┘
                                   │ 1:1
                                   ▼
                     ┌────────────────────────────┐
                     │           Review           │
                     └────────────────────────────┘
```

### Connection Strategy ([`app/db/session.py`](file:///home/vishnu/socwhiz/findworker-backend/app/db/session.py))
- **Production (AWS Aurora PostgreSQL)**: `postgresql+psycopg` connection with connection pooling (`pool_pre_ping=True`, `pool_size=10`, `max_overflow=20`).
- **Local Dev Sandbox**: If `DB_PASSWORD` is omitted, automatically falls back to `sqlite:///./findworker_dev.db` with `check_same_thread=False`.
- **Session Lifecycle**: FastAPI `Depends(get_db)` ensures isolated session per request and guaranteed session close.
- **Seeding ([`app/db/seed.py`](file:///home/vishnu/socwhiz/findworker-backend/app/db/seed.py))**: Automatically creates baseline categories and sample workers with coordinates on first boot.

---

## 🔒 Security Best Practices Implemented

1. **Password Hashing**: Native `bcrypt` (12 rounds) with unique salts. Minimum 8 characters, letter and digit validation.
2. **JWT Authentication**: Hardcoded `HS256` algorithm, sets `exp` expiration and `sub` user ID claims. Secret loaded from AWS Secrets Manager / environment.
3. **IDOR Defense**: All database operations for bookings, addresses, and notifications enforce `record.customer_id == current_customer.id` or `record.user_id == current_customer.id`. Unauthorized access returns `404 Not Found`.
4. **SQL Injection Defense**: 100% parameterized SQLAlchemy 2.0 ORM expressions (`select()`, `where()`). Zero raw SQL concatenation.
5. **Security Response Headers**: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 1; mode=block`.

---

## 🧪 Testing & Verification

Comprehensive test suite in [`tests/test_customer_api.py`](file:///home/vishnu/socwhiz/findworker-backend/tests/test_customer_api.py):

```bash
cd findworker-backend
python3 -m pytest tests/test_customer_api.py -v
```
All 11 test cases pass, covering:
- Customer registration, login, and validation
- Profile update and address management with IDOR checks
- Category listing and nearby worker GPS search (Haversine)
- Service request lifecycle (create, list, accept, reject, cancel, review)
- In-app notification delivery, unread count, and read status

