# Hotel Booking System

This project runs as microservices behind an API gateway and now uses a single MongoDB database with separate collections per service.

## Database Design

- Database name: `hotel_booking_system` (configurable)
- Collections:
  - `guests` (Guest Service)
  - `rooms` (Room Service)
  - `bookings` (Booking Service)
  - `payments` (Payment Service)
  - `notifications` (Notification Service)
  - `counters` (shared for atomic integer IDs)

## Environment Setup

1. Copy `.env.example` to `.env`.
2. Update the values if needed:

```env
MONGODB_URI=mongodb+srv://<username>:<password>@cluster0.a2vsoth.mongodb.net/?appName=Cluster0
MONGODB_DB_NAME=hotel_booking_system
```

## Run (PowerShell)

```powershell
$env:MONGODB_URI="mongodb+srv://<username>:<password>@cluster0.a2vsoth.mongodb.net/?appName=Cluster0"
$env:MONGODB_DB_NAME="hotel_booking_system"

# Start services manually in separate terminals or use your start script for bash environments
```

## Notes

- Each service creates its own indexes at startup.
- Credentials should stay in environment variables, not in source code.
- API contracts are unchanged, so your existing gateway routes continue to work.
