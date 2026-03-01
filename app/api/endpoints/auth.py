from fastapi import APIRouter, HTTPException
import datetime

from app.models.schemas import UserSignup, UserLogin
from app.core.security import get_password_hash, verify_password, create_access_token
from app.services.db import users_collection

router = APIRouter()

@router.post("/signup")
async def signup(user: UserSignup):
    if users_collection.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = get_password_hash(user.password)
    user_dict = {
        "username": user.username,
        "email": user.email,
        "password": hashed_password,
        "created_at": datetime.datetime.utcnow()
    }
    result = users_collection.insert_one(user_dict)
    
    access_token = create_access_token(data={"sub": str(result.inserted_id), "username": user.username})
    return {"access_token": access_token, "token_type": "bearer", "username": user.username}

@router.post("/login")
async def login(user: UserLogin):
    db_user = users_collection.find_one({"email": user.email})
    if not db_user or not verify_password(user.password, db_user["password"]):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    access_token = create_access_token(data={"sub": str(db_user["_id"]), "username": db_user["username"]})
    return {"access_token": access_token, "token_type": "bearer", "username": db_user["username"]}
