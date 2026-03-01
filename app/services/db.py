from pymongo import MongoClient
from app.core.config import settings

# Setup MongoDB
client = MongoClient(settings.MONGO_URI)
db = client["chatbot_db"]
users_collection = db["users"]
conversations_collection = db["conversations"]
