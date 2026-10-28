"""Login request and the User object (API_CONTRACT A.2 / A.4)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.models.enums import UserRole
from app.models.user import User


class LoginRequest(BaseModel):
    # Demo logins such as `student@demo` have no TLD, so this is deliberately not EmailStr.
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def _looks_like_email(cls, value: str) -> str:
        value = value.strip()
        local, sep, domain = value.partition("@")
        if not sep or not local or not domain or " " in value:
            raise ValueError("must be an email address")
        return value


class UserScope(BaseModel):
    institution_id: str | None = None
    institution_name: str | None = None
    region: str | None = None
    student_id: str | None = None
    university_id: str | None = None
    university_name: str | None = None

    def wire(self) -> dict[str, str | None]:
        data = self.model_dump()
        if data["university_name"] is None and data["university_id"] is None:
            data.pop("university_name")
        return data


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str
    scope: dict[str, str | None]

    @classmethod
    def from_user(cls, user: User) -> UserOut:
        scope = UserScope()
        if user.role is UserRole.INSTITUTION and user.institution is not None:
            scope.institution_id = str(user.institution.id)
            scope.institution_name = user.institution.name
            scope.region = user.institution.region.code if user.institution.region else None
        elif user.role is UserRole.RO_OFFICER and user.region is not None:
            scope.region = user.region.code
        elif user.role is UserRole.STUDENT and user.student_id is not None:
            scope.student_id = str(user.student_id)
        elif user.role is UserRole.UNIVERSITY and user.university is not None:
            scope.university_id = str(user.university.id)
            scope.university_name = user.university.name
        return cls(
            id=str(user.id),
            email=user.email,
            name=user.name,
            role=user.role.value,
            scope=scope.wire(),
        )


class UserEnvelope(BaseModel):
    user: UserOut
