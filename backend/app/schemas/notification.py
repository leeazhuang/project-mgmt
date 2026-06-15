from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: int
    title: str
    content: str
    type: str
    related_id: int
    related_type: str
    is_read: int
    created_at: str

    class Config:
        from_attributes = True
