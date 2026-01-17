"""
Pydantic schemas for authentication endpoints.
"""
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional
import uuid


class LoginRequest(BaseModel):
    """Request schema for login endpoint."""
    email: EmailStr
    password: str = Field(..., min_length=8)


class TokenResponse(BaseModel):
    """Response schema for successful authentication."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserResponse(BaseModel):
    """Response schema for user information."""
    id: uuid.UUID
    email: str
    role: str
    unit_id: Optional[uuid.UUID] = None
    created_at: datetime
    last_login_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
