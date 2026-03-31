from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime
import os
import uvicorn
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import PyMongoError
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Payment Service",
    description="Processes payments, refunds and invoices for hotel bookings",
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
payments_collection = database["payments"]
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

class PaymentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    booking_id: int = Field(gt=0)
    guest_id: int = Field(gt=0)
    amount: float = Field(gt=0)
    currency: Optional[str] = "LKR"
    payment_method: str = Field(min_length=2, max_length=50)
    room_price_per_night: float = Field(gt=0)
    total_nights: int = Field(gt=0, le=365)

class RefundRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    reason: str = Field(min_length=3, max_length=250)
    refund_amount: Optional[float] = None   

class PaymentResponse(BaseModel):
    payment_id: int
    booking_id: int
    guest_id: int
    amount: float
    currency: str
    payment_method: str
    room_price_per_night: float
    total_nights: int
    status: str             
    transaction_ref: str
    paid_at: str

def generate_ref(payment_id: int) -> str:
    return f"TXN-HTL-{datetime.now().strftime('%Y%m%d')}-{payment_id:04d}"

@app.on_event("startup")
def startup_db() -> None:
    try:
        mongo_client.admin.command("ping")
        payments_collection.create_index("payment_id", unique=True)
        payments_collection.create_index("booking_id")
        payments_collection.create_index("guest_id")
        payments_collection.create_index("status")
    except PyMongoError as ex:
        raise RuntimeError(f"Failed to initialize MongoDB for Payment Service: {ex}")

@app.get("/", tags=["Health"])
def health_check():
    return {"service": "Payment Service", "status": "running", "port": 8004}


@app.get("/ready", tags=["Health"])
def readiness_check():
    try:
        mongo_client.admin.command("ping")
        return {"service": "Payment Service", "status": "ready"}
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Database not ready")

@app.post("/payments", response_model=PaymentResponse, status_code=201, tags=["Payments"])
def create_payment(payment: PaymentCreate):
    expected = round(payment.room_price_per_night * payment.total_nights, 2)
    if round(payment.amount, 2) != expected:
        raise HTTPException(
            status_code=400,
            detail=f"Amount mismatch. Expected {expected} but got {payment.amount}"
        )
    payment_id = get_next_sequence("payment_id")
    record = {
        "payment_id": payment_id,
        **payment.model_dump(),
        "status": "PAID",
        "transaction_ref": generate_ref(payment_id),
        "paid_at": datetime.now().isoformat()
    }
    try:
        payments_collection.insert_one(record)
    except PyMongoError as ex:
        raise HTTPException(status_code=500, detail=f"Database error: {ex}")
    return clean_document(record)

@app.get("/payments", response_model=List[PaymentResponse], tags=["Payments"])
def list_payments():
    return list(payments_collection.find({}, {"_id": 0}).sort("payment_id", 1))

@app.get("/payments/{payment_id}", response_model=PaymentResponse, tags=["Payments"])
def get_payment(payment_id: int):
    payment = payments_collection.find_one({"payment_id": payment_id})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return clean_document(payment)

@app.get("/payments/booking/{booking_id}", response_model=List[PaymentResponse], tags=["Payments"])
def get_payments_by_booking(booking_id: int):
    return list(payments_collection.find({"booking_id": booking_id}, {"_id": 0}).sort("payment_id", 1))

@app.post("/payments/{payment_id}/refund", tags=["Payments"])
def refund_payment(payment_id: int, refund: RefundRequest):
    payment = payments_collection.find_one({"payment_id": payment_id})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    if payment["status"] != "PAID":
        raise HTTPException(status_code=400, detail="Only PAID payments can be refunded")
    refund_amt = payment["amount"] if refund.refund_amount is None else round(refund.refund_amount, 2)
    if refund_amt <= 0:
        raise HTTPException(status_code=400, detail="Refund amount must be greater than zero")
    if refund_amt > payment["amount"]:
        raise HTTPException(status_code=400, detail="Refund amount cannot exceed paid amount")

    updated = payments_collection.find_one_and_update(
        {"payment_id": payment_id, "status": "PAID"},
        {
            "$set": {
                "status": "REFUNDED",
                "refund_reason": refund.reason,
                "refund_amount": refund_amt,
                "refunded_at": datetime.now().isoformat(),
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(status_code=409, detail="Payment was already refunded")

    return {
        "message": f"Refund of {refund_amt} {updated['currency']} processed",
        "transaction_ref": updated["transaction_ref"],
        "reason": refund.reason
    }

@app.get("/payments/summary/total", tags=["Payments"])
def payment_summary():
    paid_payments = list(payments_collection.find({"status": "PAID"}, {"_id": 0}))
    total = sum(p["amount"] for p in paid_payments)
    currencies = {p["currency"] for p in paid_payments}
    currency = next(iter(currencies)) if len(currencies) == 1 else "MULTI"
    return {"total_revenue": total, "currency": currency, "total_transactions": len(paid_payments)}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8004, reload=True)
