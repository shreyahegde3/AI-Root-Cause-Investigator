import hashlib
from datetime import date
from typing import Dict, Any
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.services.analytics import AnalyticsService
from app.services.cache import cache_service
from app.utils.logger import logger
from app.agents.llm import AgentLLM
from app.agents.graph import run_investigation

app = FastAPI(
    title="AI SQL Root Cause Investigator API",
    description="API for SQL query execution, analytics, and Agent workflows.",
    version="1.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def parse_question_rules(question: str):
    """Parses a natural language question into SQL parameters using rule-based heuristics for Phase 2"""
    q = question.lower()
    
    # Default parameters: April 2026 vs March 2026 for Revenue
    metric = "revenue"
    p2_start, p2_end = date(2026, 4, 1), date(2026, 4, 30)
    p1_start, p1_end = date(2026, 3, 1), date(2026, 3, 31)
    filters = {}
    
    # 1. Detect metric
    if "conversion" in q or "cr " in q or "checkout" in q:
        metric = "conversion_rate"
    elif "order" in q or "volume" in q or "count" in q:
        metric = "orders"
    elif "revenue" in q or "sales" in q or "income" in q:
        metric = "revenue"
        
    # 2. Detect target period dates
    if "february" in q or "feb" in q:
        p2_start, p2_end = date(2026, 2, 1), date(2026, 2, 28)
        p1_start, p1_end = date(2026, 1, 1), date(2026, 1, 31)
        # If user didn't specify orders/revenue, check conversion because Feb is the conversion drop
        if "revenue" not in q and "sales" not in q and "order" not in q:
            metric = "conversion_rate"
    elif "october" in q or "oct" in q:
        p2_start, p2_end = date(2025, 10, 1), date(2025, 10, 31)
        p1_start, p1_end = date(2025, 9, 1), date(2025, 9, 30)
        if "corporate" in q:
            filters["segment"] = "Corporate"
        if "office supplies" in q:
            filters["category"] = "Office Supplies"
    elif "april" in q or "apr" in q:
        p2_start, p2_end = date(2026, 4, 1), date(2026, 4, 30)
        p1_start, p1_end = date(2026, 3, 1), date(2026, 3, 31)
        if "bangalore" in q:
            filters["city"] = "Bangalore"
            
    # 3. Extract generic filters
    if "bangalore" in q and "city" not in filters:
        filters["city"] = "Bangalore"
    if "corporate" in q and "segment" not in filters:
        filters["segment"] = "Corporate"
    if "electronics" in q and "category" not in filters:
        filters["category"] = "Electronics"
    if "office supplies" in q and "category" not in filters:
        filters["category"] = "Office Supplies"
        
    return metric, p1_start, p1_end, p2_start, p2_end, filters

def compare_periods(question: str) -> Dict[str, Any]:
    """Runs full comparison workflow and tags response mode."""
    report = run_investigation(question)
    report["mode"] = "comparison"
    return report

def single_period(parsed_query: Dict[str, Any], db: Session) -> Dict[str, Any]:
    """Returns a single-period metric snapshot without baseline comparison."""
    metric = parsed_query.get("metric", "revenue")
    filters = parsed_query.get("filters", {}) or {}
    p2_start_raw = parsed_query.get("p2_start")
    p2_end_raw = parsed_query.get("p2_end")
    if not p2_start_raw or not p2_end_raw:
        raise ValueError("Single-period query requires valid p2_start and p2_end")

    p2_start = date.fromisoformat(p2_start_raw)
    p2_end = date.fromisoformat(p2_end_raw)
    snapshot = AnalyticsService.get_period_metrics(
        db=db,
        metric=metric,
        start_date=p2_start,
        end_date=p2_end,
        filters=filters
    )

    value = snapshot["period"]["value"]
    metric_label = metric.replace("_", " ").title()
    period_label = p2_start.strftime("%B %Y")
    if metric in {"orders", "units_sold", "sessions"}:
        value_text = f"{value:,.0f}"
    elif metric == "conversion_rate":
        value_text = f"{value:.2f}%"
    else:
        value_text = f"${value:,.2f}"

    return {
        "mode": "single_period",
        "metric": metric,
        "period": snapshot["period"],
        "metrics": snapshot["metrics"],
        "filters": filters,
        "summary": f"{metric_label} in {period_label} was {value_text}.",
        "contributors": [],
        "confidence": 0.92,
        "recommendations": [
            "Use this snapshot as a baseline to compare against adjacent periods if trend context is needed.",
            "Break down this metric by category, region, or segment to identify concentration patterns quickly."
        ]
    }

@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    """Health check endpoint checking DB and Redis connection"""
    db_status = "healthy"
    redis_status = "healthy"
    
    # Check DB
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
        
    # Check Redis
    if not cache_service._is_active:
        redis_status = "unhealthy"
        
    return {
        "status": "healthy" if db_status == "healthy" and redis_status == "healthy" else "degraded",
        "database": db_status,
        "redis": redis_status,
        "service": "rca-backend"
    }

@app.get("/api/schema")
def schema(db: Session = Depends(get_db)):
    """Returns database table schemas and metadata"""
    return {
        "tables": {
            "customers": ["customer_id", "segment", "city", "state"],
            "products": ["product_id", "category", "product_name"],
            "orders": ["order_id", "customer_id", "product_id", "region", "category", "price", "quantity", "order_date"],
            "sessions": ["session_id", "session_date", "region", "segment", "sessions_count"]
        }
    }

@app.post("/api/investigate")
def investigate(payload: dict, db: Session = Depends(get_db)):
    """Investigates metric anomalies and returns contributors, utilizing Redis caching and Analytics Engine"""
    question = payload.get("question", "")
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")
        
    # Generate Cache Key based on hash of the question
    question_hash = hashlib.md5(question.strip().lower().encode('utf-8')).hexdigest()
    cache_key = f"rca_report:{question_hash}"
    
    # Try fetching from cache
    cached_report = cache_service.get_json(cache_key)
    if cached_report:
        logger.info("investigate_cache_hit", question=question, cache_key=cache_key)
        return cached_report
        
    logger.info("investigate_cache_miss", question=question, cache_key=cache_key)
    
    try:
        parsed_query = AgentLLM.parse_query(question)
        mode = parsed_query.get("mode", "comparison")
        if mode == "single_period":
            final_output = single_period(parsed_query, db)
        else:
            final_output = compare_periods(question)
        # Write to Redis cache with 10-minute TTL (600s)
        cache_service.set_json(cache_key, final_output, ttl_seconds=600)
        return final_output
    except Exception as e:
        logger.error("investigation_api_failed", question=question, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
