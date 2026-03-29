from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uvicorn

app = FastAPI(
    title="Payment Service",
    description="Processes payments, refunds and invoices for hotel bookings",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)


payments_db: dict = {}
_id_counter = 1

class PaymentCreate(BaseModel):
    booking_id: int
    guest_id: int
    amount: float
    currency: Optional[str] = "LKR"
    payment_method: str     
    room_price_per_night: float
    total_nights: int

class RefundRequest(BaseModel):
    reason: str
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


@app.get("/", tags=["Health"])
def health_check():
    return {"service": "Payment Service", "status": "running", "port": 8004}

@app.post("/payments", response_model=PaymentResponse, status_code=201, tags=["Payments"])
def create_payment(payment: PaymentCreate):
    global _id_counter
    expected = round(payment.room_price_per_night * payment.total_nights, 2)
    if round(payment.amount, 2) != expected:
        raise HTTPException(
            status_code=400,
            detail=f"Amount mismatch. Expected {expected} but got {payment.amount}"
        )
    record = {
        "payment_id": _id_counter,
        **payment.dict(),
        "status": "PAID",
        "transaction_ref": generate_ref(_id_counter),
        "paid_at": datetime.now().isoformat()
    }
    payments_db[_id_counter] = record
    _id_counter += 1
    return record

@app.get("/payments", response_model=List[PaymentResponse], tags=["Payments"])
def list_payments():
    return list(payments_db.values())

@app.get("/payments/{payment_id}", response_model=PaymentResponse, tags=["Payments"])
def get_payment(payment_id: int):
    if payment_id not in payments_db:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payments_db[payment_id]

@app.get("/payments/booking/{booking_id}", response_model=List[PaymentResponse], tags=["Payments"])
def get_payments_by_booking(booking_id: int):
    return [p for p in payments_db.values() if p["booking_id"] == booking_id]

@app.post("/payments/{payment_id}/refund", tags=["Payments"])
def refund_payment(payment_id: int, refund: RefundRequest):
    if payment_id not in payments_db:
        raise HTTPException(status_code=404, detail="Payment not found")
    payment = payments_db[payment_id]
    if payment["status"] != "PAID":
        raise HTTPException(status_code=400, detail="Only PAID payments can be refunded")
    refund_amt = refund.refund_amount if refund.refund_amount else payment["amount"]
    payments_db[payment_id]["status"] = "REFUNDED"
    return {
        "message": f"Refund of {refund_amt} {payment['currency']} processed",
        "transaction_ref": payment["transaction_ref"],
        "reason": refund.reason
    }

@app.get("/payments/summary/total", tags=["Payments"])
def payment_summary():
    total = sum(p["amount"] for p in payments_db.values() if p["status"] == "PAID")
    return {"total_revenue": total, "currency": "LKR", "total_transactions": len(payments_db)}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8004, reload=True)
