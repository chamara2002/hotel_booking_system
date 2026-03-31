# Hotel Booking System (Microservices)

This project contains a FastAPI-based hotel booking platform built using microservices and an API Gateway.

## Services

- API Gateway: port 8000
- Guest Service: port 8001
- Room Service: port 8002
- Booking Service: port 8003
- Payment Service: port 8004
- Notification Service: port 8005

## Prerequisites

- Python 3.10+
- MongoDB (local or remote)

## Environment Setup

1. Create or edit `.env` in the project root.
2. Set the required values in `.env`.

Required environment variables:

- `MONGODB_URI`
- `MONGODB_DB_NAME`
- `JWT_SECRET_KEY`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`

Optional overrides:

- `GUEST_SERVICE_URL`
- `ROOM_SERVICE_URL`

## Install Dependencies

Use the project virtual environment and install dependencies per service.

```powershell
# From project root
.\venv\Scripts\python.exe -m pip install -r api_gateway\requirements.txt
.\venv\Scripts\python.exe -m pip install -r services\guest_service\requirements.txt
.\venv\Scripts\python.exe -m pip install -r services\room_service\requirements.txt
.\venv\Scripts\python.exe -m pip install -r services\booking_service\requirements.txt
.\venv\Scripts\python.exe -m pip install -r services\payment_service\requirements.txt
.\venv\Scripts\python.exe -m pip install -r services\notification_service\requirements.txt
```

## Run All Services

```powershell
.\start_all.ps1
```

Stop all services:

```powershell
.\start_all.ps1 -Stop
```

## API Documentation

- Gateway Swagger: http://localhost:8000/docs
- Guest Swagger: http://localhost:8001/docs
- Room Swagger: http://localhost:8002/docs
- Booking Swagger: http://localhost:8003/docs
- Payment Swagger: http://localhost:8004/docs
- Notification Swagger: http://localhost:8005/docs

## Authentication

1. Call `POST /login` from API Gateway with admin credentials.
2. Use returned Bearer token for secured gateway routes.

