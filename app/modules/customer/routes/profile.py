"""
Customer Profile & Address Management Routes.
Protected endpoints allowing authenticated customers to:
- Retrieve their own profile
- Update profile details (name, phone, avatar)
- Manage saved service delivery addresses
"""

from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_db
from app.modules.customer.schemas import (
    CustomerAddressCreate,
    CustomerAddressOut,
    CustomerProfileOut,
    CustomerProfileUpdate,
)
from app.modules.customer.security import get_current_customer
from app.modules.customer.service import CustomerProfileService

router = APIRouter(tags=["Customer Profile & Addresses"])


@router.get(
    "/profile",
    response_model=CustomerProfileOut,
    summary="Get current customer profile",
    description="Returns the profile details of the authenticated customer requesting this endpoint.",
)
def get_customer_profile(
    current_customer: User = Depends(get_current_customer),
) -> CustomerProfileOut:
    """
    Retrieves the authenticated customer's profile.
    Requires a valid Bearer token.
    """
    return CustomerProfileService.get_profile(current_customer)


@router.put(
    "/profile",
    response_model=CustomerProfileOut,
    summary="Update customer profile",
    description="Updates editable profile fields (full name, phone number, avatar URL) for the customer.",
)
def update_customer_profile(
    payload: CustomerProfileUpdate,
    current_customer: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> CustomerProfileOut:
    """
    Updates the authenticated customer's personal details.
    Ensures input sanitization and updates the database record.
    """
    return CustomerProfileService.update_profile(db, current_customer, payload)


@router.get(
    "/addresses",
    response_model=List[CustomerAddressOut],
    summary="List saved customer addresses",
    description="Returns all saved service addresses for the authenticated customer.",
)
def list_customer_addresses(
    current_customer: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> List[CustomerAddressOut]:
    """
    Lists saved addresses for the customer.
    Results are sorted with default address first, followed by most recently created.
    """
    return CustomerProfileService.list_addresses(db, current_customer)


@router.post(
    "/addresses",
    response_model=CustomerAddressOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new service address",
    description="Adds a new delivery/service address with street, city, state, postal code, and optional GPS coordinates.",
)
def add_customer_address(
    payload: CustomerAddressCreate,
    current_customer: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> CustomerAddressOut:
    """
    Saves a new service location address for the customer.
    If 'is_default' is true, automatically unsets any previously designated default address.
    """
    return CustomerProfileService.create_address(db, current_customer, payload)


@router.delete(
    "/addresses/{address_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a saved address",
    description="Removes a saved service address by ID. Verifies customer ownership before deletion.",
)
def delete_customer_address(
    address_id: int,
    current_customer: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    """
    Deletes a saved address.
    Enforces authorization check: returns 404 if the address does not belong to the current customer.
    """
    CustomerProfileService.delete_address(db, current_customer, address_id)
    return None

