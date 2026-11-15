
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
import uuid
from datetime import datetime, timezone
import jwt

from app.modules.auth.dependencies import get_current_auth
from app.modules.auth.schemas import AccountResponse,LoginRequest, RegisterRequest, RegistrationResponse, TokenResponse, RefreshRequest, OTPVerifyRequest, OTPRequest
from app.modules.auth.services.login_service import ContactNotVerifiedError, InvalidCredentialsError, login_with_email
from app.modules.auth.services.registration_service import RegistrationConflictError, register_account

from app.modules.auth.models import Account
from app.modules.auth.services.session_service import rotate_refresh_token, revoke_all_sessions, create_session
from app.modules.auth.services.token_service import create_access_token, decode_refresh_token, create_refresh_token
from app.modules.auth.services.otp_request_service import OTPRequestError, request_otp
from app.modules.auth.otp_models import OTPPurpose
from app.modules.auth.session_models import ClientType
from app.modules.auth.services.otp_verification_service import verify_otp

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

@router.post(
    "/register",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    registration: RegisterRequest,
    db: Session = Depends(get_db),
):
    """Register a new Customer or Worker account."""

    try:
        account = register_account(db, registration)
        db.commit()
        db.refresh(account)

    except RegistrationConflictError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email address or phone number is already registered",
        ) from exc

    return RegistrationResponse(
        account_id=account.id,
        account_type=account.account_type.value,
        message="Registration successful. Please verify your contact details.",
    )



@router.post("/otp/request", status_code=status.HTTP_202_ACCEPTED)
def request_otp_endpoint(payload: OTPRequest, db: Session = Depends(get_db)):
    try:
        request_otp(db=db, request=payload)
    except OTPRequestError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to process OTP request",
        ) from None

    return {
        "message": "If the request is eligible, an OTP will be sent."
    }



@router.post("/otp/verify", status_code=status.HTTP_200_OK)
def verify_otp_endpoint(payload: OTPVerifyRequest, request: Request, db: Session = Depends(get_db)):
    try:
        result = verify_otp(
            db=db,
            challenge_id=payload.challenge_id,
            otp=payload.otp,
        )

        if result is None:
            # Persist failed attempts so they cannot be bypassed.
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid, expired, or already-used OTP",
            )

        account, purpose = result

        if purpose == OTPPurpose.LOGIN:
            refresh_token, jti, token_hash, expires_at = (
                create_refresh_token(
                    account.id,
                    account.account_type.value,
                )
            )

            auth_session = create_session(
                db=db,
                account_id=account.id,
                refresh_token_jti=jti,
                refresh_token_hash=token_hash,
                expires_at=expires_at,
                client_type=ClientType(payload.client_type.value),
                ip_address=(
                    request.client.host
                    if request.client is not None
                    else None
                ),
                user_agent=request.headers.get("user-agent"),
            )

            access_token = create_access_token(
                account_id=account.id,
                account_type=account.account_type.value,
                session_id=auth_session.id,
            )

            db.commit()

            return TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            )

        db.commit()

        return {
            "message": "Contact verified successfully",
            "purpose": purpose.value,
        }

    except HTTPException:
        raise

    except Exception:
        db.rollback()
        raise


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
)
def login(
    login_data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Authenticate an account using email and password."""

    client_ip = (
        request.client.host
        if request.client is not None
        else None
    )

    user_agent = request.headers.get("user-agent")

    try:
        account, access_token, refresh_token = login_with_email(
            db=db,
            login=login_data,
            ip_address=client_ip,
            user_agent=user_agent,
        )

        db.commit()

    except InvalidCredentialsError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    except ContactNotVerifiedError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email address or phone number before logging in",
        ) from exc

    except Exception:
        db.rollback()
        raise

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

@router.get("/me", response_model=AccountResponse, status_code=status.HTTP_200_OK)
def get_my_account(auth_data=Depends(get_current_auth)):
    """Return the currently authenticated account."""

    account, _auth_session = auth_data

    return account


@router.post("/refresh", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def refresh_tokens(refresh_data: RefreshRequest, db: Session = Depends(get_db)):
    """Rotate refresh token and issue a new access token."""

    try:
        payload = decode_refresh_token(refresh_data.refresh_token)

        account_id = uuid.UUID(payload["sub"])

        result = rotate_refresh_token(
            db=db,
            refresh_token=refresh_data.refresh_token,
            refresh_token_jti=payload["jti"],
        )

        if result is None:
            # Commit rather than roll back: an inactive account's
            # session may have been revoked inside rotate_refresh_token.
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

        auth_session, new_refresh_token = result

        account = db.get(Account, auth_session.account_id)

        if (
            account is None
            or account.id != account_id
            or account.account_type.value != payload.get("account_type")
        ):
            auth_session.revoked_at = datetime.now(timezone.utc)
            db.commit()

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

        new_access_token = create_access_token(
            account_id=account.id,
            account_type=account.account_type.value,
            session_id=auth_session.id,
        )

        db.commit()

    except jwt.PyJWTError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from None

    except HTTPException:
        raise

    except Exception:
        db.rollback()
        raise

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(auth_data=Depends(get_current_auth),db: Session = Depends(get_db)):
    """Revoke the current authenticated session."""

    _account, auth_session = auth_data

    auth_session.revoked_at = datetime.now(timezone.utc)

    db.commit()

    return {
        "message": "Successfully logged out",
    }


@router.post( "/logout-all", status_code=status.HTTP_200_OK)
def logout_all(
    auth_data=Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    """Revoke all active sessions for the authenticated account."""

    account, _auth_session = auth_data

    revoked_count = revoke_all_sessions(
        db=db,
        account_id=account.id,
    )

    db.commit()

    return {
        "message": "Successfully logged out from all devices",
        "revoked_sessions": revoked_count,
    }
