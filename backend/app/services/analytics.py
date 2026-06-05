import time
from datetime import date, timedelta
from typing import Dict, Any, List, Tuple
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.utils.logger import logger

class AnalyticsService:
    @staticmethod
    def _execute_sql(db: Session, sql_query: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Executes a SQL query, logs it, and returns the result as a list of dicts"""
        start_time = time.time()
        try:
            result = db.execute(text(sql_query), params)
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            # Format results
            columns = result.keys()
            rows = [dict(zip(columns, row)) for row in result.fetchall()]
            
            logger.info("sql_executed", 
                        query=sql_query, 
                        params=params, 
                        rows_returned=len(rows), 
                        execution_time_ms=execution_time_ms)
            return rows
        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.error("sql_execution_failed", 
                         query=sql_query, 
                         params=params, 
                         error=str(e), 
                         execution_time_ms=execution_time_ms)
            raise e

    @classmethod
    def _build_orders_query(cls, select_clause: str, filters: Dict[str, Any], group_by: str = None) -> Tuple[str, Dict[str, Any]]:
        """Builds a parameterized SQL query for the orders table with dynamic joins and filters"""
        sql = f"SELECT {select_clause} FROM orders o"
        params = {}
        
        # Determine if we need to join the customers table
        customer_fields = {'segment', 'city', 'state'}
        has_customer_filter = any(k in customer_fields for k in filters.keys())
        has_customer_group = group_by in customer_fields
        
        if has_customer_filter or has_customer_group:
            sql += " JOIN customers c ON o.customer_id = c.customer_id"
            
        # Add date range filter (caller will pass start_date and end_date in params)
        sql += " WHERE o.order_date BETWEEN :start_date AND :end_date"
        
        # Add dynamic filters
        for col, val in filters.items():
            param_name = f"filter_{col}"
            if col in customer_fields:
                sql += f" AND c.{col} = :{param_name}"
            else:
                sql += f" AND o.{col} = :{param_name}"
            params[param_name] = val
            
        if group_by:
            prefix = "c" if group_by in customer_fields else "o"
            sql += f" GROUP BY {prefix}.{group_by}"
            
        return sql, params

    @classmethod
    def _build_sessions_query(cls, select_clause: str, filters: Dict[str, Any], group_by: str = None) -> Tuple[str, Dict[str, Any]]:
        """Builds a parameterized SQL query for the sessions table with dynamic filters"""
        sql = f"SELECT {select_clause} FROM sessions s"
        params = {}
        
        # Sessions has session_date, region, segment, sessions_count
        sql += " WHERE s.session_date BETWEEN :start_date AND :end_date"
        
        # We can filter sessions by region or segment
        allowed_filters = {'region', 'segment'}
        for col, val in filters.items():
            if col in allowed_filters:
                param_name = f"filter_{col}"
                sql += f" AND s.{col} = :{param_name}"
                params[param_name] = val
                
        if group_by and group_by in {'region', 'segment'}:
            sql += f" GROUP BY s.{group_by}"
            
        return sql, params

    @classmethod
    def get_metric_aggregates(cls, db: Session, metric: str, start_date: date, end_date: date, filters: Dict[str, Any]) -> Dict[str, float]:
        """Calculates total metrics (revenue, orders, units_sold, sessions, conversion_rate) for a period"""
        params = {"start_date": start_date, "end_date": end_date}
        
        # 1. Fetch Orders Count, Revenue, and Units Sold
        select_orders = "COUNT(o.order_id) as order_count, COALESCE(SUM(o.price * o.quantity), 0) as total_revenue, COALESCE(SUM(o.quantity), 0) as units_sold"
        orders_sql, orders_params = cls._build_orders_query(select_orders, filters)
        params.update(orders_params)
        
        orders_res = cls._execute_sql(db, orders_sql, params)
        order_count = float(orders_res[0]["order_count"])
        revenue = float(orders_res[0]["total_revenue"])
        units_sold = float(orders_res[0]["units_sold"])
        
        # 2. Fetch Sessions
        select_sessions = "COALESCE(SUM(s.sessions_count), 0) as total_sessions"
        sessions_sql, sessions_params = cls._build_sessions_query(select_sessions, filters)
        # Re-map date parameters and filter parameters to sessions query parameters
        sessions_params.update({"start_date": start_date, "end_date": end_date})
        
        sessions_res = cls._execute_sql(db, sessions_sql, sessions_params)
        sessions_count = float(sessions_res[0]["total_sessions"])
        
        # 3. Calculate Conversion Rate
        conversion_rate = 0.0
        if sessions_count > 0:
            conversion_rate = (order_count / sessions_count) * 100.0
            
        return {
            "revenue": revenue,
            "orders": order_count,
            "units_sold": units_sold,
            "sessions": sessions_count,
            "conversion_rate": conversion_rate
        }

    @classmethod
    def get_dimension_breakdown(cls, db: Session, metric: str, dimension: str, start_date: date, end_date: date, filters: Dict[str, Any]) -> Dict[str, float]:
        """Gets metric values grouped by a dimension for a period"""
        params = {"start_date": start_date, "end_date": end_date}
        breakdown = {}
        
        if metric in {"revenue", "orders", "units_sold"}:
            prefix = "c" if dimension in {"segment", "city", "state"} else "o"
            select = f"{prefix}.{dimension} as val, "
            if metric == "revenue":
                select += "COALESCE(SUM(o.price * o.quantity), 0) as metric_val"
            elif metric == "orders":
                select += "COUNT(o.order_id) as metric_val"
            else: # units_sold
                select += "COALESCE(SUM(o.quantity), 0) as metric_val"
                
            sql, orders_params = cls._build_orders_query(select, filters, group_by=dimension)
            params.update(orders_params)
            rows = cls._execute_sql(db, sql, params)
            for r in rows:
                if r["val"] is not None:
                    breakdown[str(r["val"])] = float(r["metric_val"])
                    
        elif metric == "conversion_rate":
            # For conversion rate we need both orders breakdown and sessions breakdown
            # Retrieve orders by dimension
            prefix = "c" if dimension in {"segment", "city", "state"} else "o"
            select_orders = f"{prefix}.{dimension} as val, COUNT(o.order_id) as order_count"
            sql_orders, orders_params = cls._build_orders_query(select_orders, filters, group_by=dimension)
            params.update(orders_params)
            order_rows = cls._execute_sql(db, sql_orders, params)
            
            orders_map = {str(r["val"]): float(r["order_count"]) for r in order_rows if r["val"] is not None}
            
            # Retrieve sessions by dimension. Sessions table only supports 'region' and 'segment' as dimensions.
            # If the user groups by 'city', we cannot calculate conversion rate precisely because sessions table
            # doesn't have city. We fall back to 0.0 or handle it gracefully.
            sessions_map = {}
            if dimension in {"region", "segment"}:
                select_sessions = f"s.{dimension} as val, COALESCE(SUM(s.sessions_count), 0) as sessions_count"
                sql_sessions, sessions_params = cls._build_sessions_query(select_sessions, filters, group_by=dimension)
                sessions_params.update({"start_date": start_date, "end_date": end_date})
                session_rows = cls._execute_sql(db, sql_sessions, sessions_params)
                sessions_map = {str(r["val"]): float(r["sessions_count"]) for r in session_rows if r["val"] is not None}
            
            # Calculate conversion rate per dimension value
            all_keys = set(orders_map.keys()).union(sessions_map.keys())
            for key in all_keys:
                ords = orders_map.get(key, 0.0)
                sess = sessions_map.get(key, 0.0)
                breakdown[key] = (ords / sess * 100.0) if sess > 0 else 0.0
                
        return breakdown

    @classmethod
    def get_dimension_sessions(cls, db: Session, dimension: str, start_date: date, end_date: date, filters: Dict[str, Any]) -> Dict[str, float]:
        """Helper to get sessions count grouped by region or segment (used for conversion rate contribution weights)"""
        if dimension not in {"region", "segment"}:
            return {}
        select = f"s.{dimension} as val, COALESCE(SUM(s.sessions_count), 0) as sessions_count"
        sql, params = cls._build_sessions_query(select, filters, group_by=dimension)
        params.update({"start_date": start_date, "end_date": end_date})
        rows = cls._execute_sql(db, sql, params)
        return {str(r["val"]): float(r["sessions_count"]) for r in rows if r["val"] is not None}

    @classmethod
    def get_period_metrics(
        cls,
        db: Session,
        metric: str,
        start_date: date,
        end_date: date,
        filters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Returns metric snapshot for a single period without comparison math."""
        aggregates = cls.get_metric_aggregates(
            db=db,
            metric=metric,
            start_date=start_date,
            end_date=end_date,
            filters=filters
        )
        value = aggregates.get(metric, 0.0)
        return {
            "metric": metric,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "value": value
            },
            "metrics": aggregates
        }

    @classmethod
    def compare_periods(
        cls, 
        db: Session, 
        metric: str, 
        p1_start: date, 
        p1_end: date, 
        p2_start: date, 
        p2_end: date, 
        filters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compares baseline and target period aggregates and computes dimension contribution analysis"""
        
        # 1. Period Aggregates
        p1_metrics = cls.get_metric_aggregates(db, metric, p1_start, p1_end, filters)
        p2_metrics = cls.get_metric_aggregates(db, metric, p2_start, p2_end, filters)
        
        v1 = p1_metrics[metric]
        v2 = p2_metrics[metric]
        
        abs_change = v2 - v1
        pct_change = (abs_change / v1 * 100.0) if v1 > 0 else 0.0
        
        report = {
            "metric": metric,
            "period_1": {"start": p1_start.isoformat(), "end": p1_end.isoformat(), "value": v1},
            "period_2": {"start": p2_start.isoformat(), "end": p2_end.isoformat(), "value": v2},
            "absolute_change": abs_change,
            "percentage_change": pct_change,
            "dimensions_contribution": {}
        }
        
        # If there's no change, we skip contribution analysis
        if abs_change == 0:
            return report

        # Analyze contributions across key dimensions
        # Additive metrics (revenue, orders) group by city, state, category, region, segment
        # Ratio metrics (conversion_rate) group by region, segment
        dimensions_to_analyze = ["region", "category", "segment"]
        if metric != "conversion_rate":
            dimensions_to_analyze.append("city")

        for dim in dimensions_to_analyze:
            contrib_list = []
            
            # Fetch breakdown maps
            p1_breakdown = cls.get_dimension_breakdown(db, metric, dim, p1_start, p1_end, filters)
            p2_breakdown = cls.get_dimension_breakdown(db, metric, dim, p2_start, p2_end, filters)
            
            all_keys = set(p1_breakdown.keys()).union(p2_breakdown.keys())
            
            if metric == "conversion_rate" and dim in {"region", "segment"}:
                # Conversion rate (ratio) contribution logic:
                # Weighted Conversion Change = (C_i(2) - C_i(1)) * (s_i(1) / S1)
                # Expressed as % of total baseline: (Weighted Conversion Change / C1) * 100
                S1_map = cls.get_dimension_sessions(db, dim, p1_start, p1_end, filters)
                S1_total = sum(S1_map.values())
                
                for key in all_keys:
                    c1_i = p1_breakdown.get(key, 0.0)
                    c2_i = p2_breakdown.get(key, 0.0)
                    s1_i = S1_map.get(key, 0.0)
                    
                    # Compute weighted absolute drop in conversion rate points
                    weight = s1_i / S1_total if S1_total > 0 else 0.0
                    abs_contrib = (c2_i - c1_i) * weight
                    
                    # Convert to contribution percentage relative to baseline conversion C1
                    contrib_pct = (abs_contrib / v1 * 100.0) if v1 > 0 else 0.0
                    change_pct = ((c2_i - c1_i) / c1_i * 100.0) if c1_i > 0 else 0.0
                    
                    contrib_list.append({
                        "dimension_value": key,
                        "period_1_value": c1_i,
                        "period_2_value": c2_i,
                        "absolute_change": c2_i - c1_i,
                        "percentage_change": change_pct,
                        "contribution_pct": contrib_pct
                    })
            else:
                # Additive metrics (revenue, orders) contribution logic:
                # Contribution = (m_i(2) - m_i(1)) / M1 * 100
                for key in all_keys:
                    val1 = p1_breakdown.get(key, 0.0)
                    val2 = p2_breakdown.get(key, 0.0)
                    diff = val2 - val1
                    
                    contrib_pct = (diff / v1 * 100.0) if v1 > 0 else 0.0
                    change_pct = (diff / val1 * 100.0) if val1 > 0 else 0.0
                    
                    contrib_list.append({
                        "dimension_value": key,
                        "period_1_value": val1,
                        "period_2_value": val2,
                        "absolute_change": diff,
                        "percentage_change": change_pct,
                        "contribution_pct": contrib_pct
                    })
            
            # Sort contributions: find the largest negative changes first
            contrib_list.sort(key=lambda x: x["contribution_pct"])
            
            report["dimensions_contribution"][dim] = contrib_list
            
        return report
