"""User/auth API models. Never includes `password_hash` or any raw
credential — `UserPublic` is the only user shape ever returned by the API.
"""

from pydantic import BaseModel, Field


class SignupRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, description="At least 8 characters.")


class LoginRequest(BaseModel):
    email: str
    password: str


class UserPublic(BaseModel):
    id: str
    email: str
    created_at: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic
