import os
from datetime import datetime
from typing import Dict, Any, List
from langgraph.graph import StateGraph, END

from app.agents.state import AgentState
from app.agents.llm import AgentLLM
from app.services.analytics import AnalyticsService
from app.database.connection import SessionLocal
from app.utils.logger import logger

# --- Node Definitions ---

def parse_query_node(state: AgentState) -> Dict[str, Any]:
    """Extracts metric, date ranges, and filters from the question"""
    question = state["question"]
    logger.info("agent_node_start", node="parse_query", question=question)
    
    try:
        parsed = AgentLLM.parse_query(question)
        return {
            "metric": parsed.get("metric"),
            "p1_start": parsed.get("p1_start"),
            "p1_end": parsed.get("p1_end"),
            "p2_start": parsed.get("p2_start"),
            "p2_end": parsed.get("p2_end"),
            "filters": parsed.get("filters", {}),
            "error": None
        }
    except Exception as e:
        logger.error("agent_node_failed", node="parse_query", error=str(e))
        return {"error": f"Query Understanding Agent failed: {str(e)}"}

def generate_sql_node(state: AgentState) -> Dict[str, Any]:
    """Generates read-only, safe SQL queries for each analyzed dimension"""
    if state.get("error"):
        return {}
        
    metric = state["metric"]
    filters = state["filters"]
    
    logger.info("agent_node_start", node="generate_sql", metric=metric, filters=filters)
    
    # We analyze these dimensions
    dimensions = ["region", "category", "segment"]
    if metric != "conversion_rate":
        dimensions.append("city")
        
    sql_queries = {}
    try:
        for dim in dimensions:
            sql = AgentLLM.generate_sql(metric=metric, dimension=dim, filters=filters)
            sql_queries[dim] = sql
            
        return {
            "sql_queries": sql_queries,
            "error": None
        }
    except Exception as e:
        logger.error("agent_node_failed", node="generate_sql", error=str(e))
        return {"error": f"SQL Agent failed: {str(e)}"}

def run_analytics_node(state: AgentState) -> Dict[str, Any]:
    """Runs period comparison and computes absolute/percentage changes and contributions"""
    if state.get("error"):
        return {}
        
    metric = state["metric"]
    p1_start_str = state["p1_start"]
    p1_end_str = state["p1_end"]
    p2_start_str = state["p2_start"]
    p2_end_str = state["p2_end"]
    filters = state["filters"]
    
    logger.info("agent_node_start", node="run_analytics", metric=metric)
    
    # Convert strings back to date objects for service compatibility
    p1_start = datetime.strptime(p1_start_str, "%Y-%m-%d").date()
    p1_end = datetime.strptime(p1_end_str, "%Y-%m-%d").date()
    p2_start = datetime.strptime(p2_start_str, "%Y-%m-%d").date()
    p2_end = datetime.strptime(p2_end_str, "%Y-%m-%d").date()
    
    db = SessionLocal()
    try:
        report = AnalyticsService.compare_periods(
            db=db,
            metric=metric,
            p1_start=p1_start,
            p1_end=p1_end,
            p2_start=p2_start,
            p2_end=p2_end,
            filters=filters
        )
        return {
            "analytics_results": report,
            "error": None
        }
    except Exception as e:
        logger.error("agent_node_failed", node="run_analytics", error=str(e))
        return {"error": f"Analytics Agent failed: {str(e)}"}
    finally:
        db.close()

def generate_rca_node(state: AgentState) -> Dict[str, Any]:
    """Reviews analytics data and generates human-readable report with recommendations"""
    if state.get("error"):
        return {}
        
    metric = state["metric"]
    analytics = state["analytics_results"]
    p1_start = state["p1_start"]
    p2_start = state["p2_start"]
    
    logger.info("agent_node_start", node="generate_rca", metric=metric)
    
    change_pct = analytics["percentage_change"]
    
    # Extract top negative contributors for prompt context
    neg_contributors = []
    for dim, items in analytics.get("dimensions_contribution", {}).items():
        for item in items[:2]:
            if item["contribution_pct"] < -0.1:
                neg_contributors.append({
                    "dimension": dim,
                    "value": item["dimension_value"],
                    "impact": f"{item['contribution_pct']:.2f}%"
                })
                
    try:
        rca_output = AgentLLM.generate_rca(
            metric=metric,
            change_pct=change_pct,
            p1_label=datetime.strptime(p1_start, "%Y-%m-%d").strftime("%B %Y"),
            p2_label=datetime.strptime(p2_start, "%Y-%m-%d").strftime("%B %Y"),
            negative_contributors=neg_contributors
        )
        
        # Merge contributors into the final report structure
        rca_report = {
            "summary": rca_output["summary"],
            "contributors": neg_contributors,
            "confidence": rca_output["confidence"],
            "recommendations": rca_output["recommendations"]
        }
        
        return {
            "rca_report": rca_report,
            "error": None
        }
    except Exception as e:
        logger.error("agent_node_failed", node="generate_rca", error=str(e))
        return {"error": f"RCA Agent failed: {str(e)}"}

# --- Graph Orchestration Setup ---

workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("parse_query", parse_query_node)
workflow.add_node("generate_sql", generate_sql_node)
workflow.add_node("run_analytics", run_analytics_node)
workflow.add_node("generate_rca", generate_rca_node)

# Set Entrypoint
workflow.set_entry_point("parse_query")

# Set Linear Edges
workflow.add_edge("parse_query", "generate_sql")
workflow.add_edge("generate_sql", "run_analytics")
workflow.add_edge("run_analytics", "generate_rca")
workflow.add_edge("generate_rca", END)

# Compile Graph
graph = workflow.compile()

def run_investigation(question: str) -> Dict[str, Any]:
    """Compiles state and triggers the compiled agent graph flow"""
    initial_state = {
        "question": question,
        "metric": None,
        "p1_start": None,
        "p1_end": None,
        "p2_start": None,
        "p2_end": None,
        "filters": {},
        "sql_queries": {},
        "analytics_results": {},
        "rca_report": {},
        "error": None
    }
    
    logger.info("investigation_workflow_start", question=question)
    final_state = graph.invoke(initial_state)
    
    if final_state.get("error"):
        logger.error("investigation_workflow_failed", error=final_state["error"])
        raise Exception(final_state["error"])
        
    logger.info("investigation_workflow_complete")
    return final_state["rca_report"]
