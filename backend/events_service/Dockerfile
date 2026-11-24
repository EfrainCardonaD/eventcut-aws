FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY events_service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY events_service /app/events_service

EXPOSE 8001

CMD ["uvicorn", "events_service.main:app", "--host", "0.0.0.0", "--port", "8001"]
