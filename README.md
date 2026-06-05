# AI SQL Root Cause Investigator - User Manual

Welcome to the **AI SQL Root Cause Investigator**. This project is a production-oriented multi-agent analytics engineer that automatically investigates e-commerce metric anomalies using PostgreSQL, Redis caching, and LangGraph agent orchestration.

---

## 1. System Architecture & Components

The application is fully containerized and runs 4 key services:
1. **`rca-frontend` (Vite + React)**: A single-page dashboard running on port **`5173`**. Provides a search console, predefined templates, and visual report sections (summary, contributors table, confidence score, and recommendations).
2. **`rca-backend` (FastAPI)**: An API server running on port **`8000`** that hosts endpoints for health checks, schema details, and orchestrates the agent network.
3. **`rca-postgres` (PostgreSQL 15)**: The transactional data warehouse storing ~128,000 orders and ~5,800 daily traffic records, optimized with composite indexing.
4. **`rca-redis` (Redis 7)**: A caching layer storing generated SQL statements and analysis reports with a **10-minute TTL** for sub-millisecond query responses.

---

## 2. Quick Start Guide

### Step 1: Open the Workspace
Ensure you are in the project root directory:
```bash
cd "d:/new pr"
```

### Step 2: Configure OpenAI API Credentials
We support both a real LLM workflow and a rule-based mock workflow (which runs calculations on the database and generates reports without needing active API keys):
1. Open the `.env` file located in the root directory: `d:/new pr/.env`.
2. Replace `your_openai_api_key_here` with your actual OpenAI API Key:
   ```env
   OPENAI_API_KEY=sk-proj-xxxxxx...
   ```
3. Save and close the file. (If you don't have an active key, leave it as is; the system will automatically run in mock fallback mode so that it remains fully functional).

### Step 3: Launch the Services
Bring up the entire container stack using Docker Compose:
```bash
docker compose up -d
```
*(This builds the backend and frontend containers, initializes the database, validates connections, and starts the API servers in the background).*

---

## 3. Accessing the Features

### A. The Interactive Frontend Dashboard
Once the containers are online:
1. Open your web browser and navigate to **`http://localhost:5173`**.
2. You will see the **AI Root Cause Investigator** dark-mode dashboard.
3. Check the header status badge: it should display **"System Online"** (glowing green).

### B. Investigating Predefined Anomalies (One-Click Testing)
The dashboard features four quick-select suggestion cards representing the key database anomalies we simulated. Click any of them to trigger an investigation:

1. **Checkout Anomaly** (*"Why did conversion drop in February?"*):
   - **What it tests**: Calculates monthly conversion rates across the Jan-Feb boundaries.
   - **Root Cause**: Identifies a **36.13% conversion rate drop** in February 2026. Locates the largest negative impact in the **Consumer segment** (-18.02%) and the **South region** (-13.63%), pointing to a payment portal checkout failure.
2. **Regional Revenue Shock** (*"Why did revenue decrease in Bangalore during late April?"*):
   - **What it tests**: Compares Bangalore sales in the first half of April vs. the second half.
   - **Root Cause**: Locates an **82.71% sales drop** specifically in the **Electronics** category inside Bangalore during late April.
3. **Category Volume Dip** (*"Why did corporate office supplies orders drop in October?"*):
   - **What it tests**: Compares October 2025 order count vs. September 2025.
   - **Root Cause**: Detects a **70.94% order volume drop** specifically under the **Corporate segment** for **Office Supplies**.
4. **General Query Input**:
   - You can type your own custom questions into the **Console Input** and click **"Investigate"** to run the pipeline dynamically.

---

## 4. Verifying Backend Features

### A. Cache Verification (Sub-millisecond Latencies)
1. Submit an investigation request (e.g. click *"Why did conversion drop in February?"*). The first run triggers the LangGraph agent pipeline, runs SQL queries on PostgreSQL, and takes ~100–300ms.
2. Click the card a second time. The response returns **instantly (< 1ms)** because it is pulled directly from the `rca-redis` cache. The backend logs will display a `cache_hit` event.

### B. Health Status Check
You can query the backend health check via terminal to confirm database and cache connections are healthy:
```bash
curl -s http://localhost:8000/api/health
```
**Expected Output**:
```json
{"status":"healthy","database":"healthy","redis":"healthy","service":"rca-backend"}
```

### C. Database Table Schema Listing
Query the schema endpoint to inspect the available columns for customer, product, order, and traffic session tables:
```bash
curl -s http://localhost:8000/api/schema
```

---

## 5. Running Automated Verification Tests

We have created two test suites to verify that the mathematical calculations and the agent graph run correctly. You can execute these tests inside the running backend container.

### Test 1: Analytics Engine Math Test
Verifies that SQL aggregations, Month-over-Month changes, and dimension contribution ratios are mathematically correct:
```bash
docker compose exec backend python scripts/test_analytics.py
```

### Test 2: LangGraph Agent Pipeline Test
Verifies that the compiled StateGraph transitions state parameters correctly through the 4 nodes (`parse_query` -> `generate_sql` -> `run_analytics` -> `generate_rca` -> `END`):
```bash
docker compose exec backend python scripts/test_agents.py
```

---

## 6. Study Guides (Learn Modules)

For interview preparation, detailed deep dives of every technology and concept used in this project are located in the `learning/` directory:
- [`01_postgres.md`](file:///d:/new%20pr/learning/01_postgres.md): Constraints, indexing, composite B-Trees, CTE execution, and denormalization.
- [`02_fastapi.md`](file:///d:/new%20pr/learning/02_fastapi.md): Routing, ASGI async loop, dependency injection (`Depends`), and request parsing.
- [`03_redis.md`](file:///d:/new%20pr/learning/03_redis.md): Cache-aside pattern, key MD5 hashing, TTLs, and graceful degradation fallback.
- [`04_langgraph.md`](file:///d:/new%20pr/learning/04_langgraph.md): StateGraph workflows, state transitions, structured validation schemas, and LangChain comparisons.
- [`05_docker.md`](file:///d:/new%20pr/learning/05_docker.md): Orchestration, bridge networks, healthchecks, and data persistence volumes.
- [`06_agents.md`](file:///d:/new%20pr/learning/06_agents.md): Separation of concerns, model prompting constraints, and write-protected SQL generation.
