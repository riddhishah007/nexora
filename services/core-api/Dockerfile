FROM python:3.12-slim

WORKDIR /app

COPY services/core-api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services/core-api/app ./app
COPY services/worker/app ./worker
COPY services/core-api/alembic ./alembic
COPY services/core-api/alembic.ini ./alembic.ini

EXPOSE 8000

# Run migrations then start API (worker runs as merged background task inside lifespan for $0 Free tier)
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
