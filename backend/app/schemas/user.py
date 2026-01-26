from typing import Optional
from pydantic import BaseModel, EmailStr
from uuid import UUID

class UserBase(BaseModel):
    email: EmailStr
    is_active: Optional[bool] = True
    is_superuser: Optional[bool] = False
    full_name: Optional[str] = None
    role: str = "member"
    timezone: Optional[str] = "UTC"

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    timezone: Optional[str] = None

class UserInDBBase(UserBase):
    id: Optional[UUID] = None

    class Config:
        from_attributes = True

class User(UserInDBBase):
    pass

class UserInDB(UserInDBBase):
    hashed_password: str
