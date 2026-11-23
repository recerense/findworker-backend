"""
Database models for FindWorker platform.
Defines schemas for:
- User (Customers, Workers, Admins)
- CustomerAddress (Saved customer service locations)
- ServiceCategory (Catalog: Plumber, Electrician, Carpenter, etc.)
- WorkerProfile (Worker details, skills, location, rate, ratings)
- Booking (Service booking lifecycle)
- Review (Customer reviews and ratings for workers)
"""

from datetime import datetime, timezone
from typing import List, Optional
import enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Enum as SQLEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def utc_now() -> datetime:
    """Helper to return current UTC datetime."""
    return datetime.now(timezone.utc)


class UserRole(str, enum.Enum):
    CUSTOMER = "customer"
    WORKER = "worker"
    ADMIN = "admin"


class BookingStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class NotificationType(str, enum.Enum):
    REQUEST_CREATED = "REQUEST_CREATED"
    REQUEST_ACCEPTED = "REQUEST_ACCEPTED"
    REQUEST_REJECTED = "REQUEST_REJECTED"
    JOB_IN_PROGRESS = "JOB_IN_PROGRESS"
    JOB_COMPLETED = "JOB_COMPLETED"
    BOOKING_CANCELLED = "BOOKING_CANCELLED"
    GENERAL = "GENERAL"


class User(Base):
    """
    Core User entity for authentication, roles, and profile info.
    Both Customers and Workers have a corresponding User account.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(30), unique=True, index=True, nullable=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default=UserRole.CUSTOMER.value, index=True, nullable=False)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    addresses: Mapped[List["CustomerAddress"]] = relationship("CustomerAddress", back_populates="customer", cascade="all, delete-orphan")
    customer_bookings: Mapped[List["Booking"]] = relationship("Booking", back_populates="customer", cascade="all, delete-orphan")
    reviews_given: Mapped[List["Review"]] = relationship("Review", back_populates="customer")
    worker_profile: Mapped[Optional["WorkerProfile"]] = relationship("WorkerProfile", back_populates="user", uselist=False)
    notifications: Mapped[List["Notification"]] = relationship("Notification", back_populates="user", cascade="all, delete-orphan")


class CustomerAddress(Base):
    """
    Saved service addresses for Customers.
    Used during service booking for quick selection.
    """
    __tablename__ = "customer_addresses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(50), default="Home", nullable=False)
    street_address: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(20), nullable=False)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    # Relationships
    customer: Mapped["User"] = relationship("User", back_populates="addresses")


class ServiceCategory(Base):
    """
    Catalog of trade categories (e.g. Plumber, Electrician, Carpenter).
    """
    __tablename__ = "service_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    base_price: Mapped[float] = mapped_column(Float, default=40.0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    workers: Mapped[List["WorkerProfile"]] = relationship("WorkerProfile", back_populates="service_category")
    bookings: Mapped[List["Booking"]] = relationship("Booking", back_populates="service_category")


class WorkerProfile(Base):
    """
    Profile information for service professionals.
    Stores geospatial location (latitude, longitude) for nearby worker searches.
    """
    __tablename__ = "worker_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    service_category_id: Mapped[int] = mapped_column(Integer, ForeignKey("service_categories.id"), nullable=False, index=True)
    business_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hourly_rate: Mapped[float] = mapped_column(Float, default=45.0, nullable=False)
    years_of_experience: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    rating: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)
    review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    service_radius_km: Mapped[float] = mapped_column(Float, default=25.0, nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="worker_profile")
    service_category: Mapped["ServiceCategory"] = relationship("ServiceCategory", back_populates="workers")
    bookings: Mapped[List["Booking"]] = relationship("Booking", back_populates="worker")
    reviews: Mapped[List["Review"]] = relationship("Review", back_populates="worker")


class Booking(Base):
    """
    Represents a service request booked by a customer with a worker.
    Tracks schedule, address, status, and pricing.
    """
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    booking_reference: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    worker_id: Mapped[int] = mapped_column(Integer, ForeignKey("worker_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    service_category_id: Mapped[int] = mapped_column(Integer, ForeignKey("service_categories.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default=BookingStatus.PENDING.value, index=True, nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    service_address: Mapped[str] = mapped_column(Text, nullable=False)
    customer_latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    customer_longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    problem_description: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_hours: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    total_price: Mapped[float] = mapped_column(Float, nullable=False)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    customer: Mapped["User"] = relationship("User", back_populates="customer_bookings")
    worker: Mapped["WorkerProfile"] = relationship("WorkerProfile", back_populates="bookings")
    service_category: Mapped["ServiceCategory"] = relationship("ServiceCategory", back_populates="bookings")
    review: Mapped[Optional["Review"]] = relationship("Review", back_populates="booking", uselist=False)


class Review(Base):
    """
    Customer review and rating given to a worker after booking completion.
    """
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    booking_id: Mapped[int] = mapped_column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), unique=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    worker_id: Mapped[int] = mapped_column(Integer, ForeignKey("worker_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    # Relationships
    booking: Mapped["Booking"] = relationship("Booking", back_populates="review")
    customer: Mapped["User"] = relationship("User", back_populates="reviews_given")
    worker: Mapped["WorkerProfile"] = relationship("WorkerProfile", back_populates="reviews")


class Notification(Base):
    """
    In-app notification for customers.
    Alerts on booking status changes (Accepted, Rejected, In Progress, Completed).
    """
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    notification_type: Mapped[str] = mapped_column(String(50), default=NotificationType.GENERAL.value, index=True, nullable=False)
    reference_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # e.g., booking_id / request_id
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="notifications")

