from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class FormBase(BaseModel):
    name: str
    email: str
    phone_number: str
    message: Optional[str] = None
    company: str
    service: str

class FormCreate(FormBase):
    pass

class FormUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    message: Optional[str] = None
    company: Optional[str] = None
    service: Optional[str] = None

class Form(FormBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True 