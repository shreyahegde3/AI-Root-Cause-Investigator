# Resume-Ready Feature Implementation Plan

This document describes how to evolve the current project into a stronger, resume-ready analytics product while staying coherent with the existing architecture.

It is intentionally scoped to the repo contents and does not add unnecessary files or out-of-scope features.

---

## Goal

Enhance the current FastAPI + LangGraph + Redis analytics system so it can:
- support additional business metrics such as `units_sold`
- support both single-period snapshot analytics and period-over-period comparisons
- parse more natural date expressions reliably
- keep the existing agent workflow, while improving agent scope and validation
- add production-minded security and safety improvements

---

## Summary of files to update

- `backend/app/main.py`
- `backend/app/agents/graph.py`
- `backend/app/agents/llm.py`
- `backend/app/services/analytics.py`
- `backend/app/services/cache.py` (optional hardening)
- `frontend/src/App.jsx`
- `README.md` (optional documentation update)

Do not create new backend service files unless the feature requires it. Most work fits inside the current backend structure.

---

## 1. Add a new metric: `units_sold`

### Why

The current backend only calculates:
- `revenue` = `SUM(price * quantity)`
- `orders` = `COUNT(order_id)`
- `conversion_rate`

A `units_sold` metric will support questions like “How many products were sold in April 2026?” and make the system look richer.

### What to change

1. `backend/app/services/analytics.py`
   - In `get_metric_aggregates()`, return `units_sold` as `SUM(o.quantity)`.
   - In `get_dimension_breakdown()`, add a branch for `metric == 'units_sold'` and compute `SUM(o.quantity)` grouped by the requested dimension.
   - Ensure the same filter and join handling works for `segment`, `city`, `state`, `region`, and `category`.

2. `backend/app/agents/llm.py`
   - Update `mock_parse_query()` and rule-based heuristics to map phrases like:
     - `products sold`, `units sold`, `quantity sold` → `units_sold`
   - Update the structured `QueryIntent` comments and the real LLM prompt allowed metrics list to include `units_sold`.
   - If `is_mock_llm` is active, ensure `mock_generate_sql()` can produce `SUM(o.quantity)` for `units_sold`.

3. `backend/app/agents/graph.py`
   - No major change required if `metric` can now be `units_sold`.
   - The agent flow should continue to support the new metric in SQL generation and analytics.

4. Frontend
   - Update `frontend/src/App.jsx` suggestion templates or placeholders to include `units_sold` as a supported question type.

### Verification

- Use a question like: `Why did units sold change in April 2026?`
- Confirm `/api/investigate` returns a valid response without errors.

---

## 2. Add single-period snapshot analytics mode

### Why

The project is currently comparison-only. Supporting single-period analytics makes it more useful for real business questions and improves resume value.

### What to change

1. `backend/app/main.py`
   - Update `investigate()` to support both comparison and single-period results.
   - Use the parsed output to choose between:
     - `compare_periods()` for comparison mode
     - a new `single_period()` method for snapshot mode

2. `backend/app/services/analytics.py`
   - Add a `get_period_metrics()` or `single_period_metrics()` helper that returns metrics for a single range.
   - It should return the same structure as `get_metric_aggregates()` but without any comparison fields.
   - Keep the comparison path separate, so snapshot mode does not compute `period_1`.

3. `backend/app/agents/llm.py`
   - Update `mock_parse_query()` to detect single-period questions by identifying phrases such as:
     - `in April 2026`
     - `for April 2026`
     - `total in April`
   - Set a new output field such as `mode: 'single_period' | 'comparison'`.
   - In the LLM prompt, describe the two modes clearly and ask the model to return the correct mode.

4. `backend/app/agents/graph.py`
   - Adjust the agent graph if needed so that the analytics node can handle either:
     - comparison results, or
     - snapshot results
   - If the graph remains linear, have the analytics node branch based on `state['mode']`.

5. Frontend
   - Update the placeholder and suggestions to include snapshot questions such as:
     - `What were units sold in April 2026?`
     - `How many orders did Bangalore have in March 2026?`

### Verification

- Test with a single-period question and confirm response includes a single `period` result.
- Verify the comparison flow still works.

---

## 3. Improve natural date parsing

### Why

The backend currently relies on limited fixed heuristics for February / April / October. Improving date parsing makes the app much more flexible and less template-based.

### What to change

1. `backend/app/agents/llm.py`
   - Expand `mock_parse_query()` to detect explicit month/year combinations beyond current patterns.
   - Support terms such as `April 2026`, `March 2026`, `Q1 2026`, `September 2025`, and year-only date references.
   - Detect explicit date ranges and relative phrases if possible, but start with explicit month parsing.

2. Prompt redesign
   - Modify the real LLM prompt to say:
     - `If the user asks about a single period, return mode=single_period and a single start/end date.`
     - `If the user asks about a comparison, infer the previous period automatically for monthly comparisons.`
   - Provide examples for both snapshot and comparison questions.

3. Query validation
   - In `backend/app/main.py` or in a new helper, normalize the parsed dates and reject invalid ranges early.

### Verification

- Ask questions such as:
  - `What were orders in April 2026?`
  - `Why did revenue change in March 2026?`
  - `How did conversion rate perform in October 2025?`

---

## 4. Strengthen agent scoping and validation

### Why

A clean agent architecture with validation improves maintainability and makes the system appear production-ready.

### What to change

1. Define agent responsibilities clearly in `backend/app/agents/graph.py`:
   - `parse_query` → parse metric, mode, date ranges, and filters
   - `generate_sql` → build safe SQL for the requested metric and dimensions
   - `run_analytics` → execute queries and compute results
   - `generate_rca` → create the summary output

2. Add explicit validation in the parsing stage:
   - reject unsupported metrics or dimensions
   - reject invalid or missing dates
   - reject questions that are clearly outside the current domain

3. Add guardrail behavior in `backend/app/agents/llm.py`:
   - if the LLM returns invalid output, fallback to the `mock_parse_query()` heuristics
   - keep the existing `is_mock_llm` fallback path and make it resilient

4. Add structured schema enforcement in the LLM prompt:
   - include allowed values for `metric` and `mode`
   - ask the LLM to only return allowed dimensions: `city`, `state`, `segment`, `category`, `region`

### Verification

- Confirm that malformed questions do not crash the backend.
- Confirm that invalid or unsupported metric text is rejected gracefully.

---

## 5. Security and production hardening

### Why

Security improvements make the project stronger for resume claims and more reliable in a real deployment.

### What to change

1. Input validation
   - Convert `investigate()` payload handling in `backend/app/main.py` to use a Pydantic model instead of raw `dict`.
   - Validate `question` exists and is non-empty.
   - Validate any future structured input fields if you add them.

2. SQL safety
   - Keep SQL generation read-only only.
   - In `backend/app/agents/llm.py`, guard `mock_generate_sql()` and any LLM fallback SQL generation so that it never issues data-modifying SQL.
   - Optionally add a SQL safety check before execution (simple string check for `INSERT|UPDATE|DELETE|DROP|ALTER`).

3. Cache resilience
   - `backend/app/services/cache.py` already has fallback logic. Keep it and ensure Redis errors do not break the investigation flow.

4. Secrets
   - Do not check in real API keys.
   - If needed, add a `.env.example` file rather than storing `.env` in source control.

5. Optional API protection
   - Add API-key or JWT validation for `/api/investigate` if the product is presented as a deployed service.
   - This is optional for resume value, but worth noting as a future enhancement.

### Verification

- Confirm investigation still works if Redis is unavailable.
- Confirm the app rejects invalid payloads and logs errors.

---

## 6. Frontend and UX improvements

### Why

A polished user interface adds resume polish and makes the analytics product easier to demo.

### What to change

1. `frontend/src/App.jsx`
   - Add example questions for the new `units_sold` and single-period modes.
   - Update the placeholder text to mention snapshot queries.
   - Optionally add a second suggestion card for a single-period question such as:
     - `What were units sold in April 2026?`

2. Result display
   - The UI already supports summary, contributors, confidence, and recommendations.
   - If you add single-period results, ensure the UI can display them without requiring comparison labels.

### Verification

- Confirm the frontend can still call `/api/investigate` successfully.
- Confirm a new question appears in the suggestion cards and yields output.

---

## 7. Testing and validation

### Why

Test coverage is essential to make this project look credible for interviews.

### What to change

1. Add or extend tests in `backend/scripts/test_analytics.py` and `backend/scripts/test_agents.py` for:
   - `units_sold` aggregation
   - single-period snapshot mode
   - parsing of explicit month/year questions
   - comparison mode still working correctly
   - cache fallback behavior

2. Use direct backend calls in tests rather than only UI tests.

### Verification

- Run:
  - `docker compose exec backend python scripts/test_analytics.py`
  - `docker compose exec backend python scripts/test_agents.py`

---

## 8. Keep scope tight

This plan does not include:
- adding a new frontend framework
- adding a second backend service
- building a full NLP search engine
- adding features unrelated to the current analytics and agent workflow

The plan remains within the existing repo and uses the current system architecture.

---

## Recommended implementation order

1. Add `units_sold` support in analytics and query parsing.
2. Add single-period mode and a supporting backend result path.
3. Improve date parsing heuristics and LLM prompts.
4. Add explicit validation and agent scoping.
5. Harden security and cache resilience.
6. Update frontend prompts and result handling.
7. Extend tests for the new functionality.

---

## Resume value summary

After implementing this plan, you can credibly state that you:
- built a multi-agent analytics engine with flexible natural language query support
- extended the system with new business metrics and single-period snapshot analytics
- authored safe, production-minded SQL generation and caching
- added input validation, fallback behavior, and security hardening
- maintained a clean, modular backend and a responsive React dashboard
