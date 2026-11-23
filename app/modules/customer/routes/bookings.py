"""
Customer Booking Lifecycle & Review Routes.
Protected endpoints allowing authenticated customers to:
- Book a service with a selected worker
- View their booking history and track appointment status
- Retrieve specific booking details
- Cancel pending or confirmed bookings
- Submit ratings and reviews upon job completion
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_db
from app.modules.customer.schemas import (
    BookingAcceptRequest,
    BookingCancelRequest,
    BookingCreateRequest,
    BookingOut,
    BookingRejectRequest,
    ReviewCreateRequest,
    ReviewOut,
)
from app.modules.customer.security import get_current_customer
from app.modules.customer.service import CustomerBookingService

router = APIRouter(prefix="/bookings", tags=["Customer Bookings & Reviews"])


@router.post(
    "",
    response_model=BookingOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new service booking",
    description="Submits a booking request to a selected worker with appointment schedule, location, and issue description.",
)
def create_booking(
    payload: BookingCreateRequest,
    current_customer: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> BookingOut:
    """
    Creates a new service booking for the authenticated customer.
    - Validates that the requested appointment time is in the future
    - Verifies worker availability
    - Computes total estimated price (hourly rate * estimated hours)
    - Generates human-friendly booking reference (e.g., BK-20261117-A1B2)
    - Sets initial status to PENDING
    """
    return CustomerBookingService.create_booking(db, current_customer, payload)


@router.get(
    "",
    response_model=List[BookingOut],
    summary="List customer bookings",
    description="Returns all bookings created by the authenticated customer. Supports filtering by status (PENDING, CONFIRMED, IN_PROGRESS, COMPLETED, CANCELLED).",
)
def list_bookings(
    status: Optional[str] = Query(None, description="Filter by booking status (e.g. PENDING, CONFIRMED, COMPLETED, CANCELLED)"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=50, description="Pagination limit"),
    current_customer: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> List[BookingOut]:
    """
    Retrieves the customer's booking history.
    Strictly scoped to the authenticated customer ID to prevent cross-account access.
    """
    return CustomerBookingService.list_customer_bookings(
        db=db,
        current_user=current_customer,
        status_filter=status,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{booking_id}",
    response_model=BookingOut,
    summary="Get booking details",
    description="Retrieves complete information for a specific booking by ID. Verifies customer ownership.",
)
def get_booking_detail(
    booking_id: int,
    current_customer: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> BookingOut:
    """
    Retrieves a single booking's details.
    Enforces authorization check: returns 404 if the booking is not owned by the customer.
    """
    return CustomerBookingService.get_customer_booking(db, current_customer, booking_id)


@router.post(
    "/{booking_id}/cancel",
    response_model=BookingOut,
    summary="Cancel a booking",
    description="Cancels an active booking if it is in PENDING or CONFIRMED status.",
)
def cancel_booking(
    booking_id: int,
    payload: BookingCancelRequest,
    current_customer: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> BookingOut:
    """
    Allows a customer to cancel an upcoming booking.
    - Verifies booking ownership
    - Ensures the booking is not already COMPLETED or CANCELLED
    - Records the cancellation reason and updates status to CANCELLED
    """
    return CustomerBookingService.cancel_booking(db, current_customer, booking_id, payload)


@router.post(
    "/{booking_id}/accept",
    response_model=BookingOut,
    summary="Accept a service request or worker proposal",
    description="Customer accepts a service request, confirmed schedule, or worker quote. Status transitions to CONFIRMED and sends a notification.",
)
def accept_booking(
    booking_id: int,
    payload: Optional[BookingAcceptRequest] = None,
    current_customer: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> BookingOut:
    """
    Accepts/confirms a service request.
    Verifies ownership and valid status before transitioning to CONFIRMED.
    """
    return CustomerBookingService.accept_booking(db, current_customer, booking_id, payload)


@router.post(
    "/{booking_id}/reject",
    response_model=BookingOut,
    summary="Reject a service request or proposal",
    description="Customer rejects an incoming worker proposal, quotation, or unwanted request with a reason. Status transitions to REJECTED and sends a notification.",
)
def reject_booking(
    booking_id: int,
    payload: BookingRejectRequest,
    current_customer: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> BookingOut:
    """
    Rejects a service request or proposal.
    Records the rejection reason and transitions status to REJECTED.
    """
    return CustomerBookingService.reject_booking(db, current_customer, booking_id, payload)


@router.post(
    "/{booking_id}/review",
    response_model=ReviewOut,
    status_code=status.HTTP_201_CREATED,
    summary="Submit review and rating",
    description="Leaves a 1-to-5 star rating and feedback for a worker after a service has been COMPLETED.",
)
def submit_review(
    booking_id: int,
    payload: ReviewCreateRequest,
    current_customer: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> ReviewOut:
    """
    Submits a rating and review for a completed service.
    - Verifies customer ownership of the booking
    - Enforces that the booking status is COMPLETED
    - Prevents duplicate reviews for the same booking
    - Automatically updates the worker's average rating and total review count
    """
    return CustomerBookingService.submit_review(db, current_customer, booking_id, payload)

