FROM python:3.12-slim

WORKDIR /app

COPY services/core-api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services/core-api/app ./app
COPY services/worker/app ./worker
COPY services/core-api/alembic ./alembic
COPY services/core-api/alembic.ini ./alembic.ini

ENV PYTHONPATH=/app

CMD ["python", "-m", "worker.worker"]
