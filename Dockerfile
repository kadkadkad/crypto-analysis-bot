FROM python:3.9-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Environment
ENV PYTHONUNBUFFERED=1
ENV PORT=5001

# Expose port
EXPOSE 5001

# Run with gunicorn
CMD gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 120 web_dashboard:app
