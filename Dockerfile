FROM python:3.9-slim

WORKDIR /app

# Sistem bağımlılıkları
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Python bağımlılıkları
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Proje dosyalarını kopyala
COPY . .

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=5001

# Önemli: Render PORT'u 10000 civarı bir şey atar, web sunucusu onu dinlemeli
EXPOSE 5001

# Hem botu hem webi çalıştıran ana dosyayı başlat
CMD ["python", "run.py"]
