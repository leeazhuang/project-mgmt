from pydantic import BaseModel


class AttachmentOut(BaseModel):
    id: int
    target_id: int
    target_type: str
    file_name: str
    file_path: str
    file_size: int
    file_type: str
    uploader: dict
    created_at: str

    class Config:
        from_attributes = True
