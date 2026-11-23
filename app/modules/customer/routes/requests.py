"""
Customer Service Requests Routes.
Provides dedicated endpoints for:
- Requesting a service (creating a service lead / appointment)
- Viewing service requests
- Accepting worker proposals / quotes
- Rejecting worker proposals / unwanted requests
- Cancelling requests
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
)
from app.modules.customer.security import get_current_customer
from app.modules.customer.service import CustomerBookingService

router = APIRouter(prefix="/requests", tags=["Customer Service Requests"])


@router.post(
    "",
    response_model=BookingOut,
    status_code=status.HTTP_201_CREATED,
    summary="Request a service",
    description="Submits a new service request to a worker with schedule, location coordinates, and problem details.",
)
def request_service(
    payload: BookingCreateRequest,
    current_customer: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> BookingOut:
    """
    Submits a service request to a worker.
    Creates booking with PENDING status and sends an in-app notification to the customer.
    """
    return CustomerBookingService.create_booking(db, current_customer, payload)


@router.get(
    "",
    response_model=List[BookingOut],
    summary="List customer service requests",
    description="Lists all service requests created by the customer, filterable by status.",
)
def list_service_requests(
    status: Optional[str] = Query(None, description="Filter by status (PENDING, CONFIRMED, IN_PROGRESS, COMPLETED, CANCELLED, REJECTED)"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=50, description="Pagination limit"),
    current_customer: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> List[BookingOut]:
    """
    Retrieves all service requests for the authenticated customer.
    """
    return CustomerBookingService.list_customer_bookings(
        db=db,
        current_user=current_customer,
        status_filter=status,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{request_id}",
    response_model=BookingOut,
    summary="Get service request detail",
    description="Retrieves complete information for a specific service request.",
)
def get_service_request_detail(
    request_id: int,
    current_customer: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> BookingOut:
    """
    Gets details of a single service request.
    Verifies customer ownership.
    """
    return CustomerBookingService.get_customer_booking(db, current_customer, request_id)


@router.post(
    "/{request_id}/accept",
    response_model=BookingOut,
    summary="Accept service request / quote",
    description="Customer accepts a worker's schedule or quote. Transitions status to CONFIRMED and sends a notification.",
)
def accept_service_request(
    request_id: int,
    payload: Optional[BookingAcceptRequest] = None,
    current_customer: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> BookingOut:
    """
    Accepts/confirms a service request or worker proposal.
    """
    return CustomerBookingService.accept_booking(db, current_customer, request_id, payload)


@router.post(
    "/{request_id}/reject",
    response_model=BookingOut,
    summary="Reject service request / proposal",
    description="Customer rejects an incoming worker proposal, quotation, or unwanted request with a reason. Transitions status to REJECTED and sends a notification.",
)
def reject_service_request(
    request_id: int,
    payload: BookingRejectRequest,
    current_customer: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> BookingOut:
    """
    Rejects a service request or worker quote.
    """
    return CustomerBookingService.reject_booking(db, current_customer, request_id, payload)


@router.post(
    "/{request_id}/cancel",
    response_model=BookingOut,
    summary="Cancel service request",
    description="Customer cancels an upcoming service request with a reason.",
)
def cancel_service_request(
    request_id: int,
    payload: BookingCancelRequest,
    current_customer: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> BookingOut:
    """
    Cancels an upcoming service request.
    """
    return CustomerBookingService.cancel_booking(db, current_customer, request_id, payload)

