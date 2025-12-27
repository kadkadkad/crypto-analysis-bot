#!/bin/bash
# Render Deployment Startup Script - Fixed for proper logging

echo "[STARTUP] ===== RENDER DEPLOYMENT SCRIPT ====="
echo "[STARTUP] Current Time: $(date)"
echo "[STARTUP] Python Version: $(python --version)"
echo "[STARTUP] Working Directory: $(pwd)"

echo ""
echo "[STARTUP] Starting Market Analysis Engine (Worker) in background..."
# CRITICAL FIX: Redirect output to both stdout and file for visibility
# Use nohup to prevent process from being killed
# Use unbuffered output for real-time logs
nohup python -u main.py > main.log 2>&1 &
MAIN_PID=$!
echo "[STARTUP] main.py started with PID: $MAIN_PID"

# Give main.py a few seconds to initialize
echo "[STARTUP] Waiting 5 seconds for analyzer to initialize..."
sleep 5

# Check if main.py is still running
if ps -p $MAIN_PID > /dev/null; then
    echo "[STARTUP] ✅ Market Analyzer is running (PID: $MAIN_PID)"
    # Show first few lines of log
    echo "[STARTUP] --- Main.py Initial Output ---"
    head -n 20 main.log 2>/dev/null || echo "(No logs yet)"
    echo "[STARTUP] --- End Initial Output ---"
else
    echo "[STARTUP] ❌ ERROR: main.py failed to start!"
    cat main.log 2>/dev/null
    exit 1
fi

echo ""
echo "[STARTUP] Starting Web Dashboard (Flask) via Gunicorn..."
echo "[STARTUP] Binding to 0.0.0.0:$PORT"

# Run web_dashboard via Gunicorn in the foreground
# This keeps the Render service alive
gunicorn web_dashboard:app \
    --bind 0.0.0.0:$PORT \
    --workers 1 \
    --timeout 120 \
    --log-level info \
    --access-logfile - \
    --error-logfile -
