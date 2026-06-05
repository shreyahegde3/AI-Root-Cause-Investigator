# AI SQL Root Cause Investigator

A compact AI analytics app that uses a React dashboard, FastAPI backend, PostgreSQL analytics, Redis caching, and a two-model agent pipeline for root-cause analysis.

## What it does
- Accepts natural-language questions and returns a concise investigation report.
- Computes metric snapshots and period comparisons for revenue, orders, units sold, and conversion rate.
- Identifies negative contributors by dimension and adds business recommendations.
- Caches results in Redis for fast repeated responses.
- Supports local model routing with a `qwen2.5:14b` parse/RCA model and a `sqlcoder:7b` SQL model.
- Falls back to mock heuristic parsing if local LLMs are unavailable.

## Features
- React/Vite frontend with predefined investigation cards and manual query input
- FastAPI backend with `/api/health`, `/api/schema`, and `/api/investigate`
- PostgreSQL analytics engine with flexible filtering and dimension contribution analysis
- Redis cache with 10-minute TTL for repeat queries
- LangGraph-style workflow: parse -> generate SQL -> run analytics -> generate RCA
- Synthetic data generator with built-in anomaly scenarios
- Verification scripts for analytics math and agent workflow

## Quick start
1. Open the project root:
   ```bash
   cd "d:/new pr"
   ```
2. Configure `.env`:
   ```env
   OPENAI_API_KEY=mock-key
   LOCAL_LLM_BASE_URL=http://host.docker.internal:8000/v1
   LOCAL_PARSE_RCA_MODEL=qwen2.5:14b
   LOCAL_SQL_MODEL=sqlcoder:7b
   LOCAL_LLM_API_KEY=local-dev-key
   ```
3. Start all services:
   ```bash
   docker compose up -d --build
   ```
4. Initialize the data (first run):
   ```bash
   docker compose exec backend python scripts/generate_data.py
   ```
5. Open the UI:
   ```text
   http://localhost:5173
   ```

## Confirm the backend
```bash
curl -s http://localhost:8000/api/health
curl -s http://localhost:8000/api/schema
```

## Run tests
```bash
docker compose exec backend python scripts/test_analytics.py
docker compose exec backend python scripts/test_agents.py
```

## Primary example queries
- `Why did conversion drop in February?`
- `Why did revenue decrease in Bangalore during late April?`
- `Why did corporate office supplies orders drop in October?`
- `What were units sold in April 2026?`

## Notes
- Local model mode is active only when `LOCAL_LLM_BASE_URL` is reachable from the backend container.
- If local models are unavailable, the app uses a safe mock fallback.
- `.env` is ignored by git to keep secrets out of the repository.
