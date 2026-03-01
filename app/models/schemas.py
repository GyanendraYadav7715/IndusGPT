from pydantic import BaseModel
from typing import Optional

class UserSignup(BaseModel):
    username: str
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class ChatRequest(BaseModel):
    message: str
    conversationId: Optional[str] = None
