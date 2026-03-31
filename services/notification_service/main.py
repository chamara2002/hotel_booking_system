from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import os
import uvicorn
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import PyMongoError
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Notification Service",
    description="Handles email and SMS notifications for hotel guests and staff",
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
notifications_collection = database["notifications"]
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

class NotificationCreate(BaseModel):
    guest_id: int
    booking_id: Optional[int] = None
    notification_type: str 
    channel: str           
    recipient_email: Optional[str] = None
    recipient_phone: Optional[str] = None
    subject: str
    message: str

class NotificationResponse(BaseModel):
    notification_id: int
    guest_id: int
    booking_id: Optional[int]
    notification_type: str
    channel: str
    recipient_email: Optional[str]
    recipient_phone: Optional[str]
    subject: str
    message: str
    status: str            
    sent_at: str

TEMPLATES = {
    "BOOKING_CONFIRMATION": {
        "subject": "Your Booking is Confirmed!",
        "message": "Dear Guest, your hotel booking has been confirmed. We look forward to welcoming you!"
    },
    "CHECK_IN_REMINDER": {
        "subject": "Check-In Reminder",
        "message": "This is a reminder that your check-in is scheduled for tomorrow. Please arrive by 2:00 PM."
    },
    "PAYMENT_RECEIPT": {
        "subject": "Payment Receipt",
        "message": "Your payment has been successfully processed. Thank you for choosing us!"
    },
    "CANCELLATION": {
        "subject": "Booking Cancellation Notice",
        "message": "Your booking has been cancelled as requested. We hope to serve you in the future."
    }
}

@app.on_event("startup")
def startup_db() -> None:
    try:
        mongo_client.admin.command("ping")
        notifications_collection.create_index("notification_id", unique=True)
        notifications_collection.create_index("guest_id")
        notifications_collection.create_index("booking_id")
    except PyMongoError as ex:
        raise RuntimeError(f"Failed to initialize MongoDB for Notification Service: {ex}")

@app.get("/", tags=["Health"])
def health_check():
    return {"service": "Notification Service", "status": "running", "port": 8005}

@app.post("/notifications", response_model=NotificationResponse, status_code=201, tags=["Notifications"])
def send_notification(notif: NotificationCreate):
    channel = notif.channel.upper()
    if channel in ("EMAIL", "BOTH") and not notif.recipient_email:
        raise HTTPException(status_code=400, detail="recipient_email required for EMAIL channel")
    if channel in ("SMS", "BOTH") and not notif.recipient_phone:
        raise HTTPException(status_code=400, detail="recipient_phone required for SMS channel")
    record = {
        "notification_id": get_next_sequence("notification_id"),
        **notif.model_dump(),
        "channel": channel,
        "status": "SENT",  
        "sent_at": datetime.now().isoformat()
    }
    try:
        notifications_collection.insert_one(record)
    except PyMongoError as ex:
        raise HTTPException(status_code=500, detail=f"Database error: {ex}")
    return clean_document(record)

@app.post("/notifications/from-template", response_model=NotificationResponse, status_code=201, tags=["Notifications"])
def send_from_template(
    guest_id: int,
    booking_id: int,
    template_type: str,
    channel: str,
    recipient_email: Optional[str] = None,
    recipient_phone: Optional[str] = None
):
    tmpl = TEMPLATES.get(template_type.upper())
    if not tmpl:
        raise HTTPException(status_code=400, detail=f"Unknown template. Choose from {list(TEMPLATES.keys())}")
    channel_upper = channel.upper()
    if channel_upper in ("EMAIL", "BOTH") and not recipient_email:
        raise HTTPException(status_code=400, detail="recipient_email required for EMAIL channel")
    if channel_upper in ("SMS", "BOTH") and not recipient_phone:
        raise HTTPException(status_code=400, detail="recipient_phone required for SMS channel")
    record = {
        "notification_id": get_next_sequence("notification_id"),
        "guest_id": guest_id,
        "booking_id": booking_id,
        "notification_type": template_type.upper(),
        "channel": channel_upper,
        "recipient_email": recipient_email,
        "recipient_phone": recipient_phone,
        "subject": tmpl["subject"],
        "message": tmpl["message"],
        "status": "SENT",
        "sent_at": datetime.now().isoformat()
    }
    try:
        notifications_collection.insert_one(record)
    except PyMongoError as ex:
        raise HTTPException(status_code=500, detail=f"Database error: {ex}")
    return clean_document(record)

@app.get("/notifications", response_model=List[NotificationResponse], tags=["Notifications"])
def list_notifications():
    return list(notifications_collection.find({}, {"_id": 0}).sort("notification_id", 1))

@app.get("/notifications/{notification_id}", response_model=NotificationResponse, tags=["Notifications"])
def get_notification(notification_id: int):
    notification = notifications_collection.find_one({"notification_id": notification_id})
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return clean_document(notification)

@app.get("/notifications/guest/{guest_id}", response_model=List[NotificationResponse], tags=["Notifications"])
def get_notifications_by_guest(guest_id: int):
    return list(notifications_collection.find({"guest_id": guest_id}, {"_id": 0}).sort("notification_id", 1))

@app.delete("/notifications/{notification_id}", tags=["Notifications"])
def delete_notification(notification_id: int):
    result = notifications_collection.delete_one({"notification_id": notification_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": f"Notification {notification_id} deleted"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8005, reload=True)
