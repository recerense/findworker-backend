"""
Master router for FindWorker Customer Service.
Combines sub-routers for:
- /api/customer/auth          -> Registration and login
- /api/customer/profile       -> Customer profile management
- /api/customer/addresses     -> Saved service locations
- /api/customer/services      -> Nearby workers & category discovery
- /api/customer/bookings      -> Booking lifecycle & reviews
- /api/customer/requests      -> Service requests, accept, reject & cancel
- /api/customer/notifications -> In-app notifications & request status alerts
"""

from fastapi import APIRouter

from app.modules.customer.routes.auth import router as auth_router
from app.modules.customer.routes.bookings import router as bookings_router
from app.modules.customer.routes.notifications import router as notifications_router
from app.modules.customer.routes.profile import router as profile_router
from app.modules.customer.routes.requests import router as requests_router
from app.modules.customer.routes.services import router as services_router

customer_router = APIRouter(prefix="/api/customer")

# Register all modular customer route domains
customer_router.include_router(auth_router)
customer_router.include_router(profile_router)
customer_router.include_router(services_router)
customer_router.include_router(bookings_router)
customer_router.include_router(requests_router)
customer_router.include_router(notifications_router)
