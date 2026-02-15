from pydantic import BaseModel, Field, EmailStr


class ReviewAccount(BaseModel):
    hotel_name: str = Field(..., description="Hotel name")
    user_email: EmailStr = Field(..., description="User email address")
    country: str = Field(..., description="Country")
    city: str = Field(..., description="City")
