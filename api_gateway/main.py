from typing import Any, Optional
import os
import httpx
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from auth import create_access_token, verify_token

app = FastAPI(
    title="Hotel Booking System - API Gateway",
    description="Central API Gateway that routes requests to all microservices. Provides unified interface for client applications to interact with hotel booking system services.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")

# Downstream services
SERVICES = {
    "guest": "http://localhost:8001",
    "room": "http://localhost:8002",
    "booking": "http://localhost:8003",
    "payment": "http://localhost:8004",
    "notification": "http://localhost:8005",
}


class LoginRequest(BaseModel):
    username: str
    password: str

class GuestCreate(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: str
    nationality: Optional[str] = "N/A"
    id_number: str


class GuestUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    nationality: Optional[str] = None


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


class BookingCreate(BaseModel):
    guest_id: int
    room_id: int
    check_in_date: str
    check_out_date: str
    num_guests: int
    special_requests: Optional[str] = None


class BookingUpdate(BaseModel):
    check_in_date: Optional[str] = None
    check_out_date: Optional[str] = None
    special_requests: Optional[str] = None


class NotificationCreate(BaseModel):
    guest_id: int
    booking_id: Optional[int] = None
    notification_type: str
    channel: str
    recipient_email: Optional[str] = None
    recipient_phone: Optional[str] = None
    subject: str
    message: str


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


@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Log only the path to avoid leaking sensitive query-string data.
    print(f"[REQUEST] {request.method} {request.url.path}")
    response = await call_next(request)
    print(f"[RESPONSE] Status {response.status_code}")
    return response


async def forward_request(service: str, path: str, method: str, **kwargs) -> Any:
    if service not in SERVICES:
        raise HTTPException(status_code=404, detail="Service not found")

    url = f"{SERVICES[service]}{path}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.request(method=method, url=url, **kwargs)
            response_content = None
            if response.text:
                try:
                    response_content = response.json()
                except ValueError:
                    response_content = {"raw": response.text}
            return JSONResponse(content=response_content, status_code=response.status_code)
        except httpx.RequestError as ex:
            raise HTTPException(status_code=503, detail=f"Service unavailable: {str(ex)}")


@app.post("/login")
def login(payload: LoginRequest):
    if payload.username == ADMIN_USERNAME and payload.password == ADMIN_PASSWORD:
        token = create_access_token({"sub": payload.username})
        return {"access_token": token, "token_type": "bearer"}
    raise HTTPException(status_code=401, detail="Invalid credentials")


@app.get("/")
def read_root():
    return {
        "message": "API Gateway is running",
        "available_services": list(SERVICES.keys()),
    }


@app.get("/health")
async def check_all_services():
    results = {}
    async with httpx.AsyncClient(timeout=3.0) as client:
        for name, url in SERVICES.items():
            try:
                await client.get(f"{url}/")
                results[name] = {"status": "UP"}
            except Exception:
                results[name] = {"status": "DOWN"}
    return {"gateway": "UP", "services": results}


# Guest routes (open)
@app.get("/gateway/guests")
async def get_all_guests(_token: dict = Depends(verify_token)):
    return await forward_request("guest", "/guests", "GET")


@app.get("/gateway/guests/{guest_id}")
async def get_guest(guest_id: int, _token: dict = Depends(verify_token)):
    return await forward_request("guest", f"/guests/{guest_id}", "GET")


@app.post("/gateway/guests")
async def create_guest(guest: GuestCreate, _token: dict = Depends(verify_token)):
    return await forward_request("guest", "/guests", "POST", json=guest.model_dump())


@app.put("/gateway/guests/{guest_id}")
async def update_guest(guest_id: int, guest: GuestUpdate, _token: dict = Depends(verify_token)):
    return await forward_request("guest", f"/guests/{guest_id}", "PUT", json=guest.model_dump(exclude_unset=True))


@app.delete("/gateway/guests/{guest_id}")
async def delete_guest(guest_id: int, _token: dict = Depends(verify_token)):
    return await forward_request("guest", f"/guests/{guest_id}", "DELETE")


# Room routes (open reads, secured writes)
@app.get("/gateway/rooms")
async def get_all_rooms(
    available_only: bool = Query(False),
    _token: dict = Depends(verify_token),
):
    return await forward_request("room", "/rooms", "GET", params={"available_only": available_only})


@app.get("/gateway/rooms/{room_id}")
async def get_room(room_id: int, _token: dict = Depends(verify_token)):
    return await forward_request("room", f"/rooms/{room_id}", "GET")


@app.post("/gateway/rooms")
async def create_room(room: RoomCreate, _token: dict = Depends(verify_token)):
    return await forward_request("room", "/rooms", "POST", json=room.model_dump())


@app.put("/gateway/rooms/{room_id}")
async def update_room(room_id: int, room: RoomUpdate, _token: dict = Depends(verify_token)):
    return await forward_request("room", f"/rooms/{room_id}", "PUT", json=room.model_dump(exclude_unset=True))


@app.patch("/gateway/rooms/{room_id}/availability")
async def set_room_availability(
    room_id: int,
    is_available: bool = Query(...),
    _token: dict = Depends(verify_token),
):
    return await forward_request(
        "room",
        f"/rooms/{room_id}/availability",
        "PATCH",
        params={"is_available": is_available},
    )


@app.delete("/gateway/rooms/{room_id}")
async def delete_room(room_id: int, _token: dict = Depends(verify_token)):
    return await forward_request("room", f"/rooms/{room_id}", "DELETE")


# Booking routes (secured)
@app.get("/gateway/bookings")
async def get_all_bookings(_token: dict = Depends(verify_token)):
    return await forward_request("booking", "/bookings", "GET")


@app.get("/gateway/bookings/{booking_id}")
async def get_booking(booking_id: int, _token: dict = Depends(verify_token)):
    return await forward_request("booking", f"/bookings/{booking_id}", "GET")


@app.get("/gateway/bookings/guest/{guest_id}")
async def get_bookings_by_guest(guest_id: int, _token: dict = Depends(verify_token)):
    return await forward_request("booking", f"/bookings/guest/{guest_id}", "GET")


@app.post("/gateway/bookings")
async def create_booking(booking: BookingCreate, _token: dict = Depends(verify_token)):
    return await forward_request("booking", "/bookings", "POST", json=booking.model_dump())


@app.put("/gateway/bookings/{booking_id}")
async def update_booking(
    booking_id: int,
    booking: BookingUpdate,
    _token: dict = Depends(verify_token),
):
    return await forward_request(
        "booking",
        f"/bookings/{booking_id}",
        "PUT",
        json=booking.model_dump(exclude_unset=True),
    )


@app.patch("/gateway/bookings/{booking_id}/status")
async def update_booking_status(
    booking_id: int,
    status: str = Query(...),
    _token: dict = Depends(verify_token),
):
    return await forward_request(
        "booking",
        f"/bookings/{booking_id}/status",
        "PATCH",
        params={"status": status},
    )


@app.delete("/gateway/bookings/{booking_id}")
async def cancel_booking(booking_id: int, _token: dict = Depends(verify_token)):
    return await forward_request("booking", f"/bookings/{booking_id}", "DELETE")


# Payment routes (secured)
@app.get("/gateway/payments")
async def get_all_payments(_token: dict = Depends(verify_token)):
    return await forward_request("payment", "/payments", "GET")


@app.get("/gateway/payments/{payment_id}")
async def get_payment(payment_id: int, _token: dict = Depends(verify_token)):
    return await forward_request("payment", f"/payments/{payment_id}", "GET")


@app.get("/gateway/payments/booking/{booking_id}")
async def get_payments_by_booking(booking_id: int, _token: dict = Depends(verify_token)):
    return await forward_request("payment", f"/payments/booking/{booking_id}", "GET")


@app.post("/gateway/payments")
async def create_payment(payment: PaymentCreate, _token: dict = Depends(verify_token)):
    return await forward_request("payment", "/payments", "POST", json=payment.model_dump())


@app.post("/gateway/payments/{payment_id}/refund")
async def refund_payment(
    payment_id: int,
    refund: RefundRequest,
    _token: dict = Depends(verify_token),
):
    return await forward_request(
        "payment",
        f"/payments/{payment_id}/refund",
        "POST",
        json=refund.model_dump(exclude_unset=True),
    )


@app.get("/gateway/payments/summary/total")
async def get_payment_summary(_token: dict = Depends(verify_token)):
    return await forward_request("payment", "/payments/summary/total", "GET")


# Notification routes (secured)
@app.get("/gateway/notifications")
async def get_all_notifications(_token: dict = Depends(verify_token)):
    return await forward_request("notification", "/notifications", "GET")


@app.get("/gateway/notifications/{notification_id}")
async def get_notification(notification_id: int, _token: dict = Depends(verify_token)):
    return await forward_request("notification", f"/notifications/{notification_id}", "GET")


@app.get("/gateway/notifications/guest/{guest_id}")
async def get_notifications_by_guest(guest_id: int, _token: dict = Depends(verify_token)):
    return await forward_request("notification", f"/notifications/guest/{guest_id}", "GET")


@app.post("/gateway/notifications")
async def send_notification(notif: NotificationCreate, _token: dict = Depends(verify_token)):
    return await forward_request("notification", "/notifications", "POST", json=notif.model_dump())


@app.post("/gateway/notifications/from-template")
async def send_from_template(
    guest_id: int = Query(...),
    booking_id: int = Query(...),
    template_type: str = Query(...),
    channel: str = Query(...),
    recipient_email: Optional[str] = Query(None),
    recipient_phone: Optional[str] = Query(None),
    _token: dict = Depends(verify_token),
):
    params = {
        "guest_id": guest_id,
        "booking_id": booking_id,
        "template_type": template_type,
        "channel": channel,
    }
    if recipient_email is not None:
        params["recipient_email"] = recipient_email
    if recipient_phone is not None:
        params["recipient_phone"] = recipient_phone
    return await forward_request("notification", "/notifications/from-template", "POST", params=params)


@app.delete("/gateway/notifications/{notification_id}")
async def delete_notification(notification_id: int, _token: dict = Depends(verify_token)):
    return await forward_request("notification", f"/notifications/{notification_id}", "DELETE")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
