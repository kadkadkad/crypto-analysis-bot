#!/bin/bash
# Render Deployment Startup Script

echo "[STARTUP] Starting Market Analysis Engine (Worker) in background..."
# Run main.py in the background
# We use --unbuffered or just redirect to stdout for Render logs
python main.py &

echo "[STARTUP] Starting Web Dashboard (Flask) via Gunicorn..."
# Run web_dashboard via Gunicorn in the foreground
# Bind to the PORT provided by Render
# Using 1 worker to stay within Free Tier memory limits (512MB)
gunicorn web_dashboard:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120
