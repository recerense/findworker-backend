"""
Initial database seeder for FindWorker.
Seeds:
- Standard trade categories (Plumbing, Electrical, Carpentry, AC Service, Home Cleaning, Appliance Repair, Painting)
- Sample verified workers with coordinates for testing nearby search out-of-the-box
"""

import logging
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ServiceCategory, User, UserRole, WorkerProfile
from app.modules.customer.security import hash_password

logger = logging.getLogger(__name__)

INITIAL_CATEGORIES = [
    {
        "name": "Plumbing",
        "slug": "plumbing",
        "description": "Pipe repair, drain cleaning, tap fixing, bathroom fittings, and water heater installation.",
        "icon": "wrench",
        "base_price": 40.0,
    },
    {
        "name": "Electrical",
        "slug": "electrical",
        "description": "Wiring repair, short circuit fixes, switchboard installation, ceiling fans, and lighting.",
        "icon": "zap",
        "base_price": 45.0,
    },
    {
        "name": "Carpentry",
        "slug": "carpentry",
        "description": "Furniture repair, custom woodwork, door locks, hinges, and kitchen cabinets.",
        "icon": "hammer",
        "base_price": 50.0,
    },
    {
        "name": "AC & Appliance Repair",
        "slug": "ac-appliance-repair",
        "description": "Air conditioner servicing, gas refilling, refrigerator, washing machine, and microwave repairs.",
        "icon": "wind",
        "base_price": 55.0,
    },
    {
        "name": "Home Cleaning",
        "slug": "home-cleaning",
        "description": "Deep home cleaning, kitchen & bathroom sanitization, sofa cleaning, and carpet shampooing.",
        "icon": "sparkles",
        "base_price": 35.0,
    },
    {
        "name": "Painting & Waterproofing",
        "slug": "painting",
        "description": "Interior and exterior wall painting, waterproof coating, wall putty, and touch-ups.",
        "icon": "paint-brush",
        "base_price": 60.0,
    },
]

# Sample workers near a central location (e.g., Central Bangalore coordinates ~ 12.9716, 77.5946)
SAMPLE_WORKERS = [
    {
        "name": "Ramesh Kumar",
        "email": "ramesh.plumber@findworker.test",
        "phone": "+919876543210",
        "category_slug": "plumbing",
        "business_name": "Ramesh Quick Plumbing Solutions",
        "bio": "Certified master plumber with over 8 years experience in residential pipe repair, leak detection, and sanitary installations.",
        "hourly_rate": 45.0,
        "years_of_experience": 8,
        "rating": 4.9,
        "review_count": 34,
        "latitude": 12.9750,
        "longitude": 77.5990,
    },
    {
        "name": "Suresh Electricals",
        "email": "suresh.electric@findworker.test",
        "phone": "+919876543211",
        "category_slug": "electrical",
        "business_name": "Suresh Pro Electric Works",
        "bio": "Licensed electrician specializing in circuit breaker repairs, switchboard installations, and inverter setups.",
        "hourly_rate": 50.0,
        "years_of_experience": 6,
        "rating": 4.8,
        "review_count": 28,
        "latitude": 12.9690,
        "longitude": 77.5890,
    },
    {
        "name": "Anil Sharma",
        "email": "anil.carpenter@findworker.test",
        "phone": "+919876543212",
        "category_slug": "carpentry",
        "business_name": "Sharma Woodcraft & Furnishing",
        "bio": "Experienced carpenter for custom furniture, door repair, modular kitchens, and laminate fitting.",
        "hourly_rate": 55.0,
        "years_of_experience": 10,
        "rating": 4.7,
        "review_count": 19,
        "latitude": 12.9810,
        "longitude": 77.6050,
    },
    {
        "name": "CoolBreeze AC Care",
        "email": "coolbreeze.ac@findworker.test",
        "phone": "+919876543213",
        "category_slug": "ac-appliance-repair",
        "business_name": "CoolBreeze Air Conditioner Services",
        "bio": "Certified HVAC technicians for split and window AC repair, deep cleaning, gas refill, and installation.",
        "hourly_rate": 60.0,
        "years_of_experience": 5,
        "rating": 4.9,
        "review_count": 42,
        "latitude": 12.9630,
        "longitude": 77.6110,
    },
]


def seed_database(db: Session) -> None:
    """
    Seeds initial service catalog categories and sample worker profiles
    if the database is currently empty.
    """
    # 1. Seed categories
    category_map = {}
    for cat_data in INITIAL_CATEGORIES:
        existing = db.execute(
            select(ServiceCategory).where(ServiceCategory.slug == cat_data["slug"])
        ).scalar_one_or_none()
        if not existing:
            cat = ServiceCategory(**cat_data)
            db.add(cat)
            db.flush()
            category_map[cat.slug] = cat.id
            logger.info(f"Seeded service category: {cat.name}")
        else:
            category_map[existing.slug] = existing.id

    # 2. Seed sample workers
    for worker_data in SAMPLE_WORKERS:
        existing_user = db.execute(
            select(User).where(User.email == worker_data["email"])
        ).scalar_one_or_none()
        if not existing_user:
            user = User(
                email=worker_data["email"],
                phone=worker_data["phone"],
                full_name=worker_data["name"],
                hashed_password=hash_password("WorkerSecurePass123!"),
                role=UserRole.WORKER.value,
                is_active=True,
            )
            db.add(user)
            db.flush()

            cat_id = category_map.get(worker_data["category_slug"])
            if cat_id:
                worker_profile = WorkerProfile(
                    user_id=user.id,
                    service_category_id=cat_id,
                    business_name=worker_data["business_name"],
                    bio=worker_data["bio"],
                    hourly_rate=worker_data["hourly_rate"],
                    years_of_experience=worker_data["years_of_experience"],
                    rating=worker_data["rating"],
                    review_count=worker_data["review_count"],
                    latitude=worker_data["latitude"],
                    longitude=worker_data["longitude"],
                    service_radius_km=30.0,
                    is_available=True,
                    is_verified=True,
                )
                db.add(worker_profile)
                logger.info(f"Seeded worker profile: {user.full_name}")

    db.commit()

