from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uvicorn

app = FastAPI(
    title="Guest Service",
    description="Manages hotel guest profiles and authentication",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# In-memory DB
guests_db: dict = {}
_id_counter = 1

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

# Routes
@app.get("/", tags=["Health"])
def health_check():
    return {"service": "Guest Service", "status": "running", "port": 8001}

@app.post("/guests", response_model=GuestResponse, status_code=201, tags=["Guests"])
def create_guest(guest: GuestCreate):
    global _id_counter
    # Check duplicate email
    for g in guests_db.values():
        if g["email"] == guest.email:
            raise HTTPException(status_code=400, detail="Email already registered")
    record = {
        "guest_id": _id_counter,
        **guest.dict(),
        "created_at": datetime.now().isoformat()
    }
    guests_db[_id_counter] = record
    _id_counter += 1
    return record

@app.get("/guests", response_model=List[GuestResponse], tags=["Guests"])
def list_guests():
    return list(guests_db.values())

@app.get("/guests/{guest_id}", response_model=GuestResponse, tags=["Guests"])
def get_guest(guest_id: int):
    if guest_id not in guests_db:
        raise HTTPException(status_code=404, detail="Guest not found")
    return guests_db[guest_id]

@app.put("/guests/{guest_id}", response_model=GuestResponse, tags=["Guests"])
def update_guest(guest_id: int, update: GuestUpdate):
    if guest_id not in guests_db:
        raise HTTPException(status_code=404, detail="Guest not found")
    for field, value in update.dict(exclude_none=True).items():
        guests_db[guest_id][field] = value
    return guests_db[guest_id]

@app.delete("/guests/{guest_id}", tags=["Guests"])
def delete_guest(guest_id: int):
    if guest_id not in guests_db:
        raise HTTPException(status_code=404, detail="Guest not found")
    del guests_db[guest_id]
    return {"message": f"Guest {guest_id} deleted successfully"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
