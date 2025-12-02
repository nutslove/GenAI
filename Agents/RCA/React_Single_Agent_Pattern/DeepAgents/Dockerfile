FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt
  
COPY *.py .
COPY .env .
COPY service-account-key.json .

EXPOSE 8089

CMD ["python", "-u", "alert_receiver.py"]
