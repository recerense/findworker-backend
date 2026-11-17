"""
Customer Authentication Routes.
Provides endpoints for:
- Customer account registration
- Customer login & JWT access token generation
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.customer.schemas import (
    CustomerLoginRequest,
    CustomerRegisterRequest,
    TokenResponse,
)
from app.modules.customer.service import CustomerAuthService

router = APIRouter(prefix="/auth", tags=["Customer Authentication"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new customer account",
    description="Creates a new customer account with full name, email, phone, and password. Returns a signed JWT token.",
)
def register_customer(
    payload: CustomerRegisterRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """
    Handles customer self-registration.
    - Validates email and phone uniqueness
    - Enforces password strength rules (min 8 chars, letter + digit)
    - Hashes password using bcrypt with random salt
    - Creates database record in users table with role='customer'
    - Returns authentication token for immediate session activation
    """
    return CustomerAuthService.register_customer(db, payload)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Customer login",
    description="Authenticates customer credentials (email + password) and issues a Bearer JWT access token.",
)
def login_customer(
    payload: CustomerLoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """
    Handles customer credential authentication.
    - Verifies email and password using constant-time hash comparison
    - Validates user active status
    - Issues a HS256-signed JWT access token containing subject ID and customer role
    """
    return CustomerAuthService.authenticate_customer(db, payload)

