#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# start_all.sh  —  Starts all Hotel Booking System microservices + API Gateway
# ─────────────────────────────────────────────────────────────────────────────
# Usage:
#   chmod +x start_all.sh
#   ./start_all.sh          # start all services
#   ./start_all.sh stop     # kill all services

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
PIDS_FILE="$BASE_DIR/.pids"

start_service() {
  local NAME=$1
  local DIR=$2
  local PORT=$3

  echo "Starting $NAME on port $PORT ..."
  cd "$DIR"
  pip install -r requirements.txt -q
  uvicorn main:app --host 0.0.0.0 --port "$PORT" --reload &
  echo $! >> "$PIDS_FILE"
  echo "$NAME started (PID $!)"
  cd "$BASE_DIR"
}

stop_all() {
  if [ -f "$PIDS_FILE" ]; then
    echo "Stopping all services..."
    while read -r pid; do
      kill "$pid" 2>/dev/null && echo "  Killed PID $pid"
    done < "$PIDS_FILE"
    rm "$PIDS_FILE"
    echo "All services stopped."
  else
    echo "No running services found."
  fi
}

if [ "$1" = "stop" ]; then
  stop_all
  exit 0
fi

# Clear old PIDs
rm -f "$PIDS_FILE"

echo ""
echo "Hotel Booking System — Starting All Services"
echo "=================================================="

start_service "Guest Service"        "$BASE_DIR/services/guest_service"        8001
start_service "Room Service"         "$BASE_DIR/services/room_service"         8002
start_service "Booking Service"      "$BASE_DIR/services/booking_service"      8003
start_service "Payment Service"      "$BASE_DIR/services/payment_service"      8004
start_service "Notification Service" "$BASE_DIR/services/notification_service" 8005

echo ""
echo "Waiting 3 seconds for services to initialize..."
sleep 3

start_service "API Gateway"          "$BASE_DIR/api_gateway"                   8000

echo ""
echo "=================================================="
echo "All services are running!"
echo ""
echo "  API Gateway (single entry point):"
echo "  → http://localhost:8000/docs"
echo ""
echo "  Individual Service Swagger Docs:"
echo "  → Guest Service:        http://localhost:8001/docs"
echo "  → Room Service:         http://localhost:8002/docs"
echo "  → Booking Service:      http://localhost:8003/docs"
echo "  → Payment Service:      http://localhost:8004/docs"
echo "  → Notification Service: http://localhost:8005/docs"
echo ""
echo "  Run './start_all.sh stop' to stop all services."
echo "=================================================="
