#!/bin/bash
# start_production.sh — Startup script for Docker production environment

echo "Checking database connectivity and running migrations..."
# Run alembic migrations to head
alembic upgrade head

echo "Starting Gunicorn server..."
# Start Gunicorn
exec gunicorn main:app \
     --worker-class uvicorn.workers.UvicornWorker \
     --workers 4 \
     --bind 0.0.0.0:8000 \
     --timeout 120 \
     --graceful-timeout 30 \
     --max-requests 1000 \
     --max-requests-jitter 100 \
     --access-logfile - \
     --error-logfile - \
     --log-level info
