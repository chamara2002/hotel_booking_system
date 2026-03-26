"""
API Gateway for Hotel Booking System
─────────────────────────────────────
All microservices are accessible through a SINGLE PORT (8000).
No need to remember individual service ports.

Routing table:
  /guest/*           →  Guest Service      (port 8001)
  /room/*            →  Room Service       (port 8002)
  /booking/*         →  Booking Service    (port 8003)
  /payment/*         →  Payment Service    (port 8004)
  /notification/*    →  Notification Service (port 8005)
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import httpx
import uvicorn

app = FastAPI(
    title="Hotel Booking System — API Gateway",
    description="""
## Hotel Booking System — Central API Gateway

This gateway routes all requests to the appropriate microservice.
You only need **one port (8000)** to access every service.

| Prefix | Service | Internal Port |
|--------|---------|--------------|
| `/guest` | Guest Service | 8001 |
| `/room` | Room Service | 8002 |
| `/booking` | Booking Service | 8003 |
| `/payment` | Payment Service | 8004 |
| `/notification` | Notification Service | 8005 |
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Service registry
SERVICE_REGISTRY = {
    "guest":        "http://localhost:8001",
    "room":         "http://localhost:8002",
    "booking":      "http://localhost:8003",
    "payment":      "http://localhost:8004",
    "notification": "http://localhost:8005",
}

# Helper: forward request to target service
async def forward(request: Request, target_url: str):
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Preserve method, headers, body and query params
        body = await request.body()
        headers = dict(request.headers)
        headers.pop("host", None)  # Remove host so target sets its own

        response = await client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body,
            params=dict(request.query_params),
        )
        try:
            return JSONResponse(content=response.json(), status_code=response.status_code)
        except Exception:
            return JSONResponse(content={"raw": response.text}, status_code=response.status_code)

# Gateway root
@app.get("/", tags=["Gateway"])
async def gateway_health():
    return {
        "gateway": "Hotel Booking System API Gateway",
        "status": "running",
        "port": 8000,
        "services": {name: f"{url} → /api/v1/{name}" for name, url in SERVICE_REGISTRY.items()}
    }

@app.get("/health", tags=["Gateway"])
async def check_all_services():
    """Ping all downstream services and report their status."""
    results = {}
    async with httpx.AsyncClient(timeout=3.0) as client:
        for name, url in SERVICE_REGISTRY.items():
            try:
                resp = await client.get(f"{url}/")
                results[name] = {"status": "UP", "port": url.split(":")[-1]}
            except Exception:
                results[name] = {"status": "DOWN", "port": url.split(":")[-1]}
    return {"gateway": "UP", "services": results}

# Guest Service routes 
@app.api_route("/guest/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], tags=["Guest Service"])
async def guest_proxy(path: str, request: Request):
    """Proxy to Guest Service — manage hotel guests"""
    target = f"{SERVICE_REGISTRY['guest']}/guests/{path}"
    return await forward(request, target)

@app.api_route("/guest", methods=["GET", "POST"], tags=["Guest Service"])
async def guest_proxy_root(request: Request):
    """Proxy to Guest Service root — list or create guests"""
    target = f"{SERVICE_REGISTRY['guest']}/guests"
    return await forward(request, target)

# Room Service routes 
@app.api_route("/room/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], tags=["Room Service"])
async def room_proxy(path: str, request: Request):
    """Proxy to Room Service — manage hotel rooms"""
    target = f"{SERVICE_REGISTRY['room']}/rooms/{path}"
    return await forward(request, target)

@app.api_route("/room", methods=["GET", "POST"], tags=["Room Service"])
async def room_proxy_root(request: Request):
    """Proxy to Room Service root — list or create rooms"""
    target = f"{SERVICE_REGISTRY['room']}/rooms"
    return await forward(request, target)

# Booking Service routes 
@app.api_route("/booking/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], tags=["Booking Service"])
async def booking_proxy(path: str, request: Request):
    """Proxy to Booking Service — manage reservations"""
    target = f"{SERVICE_REGISTRY['booking']}/bookings/{path}"
    return await forward(request, target)

@app.api_route("/booking", methods=["GET", "POST"], tags=["Booking Service"])
async def booking_proxy_root(request: Request):
    """Proxy to Booking Service root — list or create bookings"""
    target = f"{SERVICE_REGISTRY['booking']}/bookings"
    return await forward(request, target)

# Payment Service routes
@app.api_route("/payment/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], tags=["Payment Service"])
async def payment_proxy(path: str, request: Request):
    """Proxy to Payment Service — handle payments & refunds"""
    target = f"{SERVICE_REGISTRY['payment']}/payments/{path}"
    return await forward(request, target)

@app.api_route("/payment", methods=["GET", "POST"], tags=["Payment Service"])
async def payment_proxy_root(request: Request):
    """Proxy to Payment Service root — list or create payments"""
    target = f"{SERVICE_REGISTRY['payment']}/payments"
    return await forward(request, target)

# Notification Service routes
@app.api_route("/notification/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], tags=["Notification Service"])
async def notification_proxy(path: str, request: Request):
    """Proxy to Notification Service — send and manage notifications"""
    target = f"{SERVICE_REGISTRY['notification']}/notifications/{path}"
    return await forward(request, target)

@app.api_route("/notification", methods=["GET", "POST"], tags=["Notification Service"])
async def notification_proxy_root(request: Request):
    """Proxy to Notification Service root — list or send notifications"""
    target = f"{SERVICE_REGISTRY['notification']}/notifications"
    return await forward(request, target)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
