"""Pydantic models: request validation and response shapes."""
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[0-9][0-9\s\-()]{6,19}$")


class StudentCreate(BaseModel):
    """Full student payload. Used for POST and PUT, and to re-validate PATCH results."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "name": "Aarav Sharma",
                "date_of_birth": "2004-03-15",
                "email": "aarav.sharma@example.com",
                "phone": "+91 90000 00001",
                "course": "Python Backend Development",
                "address": "12 Sample Street, Kolkata",
                "enrollment_date": "2024-07-01",
            }
        },
    )

    name: str = Field(min_length=1, max_length=100)
    date_of_birth: date
    email: Optional[str] = Field(default=None, max_length=254)
    phone: Optional[str] = Field(default=None, max_length=30)
    course: Optional[str] = Field(default=None, max_length=100)
    address: Optional[str] = Field(default=None, max_length=300)
    enrollment_date: Optional[date] = None

    @field_validator("email", "phone", "course", "address", mode="before")
    @classmethod
    def blank_to_none(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("email")
    @classmethod
    def check_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not EMAIL_RE.match(v):
            raise ValueError("must be a valid email address")
        return v.lower()

    @field_validator("phone")
    @classmethod
    def check_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not PHONE_RE.match(v):
            raise ValueError("must be a valid phone number (7-20 digits, may start with +)")
        return v

    @field_validator("date_of_birth")
    @classmethod
    def check_dob(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("date_of_birth cannot be in the future")
        if v.year < 1900:
            raise ValueError("date_of_birth must be 1900 or later")
        return v

    @model_validator(mode="after")
    def check_cross_fields(self) -> "StudentCreate":
        if self.email is None and self.phone is None:
            raise ValueError("at least one of 'email' or 'phone' is required")
        if self.enrollment_date and self.enrollment_date < self.date_of_birth:
            raise ValueError("enrollment_date cannot be before date_of_birth")
        return self


class StudentUpdate(BaseModel):
    """PATCH payload: every field optional. The merged result is re-validated
    against StudentCreate in the route, so all the rules above still apply."""

    name: Optional[str] = None
    date_of_birth: Optional[date] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    course: Optional[str] = None
    address: Optional[str] = None
    enrollment_date: Optional[date] = None


class StudentOut(BaseModel):
    id: int
    name: str
    date_of_birth: date
    email: Optional[str] = None
    phone: Optional[str] = None
    course: Optional[str] = None
    address: Optional[str] = None
    enrollment_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)

    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={"example": {"question": "List students born after 2005"}},
    )


class AskResponse(BaseModel):
    question: str
    answer: str
    model: str
    filters_applied: Dict[str, Any]
    total_students_in_database: int
    total_matching: int
    records_used: List[Dict[str, Any]]
