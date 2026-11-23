"""
Pydantic schemas for Customer Service.
Validates inputs and formats outputs for:
- Authentication & JWT Token responses
- Profile and address management
- Nearby services & worker search
- Booking creation and lifecycle
- Reviews and ratings
"""

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# =============================================================================
# Authentication & User Schemas
# =============================================================================

class CustomerRegisterRequest(BaseModel):
    """Payload for customer account registration."""
    full_name: str = Field(..., min_length=2, max_length=100, description="Full name of customer")
    email: EmailStr = Field(..., description="Unique email address")
    phone: Optional[str] = Field(None, min_length=7, max_length=20, description="Contact phone number")
    password: str = Field(..., min_length=8, max_length=128, description="Password (minimum 8 characters)")

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Enforces strong password rules (min 8 chars, at least one letter and digit)."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least one letter.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        return v


class CustomerLoginRequest(BaseModel):
    """Payload for customer login."""
    email: EmailStr = Field(..., description="Registered customer email")
    password: str = Field(..., description="Account password")


class CustomerProfileOut(BaseModel):
    """Customer profile details returned in responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    role: str
    avatar_url: Optional[str] = None
    created_at: datetime


class TokenResponse(BaseModel):
    """Standard JWT authentication response."""
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    customer: CustomerProfileOut


class CustomerProfileUpdate(BaseModel):
    """Payload to update customer profile fields."""
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = Field(None, min_length=7, max_length=20)
    avatar_url: Optional[str] = Field(None, max_length=500)


# =============================================================================
# Address Schemas
# =============================================================================

class CustomerAddressCreate(BaseModel):
    """Payload to add a new service address."""
    title: str = Field("Home", min_length=1, max_length=50, description="Address label (e.g., Home, Office)")
    street_address: str = Field(..., min_length=3, max_length=255)
    city: str = Field(..., min_length=2, max_length=100)
    state: str = Field(..., min_length=2, max_length=100)
    postal_code: str = Field(..., min_length=3, max_length=20)
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0, description="Latitude for location pin")
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0, description="Longitude for location pin")
    is_default: bool = False


class CustomerAddressOut(BaseModel):
    """Customer address response schema."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    title: str
    street_address: str
    city: str
    state: str
    postal_code: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_default: bool
    created_at: datetime


# =============================================================================
# Service Category & Nearby Worker Search Schemas
# =============================================================================

class ServiceCategoryOut(BaseModel):
    """Service catalog category response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    description: Optional[str] = None
    icon: Optional[str] = None
    base_price: float
    is_active: bool


class WorkerPublicOut(BaseModel):
    """Public worker listing shown in nearby service search results."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    full_name: str
    business_name: Optional[str] = None
    avatar_url: Optional[str] = None
    category_id: int
    category_name: str
    hourly_rate: float
    rating: float
    review_count: int
    years_of_experience: int
    distance_km: Optional[float] = Field(None, description="Distance from customer location in kilometers")
    is_available: bool
    latitude: float
    longitude: float


class WorkerReviewSummary(BaseModel):
    """Summary of review shown on worker profile."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_name: str
    rating: int
    comment: Optional[str] = None
    created_at: datetime


class WorkerDetailOut(WorkerPublicOut):
    """Detailed worker profile with bio and recent reviews."""
    bio: Optional[str] = None
    service_radius_km: float
    recent_reviews: List[WorkerReviewSummary] = []


# =============================================================================
# Booking & Review Schemas
# =============================================================================

class BookingCreateRequest(BaseModel):
    """Payload to create a service booking."""
    worker_id: int = Field(..., description="ID of worker to book")
    service_category_id: int = Field(..., description="Service category ID")
    scheduled_at: datetime = Field(..., description="Desired appointment time (UTC)")
    service_address: str = Field(..., min_length=5, description="Full address where service is needed")
    customer_latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    customer_longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    problem_description: str = Field(..., min_length=10, max_length=2000, description="Description of the issue or job")
    estimated_hours: float = Field(1.0, ge=0.5, le=24.0, description="Estimated work duration in hours")

    @field_validator("scheduled_at")
    @classmethod
    def validate_future_date(cls, v: datetime) -> datetime:
        """Ensures scheduled appointment time is in the future."""
        # Strip timezone if naive for safe comparison
        v_naive = v.replace(tzinfo=None) if v.tzinfo else v
        if v_naive < datetime.now(timezone.utc).replace(tzinfo=None):
            raise ValueError("Scheduled appointment time must be in the future.")
        return v


class BookingCancelRequest(BaseModel):
    """Payload to cancel an existing booking."""
    cancellation_reason: str = Field(..., min_length=5, max_length=500, description="Reason for cancellation")


class ReviewCreateRequest(BaseModel):
    """Payload to submit a review for a completed service."""
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5 stars")
    comment: Optional[str] = Field(None, max_length=1000, description="Detailed customer feedback")


class ReviewOut(BaseModel):
    """Customer review response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    booking_id: int
    worker_id: int
    rating: int
    comment: Optional[str] = None
    created_at: datetime


class BookingOut(BaseModel):
    """Full booking details returned to the customer."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    booking_reference: str
    customer_id: int
    worker_id: int
    worker_name: str
    worker_phone: Optional[str] = None
    worker_avatar: Optional[str] = None
    service_category_id: int
    category_name: str
    status: str
    scheduled_at: datetime
    service_address: str
    problem_description: str
    estimated_hours: float
    total_price: float
    cancellation_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    review: Optional[ReviewOut] = None


class BookingRejectRequest(BaseModel):
    """Payload for rejecting a service request or worker proposal."""
    rejection_reason: str = Field(..., min_length=5, max_length=500, description="Reason for rejecting the service request")


class BookingAcceptRequest(BaseModel):
    """Payload for customer accepting a service quote, schedule, or proposal."""
    note: Optional[str] = Field(None, max_length=500, description="Optional acceptance confirmation note")


# =============================================================================
# Notification Schemas
# =============================================================================

class NotificationOut(BaseModel):
    """In-app notification item representation."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    message: str
    notification_type: str
    reference_id: Optional[int] = None
    is_read: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    """Paginated notification list response with total unread count."""
    notifications: List[NotificationOut]
    unread_count: int
    total: int


class UnreadCountResponse(BaseModel):
    """Quick response for UI notification badge count."""
    unread_count: int


class SimulateNotificationRequest(BaseModel):
    """
    Utility payload to simulate a worker-driven notification event
    (e.g. Worker Accepted, Worker Rejected, Job Started, Job Completed).
    Allows customer service to be tested standalone without waiting for worker service.
    """
    title: str = Field(..., min_length=3, max_length=150)
    message: str = Field(..., min_length=5, max_length=1000)
    notification_type: str = Field("REQUEST_ACCEPTED", description="One of: REQUEST_ACCEPTED, REQUEST_REJECTED, JOB_IN_PROGRESS, JOB_COMPLETED, GENERAL")
    reference_id: Optional[int] = Field(None, description="Related booking / request ID")

