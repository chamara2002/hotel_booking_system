from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uvicorn

app = FastAPI(
    title="Room Service",
    description="Manages hotel rooms, types, availability and pricing",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# In-memory DB
rooms_db: dict = {}
_id_counter = 1

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

# Routes 
@app.get("/", tags=["Health"])
def health_check():
    return {"service": "Room Service", "status": "running", "port": 8002}

@app.post("/rooms", response_model=RoomResponse, status_code=201, tags=["Rooms"])
def create_room(room: RoomCreate):
    global _id_counter
    for r in rooms_db.values():
        if r["room_number"] == room.room_number:
            raise HTTPException(status_code=400, detail="Room number already exists")
    record = {
        "room_id": _id_counter,
        **room.dict(),
        "is_available": True,
        "created_at": datetime.now().isoformat()
    }
    rooms_db[_id_counter] = record
    _id_counter += 1
    return record

@app.get("/rooms", response_model=List[RoomResponse], tags=["Rooms"])
def list_rooms(available_only: bool = False):
    rooms = list(rooms_db.values())
    if available_only:
        rooms = [r for r in rooms if r["is_available"]]
    return rooms

@app.get("/rooms/{room_id}", response_model=RoomResponse, tags=["Rooms"])
def get_room(room_id: int):
    if room_id not in rooms_db:
        raise HTTPException(status_code=404, detail="Room not found")
    return rooms_db[room_id]

@app.put("/rooms/{room_id}", response_model=RoomResponse, tags=["Rooms"])
def update_room(room_id: int, update: RoomUpdate):
    if room_id not in rooms_db:
        raise HTTPException(status_code=404, detail="Room not found")
    for field, value in update.dict(exclude_none=True).items():
        rooms_db[room_id][field] = value
    return rooms_db[room_id]

@app.patch("/rooms/{room_id}/availability", tags=["Rooms"])
def toggle_availability(room_id: int, is_available: bool):
    if room_id not in rooms_db:
        raise HTTPException(status_code=404, detail="Room not found")
    rooms_db[room_id]["is_available"] = is_available
    status = "available" if is_available else "unavailable"
    return {"message": f"Room {room_id} marked as {status}"}

@app.delete("/rooms/{room_id}", tags=["Rooms"])
def delete_room(room_id: int):
    if room_id not in rooms_db:
        raise HTTPException(status_code=404, detail="Room not found")
    del rooms_db[room_id]
    return {"message": f"Room {room_id} deleted successfully"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
