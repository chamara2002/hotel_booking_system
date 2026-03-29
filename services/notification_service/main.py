from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uvicorn

app = FastAPI(
    title="Notification Service",
    description="Handles email and SMS notifications for hotel guests and staff",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)


notifications_db: dict = {}
_id_counter = 1


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
        "subject": "Your Booking is Confirmed! 🏨",
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


@app.get("/", tags=["Health"])
def health_check():
    return {"service": "Notification Service", "status": "running", "port": 8005}

@app.post("/notifications", response_model=NotificationResponse, status_code=201, tags=["Notifications"])
def send_notification(notif: NotificationCreate):
    global _id_counter
    channel = notif.channel.upper()
    if channel in ("EMAIL", "BOTH") and not notif.recipient_email:
        raise HTTPException(status_code=400, detail="recipient_email required for EMAIL channel")
    if channel in ("SMS", "BOTH") and not notif.recipient_phone:
        raise HTTPException(status_code=400, detail="recipient_phone required for SMS channel")
    record = {
        "notification_id": _id_counter,
        **notif.dict(),
        "channel": channel,
        "status": "SENT",  
        "sent_at": datetime.now().isoformat()
    }
    notifications_db[_id_counter] = record
    _id_counter += 1
    return record

@app.post("/notifications/from-template", response_model=NotificationResponse, status_code=201, tags=["Notifications"])
def send_from_template(
    guest_id: int,
    booking_id: int,
    template_type: str,
    channel: str,
    recipient_email: Optional[str] = None,
    recipient_phone: Optional[str] = None
):
    global _id_counter
    tmpl = TEMPLATES.get(template_type.upper())
    if not tmpl:
        raise HTTPException(status_code=400, detail=f"Unknown template. Choose from {list(TEMPLATES.keys())}")
    channel_upper = channel.upper()
    if channel_upper in ("EMAIL", "BOTH") and not recipient_email:
        raise HTTPException(status_code=400, detail="recipient_email required for EMAIL channel")
    if channel_upper in ("SMS", "BOTH") and not recipient_phone:
        raise HTTPException(status_code=400, detail="recipient_phone required for SMS channel")
    record = {
        "notification_id": _id_counter,
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
    notifications_db[_id_counter] = record
    _id_counter += 1
    return record

@app.get("/notifications", response_model=List[NotificationResponse], tags=["Notifications"])
def list_notifications():
    return list(notifications_db.values())

@app.get("/notifications/{notification_id}", response_model=NotificationResponse, tags=["Notifications"])
def get_notification(notification_id: int):
    if notification_id not in notifications_db:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notifications_db[notification_id]

@app.get("/notifications/guest/{guest_id}", response_model=List[NotificationResponse], tags=["Notifications"])
def get_notifications_by_guest(guest_id: int):
    return [n for n in notifications_db.values() if n["guest_id"] == guest_id]

@app.delete("/notifications/{notification_id}", tags=["Notifications"])
def delete_notification(notification_id: int):
    if notification_id not in notifications_db:
        raise HTTPException(status_code=404, detail="Notification not found")
    del notifications_db[notification_id]
    return {"message": f"Notification {notification_id} deleted"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8005, reload=True)
