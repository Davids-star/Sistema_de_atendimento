from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: EmailStr
    phone: str | None
    status: str            # pending_email | pending_approval | active | disabled
    is_owner: bool
    email_verified_at: datetime | None
    approved_at: datetime | None
    created_at: datetime
