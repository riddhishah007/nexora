FROM nexora-phase1-core-api

# worker code added on top of core-api image (avoids re-pip-install)
COPY services/worker/app ./worker

ENV PYTHONPATH=/app

CMD ["python", "-m", "worker.worker"]
