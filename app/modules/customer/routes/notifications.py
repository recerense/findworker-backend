"""
Customer Notification Routes.
Protected endpoints allowing authenticated customers to:
- Retrieve their in-app notifications
- Check unread notification badge count
- Mark individual or all notifications as read
- Simulate worker response events (acceptance, rejection) for testing
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_db
from app.modules.customer.schemas import (
    NotificationListResponse,
    NotificationOut,
    SimulateNotificationRequest,
    UnreadCountResponse,
)
from app.modules.customer.security import get_current_customer
from app.modules.customer.service import CustomerNotificationService

router = APIRouter(prefix="/notifications", tags=["Customer Notifications"])


@router.get(
    "",
    response_model=NotificationListResponse,
    summary="List customer notifications",
    description="Returns notifications for the authenticated customer. Supports filtering by unread status and pagination.",
)
def list_notifications(
    unread_only: bool = Query(False, description="Filter only unread notifications"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=50, description="Pagination limit"),
    current_customer: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> NotificationListResponse:
    """
    Retrieves the customer's notifications list with unread counter.
    Strictly isolated to current_customer.id.
    """
    return CustomerNotificationService.list_notifications(
        db=db,
        current_user=current_customer,
        unread_only=unread_only,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    summary="Get unread notification count",
    description="Returns the total count of unread notifications for display in UI notification badges.",
)
def get_unread_count(
    current_customer: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> UnreadCountResponse:
    """
    Lightweight endpoint returning only the unread notification count.
    Used by frontend bell icon badges.
    """
    count = CustomerNotificationService.get_unread_count(db, current_customer)
    return UnreadCountResponse(unread_count=count)


@router.put(
    "/{notification_id}/read",
    response_model=NotificationOut,
    summary="Mark notification as read",
    description="Marks a specific notification as read. Enforces customer ownership verification.",
)
def mark_notification_as_read(
    notification_id: int,
    current_customer: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> NotificationOut:
    """
    Marks a single notification as read.
    Returns 404 if the notification does not exist or does not belong to the customer.
    """
    return CustomerNotificationService.mark_as_read(db, current_customer, notification_id)


@router.put(
    "/read-all",
    summary="Mark all notifications as read",
    description="Marks all unread notifications for the authenticated customer as read in bulk.",
)
def mark_all_notifications_as_read(
    current_customer: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    """
    Marks all notifications for the customer as read.
    """
    updated_count = CustomerNotificationService.mark_all_as_read(db, current_customer)
    return {
        "message": "All notifications marked as read.",
        "marked_count": updated_count,
    }


@router.post(
    "/simulate",
    response_model=NotificationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Simulate incoming notification event",
    description="Utility endpoint to simulate an external worker event (e.g. Worker Accepted Request, Worker Rejected Request, Worker Started Job) to test the customer notification flow independently.",
)
def simulate_notification_event(
    payload: SimulateNotificationRequest,
    current_customer: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> NotificationOut:
    """
    Allows developers or testing harnesses to push simulated worker events
    (REQUEST_ACCEPTED, REQUEST_REJECTED, JOB_IN_PROGRESS, JOB_COMPLETED) to the customer.
    """
    return CustomerNotificationService.create_notification(
        db=db,
        user_id=current_customer.id,
        title=payload.title,
        message=payload.message,
        notification_type=payload.notification_type,
        reference_id=payload.reference_id,
    )

