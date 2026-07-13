FROM med-audit:latest

WORKDIR /app

COPY wheels /wheels
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-index --find-links=/wheels --upgrade -r /tmp/requirements.txt

COPY backend /app

ENTRYPOINT []
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 CMD curl -fsS http://127.0.0.1:8000/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--workers", "1"]
