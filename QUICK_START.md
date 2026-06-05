# Quick Start: Implementing the Feature Plan

## What You Have
- **IMPLEMENTATION_PLAN.md** - Full detailed plan with rationale for each feature
- **IMPLEMENTATION_GUIDE.md** - Step-by-step guide organized by feature
- Current codebase with key files already identified

## The 7 Features (in order)

### 1. Add units_sold Support (Analytics Foundation)
- Add SUM(quantity) calculation to analytics.py
- Update LLM to recognize "units sold", "products sold" phrases
- Add frontend suggestion cards

### 2. Add Single-Period Mode (Core Feature)
- Create get_period_metrics() method in analytics
- Update llm.py to detect single-period vs comparison questions
- Add branching logic in main.py endpoint

### 3. Improve Date Parsing (Robustness)
- Support all 12 months (currently only Feb, April, Oct)
- Auto-infer previous period for comparisons
- Add date validation

### 4. Validation & Agent Scoping (Production Ready)
- Add validate_parsed_query() function
- Check allowed metrics: {revenue, orders, units_sold, conversion_rate}
- Check allowed dimensions: {city, state, segment, category, region}
- Add LLM fallback to mock parsing

### 5. Security Hardening (Trust Building)
- Pydantic model for request validation in main.py
- SQL safety checks (no INSERT/UPDATE/DELETE/DROP)
- Add .env.example file

### 6. Frontend Polish (UX)
- New suggestion cards for units_sold + single-period
- Update placeholder text
- Ensure UI handles single-period results

### 7. Comprehensive Tests (Credibility)
- Unit tests for analytics (units_sold, single_period)
- Unit tests for parsing (multi-month dates, modes)
- Integration tests for validation

## Key Files to Edit

```
backend/app/services/analytics.py   → Add units_sold & get_period_metrics()
backend/app/agents/llm.py           → Improve parsing, add validation
backend/app/main.py                 → Add branching, Pydantic model
frontend/src/App.jsx                → Add suggestion cards
backend/scripts/test_analytics.py    → Add metric & period tests
backend/scripts/test_agents.py       → Add parsing tests
.env.example                        → Create env template
```

## Resume Value
After implementing, you can claim:
- "Built multi-agent analytics engine with flexible NLP query support"
- "Extended system with new business metrics + snapshot analytics"
- "Implemented safe SQL generation with input validation"
- "Added production security hardening and fallback behavior"
- "Created responsive React dashboard with intelligent suggestions"

## Next Steps
1. Open IMPLEMENTATION_GUIDE.md for detailed step-by-step instructions
2. Start with Step 1: units_sold support
3. Test each feature as you complete it
4. Run: `docker compose exec backend python scripts/test_analytics.py`
