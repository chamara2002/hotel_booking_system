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
    title="Guest Service",
    description="Manages hotel guest profiles and authentication",
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
guests_collection = database["guests"]
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
class GuestCreate(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: str
    nationality: Optional[str] = "N/A"
    id_number: str  # Passport / NIC

class GuestUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    nationality: Optional[str] = None

class GuestResponse(BaseModel):
    guest_id: int
    first_name: str
    last_name: str
    email: str
    phone: str
    nationality: str
    id_number: str
    created_at: str


@app.on_event("startup")
def startup_db() -> None:
    try:
        mongo_client.admin.command("ping")
        guests_collection.create_index("guest_id", unique=True)
        guests_collection.create_index("email", unique=True)
    except PyMongoError as ex:
        raise RuntimeError(f"Failed to initialize MongoDB for Guest Service: {ex}")

# Routes
@app.get("/", tags=["Health"])
def health_check():
    return {"service": "Guest Service", "status": "running", "port": 8001}

@app.post("/guests", response_model=GuestResponse, status_code=201, tags=["Guests"])
def create_guest(guest: GuestCreate):
    record = {
        "guest_id": get_next_sequence("guest_id"),
        **guest.model_dump(),
        "created_at": datetime.now().isoformat()
    }
    try:
        guests_collection.insert_one(record)
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="Email already registered")
    except PyMongoError as ex:
        raise HTTPException(status_code=500, detail=f"Database error: {ex}")
    return clean_document(record)

@app.get("/guests", response_model=List[GuestResponse], tags=["Guests"])
def list_guests():
    records = list(guests_collection.find({}, {"_id": 0}).sort("guest_id", 1))
    return records

@app.get("/guests/{guest_id}", response_model=GuestResponse, tags=["Guests"])
def get_guest(guest_id: int):
    record = guests_collection.find_one({"guest_id": guest_id})
    if not record:
        raise HTTPException(status_code=404, detail="Guest not found")
    return clean_document(record)

@app.put("/guests/{guest_id}", response_model=GuestResponse, tags=["Guests"])
def update_guest(guest_id: int, update: GuestUpdate):
    updates = update.model_dump(exclude_none=True)
    if not updates:
        record = guests_collection.find_one({"guest_id": guest_id})
        if not record:
            raise HTTPException(status_code=404, detail="Guest not found")
        return clean_document(record)

    try:
        record = guests_collection.find_one_and_update(
            {"guest_id": guest_id},
            {"$set": updates},
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="Email already registered")
    except PyMongoError as ex:
        raise HTTPException(status_code=500, detail=f"Database error: {ex}")

    if not record:
        raise HTTPException(status_code=404, detail="Guest not found")
    return clean_document(record)

@app.delete("/guests/{guest_id}", tags=["Guests"])
def delete_guest(guest_id: int):
    result = guests_collection.delete_one({"guest_id": guest_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Guest not found")
    return {"message": f"Guest {guest_id} deleted successfully"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
