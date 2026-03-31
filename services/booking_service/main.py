from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime
import os
import uvicorn
import httpx
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import PyMongoError
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Booking Service",
    description="Handles hotel room reservations, check-in and check-out",
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
bookings_collection = database["bookings"]
counters_collection = database["counters"]
GUEST_SERVICE_URL = os.getenv("GUEST_SERVICE_URL", "http://localhost:8001")
ROOM_SERVICE_URL = os.getenv("ROOM_SERVICE_URL", "http://localhost:8002")


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
class BookingCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    guest_id: int = Field(gt=0)
    room_id: int = Field(gt=0)
    check_in_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    check_out_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    num_guests: int = Field(ge=1, le=20)
    special_requests: Optional[str] = None

class BookingUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    check_in_date: Optional[str] = None
    check_out_date: Optional[str] = None
    special_requests: Optional[str] = None

class BookingResponse(BaseModel):
    booking_id: int
    guest_id: int
    room_id: int
    check_in_date: str
    check_out_date: str
    num_guests: int
    special_requests: Optional[str]
    status: str             # PENDING | CONFIRMED | CHECKED_IN | CHECKED_OUT | CANCELLED
    total_nights: int
    created_at: str

def calculate_nights(check_in: str, check_out: str) -> int:
    fmt = "%Y-%m-%d"
    delta = datetime.strptime(check_out, fmt) - datetime.strptime(check_in, fmt)
    return delta.days


def validate_guest_and_room(guest_id: int, room_id: int) -> None:
    try:
        with httpx.Client(timeout=3.0) as client:
            guest_response = client.get(f"{GUEST_SERVICE_URL}/guests/{guest_id}")
            if guest_response.status_code == 404:
                raise HTTPException(status_code=400, detail="Guest does not exist")
            if guest_response.status_code >= 500:
                raise HTTPException(status_code=503, detail="Guest service unavailable")

            room_response = client.get(f"{ROOM_SERVICE_URL}/rooms/{room_id}")
            if room_response.status_code == 404:
                raise HTTPException(status_code=400, detail="Room does not exist")
            if room_response.status_code >= 500:
                raise HTTPException(status_code=503, detail="Room service unavailable")

            room = room_response.json()
            if not room.get("is_available", False):
                raise HTTPException(status_code=400, detail="Room is not available")
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Dependency service unavailable")


@app.on_event("startup")
def startup_db() -> None:
    try:
        mongo_client.admin.command("ping")
        bookings_collection.create_index("booking_id", unique=True)
        bookings_collection.create_index("guest_id")
        bookings_collection.create_index("room_id")
    except PyMongoError as ex:
        raise RuntimeError(f"Failed to initialize MongoDB for Booking Service: {ex}")

# Routes
@app.get("/", tags=["Health"])
def health_check():
    return {"service": "Booking Service", "status": "running", "port": 8003}


@app.get("/ready", tags=["Health"])
def readiness_check():
    try:
        mongo_client.admin.command("ping")
        return {"service": "Booking Service", "status": "ready"}
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Database not ready")

@app.post("/bookings", response_model=BookingResponse, status_code=201, tags=["Bookings"])
def create_booking(booking: BookingCreate):
    validate_guest_and_room(booking.guest_id, booking.room_id)
    nights = calculate_nights(booking.check_in_date, booking.check_out_date)
    if nights <= 0:
        raise HTTPException(status_code=400, detail="Check-out must be after check-in")
    record = {
        "booking_id": get_next_sequence("booking_id"),
        **booking.model_dump(),
        "status": "CONFIRMED",
        "total_nights": nights,
        "created_at": datetime.now().isoformat()
    }
    try:
        bookings_collection.insert_one(record)
    except PyMongoError as ex:
        raise HTTPException(status_code=500, detail=f"Database error: {ex}")
    return clean_document(record)

@app.get("/bookings", response_model=List[BookingResponse], tags=["Bookings"])
def list_bookings():
    return list(bookings_collection.find({}, {"_id": 0}).sort("booking_id", 1))

@app.get("/bookings/{booking_id}", response_model=BookingResponse, tags=["Bookings"])
def get_booking(booking_id: int):
    booking = bookings_collection.find_one({"booking_id": booking_id})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return clean_document(booking)

@app.get("/bookings/guest/{guest_id}", response_model=List[BookingResponse], tags=["Bookings"])
def get_bookings_by_guest(guest_id: int):
    return list(bookings_collection.find({"guest_id": guest_id}, {"_id": 0}).sort("booking_id", 1))

@app.put("/bookings/{booking_id}", response_model=BookingResponse, tags=["Bookings"])
def update_booking(booking_id: int, update: BookingUpdate):
    existing = bookings_collection.find_one({"booking_id": booking_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Booking not found")

    updates = update.model_dump(exclude_none=True)
    if update.check_in_date or update.check_out_date:
        next_check_in = updates.get("check_in_date", existing["check_in_date"])
        next_check_out = updates.get("check_out_date", existing["check_out_date"])
        nights = calculate_nights(
            next_check_in,
            next_check_out,
        )
        if nights <= 0:
            raise HTTPException(status_code=400, detail="Check-out must be after check-in")
        updates["total_nights"] = nights

    if updates:
        bookings_collection.update_one({"booking_id": booking_id}, {"$set": updates})

    updated = bookings_collection.find_one({"booking_id": booking_id})
    return clean_document(updated)

@app.patch("/bookings/{booking_id}/status", tags=["Bookings"])
def update_booking_status(booking_id: int, status: str):
    valid = ["PENDING", "CONFIRMED", "CHECKED_IN", "CHECKED_OUT", "CANCELLED"]
    if status.upper() not in valid:
        raise HTTPException(status_code=400, detail=f"Status must be one of {valid}")
    result = bookings_collection.update_one(
        {"booking_id": booking_id},
        {"$set": {"status": status.upper()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Booking not found")
    return {"message": f"Booking {booking_id} status updated to {status.upper()}"}

@app.delete("/bookings/{booking_id}", tags=["Bookings"])
def cancel_booking(booking_id: int):
    result = bookings_collection.update_one(
        {"booking_id": booking_id},
        {"$set": {"status": "CANCELLED"}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Booking not found")
    return {"message": f"Booking {booking_id} has been cancelled"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=True)
