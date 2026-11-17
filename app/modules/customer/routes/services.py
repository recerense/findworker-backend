"""
Customer Services & Nearby Workers Discovery Routes.
Provides endpoints for:
- Browsing trade and service categories (Plumber, Electrician, Carpenter, etc.)
- Searching for nearby workers based on GPS coordinates and radius
- Viewing detailed worker profiles with experience, rates, and reviews
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.customer.schemas import (
    ServiceCategoryOut,
    WorkerDetailOut,
    WorkerPublicOut,
)
from app.modules.customer.service import NearbyServicesService

router = APIRouter(tags=["Customer Services & Workers Search"])


@router.get(
    "/services/categories",
    response_model=List[ServiceCategoryOut],
    summary="List available service categories",
    description="Returns all active trade service categories (e.g. Plumbing, Electrical, Cleaning, Appliance Repair) with base pricing and descriptions.",
)
def list_service_categories(
    db: Session = Depends(get_db),
) -> List[ServiceCategoryOut]:
    """
    Public catalog endpoint to fetch all active service categories.
    Used by the customer frontend to populate service selection tiles and filters.
    """
    return NearbyServicesService.list_categories(db)


@router.get(
    "/services/nearby",
    response_model=List[WorkerPublicOut],
    summary="Search nearby service workers",
    description="Finds verified, available service professionals near a specific GPS latitude/longitude within a given radius using Haversine calculation.",
)
def search_nearby_workers(
    latitude: float = Query(..., ge=-90.0, le=90.0, description="Customer's current latitude coordinate"),
    longitude: float = Query(..., ge=-180.0, le=180.0, description="Customer's current longitude coordinate"),
    category_id: Optional[int] = Query(None, description="Filter by service category ID (e.g., 1 for Plumbing)"),
    radius_km: float = Query(25.0, ge=1.0, le=100.0, description="Search radius in kilometers (default: 25 km)"),
    keyword: Optional[str] = Query(None, min_length=2, max_length=50, description="Search keyword matching worker name, trade, or bio"),
    min_rating: Optional[float] = Query(None, ge=1.0, le=5.0, description="Filter workers with minimum average rating (e.g. 4.0)"),
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination"),
    limit: int = Query(20, ge=1, le=50, description="Maximum number of workers to return"),
    db: Session = Depends(get_db),
) -> List[WorkerPublicOut]:
    """
    Discovers nearby service professionals in real-time.
    - Calculates distance using Haversine spherical trigonometry formula
    - Filters workers by active availability and distance <= radius_km
    - Orders results with the nearest worker first
    - Returns calculated distance_km for each provider
    """
    return NearbyServicesService.search_nearby_workers(
        db=db,
        latitude=latitude,
        longitude=longitude,
        category_id=category_id,
        radius_km=radius_km,
        keyword=keyword,
        min_rating=min_rating,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/workers/{worker_id}",
    response_model=WorkerDetailOut,
    summary="Get worker profile details",
    description="Retrieves a worker's comprehensive profile including trade experience, hourly rate, coverage radius, bio, and past customer reviews.",
)
def get_worker_profile(
    worker_id: int,
    db: Session = Depends(get_db),
) -> WorkerDetailOut:
    """
    Fetches public profile and feedback history for a specific worker.
    Returns 404 if the worker does not exist.
    """
    return NearbyServicesService.get_worker_detail(db, worker_id)

