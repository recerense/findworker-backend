
import uuid
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from app.modules.auth.otp_models import OTPPurpose

class RegistrationType(str, Enum):
    CUSTOMER = "CUSTOMER"
    WORKER = "WORKER"


class ClientTypeSchema(str, Enum):
    MOBILE = "MOBILE"
    WEB = "WEB"
    CAPACITOR = "CAPACITOR"
    API = "API"



class RegisterRequest(BaseModel):
    account_type: RegistrationType

    email: EmailStr | None = None
    phone: str | None = Field(default=None, min_length=8, max_length=20)
    password: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip()

        if not normalized.startswith("+"):
            raise ValueError("Phone number must include country code")

        digits = normalized[1:]

        if not digits.isdigit() or not 8 <= len(digits) <= 15:
            raise ValueError("Invalid international phone number")

        return normalized

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr | None) -> EmailStr | None:
        if value is None:
            return None

        return value.lower()

    @model_validator(mode="after")
    def validate_registration_method(self):
        if not self.email and not self.phone:
            raise ValueError("Email or phone number is required")

        if self.email and not self.password:
            raise ValueError(
                "Password is required when registering with email"
            )

        if self.password and not self.email:
            raise ValueError(
                "Email is required when registering with password"
            )

        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    client_type: ClientTypeSchema = ClientTypeSchema.MOBILE



class OTPRequest(BaseModel):
    destination: str = Field(min_length=8, max_length=255)
    purpose: OTPPurpose
    client_type: ClientTypeSchema = ClientTypeSchema.MOBILE

    @field_validator("destination")
    @classmethod
    def normalize_destination(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_destination(self):
        if self.purpose in {
            OTPPurpose.VERIFY_EMAIL,
            OTPPurpose.PASSWORD_RESET,
        }:
            from pydantic import TypeAdapter

            email = TypeAdapter(EmailStr).validate_python(
                self.destination
            )
            self.destination = str(email).lower()
        else:
            normalized = self.destination

            if not normalized.startswith("+"):
                raise ValueError(
                    "Phone number must include country code"
                )

            digits = normalized[1:]

            if not digits.isdigit() or not 8 <= len(digits) <= 15:
                raise ValueError("Invalid international phone number")

            self.destination = normalized

        return self


class OTPVerifyRequest(BaseModel):
    challenge_id: uuid.UUID
    otp: str = Field(pattern=r"^\d{6}$")
    client_type: ClientTypeSchema = ClientTypeSchema.MOBILE


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RegistrationResponse(BaseModel):
    account_id: uuid.UUID
    account_type: RegistrationType
    message: str


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_type: RegistrationType
    email: EmailStr | None
    phone: str | None
    is_email_verified: bool
    is_phone_verified: bool
    is_active: bool
