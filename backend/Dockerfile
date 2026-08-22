FROM python:3.11-slim
WORKDIR /app
COPY backend/pyproject.toml ./backend/pyproject.toml
COPY ai-engine ./ai-engine
RUN pip install --no-cache-dir ./backend
COPY backend ./backend
ENV DATABASE_URL=sqlite:///./backend.db STORAGE_PATH=/app/storage
EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
