# AIC Predictive Maintenance MVP

This repository demonstrates the synchronous MVP chain: asset, SOP and maintenance-history upload; CSV sensor and QC image input; deterministic anomaly and health scoring; AI-assisted explanation; coordinator approval; technician result submission; one synchronous verification; final report; and best-effort maintenance-history write-back to the knowledge base. The app database commit is authoritative; vector ingestion is retried separately and its status is exposed honestly.

## MVP limits and compliance

The MVP deliberately does not include continuous learning, auto-tuning, automatic retraining, background jobs, automatic feedback loops, multi-machine analytics dashboards, an analysis-history page, notifications, real-time sensor streaming, live PLC/IoT integrations, ERP/CMMS integration, authentication or account management, or bulk-testing scripts. The MVP is limited to synchronous interaction, core inference with parameters static at demonstration time, and a focused UI.

This implements the rulebook boundary: “Implementasi AI wajib hanya berfokus pada fungsionalitas inferensi utama (core inference) dengan parameter yang bersifat statis pada saat demonstrasi berjalan.” There are no background jobs, schedulers, retraining loops, or automatic model updates. Demo headers are tenant scoping only, not production authentication. The real DeepSeek path requires credentials and network access; offline mode is available for local demonstration and tests.

## Run

```bash
cp .env.example .env
docker compose up --build
```

Open `http://localhost:5173`. Local backend development details are in `backend/README.md`.
