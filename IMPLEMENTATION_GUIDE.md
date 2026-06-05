# Step-by-Step Implementation Guide

## Overview
This guide walks you through implementing the IMPLEMENTATION_PLAN.md step by step. We'll work systematically through 7 features.

## Step 1: Add units_sold Support
### Files to modify:
- `backend/app/services/analytics.py`
- `backend/app/agents/llm.py`
- `frontend/src/App.jsx`

### What to do:
1. In analytics.py `get_metric_aggregates()`: Add units_sold = SUM(o.quantity)
2. In analytics.py `get_dimension_breakdown()`: Add units_sold branch for SUM(o.quantity) by dimension
3. In llm.py: Update mock_parse_query() to recognize "units sold", "products sold", "quantity sold" → "units_sold"
4. In llm.py: Add units_sold to allowed metrics list
5. Update frontend suggestions to include units_sold questions

### Verification: Test with query like "Why did units sold change in April 2026?"

---

## Step 2: Add Single-Period Snapshot Mode
### Files to modify:
- `backend/app/services/analytics.py`
- `backend/app/agents/llm.py`
- `backend/app/main.py`

### What to do:
1. In analytics.py: Create new method `get_period_metrics()` that returns single period aggregates
2. In llm.py: Update mock_parse_query() to detect mode='single_period' (keywords: "in April", "for", "total in", "What were")
3. In main.py: Add branching logic in `/api/investigate` to call single_period() or compare_periods() based on mode
4. Create new `single_period()` helper in main.py that returns mode + metrics without comparison

### Verification: Test with "What were orders in April 2026?" - should return single period, not comparison

---

## Step 3: Improve Date Parsing
### Files to modify:
- `backend/app/agents/llm.py`

### What to do:
1. Expand month_map in mock_parse_query() to support all 12 months (not just Feb, April, Oct)
2. Support explicit month/year patterns like "April 2026", "March 2025"
3. For single_period mode: infer month range from parsed date
4. For comparison mode: auto-generate previous period (e.g., April 2026 vs March 2026)
5. Add validation for invalid date ranges

### Verification: Test with multiple month names and dates like "March 2026", "September 2025"

---

## Step 4: Strengthen Validation & Agent Scoping
### Files to modify:
- `backend/app/agents/llm.py`
- `backend/app/agents/graph.py` (optional)

### What to do:
1. In llm.py: Add validate_parsed_query() function to check:
   - metric in allowed list: {revenue, orders, units_sold, conversion_rate}
   - dimension in allowed list: {city, state, segment, category, region} or None
   - mode in {single_period, comparison}
   - start_date and end_date are valid dates
2. Add fallback: if LLM output invalid, use mock_parse_query()
3. Update mock_parse_query() to be more robust

### Verification: Test invalid inputs like "unknown metric xyz" - should reject gracefully

---

## Step 5: Security & Production Hardening
### Files to modify:
- `backend/app/main.py`
- `backend/app/agents/llm.py`
- `backend/app/services/cache.py` (optional)

### What to do:
1. In main.py: Create Pydantic model `InvestigateRequest` with:
   - question: str (non-empty)
   - Validate in investigate() endpoint
2. In llm.py: Add SQL safety check - reject SQL with INSERT|UPDATE|DELETE|DROP|ALTER
3. Add `.env.example` file with template of required variables
4. Ensure cache errors don't break the flow (already in place)

### Verification: Test with malformed payload and verify error response

---

## Step 6: Frontend & UX Improvements
### Files to modify:
- `frontend/src/App.jsx`

### What to do:
1. Add new suggestion cards for:
   - Single-period example: "What were units sold in April 2026?"
   - Another comparison example: "How did conversion rate change in March 2026?"
2. Update placeholder text mentioning snapshot mode
3. Ensure UI can display single-period results (no period_1)

### Verification: Test frontend suggestions and verify backend calls work

---

## Step 7: Add Tests
### Files to modify:
- `backend/scripts/test_analytics.py`
- `backend/scripts/test_agents.py`

### What to do:
1. In test_analytics.py:
   - Test get_period_metrics() for single period
   - Test units_sold metric calculation
   - Test dimension breakdown for units_sold
2. In test_agents.py:
   - Test parsing of single_period vs comparison questions
   - Test date parsing for multiple months
   - Test validation of invalid queries
   - Test fallback to mock_parse_query()

### Verification: Run tests: docker compose exec backend python scripts/test_analytics.py

---

## Implementation Order
1. **Step 1**: units_sold (analytics → llm → frontend)
2. **Step 2**: Single-period mode (analytics → llm → main.py)
3. **Step 3**: Date parsing (llm improvements)
4. **Step 4**: Validation (llm guards)
5. **Step 5**: Security (main.py + llm)
6. **Step 6**: Frontend (UI updates)
7. **Step 7**: Tests (comprehensive test coverage)

## Quick Commands
```bash
# View and edit files
nano backend/app/services/analytics.py
nano backend/app/agents/llm.py
nano backend/app/main.py
nano frontend/src/App.jsx

# Test
docker compose exec backend python scripts/test_analytics.py
docker compose exec backend python scripts/test_agents.py

# Run backend
docker compose up backend
```
