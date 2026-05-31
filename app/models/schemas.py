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

class VerifyPaymentPayload(BaseModel):
    razorpay_payment_id: str
    razorpay_order_id: str
    razorpay_signature: str
