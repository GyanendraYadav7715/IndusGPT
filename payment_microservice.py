import os
import hmac
import hashlib
import uuid
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Razorpay Payment Microservice")

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "rzp_test_mockkeyid123")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "mockkeysecret456")

class OrderRequest(BaseModel):
    amount: int  # in paise (e.g. 29900 for Rs.299)
    currency: str = "INR"

class VerificationRequest(BaseModel):
    razorpay_payment_id: str
    razorpay_order_id: str
    razorpay_signature: str

def is_mock_mode() -> bool:
    return (
        not RAZORPAY_KEY_ID 
        or not RAZORPAY_KEY_SECRET 
        or RAZORPAY_KEY_ID.startswith("rzp_test_mock") 
        or RAZORPAY_KEY_SECRET.startswith("mock")
    )

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "mock_mode": is_mock_mode(),
        "key_id_set": bool(RAZORPAY_KEY_ID and not RAZORPAY_KEY_ID.startswith("rzp_test_mock"))
    }

@app.post("/payment/order")
def create_order(request: OrderRequest):
    # Check if mock mode is active
    if is_mock_mode():
        order_id = f"order_mock_{uuid.uuid4().hex[:12]}"
        print(f"[Mock Mode] Created order {order_id} for amount {request.amount}")
        return {
            "id": order_id,
            "amount": request.amount,
            "currency": request.currency,
            "key_id": "rzp_test_mockkeyid123",
            "is_simulated": True
        }

    # Real Razorpay Order Creation via direct HTTP REST call
    try:
        url = "https://api.razorpay.com/v1/orders"
        payload = {
            "amount": request.amount,
            "currency": request.currency,
            "receipt": f"receipt_{uuid.uuid4().hex[:8]}"
        }
        response = requests.post(
            url,
            json=payload,
            auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET),
            headers={"Content-Type": "application/json"}
        )
        if response.status_code != 200:
            print(f"Razorpay API Error: {response.text}")
            raise HTTPException(status_code=500, detail="Failed to create Razorpay order")
        
        order_data = response.json()
        return {
            "id": order_data["id"],
            "amount": order_data["amount"],
            "currency": order_data["currency"],
            "key_id": RAZORPAY_KEY_ID,
            "is_simulated": False
        }
    except Exception as e:
        print(f"Exception creating Razorpay order: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/payment/verify")
def verify_payment(request: VerificationRequest):
    # Check if mock mode is active
    if request.razorpay_order_id.startswith("order_mock_"):
        print(f"[Mock Mode] Verified payment for order {request.razorpay_order_id}")
        return {"status": "success", "message": "Signature verified (simulated)"}

    # Real HMAC verification of signature
    try:
        payload = f"{request.razorpay_order_id}|{request.razorpay_payment_id}"
        generated_signature = hmac.new(
            RAZORPAY_KEY_SECRET.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()

        if hmac.compare_digest(generated_signature, request.razorpay_signature):
            return {"status": "success", "message": "Signature verified successfully"}
        else:
            raise HTTPException(status_code=400, detail="Signature verification failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
