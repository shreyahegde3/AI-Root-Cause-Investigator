# Redis Caching Deep Dive - Learning Module

This document outlines the Redis caching concepts utilized in Phase 2 of the **AI SQL Root Cause Investigator** project.

---

## 1. Cache-Aside Caching Pattern & TTLs

### What problem does it solve?
Running analytical aggregations on databases takes CPU cycles and time (e.g. 5–50ms). If multiple users ask the same business question, executing the same expensive SQL queries repeatedly is redundant and wastes database resources.

### Why did we need it?
Our agents and frontend will make repeated requests. We cache generated reports in Redis. By applying a **Time-To-Live (TTL)** of 10 minutes, we ensure that:
1. Subsequent identical requests return instantly (< 1ms).
2. The data remains relatively fresh (automatically expires after 10 minutes).

### Tradeoffs
- **Pros**: Drastically reduces database CPU load, sub-millisecond API response latency, cost reduction on database scaling.
- **Cons**: Cache coherence issues (data updates in PostgreSQL will not reflect in the cache until the 10-minute TTL expires, leading to "stale reads").

### Alternative Approaches
- **In-Memory Python Dict Caching**: Caching results in global dictionary variables in FastAPI.
  - *Tradeoff*: Simple and requires no external services. However, cache contents are lost on container restart, and if we scale the backend to multiple instances (e.g. multiple replicas), they cannot share the cache.
- **Database Materialized Views**: Creating tables that cache query results directly inside PostgreSQL.
  - *Tradeoff*: Keeps cache inside SQL layer, but lacks microsecond caching speeds and must be refreshed manually.

### Concept Breakdown

#### 1. Explanation
We use the **Cache-Aside Pattern**:
1. Check if the result is in the cache (Cache Hit). If yes, return it.
2. If not (Cache Miss), compute the result (query DB).
3. Save the result in the cache with a TTL (expiration timer) for future queries.

#### 2. Key Generation (Hashing)
User questions can be long and contain spaces or capitals. To query cache keys efficiently, we hash the normalized question using **MD5** to create a standard, fixed-length cache key:
```python
question_hash = hashlib.md5(question.strip().lower().encode('utf-8')).hexdigest()
cache_key = f"rca_report:{question_hash}"
```

#### 3. Interview Questions
1. *What is the difference between Cache-Aside, Write-Through, and Write-Back caching strategies?*
2. *How does Redis manage memory eviction? (Explain LRU vs LFU eviction policies).*
3. *What is Cache Stampede (or Cache Penetration / Cache Avalanche), and how can you prevent it?*

#### 4. Common Mistakes
- **Infinite TTLs**: Forgetting to set a TTL, causing Redis to run out of memory over time as keys accumulate. Always set an expiration (`ex` parameter in redis client).
- **Stale Data Ignored**: Setting TTLs too high (e.g. 24 hours) for metrics that business users expect to see updated in real-time.

---

## 2. Resilient Fallbacks (Graceful Degradation)

### What problem does it solve?
If Redis crashes or suffers network issues, the application should **not** crash. A cache is an optimization, not a hard system dependency.

### Why did we need it?
In production, a Redis connection error shouldn't prevent users from querying the database. Our `CacheService` handles Redis connection failures gracefully by logging the issue and bypassing the cache (acting as a cache-miss).

### Concept Breakdown

#### 1. Implementation
In `backend/app/services/cache.py`, we test the connection during initialization and wrap all calls in `try/except` blocks:
```python
class CacheService:
    def __init__(self):
        try:
            self.client = redis.Redis.from_url(redis_url, socket_timeout=2.0)
            self.client.ping()  # Verifies Redis is active
            self._is_active = True
        except Exception:
            self._is_active = False # Decouples connection failure

    def get(self, key: str):
        if not self._is_active:
            return None # Falls back to database query
        try:
            return self.client.get(key)
        except Exception:
            return None
```

#### 2. Interview Questions
1. *What is the Circuit Breaker pattern, and how does it relate to caching?*
2. *Why is it important to set timeouts (`socket_timeout`) on connection clients to external services?*

#### 3. Common Mistakes
- **Hard Dependencies**: Letting a Redis connection failure crash the entire web application startup. Always catch connection exceptions in the cache service initialization.
