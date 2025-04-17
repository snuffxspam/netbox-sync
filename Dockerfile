FROM python:3.11-slim

WORKDIR /app

COPY netbox_sync.py .
COPY .env .
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt
RUN apt update && apt install cron -y

RUN echo "*/10 * * * * root cd /app && /usr/local/bin/python /app/netbox_sync.py >> /var/log/cron.log 2>&1" > /etc/cron.d/netbox-sync-cron && \
    chmod 0644 /etc/cron.d/netbox-sync-cron

RUN touch /var/log/cron.log

CMD ["sh", "-c", "cron && tail -f /var/log/cron.log"]
