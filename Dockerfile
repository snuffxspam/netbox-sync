FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir -r requirements.txt

COPY netbox_sync.py .
COPY .env .
COPY requirements.txt .

CMD ["python", "netbox_sync.py"]
