import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME = "Multilingual Chatbot API"
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-key-change-in-production")
    ALGORITHM = "HS256"
    SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
    PAYMENT_MICROSERVICE_URL = os.getenv("PAYMENT_MICROSERVICE_URL", "http://localhost:8001")

settings = Settings()
