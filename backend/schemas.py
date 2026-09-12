from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Any
from uuid import UUID
from datetime import datetime

class MessageBase(BaseModel):
    role: str
    content: str
    metadata: Optional[dict[str, Any]] = {}

class MessageCreate(MessageBase):
    pass

class MessageResponse(MessageBase):
    id: UUID
    session_id: UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class SessionBase(BaseModel):
    title: str

class SessionCreate(SessionBase):
    pass

class SessionResponse(SessionBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse] = []

    model_config = ConfigDict(from_attributes=True)

class ChatRequest(BaseModel):
    message: str
    llm_provider: str = "ollama" # or "anthropic"
