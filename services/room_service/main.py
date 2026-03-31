from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import os
import uvicorn
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Room Service",
    description="Manages hotel rooms, types, availability and pricing",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "hotel_booking_system")

if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI environment variable is required")

mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
database = mongo_client[MONGODB_DB_NAME]
rooms_collection = database["rooms"]
counters_collection = database["counters"]


def get_next_sequence(counter_name: str) -> int:
    counter = counters_collection.find_one_and_update(
        {"_id": counter_name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return counter["seq"]

def clean_document(document: dict) -> dict:
    document.pop("_id", None)
    return document

# Models 
class RoomCreate(BaseModel):
    room_number: str
    room_type: str        
    floor: int
    price_per_night: float
    max_occupancy: int
    amenities: Optional[str] = "WiFi, TV, AC"

class RoomUpdate(BaseModel):
    price_per_night: Optional[float] = None
    is_available: Optional[bool] = None
    amenities: Optional[str] = None

class RoomResponse(BaseModel):
    room_id: int
    room_number: str
    room_type: str
    floor: int
    price_per_night: float
    max_occupancy: int
    amenities: str
    is_available: bool
    created_at: str

@app.on_event("startup")
def startup_db() -> None:
    try:
        mongo_client.admin.command("ping")
        rooms_collection.create_index("room_id", unique=True)
        rooms_collection.create_index("room_number", unique=True)
    except PyMongoError as ex:
        raise RuntimeError(f"Failed to initialize MongoDB for Room Service: {ex}")

# Routes 
@app.get("/", tags=["Health"])
def health_check():
    return {"service": "Room Service", "status": "running", "port": 8002}

@app.post("/rooms", response_model=RoomResponse, status_code=201, tags=["Rooms"])
def create_room(room: RoomCreate):
    record = {
        "room_id": get_next_sequence("room_id"),
        **room.model_dump(),
        "is_available": True,
        "created_at": datetime.now().isoformat()
    }
    try:
        rooms_collection.insert_one(record)
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="Room number already exists")
    except PyMongoError as ex:
        raise HTTPException(status_code=500, detail=f"Database error: {ex}")
    return clean_document(record)

@app.get("/rooms", response_model=List[RoomResponse], tags=["Rooms"])
def list_rooms(available_only: bool = False):
    filter_query = {"is_available": True} if available_only else {}
    rooms = list(rooms_collection.find(filter_query, {"_id": 0}).sort("room_id", 1))
    if available_only:
        rooms = [r for r in rooms if r["is_available"]]
    return rooms

@app.get("/rooms/{room_id}", response_model=RoomResponse, tags=["Rooms"])
def get_room(room_id: int):
    room = rooms_collection.find_one({"room_id": room_id})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return clean_document(room)

@app.put("/rooms/{room_id}", response_model=RoomResponse, tags=["Rooms"])
def update_room(room_id: int, update: RoomUpdate):
    updates = update.model_dump(exclude_none=True)
    if not updates:
        room = rooms_collection.find_one({"room_id": room_id})
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        return clean_document(room)

    try:
        room = rooms_collection.find_one_and_update(
            {"room_id": room_id},
            {"$set": updates},
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="Room number already exists")
    except PyMongoError as ex:
        raise HTTPException(status_code=500, detail=f"Database error: {ex}")

    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return clean_document(room)

@app.patch("/rooms/{room_id}/availability", tags=["Rooms"])
def toggle_availability(room_id: int, is_available: bool):
    result = rooms_collection.update_one(
        {"room_id": room_id},
        {"$set": {"is_available": is_available}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Room not found")
    status = "available" if is_available else "unavailable"
    return {"message": f"Room {room_id} marked as {status}"}

@app.delete("/rooms/{room_id}", tags=["Rooms"])
def delete_room(room_id: int):
    result = rooms_collection.delete_one({"room_id": room_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Room not found")
    return {"message": f"Room {room_id} deleted successfully"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
