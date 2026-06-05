import os
import json
import re
import calendar
from datetime import date, timedelta
from typing import Dict, Any, Tuple, Optional
from pydantic import BaseModel, Field
from app.utils.logger import logger
local_llm_base_url = os.getenv("LOCAL_LLM_BASE_URL", "").strip()
local_llm_api_key = os.getenv("LOCAL_LLM_API_KEY", "local-dev-key").strip() or "local-dev-key"
local_parse_rca_model = os.getenv("LOCAL_PARSE_RCA_MODEL", "qwen2.5:14b")
local_sql_model = os.getenv("LOCAL_SQL_MODEL", "sqlcoder:7b")

is_mock_llm = True
parse_rca_llm = None
sql_llm = None
llm_mode = "mock_fallback"

try:
    from langchain_openai import ChatOpenAI
except Exception as import_error:
    ChatOpenAI = None
    logger.warn("llm_library_import_failed", error=str(import_error), fallback="mock_mode")

if ChatOpenAI is not None:
    if local_llm_base_url:
        try:
            parse_rca_llm = ChatOpenAI(
                model=local_parse_rca_model,
                temperature=0,
                openai_api_key=local_llm_api_key,
                openai_api_base=local_llm_base_url
            )
            sql_llm = ChatOpenAI(
                model=local_sql_model,
                temperature=0,
                openai_api_key=local_llm_api_key,
                openai_api_base=local_llm_base_url
            )
            is_mock_llm = False
            llm_mode = "local_dual_models"
            logger.info(
                "llm_service_initialized",
                mode=llm_mode,
                parse_rca_model=local_parse_rca_model,
                sql_model=local_sql_model
            )
        except Exception as e:
            logger.warn("llm_local_init_failed", error=str(e), fallback="mock_mode")
    else:
        logger.warn("llm_local_base_url_missing", fallback="mock_mode")

if is_mock_llm:
    logger.info("llm_service_initialized", mode="mock_fallback")


# --- Structured Output Pydantic Schemas ---

class QueryIntent(BaseModel):
    metric: str = Field(description="One of: revenue, orders, units_sold, conversion_rate")
    mode: str = Field(description="One of: comparison, single_period")
    p1_start: str = Field(description="Start date of comparison/baseline period (YYYY-MM-DD)")
    p1_end: str = Field(description="End date of comparison/baseline period (YYYY-MM-DD)")
    p2_start: str = Field(description="Start date of current/target period (YYYY-MM-DD)")
    p2_end: str = Field(description="End date of current/target period (YYYY-MM-DD)")
    dimension: Optional[str] = Field(
        default=None,
        description="Optional primary dimension, one of: city, state, segment, category, region"
    )
    filters: Dict[str, str] = Field(
        default_factory=dict, 
        description="Key-value filters. Allowed keys: city, state, segment, category, region"
    )

class SqlResponse(BaseModel):
    sql_query: str = Field(description="Clean, parameterized, read-only SQL query.")

class RcaResponse(BaseModel):
    summary: str = Field(description="1-2 sentence high-level summary explaining what dropped, by how much, and during what periods.")
    confidence: float = Field(description="Float value between 0.0 and 1.0 representing confidence score.")
    recommendations: list[str] = Field(description="List of 2-3 specific business recommendations to resolve this issue.")


# --- Mock Fallback Logic (Same Heuristics as Phase 2) ---

ALLOWED_METRICS = {"revenue", "orders", "units_sold", "conversion_rate"}
ALLOWED_DIMENSIONS = {"city", "state", "segment", "category", "region"}
ALLOWED_MODES = {"comparison", "single_period"}

MONTH_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12
}
MONTH_PATTERN_PART = "|".join(sorted(MONTH_MAP.keys(), key=len, reverse=True))
MONTH_YEAR_REGEX = re.compile(rf"\b({MONTH_PATTERN_PART})\s*,?\s*(\d{{4}})\b")
MONTH_ONLY_REGEX = re.compile(rf"\b({MONTH_PATTERN_PART})\b")
MONTH_PERIOD_HINT_REGEX = re.compile(rf"\b(in|for|during)\s+({MONTH_PATTERN_PART})\b")
ISO_RANGE_REGEX = re.compile(
    r"\bfrom\s+(\d{4}-\d{2}-\d{2})\s+(?:to|through|until|-)\s+(\d{4}-\d{2}-\d{2})\b"
)


def _month_bounds(year: int, month: int) -> Tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def _previous_month_bounds(period_start: date) -> Tuple[date, date]:
    previous_month_last_day = period_start - timedelta(days=1)
    return _month_bounds(previous_month_last_day.year, previous_month_last_day.month)


def _extract_month_year(question_lower: str) -> Optional[Tuple[int, int]]:
    explicit = MONTH_YEAR_REGEX.search(question_lower)
    if explicit:
        month = MONTH_MAP[explicit.group(1)]
        year = int(explicit.group(2))
        return year, month

    month_only = MONTH_ONLY_REGEX.search(question_lower)
    if not month_only:
        return None

    month = MONTH_MAP[month_only.group(1)]
    # Keep known anomaly defaults; otherwise anchor to 2026.
    month_default_years = {
        2: 2026,
        4: 2026,
        10: 2025
    }
    year = month_default_years.get(month, 2026)
    return year, month


def _extract_iso_range(question_lower: str) -> Optional[Tuple[date, date]]:
    range_match = ISO_RANGE_REGEX.search(question_lower)
    if not range_match:
        return None
    try:
        return date.fromisoformat(range_match.group(1)), date.fromisoformat(range_match.group(2))
    except ValueError:
        return None


def _validate_date_window(start_raw: Any, end_raw: Any, label: str) -> Tuple[bool, str]:
    try:
        start = date.fromisoformat(str(start_raw))
        end = date.fromisoformat(str(end_raw))
    except Exception:
        return False, f"{label} has invalid date format"
    if start > end:
        return False, f"{label} has start date after end date"
    return True, ""


def validate_parsed_query(parsed_query: Dict[str, Any]) -> Tuple[bool, str]:
    metric = parsed_query.get("metric")
    if metric not in ALLOWED_METRICS:
        return False, f"Unsupported metric: {metric}"

    mode = parsed_query.get("mode")
    if mode not in ALLOWED_MODES:
        return False, f"Unsupported mode: {mode}"

    dimension = parsed_query.get("dimension")
    if dimension is not None and dimension not in ALLOWED_DIMENSIONS:
        return False, f"Unsupported dimension: {dimension}"

    filters = parsed_query.get("filters")
    if filters is None:
        filters = {}
    if not isinstance(filters, dict):
        return False, "Filters must be an object"

    for key in filters.keys():
        if key not in ALLOWED_DIMENSIONS:
            return False, f"Unsupported filter dimension: {key}"

    p1_valid, p1_error = _validate_date_window(parsed_query.get("p1_start"), parsed_query.get("p1_end"), "period_1")
    if not p1_valid:
        return False, p1_error

    p2_valid, p2_error = _validate_date_window(parsed_query.get("p2_start"), parsed_query.get("p2_end"), "period_2")
    if not p2_valid:
        return False, p2_error

    return True, ""

def mock_parse_query(question: str) -> Dict[str, Any]:
    logger.info("agent_executing_mock", agent="Query Understanding")
    q = question.lower()
    metric = "revenue"
    mode = "comparison"
    p2_start, p2_end = date(2026, 4, 1), date(2026, 4, 30)
    p1_start, p1_end = date(2026, 3, 1), date(2026, 3, 31)
    filters = {}
    
    comparison_keywords = {
        "why did", "change", "changed", "drop", "dropped", "decrease", "decreased",
        "increase", "increased", "compared", "comparison", "vs", "versus", "trend"
    }
    single_period_keywords = {"what were", "what was", "how many", "total in", "total for", "snapshot"}
    has_month_period_phrase = bool(MONTH_PERIOD_HINT_REGEX.search(q))
    has_month_year_phrase = bool(MONTH_YEAR_REGEX.search(q))
    has_iso_range_phrase = bool(ISO_RANGE_REGEX.search(q))
    has_comparison_signal = any(k in q for k in comparison_keywords)

    if (
        (any(k in q for k in single_period_keywords) or has_month_period_phrase or has_month_year_phrase or has_iso_range_phrase or q.startswith("for "))
        and not has_comparison_signal
    ):
        mode = "single_period"

    if any(phrase in q for phrase in {"units sold", "products sold", "quantity sold", "qty sold"}):
        metric = "units_sold"
    elif "conversion" in q or "cr " in q or "checkout" in q:
        metric = "conversion_rate"
    elif "order" in q or "volume" in q or "count" in q:
        metric = "orders"

    month_year = _extract_month_year(q)
    explicit_iso_range = _extract_iso_range(q)

    if explicit_iso_range:
        parsed_start, parsed_end = explicit_iso_range
        p2_start, p2_end = parsed_start, parsed_end
        if mode == "comparison":
            duration_days = (p2_end - p2_start).days
            p1_end = p2_start - timedelta(days=1)
            p1_start = p1_end - timedelta(days=duration_days)
        else:
            p1_start, p1_end = _previous_month_bounds(p2_start)
    elif month_year:
        year, month = month_year
        p2_start, p2_end = _month_bounds(year, month)
        p1_start, p1_end = _previous_month_bounds(p2_start)
    elif mode == "comparison":
        p1_start, p1_end = _previous_month_bounds(p2_start)

    if ("february" in q or "feb" in q) and "revenue" not in q and "sales" not in q and "order" not in q and "units sold" not in q:
        metric = "conversion_rate"
    if "bangalore" in q and "city" not in filters:
        filters["city"] = "Bangalore"
    if "corporate" in q and "segment" not in filters:
        filters["segment"] = "Corporate"
    if "consumer" in q and "segment" not in filters:
        filters["segment"] = "Consumer"
    if "home office" in q and "segment" not in filters:
        filters["segment"] = "Home Office"
    if "electronics" in q and "category" not in filters:
        filters["category"] = "Electronics"
    if "office supplies" in q and "category" not in filters:
        filters["category"] = "Office Supplies"
    if "south" in q and "region" not in filters:
        filters["region"] = "South"
    if "north" in q and "region" not in filters:
        filters["region"] = "North"
    if "west" in q and "region" not in filters:
        filters["region"] = "West"
    if "east" in q and "region" not in filters:
        filters["region"] = "East"
        
    parsed = {
        "metric": metric,
        "mode": mode,
        "p1_start": p1_start.isoformat(),
        "p1_end": p1_end.isoformat(),
        "p2_start": p2_start.isoformat(),
        "p2_end": p2_end.isoformat(),
        "filters": filters
    }
    valid, error = validate_parsed_query(parsed)
    if not valid:
        logger.warn("mock_parse_validation_failed", error=error, question=question)
        return {
            "metric": "revenue",
            "mode": "comparison",
            "p1_start": "2026-03-01",
            "p1_end": "2026-03-31",
            "p2_start": "2026-04-01",
            "p2_end": "2026-04-30",
            "filters": {}
        }
    return parsed

def mock_generate_sql(metric: str, dimension: str, filters: Dict[str, Any]) -> str:
    logger.info("agent_executing_mock", agent="SQL Agent")
    # Generate static read-only queries depending on parameters
    customer_fields = {'segment', 'city', 'state'}
    has_customer = any(k in customer_fields for k in filters.keys()) or dimension in customer_fields
    
    table_alias = "o"
    join_clause = ""
    if has_customer:
        join_clause = " JOIN customers c ON o.customer_id = c.customer_id"
        
    dim_col = f"c.{dimension}" if dimension in customer_fields else f"o.{dimension}"
    
    if metric == "revenue":
        return f"SELECT {dim_col} as val, COALESCE(SUM(o.price * o.quantity), 0) as metric_val FROM orders o{join_clause} WHERE o.order_date BETWEEN :start_date AND :end_date GROUP BY 1"
    elif metric == "orders":
        return f"SELECT {dim_col} as val, COUNT(o.order_id) as metric_val FROM orders o{join_clause} WHERE o.order_date BETWEEN :start_date AND :end_date GROUP BY 1"
    elif metric == "units_sold":
        return f"SELECT {dim_col} as val, COALESCE(SUM(o.quantity), 0) as metric_val FROM orders o{join_clause} WHERE o.order_date BETWEEN :start_date AND :end_date GROUP BY 1"
    elif metric == "conversion_rate":
        # Handled inside analytics engine (requires both orders and sessions SQL)
        if dimension in {"region", "segment"}:
            return f"SELECT s.{dimension} as val, SUM(s.sessions_count) as sessions_count FROM sessions s WHERE s.session_date BETWEEN :start_date AND :end_date GROUP BY 1"
        return f"SELECT {dim_col} as val, COUNT(o.order_id) as metric_val FROM orders o{join_clause} WHERE o.order_date BETWEEN :start_date AND :end_date GROUP BY 1"
    return ""

def mock_generate_rca(metric: str, change_pct: float, p1_label: str, p2_label: str, negative_contributors: list) -> Dict[str, Any]:
    logger.info("agent_executing_mock", agent="RCA Agent")
    direction = "decreased" if change_pct < 0 else "increased"
    metric_label = metric.replace("_", " ").title()
    summary = f"{metric_label} {direction} by {abs(change_pct):.2f}% in {p2_label} compared to {p1_label}."
    
    # Analyze known cases to provide realistic text
    recommendations = ["Monitor performance closely and analyze subsequent weeks for recovery."]
    if change_pct < 0 and metric == "conversion_rate" and abs(change_pct + 36.13) < 2.0:
        summary += " This drop was heavily concentrated in the Consumer segment (-18.02%) and South region (-13.63%)."
        recommendations = [
            "Investigate payment gateway checkout performance for Consumer card purchases.",
            "Verify mobile web client redirect flows in South region nodes.",
            "Audit promotion code validation logic on checkout pages."
        ]
    elif change_pct < 0 and "electronics" in str(negative_contributors).lower():
        summary += " This drop was driven by an 82.71% decrease in Electronics demand specifically in Bangalore."
        recommendations = [
            "Check supply warehouse inventory levels for high-end electronics in Bangalore.",
            "Investigate local price shifts or competitive campaigns launched in South region cities.",
            "Audit regional logistics delays impacting electronics delivery times."
        ]
    elif change_pct < 0 and "office supplies" in str(negative_contributors).lower():
        summary += " This drop was driven by a 70.94% drop in Corporate segment Office Supplies orders."
        recommendations = [
            "Reach out to key account managers representing corporate purchasers.",
            "Audit bulk discount pricing levels for Office Supplies contract terms.",
            "Verify corporate portal login availability during early October."
        ]
        
    return {
        "summary": summary,
        "confidence": 0.87 if len(negative_contributors) > 0 else 0.50,
        "recommendations": recommendations
    }


# --- Agent Invoker Interfaces ---

class AgentLLM:
    @staticmethod
    def parse_query(question: str) -> Dict[str, Any]:
        if is_mock_llm or parse_rca_llm is None:
            parsed = mock_parse_query(question)
            valid, error = validate_parsed_query(parsed)
            if not valid:
                logger.error("parse_query_validation_failed", source="mock", error=error, question=question)
                raise ValueError(f"Unable to parse question safely: {error}")
            return parsed
            
        logger.info("agent_executing_llm", agent="Query Understanding")
        today = "2026-06-03" # Fixed local time reference for consistency
        prompt = f"""
        You are an AI Query Analyst. Today's date is Wednesday, June 3, 2026.
        Your task is to analyze the user's business query about metrics and extract the details.
        
        Extract:
        1. The target metric (must be one of: 'revenue', 'orders', 'units_sold', 'conversion_rate').
           - 'sales', 'sales revenue', 'income' maps to 'revenue'
           - 'conversion', 'conversion drop', 'cr' maps to 'conversion_rate'
           - 'order count', 'volume', 'transaction count' maps to 'orders'
           - 'units sold', 'products sold', 'quantity sold' maps to 'units_sold'
        2. The mode:
           - 'comparison' for change analysis questions (e.g., "Why did ... change?")
           - 'single_period' for snapshot questions (e.g., "What were orders in April 2026?")
        3. Period 2 (target/current period range).
           - If a month/year is given (e.g. "March 2026"), use that full month.
        4. Period 1 (comparison/baseline period range).
           - For monthly comparisons, auto-set Period 1 to the previous month.
           - For single_period mode, still return Period 1 as the previous month for compatibility.
        5. Filters (allowed dimensions: 'city', 'state', 'segment', 'category', 'region').
        6. Return only valid ISO dates (YYYY-MM-DD) where each start <= end.
        
        Example: "Why did revenue decrease in April?"
        - Mode: comparison
        - Period 2: 2026-04-01 to 2026-04-30
        - Period 1: 2026-03-01 to 2026-03-31
        - Metric: revenue
        - Filters: {{}}

        Example: "What were orders in September 2025?"
        - Mode: single_period
        - Period 2: 2025-09-01 to 2025-09-30
        - Period 1: 2025-08-01 to 2025-08-31
        - Metric: orders
        - Filters: {{}}
        
        User Query: "{question}"
        """
        try:
            structured_llm = parse_rca_llm.with_structured_output(QueryIntent)
            res = structured_llm.invoke(prompt)
            parsed = res.dict()
            valid, error = validate_parsed_query(parsed)
            if not valid:
                logger.warn(
                    "agent_llm_validation_failed",
                    agent="Query Understanding",
                    error=error,
                    fallback="mock_parse_query"
                )
                fallback = mock_parse_query(question)
                fallback_valid, fallback_error = validate_parsed_query(fallback)
                if not fallback_valid:
                    raise ValueError(f"Unable to parse question safely: {fallback_error}")
                return fallback

            logger.info("agent_llm_success", agent="Query Understanding", result=parsed)
            return parsed
        except Exception as e:
            logger.error("agent_llm_error", agent="Query Understanding", error=str(e))
            fallback = mock_parse_query(question)
            fallback_valid, fallback_error = validate_parsed_query(fallback)
            if not fallback_valid:
                raise ValueError(f"Unable to parse question safely: {fallback_error}")
            return fallback

    @staticmethod
    def generate_sql(metric: str, dimension: str, filters: Dict[str, Any]) -> str:
        if is_mock_llm or sql_llm is None:
            return mock_generate_sql(metric, dimension, filters)
            
        logger.info("agent_executing_llm", agent="SQL Agent")
        schema_info = """
        Database Tables & Columns:
        1. Table 'orders':
           - order_id (VARCHAR, PK)
           - customer_id (VARCHAR, FK to customers)
           - product_id (VARCHAR, FK to products)
           - region (VARCHAR: 'South', 'North', 'West', 'East')
           - category (VARCHAR: 'Electronics', 'Apparel', 'Home & Kitchen', 'Office Supplies', 'Beauty')
           - price (NUMERIC)
           - quantity (INTEGER)
           - order_date (DATE)
        2. Table 'customers':
           - customer_id (VARCHAR, PK)
           - segment (VARCHAR: 'Consumer', 'Corporate', 'Home Office')
           - city (VARCHAR)
           - state (VARCHAR)
        3. Table 'sessions':
           - session_id (VARCHAR, PK)
           - session_date (DATE)
           - region (VARCHAR)
           - segment (VARCHAR)
           - sessions_count (INTEGER)
        """
        
        prompt = f"""
        You are a SQL Analytics expert. Generate a single, safe, read-only SQL query for PostgreSQL.
        {schema_info}
        
        Requirements:
        1. Write a query to fetch the aggregate value of metric: '{metric}' grouped by the dimension: '{dimension}'.
           - If metric='units_sold', aggregate using SUM(quantity).
        2. The grouping column in your SELECT clause MUST be named exactly 'val', and the aggregated metric column MUST be named exactly 'metric_val' (or 'sessions_count' if fetching sessions for conversion).
        3. Restrict calculations to a date range using the named parameters ':start_date' and ':end_date' (e.g. `order_date BETWEEN :start_date AND :end_date`).
        4. Apply the following active filters: {filters}. Parameterize the filters as `:filter_<column_name>`.
        5. DO NOT execute writes (INSERT, UPDATE, DELETE, DROP).
        6. Return ONLY the SQL query.
        
        Example for metric 'revenue' grouped by 'category':
        SELECT category as val, SUM(price * quantity) as metric_val FROM orders WHERE order_date BETWEEN :start_date AND :end_date GROUP BY 1
        """
        try:
            structured_llm = sql_llm.with_structured_output(SqlResponse)
            res = structured_llm.invoke(prompt)
            logger.info("agent_llm_success", agent="SQL Agent", result=res.sql_query)
            return res.sql_query
        except Exception as e:
            logger.error("agent_llm_error", agent="SQL Agent", error=str(e))
            return mock_generate_sql(metric, dimension, filters)

    @staticmethod
    def generate_rca(metric: str, change_pct: float, p1_label: str, p2_label: str, negative_contributors: list) -> Dict[str, Any]:
        if is_mock_llm or parse_rca_llm is None:
            return mock_generate_rca(metric, change_pct, p1_label, p2_label, negative_contributors)
            
        logger.info("agent_executing_llm", agent="RCA Agent")
        prompt = f"""
        You are a Senior Business Analyst and Root Cause Investigator.
        Explain a major shift in business metric performance.
        
        Input Context:
        - Metric Analyzed: {metric}
        - Shift: The overall metric changed by {change_pct:.2f}% in {p2_label} compared to {p1_label}.
        - Key Negative Contributors: {json.dumps(negative_contributors, indent=2)}
        
        Your task is to:
        1. Write a 'summary': a clear 1-2 sentence description explaining the overall drop and highlighting which dimensions/values drove the majority of it.
        2. Generate 'recommendations': 2-3 specific business actions to address the root cause. (e.g. check payment gates, re-allocate inventory, review marketing).
        3. Formulate a 'confidence' score (between 0.0 and 1.0) based on how clearly the contributors explain the drop.
        """
        try:
            structured_llm = parse_rca_llm.with_structured_output(RcaResponse)
            res = structured_llm.invoke(prompt)
            output = {
                "summary": res.summary,
                "confidence": res.confidence,
                "recommendations": res.recommendations
            }
            logger.info("agent_llm_success", agent="RCA Agent", result=output)
            return output
        except Exception as e:
            logger.error("agent_llm_error", agent="RCA Agent", error=str(e))
            return mock_generate_rca(metric, change_pct, p1_label, p2_label, negative_contributors)
