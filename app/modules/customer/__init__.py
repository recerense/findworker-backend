"""
Customer Module for FindWorker.
Provides FastAPI router and services for customer registration, authentication,
profile management, nearby service discovery, and booking lifecycle.
"""

from app.modules.customer.router import customer_router

__all__ = ["customer_router"]

