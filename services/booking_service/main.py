from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
import uvicorn

app = FastAPI(
    title="Booking Service",
    description="Handles hotel room reservations, check-in and check-out",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# ── In-memory DB ──────────────────────────────────────────────────────────────
bookings_db: dict = {}
_id_counter = 1

# ── Models ────────────────────────────────────────────────────────────────────
class BookingCreate(BaseModel):
    guest_id: int
    room_id: int
    check_in_date: str      # YYYY-MM-DD
    check_out_date: str     # YYYY-MM-DD
    num_guests: int
    special_requests: Optional[str] = None

class BookingUpdate(BaseModel):
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

# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def health_check():
    return {"service": "Booking Service", "status": "running", "port": 8003}

@app.post("/bookings", response_model=BookingResponse, status_code=201, tags=["Bookings"])
def create_booking(booking: BookingCreate):
    global _id_counter
    nights = calculate_nights(booking.check_in_date, booking.check_out_date)
    if nights <= 0:
        raise HTTPException(status_code=400, detail="Check-out must be after check-in")
    record = {
        "booking_id": _id_counter,
        **booking.dict(),
        "status": "CONFIRMED",
        "total_nights": nights,
        "created_at": datetime.now().isoformat()
    }
    bookings_db[_id_counter] = record
    _id_counter += 1
    return record

@app.get("/bookings", response_model=List[BookingResponse], tags=["Bookings"])
def list_bookings():
    return list(bookings_db.values())

@app.get("/bookings/{booking_id}", response_model=BookingResponse, tags=["Bookings"])
def get_booking(booking_id: int):
    if booking_id not in bookings_db:
        raise HTTPException(status_code=404, detail="Booking not found")
    return bookings_db[booking_id]

@app.get("/bookings/guest/{guest_id}", response_model=List[BookingResponse], tags=["Bookings"])
def get_bookings_by_guest(guest_id: int):
    return [b for b in bookings_db.values() if b["guest_id"] == guest_id]

@app.put("/bookings/{booking_id}", response_model=BookingResponse, tags=["Bookings"])
def update_booking(booking_id: int, update: BookingUpdate):
    if booking_id not in bookings_db:
        raise HTTPException(status_code=404, detail="Booking not found")
    for field, value in update.dict(exclude_none=True).items():
        bookings_db[booking_id][field] = value
    if update.check_in_date or update.check_out_date:
        nights = calculate_nights(
            bookings_db[booking_id]["check_in_date"],
            bookings_db[booking_id]["check_out_date"]
        )
        if nights <= 0:
            raise HTTPException(status_code=400, detail="Check-out must be after check-in")
        bookings_db[booking_id]["total_nights"] = nights
    return bookings_db[booking_id]

@app.patch("/bookings/{booking_id}/status", tags=["Bookings"])
def update_booking_status(booking_id: int, status: str):
    valid = ["PENDING", "CONFIRMED", "CHECKED_IN", "CHECKED_OUT", "CANCELLED"]
    if status.upper() not in valid:
        raise HTTPException(status_code=400, detail=f"Status must be one of {valid}")
    if booking_id not in bookings_db:
        raise HTTPException(status_code=404, detail="Booking not found")
    bookings_db[booking_id]["status"] = status.upper()
    return {"message": f"Booking {booking_id} status updated to {status.upper()}"}

@app.delete("/bookings/{booking_id}", tags=["Bookings"])
def cancel_booking(booking_id: int):
    if booking_id not in bookings_db:
        raise HTTPException(status_code=404, detail="Booking not found")
    bookings_db[booking_id]["status"] = "CANCELLED"
    return {"message": f"Booking {booking_id} has been cancelled"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=True)
