"""
Main FastAPI application entry point for FindWorker platform.
Integrates:
- Database schema initialization
- Customer service APIs (/api/customer)
- Security middleware (Strict CORS, Security Headers, Clickjacking prevention)
- System health checks
"""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.models import Base
from app.db.seed import seed_database
from app.db.session import SessionLocal, engine
from app.modules.customer import customer_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan lifecycle manager.
    Initializes database tables on startup and seeds baseline catalog data.
    """
    logger.info("Initializing database schema...")
    Base.metadata.create_all(bind=engine)

    # Seed baseline service categories and initial test workers
    db = SessionLocal()
    try:
        seed_database(db)
    except Exception as exc:
        logger.error(f"Error during initial database seeding: {exc}")
    finally:
        db.close()

    yield
    logger.info("Shutting down FindWorker API...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="On-demand platform connecting customers with skilled local service professionals (Plumbers, Electricians, Carpenters, etc.)",
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# -----------------------------------------------------------------------------
# Security Middleware: Strict CORS Policy
# -----------------------------------------------------------------------------
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)


# -----------------------------------------------------------------------------
# Security Headers Middleware (X-Content-Type-Options, X-Frame-Options, CSP)
# -----------------------------------------------------------------------------
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """
    Enforces security response headers across all API endpoints:
    - nosniff to prevent MIME-sniffing
    - DENY to prevent clickjacking attacks
    - Restrictive permissions policy
    """
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(self), microphone=(), camera=()"
    return response


# -----------------------------------------------------------------------------
# Register Service Routers
# -----------------------------------------------------------------------------
app.include_router(customer_router)


# -----------------------------------------------------------------------------
# Base Endpoints
# -----------------------------------------------------------------------------
@app.get("/health", tags=["Health"])
def health_check():
    """System health check endpoint for ALB target group probes."""
    return {
        "status": "healthy",
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/", tags=["Root"])
def root():
    """API Gateway root discovery endpoint."""
    return {
        "message": "Welcome to FindWorker API Platform",
        "documentation": "/docs",
        "services": {
            "customer": "/api/customer",
            "health": "/health",
        },
    }
