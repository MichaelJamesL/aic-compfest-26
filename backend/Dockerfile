FROM python:3.11-slim
WORKDIR /app
COPY ai-engine ./ai-engine
COPY backend ./backend
RUN pip install --no-cache-dir ./ai-engine ./backend
RUN useradd --create-home --uid 10001 appuser && mkdir -p /app/storage && chown -R appuser:appuser /app/storage
ENV DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/app \
    AIENGINE_DATABASE_URL=postgresql://postgres:postgres@db:5432/ai \
    STORAGE_PATH=/app/storage
EXPOSE 8000
USER appuser
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
