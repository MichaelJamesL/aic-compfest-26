# 3.12 matches the host virtualenvs, so a warm uv cache mounted from the host
# has wheels with the right tags instead of re-resolving everything for 3.11.
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY ai-engine ./ai-engine
COPY backend ./backend

# torch first, alone, and explicitly from the CPU index: PyPI's torch is the CUDA
# build (~2.5GB of nvidia wheels this image will never use). pip ignores the
# [tool.uv.sources] pin in ai-engine/pyproject.toml, uv honours it only for its
# own project resolution, so the index is named here rather than assumed.
#
# The second install must NOT see the torch index: uv takes a package only from
# the first index that carries it, and that mirror pins an ancient `requests`
# that fastembed rejects. torch is already satisfied by then, so PyPI is enough.
#
# The cache mount keeps anomalib + torch (~1.8GB) out of every later rebuild.
# Seed it from an existing uv cache with:
#   docker buildx build --build-context uvcache=$HOME/.cache/uv ...
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    uv pip install --system --index-url https://download.pytorch.org/whl/cpu \
        torch torchvision \
 && uv pip install --system "./ai-engine[vision]" ./backend

RUN useradd --create-home --uid 10001 appuser && mkdir -p /app/storage && chown -R appuser:appuser /app/storage
ENV DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/app \
    AIENGINE_DATABASE_URL=postgresql://postgres:postgres@db:5432/ai \
    STORAGE_PATH=/app/storage
EXPOSE 8000
USER appuser
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
