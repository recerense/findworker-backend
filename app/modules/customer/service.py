"""
Business logic and service layer for Customer operations.
Implements:
- Customer registration and secure login
- Profile and saved address management
- Nearby services & worker geospatial search (Haversine formula)
- Service booking lifecycle (create, list, detail, cancellation)
- Review submission and worker rating aggregation
"""

from datetime import datetime, timezone
import math
import secrets
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.config import settings
from app.db.models import (
    Booking,
    BookingStatus,
    CustomerAddress,
    Notification,
    NotificationType,
    Review,
    ServiceCategory,
    User,
    UserRole,
    WorkerProfile,
)
from app.modules.customer.schemas import (
    BookingAcceptRequest,
    BookingCancelRequest,
    BookingCreateRequest,
    BookingOut,
    BookingRejectRequest,
    CustomerAddressCreate,
    CustomerAddressOut,
    CustomerLoginRequest,
    CustomerProfileOut,
    CustomerProfileUpdate,
    CustomerRegisterRequest,
    NotificationListResponse,
    NotificationOut,
    ReviewCreateRequest,
    ReviewOut,
    ServiceCategoryOut,
    SimulateNotificationRequest,
    TokenResponse,
    UnreadCountResponse,
    WorkerDetailOut,
    WorkerPublicOut,
    WorkerReviewSummary,
)
from app.modules.customer.security import (
    create_access_token,
    hash_password,
    verify_password,
)


def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes the great-circle distance between two geographic coordinates in kilometers
    using the Haversine trigonometric formula.
    """
    R = 6371.0  # Earth's mean radius in kilometers
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(R * c, 2)


class CustomerAuthService:
    """Authentication and identity operations for customers."""

    @staticmethod
    def register_customer(db: Session, data: CustomerRegisterRequest) -> TokenResponse:
        """
        Registers a new customer account.
        - Validates uniqueness of email and phone
        - Hashes password using bcrypt
        - Creates User record with role='customer'
        - Generates JWT access token
        """
        # Check if email is already taken
        existing_email = db.execute(
            select(User).where(User.email == data.email.lower().strip())
        ).scalar_one_or_none()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email address already exists.",
            )

        # Check if phone is already taken
        if data.phone:
            existing_phone = db.execute(
                select(User).where(User.phone == data.phone.strip())
            ).scalar_one_or_none()
            if existing_phone:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="An account with this phone number already exists.",
                )

        # Hash password securely
        hashed_pwd = hash_password(data.password)

        # Create new customer user
        new_customer = User(
            email=data.email.lower().strip(),
            phone=data.phone.strip() if data.phone else None,
            full_name=data.full_name.strip(),
            hashed_password=hashed_pwd,
            role=UserRole.CUSTOMER.value,
            is_active=True,
        )
        db.add(new_customer)
        db.commit()
        db.refresh(new_customer)

        # Issue access token
        access_token = create_access_token(
            data={"sub": str(new_customer.id), "email": new_customer.email, "role": new_customer.role}
        )

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
            customer=CustomerProfileOut.model_validate(new_customer),
        )

    @staticmethod
    def authenticate_customer(db: Session, data: CustomerLoginRequest) -> TokenResponse:
        """
        Authenticates a customer using email and password.
        - Validates credentials using constant-time comparison
        - Confirms customer role and active status
        - Returns JWT bearer token
        """
        user = db.execute(
            select(User).where(User.email == data.email.lower().strip())
        ).scalar_one_or_none()

        if not user or not verify_password(data.password, user.hashed_password):
            # Generic message to prevent user enumeration attacks
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account has been deactivated. Please contact support.",
            )

        # Issue access token
        access_token = create_access_token(
            data={"sub": str(user.id), "email": user.email, "role": user.role}
        )

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
            customer=CustomerProfileOut.model_validate(user),
        )


class CustomerProfileService:
    """Manages customer profiles and saved service locations."""

    @staticmethod
    def get_profile(current_user: User) -> CustomerProfileOut:
        """Retrieves profile of the authenticated customer."""
        return CustomerProfileOut.model_validate(current_user)

    @staticmethod
    def update_profile(db: Session, current_user: User, data: CustomerProfileUpdate) -> CustomerProfileOut:
        """Updates full name, phone number, or avatar URL for the customer."""
        if data.full_name is not None:
            current_user.full_name = data.full_name.strip()
        if data.phone is not None:
            current_user.phone = data.phone.strip()
        if data.avatar_url is not None:
            current_user.avatar_url = data.avatar_url.strip()

        db.add(current_user)
        db.commit()
        db.refresh(current_user)
        return CustomerProfileOut.model_validate(current_user)

    @staticmethod
    def list_addresses(db: Session, current_user: User) -> List[CustomerAddressOut]:
        """Lists all saved addresses belonging to the customer."""
        stmt = (
            select(CustomerAddress)
            .where(CustomerAddress.customer_id == current_user.id)
            .order_by(CustomerAddress.is_default.desc(), CustomerAddress.created_at.desc())
        )
        addresses = db.execute(stmt).scalars().all()
        return [CustomerAddressOut.model_validate(a) for a in addresses]

    @staticmethod
    def create_address(db: Session, current_user: User, data: CustomerAddressCreate) -> CustomerAddressOut:
        """
        Creates a new service address.
        If marked as default, unsets default status on all previous addresses.
        """
        if data.is_default:
            # Unset existing defaults
            existing_addresses = db.execute(
                select(CustomerAddress).where(CustomerAddress.customer_id == current_user.id)
            ).scalars().all()
            for addr in existing_addresses:
                addr.is_default = False

        new_address = CustomerAddress(
            customer_id=current_user.id,
            title=data.title.strip(),
            street_address=data.street_address.strip(),
            city=data.city.strip(),
            state=data.state.strip(),
            postal_code=data.postal_code.strip(),
            latitude=data.latitude,
            longitude=data.longitude,
            is_default=data.is_default,
        )
        db.add(new_address)
        db.commit()
        db.refresh(new_address)
        return CustomerAddressOut.model_validate(new_address)

    @staticmethod
    def delete_address(db: Session, current_user: User, address_id: int) -> bool:
        """
        Deletes a customer address.
        Enforces strict customer ownership verification to prevent IDOR vulnerabilities.
        """
        stmt = select(CustomerAddress).where(
            CustomerAddress.id == address_id,
            CustomerAddress.customer_id == current_user.id,
        )
        address = db.execute(stmt).scalar_one_or_none()
        if not address:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Address not found or not owned by the current customer.",
            )

        db.delete(address)
        db.commit()
        return True


class NearbyServicesService:
    """Geospatial search and catalog exploration for nearby workers and trades."""

    @staticmethod
    def list_categories(db: Session) -> List[ServiceCategoryOut]:
        """Returns all active service catalog categories."""
        stmt = select(ServiceCategory).where(ServiceCategory.is_active == True).order_by(ServiceCategory.name.asc())
        categories = db.execute(stmt).scalars().all()
        return [ServiceCategoryOut.model_validate(c) for c in categories]

    @staticmethod
    def search_nearby_workers(
        db: Session,
        latitude: float,
        longitude: float,
        category_id: Optional[int] = None,
        radius_km: float = 25.0,
        keyword: Optional[str] = None,
        min_rating: Optional[float] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[WorkerPublicOut]:
        """
        Discovers nearby service professionals using coordinates and Haversine distance.
        - Filters by service category, keyword, rating, and availability
        - Calculates real-time distance from customer coordinates
        - Restricts results to workers within radius_km
        - Sorts by closest distance first
        """
        query = (
            select(WorkerProfile)
            .options(joinedload(WorkerProfile.user), joinedload(WorkerProfile.service_category))
            .where(
                WorkerProfile.is_available == True,
                WorkerProfile.is_verified == True,
            )
        )

        if category_id:
            query = query.where(WorkerProfile.service_category_id == category_id)

        if min_rating is not None:
            query = query.where(WorkerProfile.rating >= min_rating)

        if keyword:
            search_pattern = f"%{keyword.strip()}%"
            query = query.join(WorkerProfile.user).join(WorkerProfile.service_category).where(
                or_(
                    User.full_name.ilike(search_pattern),
                    WorkerProfile.business_name.ilike(search_pattern),
                    WorkerProfile.bio.ilike(search_pattern),
                    ServiceCategory.name.ilike(search_pattern),
                )
            )

        workers = db.execute(query).scalars().all()

        # Compute distance and filter within radius
        matched_workers = []
        for worker in workers:
            dist = calculate_haversine_distance(latitude, longitude, worker.latitude, worker.longitude)
            if dist <= radius_km:
                matched_workers.append({
                    "id": worker.id,
                    "user_id": worker.user_id,
                    "full_name": worker.user.full_name,
                    "business_name": worker.business_name,
                    "avatar_url": worker.user.avatar_url,
                    "category_id": worker.service_category_id,
                    "category_name": worker.service_category.name,
                    "hourly_rate": worker.hourly_rate,
                    "rating": worker.rating,
                    "review_count": worker.review_count,
                    "years_of_experience": worker.years_of_experience,
                    "distance_km": dist,
                    "is_available": worker.is_available,
                    "latitude": worker.latitude,
                    "longitude": worker.longitude,
                })

        # Sort by proximity (closest first)
        matched_workers.sort(key=lambda x: x["distance_km"])

        # Paginate results
        paginated = matched_workers[skip : skip + limit]
        return [WorkerPublicOut(**w) for w in paginated]

    @staticmethod
    def get_worker_detail(db: Session, worker_id: int) -> WorkerDetailOut:
        """
        Fetches detailed information for a specific worker, including bio and recent reviews.
        """
        stmt = (
            select(WorkerProfile)
            .options(
                joinedload(WorkerProfile.user),
                joinedload(WorkerProfile.service_category),
                selectinload(WorkerProfile.reviews).joinedload(Review.customer),
            )
            .where(WorkerProfile.id == worker_id)
        )
        worker = db.execute(stmt).scalar_one_or_none()
        if not worker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Worker profile not found.",
            )

        # Format recent reviews
        recent_reviews = []
        for r in worker.reviews:
            recent_reviews.append(
                WorkerReviewSummary(
                    id=r.id,
                    customer_name=r.customer.full_name if r.customer else "Anonymous Customer",
                    rating=r.rating,
                    comment=r.comment,
                    created_at=r.created_at,
                )
            )

        return WorkerDetailOut(
            id=worker.id,
            user_id=worker.user_id,
            full_name=worker.user.full_name,
            business_name=worker.business_name,
            avatar_url=worker.user.avatar_url,
            category_id=worker.service_category_id,
            category_name=worker.service_category.name,
            hourly_rate=worker.hourly_rate,
            rating=worker.rating,
            review_count=worker.review_count,
            years_of_experience=worker.years_of_experience,
            distance_km=None,
            is_available=worker.is_available,
            latitude=worker.latitude,
            longitude=worker.longitude,
            bio=worker.bio,
            service_radius_km=worker.service_radius_km,
            recent_reviews=recent_reviews,
        )


class CustomerBookingService:
    """Manages the full booking lifecycle for customers."""

    @staticmethod
    def _format_booking_out(booking: Booking) -> BookingOut:
        """Helper to serialize a Booking model into the BookingOut schema."""
        review_out = None
        if booking.review:
            review_out = ReviewOut.model_validate(booking.review)

        return BookingOut(
            id=booking.id,
            booking_reference=booking.booking_reference,
            customer_id=booking.customer_id,
            worker_id=booking.worker_id,
            worker_name=booking.worker.user.full_name if booking.worker and booking.worker.user else "Worker",
            worker_phone=booking.worker.user.phone if booking.worker and booking.worker.user else None,
            worker_avatar=booking.worker.user.avatar_url if booking.worker and booking.worker.user else None,
            service_category_id=booking.service_category_id,
            category_name=booking.service_category.name if booking.service_category else "Service",
            status=booking.status,
            scheduled_at=booking.scheduled_at,
            service_address=booking.service_address,
            problem_description=booking.problem_description,
            estimated_hours=booking.estimated_hours,
            total_price=booking.total_price,
            cancellation_reason=booking.cancellation_reason,
            created_at=booking.created_at,
            updated_at=booking.updated_at,
            review=review_out,
        )

    @staticmethod
    def create_booking(db: Session, current_user: User, data: BookingCreateRequest) -> BookingOut:
        """
        Creates a new service booking request with a worker.
        - Validates worker existence and availability
        - Calculates total price based on worker's hourly rate and estimated hours
        - Assigns unique reference string (BK-YYYYMMDD-XXXX)
        - Sets initial status to PENDING
        """
        worker_stmt = (
            select(WorkerProfile)
            .options(joinedload(WorkerProfile.user), joinedload(WorkerProfile.service_category))
            .where(WorkerProfile.id == data.worker_id)
        )
        worker = db.execute(worker_stmt).scalar_one_or_none()
        if not worker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Selected worker does not exist.",
            )

        if not worker.is_available:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected worker is currently unavailable for new bookings.",
            )

        # Calculate estimated price
        total_price = round(worker.hourly_rate * data.estimated_hours, 2)

        # Generate unique readable booking reference
        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        unique_suffix = secrets.token_hex(3).upper()
        reference = f"BK-{today_str}-{unique_suffix}"

        new_booking = Booking(
            booking_reference=reference,
            customer_id=current_user.id,
            worker_id=worker.id,
            service_category_id=data.service_category_id,
            status=BookingStatus.PENDING.value,
            scheduled_at=data.scheduled_at,
            service_address=data.service_address.strip(),
            customer_latitude=data.customer_latitude,
            customer_longitude=data.customer_longitude,
            problem_description=data.problem_description.strip(),
            estimated_hours=data.estimated_hours,
            total_price=total_price,
        )
        db.add(new_booking)
        db.flush()

        # Send in-app notification to customer
        notification = Notification(
            user_id=current_user.id,
            title="Service Request Sent",
            message=f"Your request {reference} has been sent to {worker.user.full_name}. We will notify you once accepted.",
            notification_type=NotificationType.REQUEST_CREATED.value,
            reference_id=new_booking.id,
            is_read=False,
        )
        db.add(notification)
        db.commit()
        db.refresh(new_booking)

        return CustomerBookingService._format_booking_out(new_booking)

    @staticmethod
    def list_customer_bookings(
        db: Session,
        current_user: User,
        status_filter: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[BookingOut]:
        """
        Lists bookings created by the authenticated customer.
        Supports optional filtering by status (PENDING, CONFIRMED, COMPLETED, CANCELLED).
        Strictly scoped to current_user.id to prevent cross-customer data leakage.
        """
        query = (
            select(Booking)
            .options(
                joinedload(Booking.worker).joinedload(WorkerProfile.user),
                joinedload(Booking.service_category),
                joinedload(Booking.review),
            )
            .where(Booking.customer_id == current_user.id)
        )

        if status_filter:
            query = query.where(Booking.status == status_filter.upper())

        query = query.order_by(Booking.created_at.desc()).offset(skip).limit(limit)
        bookings = db.execute(query).unique().scalars().all()
        return [CustomerBookingService._format_booking_out(b) for b in bookings]

    @staticmethod
    def get_customer_booking(db: Session, current_user: User, booking_id: int) -> BookingOut:
        """
        Retrieves details of a specific booking.
        Enforces customer ownership verification.
        """
        stmt = (
            select(Booking)
            .options(
                joinedload(Booking.worker).joinedload(WorkerProfile.user),
                joinedload(Booking.service_category),
                joinedload(Booking.review),
            )
            .where(
                Booking.id == booking_id,
                Booking.customer_id == current_user.id,
            )
        )
        booking = db.execute(stmt).unique().scalar_one_or_none()
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found or access denied.",
            )

        return CustomerBookingService._format_booking_out(booking)

    @staticmethod
    def cancel_booking(
        db: Session,
        current_user: User,
        booking_id: int,
        data: BookingCancelRequest,
    ) -> BookingOut:
        """
        Cancels an active booking.
        - Validates ownership
        - Enforces that only PENDING or CONFIRMED bookings can be cancelled
        """
        stmt = (
            select(Booking)
            .options(
                joinedload(Booking.worker).joinedload(WorkerProfile.user),
                joinedload(Booking.service_category),
                joinedload(Booking.review),
            )
            .where(
                Booking.id == booking_id,
                Booking.customer_id == current_user.id,
            )
        )
        booking = db.execute(stmt).unique().scalar_one_or_none()
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found or access denied.",
            )

        if booking.status in [BookingStatus.COMPLETED.value, BookingStatus.CANCELLED.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel a booking that is already {booking.status}.",
            )

        booking.status = BookingStatus.CANCELLED.value
        booking.cancellation_reason = data.cancellation_reason.strip()
        booking.updated_at = datetime.now(timezone.utc)

        notification = Notification(
            user_id=current_user.id,
            title="Service Request Cancelled",
            message=f"You cancelled request {booking.booking_reference}. Reason: {data.cancellation_reason.strip()}",
            notification_type=NotificationType.BOOKING_CANCELLED.value,
            reference_id=booking.id,
            is_read=False,
        )
        db.add(notification)
        db.add(booking)
        db.commit()
        db.refresh(booking)

        return CustomerBookingService._format_booking_out(booking)

    @staticmethod
    def accept_booking(
        db: Session,
        current_user: User,
        booking_id: int,
        data: Optional[BookingAcceptRequest] = None,
    ) -> BookingOut:
        """
        Customer accepts an updated schedule, quote, or worker proposal for a booking.
        Transitions status to CONFIRMED.
        Creates an in-app notification for the customer.
        """
        stmt = (
            select(Booking)
            .options(
                joinedload(Booking.worker).joinedload(WorkerProfile.user),
                joinedload(Booking.service_category),
                joinedload(Booking.review),
            )
            .where(
                Booking.id == booking_id,
                Booking.customer_id == current_user.id,
            )
        )
        booking = db.execute(stmt).unique().scalar_one_or_none()
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found or access denied.",
            )

        if booking.status in [BookingStatus.CANCELLED.value, BookingStatus.REJECTED.value, BookingStatus.COMPLETED.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot accept a booking that is currently {booking.status}.",
            )

        booking.status = BookingStatus.CONFIRMED.value
        booking.updated_at = datetime.now(timezone.utc)
        db.add(booking)

        notification = Notification(
            user_id=current_user.id,
            title="Service Request Confirmed",
            message=f"You have confirmed service request {booking.booking_reference}. Worker will arrive as scheduled.",
            notification_type=NotificationType.REQUEST_ACCEPTED.value,
            reference_id=booking.id,
            is_read=False,
        )
        db.add(notification)
        db.commit()
        db.refresh(booking)

        return CustomerBookingService._format_booking_out(booking)

    @staticmethod
    def reject_booking(
        db: Session,
        current_user: User,
        booking_id: int,
        data: BookingRejectRequest,
    ) -> BookingOut:
        """
        Customer rejects a service request, quotation, or proposal.
        Transitions status to REJECTED.
        Creates an in-app notification for the customer.
        """
        stmt = (
            select(Booking)
            .options(
                joinedload(Booking.worker).joinedload(WorkerProfile.user),
                joinedload(Booking.service_category),
                joinedload(Booking.review),
            )
            .where(
                Booking.id == booking_id,
                Booking.customer_id == current_user.id,
            )
        )
        booking = db.execute(stmt).unique().scalar_one_or_none()
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found or access denied.",
            )

        if booking.status in [BookingStatus.CANCELLED.value, BookingStatus.REJECTED.value, BookingStatus.COMPLETED.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reject a booking that is currently {booking.status}.",
            )

        booking.status = BookingStatus.REJECTED.value
        booking.cancellation_reason = data.rejection_reason.strip()
        booking.updated_at = datetime.now(timezone.utc)
        db.add(booking)

        notification = Notification(
            user_id=current_user.id,
            title="Service Request Rejected",
            message=f"Service request {booking.booking_reference} was rejected. Reason: {data.rejection_reason.strip()}",
            notification_type=NotificationType.REQUEST_REJECTED.value,
            reference_id=booking.id,
            is_read=False,
        )
        db.add(notification)
        db.commit()
        db.refresh(booking)

        return CustomerBookingService._format_booking_out(booking)

    @staticmethod
    def submit_review(
        db: Session,
        current_user: User,
        booking_id: int,
        data: ReviewCreateRequest,
    ) -> ReviewOut:
        """
        Submits a customer rating and review for a completed service booking.
        - Enforces customer ownership
        - Verifies booking status is COMPLETED
        - Prevents multiple reviews for the same booking
        - Recalculates the worker's average rating and total review count
        """
        stmt = select(Booking).where(
            Booking.id == booking_id,
            Booking.customer_id == current_user.id,
        )
        booking = db.execute(stmt).scalar_one_or_none()
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found or access denied.",
            )

        if booking.status != BookingStatus.COMPLETED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reviews can only be submitted for completed bookings.",
            )

        # Check for existing review
        existing_review = db.execute(
            select(Review).where(Review.booking_id == booking.id)
        ).scalar_one_or_none()
        if existing_review:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A review has already been submitted for this booking.",
            )

        # Insert new review
        new_review = Review(
            booking_id=booking.id,
            customer_id=current_user.id,
            worker_id=booking.worker_id,
            rating=data.rating,
            comment=data.comment.strip() if data.comment else None,
        )
        db.add(new_review)
        db.flush()

        # Recalculate worker's aggregate rating
        worker = db.execute(
            select(WorkerProfile).where(WorkerProfile.id == booking.worker_id)
        ).scalar_one()

        avg_rating_stmt = select(func.avg(Review.rating), func.count(Review.id)).where(
            Review.worker_id == worker.id
        )
        avg_rating, total_reviews = db.execute(avg_rating_stmt).one()

        worker.rating = round(float(avg_rating or data.rating), 1)
        worker.review_count = int(total_reviews or 1)
        db.add(worker)

        db.commit()
        db.refresh(new_review)

        return ReviewOut.model_validate(new_review)


class CustomerNotificationService:
    """Manages in-app customer notifications and status alerts."""

    @staticmethod
    def list_notifications(
        db: Session,
        current_user: User,
        unread_only: bool = False,
        skip: int = 0,
        limit: int = 20,
    ) -> NotificationListResponse:
        """
        Lists notifications for the authenticated customer.
        Supports filtering by unread status.
        Returns notification items, total count, and unread count.
        """
        query = select(Notification).where(Notification.user_id == current_user.id)
        if unread_only:
            query = query.where(Notification.is_read == False)

        total_stmt = select(func.count(Notification.id)).where(Notification.user_id == current_user.id)
        total_count = db.execute(total_stmt).scalar() or 0

        unread_stmt = select(func.count(Notification.id)).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
        unread_count = db.execute(unread_stmt).scalar() or 0

        query = query.order_by(Notification.created_at.desc()).offset(skip).limit(limit)
        items = db.execute(query).scalars().all()

        return NotificationListResponse(
            notifications=[NotificationOut.model_validate(n) for n in items],
            unread_count=unread_count,
            total=total_count,
        )

    @staticmethod
    def get_unread_count(db: Session, current_user: User) -> int:
        """Returns the number of unread notifications for badge display."""
        stmt = select(func.count(Notification.id)).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
        return db.execute(stmt).scalar() or 0

    @staticmethod
    def mark_as_read(db: Session, current_user: User, notification_id: int) -> NotificationOut:
        """
        Marks a specific notification as read.
        Verifies customer ownership to prevent IDOR vulnerabilities.
        """
        stmt = select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
        notification = db.execute(stmt).scalar_one_or_none()
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found.",
            )

        notification.is_read = True
        db.add(notification)
        db.commit()
        db.refresh(notification)
        return NotificationOut.model_validate(notification)

    @staticmethod
    def mark_all_as_read(db: Session, current_user: User) -> int:
        """Marks all notifications for the current customer as read."""
        stmt = select(Notification).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
        unread_notifications = db.execute(stmt).scalars().all()
        count = len(unread_notifications)
        for n in unread_notifications:
            n.is_read = True
            db.add(n)
        db.commit()
        return count

    @staticmethod
    def create_notification(
        db: Session,
        user_id: int,
        title: str,
        message: str,
        notification_type: str = NotificationType.GENERAL.value,
        reference_id: Optional[int] = None,
    ) -> NotificationOut:
        """
        Utility to create a notification for a user.
        Used by service hooks or simulation endpoints.
        """
        notification = Notification(
            user_id=user_id,
            title=title.strip(),
            message=message.strip(),
            notification_type=notification_type,
            reference_id=reference_id,
            is_read=False,
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        return NotificationOut.model_validate(notification)

