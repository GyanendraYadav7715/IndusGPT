from fastapi import APIRouter, HTTPException, Depends
import bson
import datetime

from app.models.schemas import ChatRequest, VerifyPaymentPayload
from app.core.security import get_current_user
from app.services.db import conversations_collection, users_collection
from app.services.chatbot_service import MultilingualChatbotService
from app.core.config import settings

router = APIRouter()

# Initialize Chatbot
if not settings.SARVAM_API_KEY:
    print("Warning: SARVAM_API_KEY environment variable not set. Chatbot will not work correctly.")
chatbot = MultilingualChatbotService(settings.SARVAM_API_KEY)


@router.get("/conversations")
async def get_conversations(user_id: str = Depends(get_current_user)):
    conversations = list(conversations_collection.find({"userId": user_id}).sort("timestamp", -1))
    
    result = []
    for conv in conversations:
        title = "New Conversation"
        messages = conv.get("messages", [])
        if messages:
            for msg in messages:
                if msg["role"] == "user":
                    title = msg["content"][:30] + ("..." if len(msg["content"]) > 30 else "")
                    break

        result.append({
            "id": str(conv["_id"]),
            "title": title,
            "timestamp": conv["timestamp"],
            "messageCount": len(messages)
        })
    return result

@router.get("/conversations/{conversation_id}")
async def get_conversation_history(conversation_id: str, user_id: str = Depends(get_current_user)):
    try:
        conv = conversations_collection.find_one({"_id": bson.ObjectId(conversation_id), "userId": user_id})
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        conv["_id"] = str(conv["_id"])
        return conv
    except bson.errors.InvalidId:
         raise HTTPException(status_code=400, detail="Invalid Conversation ID format")

@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, user_id: str = Depends(get_current_user)):
    try:
        result = conversations_collection.delete_one({"_id": bson.ObjectId(conversation_id), "userId": user_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {"status": "success", "message": "Conversation deleted successfully"}
    except bson.errors.InvalidId:
        raise HTTPException(status_code=400, detail="Invalid Conversation ID format")

@router.post("/chat")
async def chat_endpoint(request: ChatRequest, user_id: str = Depends(get_current_user)):
    if not settings.SARVAM_API_KEY:
        return {"response": "Error: SARVAM_API_KEY not configured.", "language": "english"}
    
    # Load user and check subscription/limits
    db_user = users_collection.find_one({"_id": bson.ObjectId(user_id)})
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    is_subscribed = db_user.get("is_subscribed", False)
    subscription_expires_at = db_user.get("subscription_expires_at")
    
    # Check if subscription is active
    has_active_subscription = False
    if is_subscribed and subscription_expires_at:
        if subscription_expires_at > datetime.datetime.utcnow():
            has_active_subscription = True

    if not has_active_subscription:
        messages_sent = db_user.get("messages_sent", 0)
        if messages_sent >= 5:
            raise HTTPException(status_code=403, detail="FREE_LIMIT_REACHED")
        
        # Increment message count
        users_collection.update_one({"_id": bson.ObjectId(user_id)}, {"$inc": {"messages_sent": 1}})

    conv_id = request.conversationId
    history = []

    if conv_id:
        try:
            conv = conversations_collection.find_one({"_id": bson.ObjectId(conv_id), "userId": user_id})
            if not conv:
                raise HTTPException(status_code=404, detail="Conversation not found")
            
            for msg in conv.get("messages", []):
               history.append({"role": msg["role"], "content": msg["content"]})
        except bson.errors.InvalidId:
            raise HTTPException(status_code=400, detail="Invalid Conversation ID")
    else:
        new_conv = {
            "userId": user_id,
            "timestamp": datetime.datetime.utcnow(),
            "messages": []
        }
        result = conversations_collection.insert_one(new_conv)
        conv_id = str(result.inserted_id)
    
    chatbot.conversation_history = history
    response_data = chatbot.get_chat_response(request.message)

    conversations_collection.update_one(
        {"_id": bson.ObjectId(conv_id)},
        {"$push": {
            "messages": {
                "$each": [
                    {"role": "user", "content": request.message, "timestamp": datetime.datetime.utcnow()},
                    {"role": "assistant", "content": response_data["response"], "language": response_data["language"], "timestamp": datetime.datetime.utcnow()}
                ]
            }
        },
        "$set": {"timestamp": datetime.datetime.utcnow()}
        }
    )

    return {
        "response": response_data["response"], 
        "language": response_data["language"],
        "conversationId": conv_id
    }

@router.get("/subscription/status")
async def get_subscription_status(user_id: str = Depends(get_current_user)):
    db_user = users_collection.find_one({"_id": bson.ObjectId(user_id)})
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    is_subscribed = db_user.get("is_subscribed", False)
    subscription_expires_at = db_user.get("subscription_expires_at")
    
    # Check expiration
    has_active_subscription = False
    if is_subscribed and subscription_expires_at:
        if subscription_expires_at > datetime.datetime.utcnow():
            has_active_subscription = True

    return {
        "is_subscribed": has_active_subscription,
        "subscription_expires_at": subscription_expires_at.isoformat() if subscription_expires_at else None,
        "messages_sent": db_user.get("messages_sent", 0),
        "username": db_user.get("username", "User")
    }

@router.post("/subscription/create-order")
async def create_subscription_order(user_id: str = Depends(get_current_user)):
    import requests
    # Price is ₹299 (29900 paise)
    try:
        response = requests.post(
            f"{settings.PAYMENT_MICROSERVICE_URL}/payment/order",
            json={"amount": 29900, "currency": "INR"}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to create payment order via microservice")
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Payment microservice offline: {str(e)}")

@router.post("/subscription/verify-payment")
async def verify_subscription_payment(payload: VerifyPaymentPayload, user_id: str = Depends(get_current_user)):
    import requests
    # Call payment microservice
    try:
        response = requests.post(
            f"{settings.PAYMENT_MICROSERVICE_URL}/payment/verify",
            json=payload.dict()
        )
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Payment verification failed")
        
        # Update user status to PRO (subscribed) for 30 days
        expiry_date = datetime.datetime.utcnow() + datetime.timedelta(days=30)
        users_collection.update_one(
            {"_id": bson.ObjectId(user_id)},
            {"$set": {
                "is_subscribed": True,
                "subscription_expires_at": expiry_date
            }}
        )
        return {"status": "success", "message": "Subscription activated!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Payment microservice error: {str(e)}")
