from typing import TypedDict, Dict, Any, List, Optional

class AgentState(TypedDict):
    question: str
    metric: Optional[str]
    p1_start: Optional[str]
    p1_end: Optional[str]
    p2_start: Optional[str]
    p2_end: Optional[str]
    filters: Optional[Dict[str, Any]]
    sql_queries: Optional[Dict[str, str]]
    analytics_results: Optional[Dict[str, Any]]
    rca_report: Optional[Dict[str, Any]]
    error: Optional[str]
