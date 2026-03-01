from fastapi import APIRouter, HTTPException, Depends
import bson
import datetime

from app.models.schemas import ChatRequest
from app.core.security import get_current_user
from app.services.db import conversations_collection
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

@router.post("/chat")
async def chat_endpoint(request: ChatRequest, user_id: str = Depends(get_current_user)):
    if not settings.SARVAM_API_KEY:
        return {"response": "Error: SARVAM_API_KEY not configured.", "language": "english"}
    
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
