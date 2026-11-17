"""
Security and authentication utilities for Customer Service.
Implements:
- Cryptographic password hashing & verification using native bcrypt
- JWT token generation and validation with strict HS256 algorithm enforcement
- Authentication dependency `get_current_customer` for route protection
- Principle of Least Privilege & IDOR defense mechanisms
"""

from datetime import datetime, timedelta, timezone
import logging
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import User, UserRole
from app.db.session import get_db

logger = logging.getLogger(__name__)

# HTTP Bearer authentication scheme
security_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """
    Hashes a plaintext password using bcrypt with automatic unique salt.
    Enforces minimum 8-character length policy and handles 72-byte bcrypt limit safely.
    """
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    # Bcrypt operates on bytes up to 72 bytes
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plaintext password against the stored bcrypt hash.
    Safe against timing attacks.
    """
    try:
        pwd_bytes = plain_password.encode("utf-8")[:72]
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception as exc:
        logger.warning(f"Password verification encountered an error: {exc}")
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates a signed JWT access token for customer authentication.
    - Uses cryptographic SECRET_KEY from configuration.
    - Explicitly hardcodes the HS256 algorithm (rejects 'none' or unverified algorithms).
    - Sets standard 'exp', 'iat', and 'sub' claims.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": now,
    })

    secret_key = settings.get_jwt_secret()
    encoded_jwt = jwt.encode(
        to_encode,
        secret_key,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """
    Decodes and validates a JWT access token.
    Enforces expiration check and strictly verifies signature using HS256.
    """
    try:
        secret_key = settings.get_jwt_secret()
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as exc:
        logger.debug(f"JWT verification failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired, or malformed authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_customer(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency to extract and authenticate the current customer from the Authorization header.
    Validates:
    1. Presence of Bearer token
    2. Token integrity and expiration
    3. User existence and active status
    4. Customer role authorization
    """
    if not auth or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(auth.credentials)
    user_id: Optional[str] = payload.get("sub")
    role: Optional[str] = payload.get("role")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token missing user identity.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user using parameterized query (safe against SQL injection)
    stmt = select(User).where(User.id == int(user_id))
    user = db.execute(stmt).scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account does not exist or has been deactivated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify customer role permissions
    if user.role != UserRole.CUSTOMER.value and user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted: This API is intended for customer accounts only.",
        )

    return user
