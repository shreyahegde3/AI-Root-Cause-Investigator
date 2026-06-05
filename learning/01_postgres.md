# PostgreSQL Deep Dive - Learning Module

This document outlines the PostgreSQL database concepts utilized in Phase 1 of the **AI SQL Root Cause Investigator** project.

---

## 1. Relational Schema Design & Constraints

### Problem Solved
Structured business data requires consistency, safety, and relationships. Relational schemas allow data to be normalized across tables, preventing duplicate data and keeping relationships clean.

### Why We Needed It
We need to model the connections between `customers` (who buy), `products` (what they buy), and `orders` (the transaction). Constraints (like `FOREIGN KEY` and `NOT NULL`) ensure that we cannot record an order for a customer who doesn't exist, nor can we insert an order without a price or quantity.

### Tradeoffs
- **Pros**: Strong data integrity, low redundancy (easy to update records in one place), database-enforced safety.
- **Cons**: Write overhead (checking constraints on inserts/updates), complex reads requiring joins.

### Alternative Approaches
- **NoSQL Document Database (e.g., MongoDB)**: Storing orders as nested documents containing customer and product details in a single JSON block.
  - *Tradeoff*: Super fast writes and simple reads, but lacks strict schemas and transactions. Updating a customer's address would require updating thousands of historical order documents (denormalization issues).

### Concept Breakdown

#### 1. Explanation
Relational schemas use keys to enforce integrity:
- **Primary Key (PK)**: Uniquely identifies a row (e.g., `order_id`).
- **Foreign Key (FK)**: Points to a Primary Key in another table, enforcing referential integrity.
- **Nullability (`NOT NULL`)**: Enforces that a column must contain a value.

#### 2. Example DDL (Data Definition Language)
```sql
CREATE TABLE orders (
    order_id VARCHAR(50) PRIMARY KEY,
    customer_id VARCHAR(50) REFERENCES customers(customer_id) NOT NULL,
    product_id VARCHAR(50) REFERENCES products(product_id) NOT NULL,
    price NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    order_date DATE NOT NULL
);
```

#### 3. Interview Questions
1. *What is referential integrity, and how does PostgreSQL enforce it?*
2. *What is the difference between a Primary Key and a Unique constraint?*
3. *What happens to child records in PostgreSQL when a parent record is deleted? (Explain `ON DELETE CASCADE` vs. `ON DELETE RESTRICT`).*

#### 4. Common Mistakes
- **No Indexes on Foreign Keys**: PostgreSQL does **not** automatically index foreign key columns. If you frequently join `orders` and `customers` on `customer_id` or delete parent rows, PostgreSQL must perform full-table scans unless you explicitly create an index on the FK.
- **Using UUIDs vs. Auto-Incrementing Integers**: Using randomized UUIDs as primary keys can cause write bottlenecks due to "index page fragmentation" in B-Trees. Sorted identifiers (like BigInt or UUIDv7) are better for high-write databases.

---

## 2. B-Tree Indexing (Single & Composite)

### Problem Solved
Scanning a table of 100,000+ rows line-by-line (Sequential Scan) to find matching records is slow and resource-intensive.

### Why We Needed It
Analytics engineers write queries filtering by specific dates, categories, or regions (e.g., "orders in Bangalore for Electronics"). Without indexes, every analytics agent check would lag. We created single-column indexes on keys, and a composite index `idx_order_date_region_category` on `orders(order_date, region, category)`.

### Tradeoffs
- **Pros**: Speeds up SELECT queries from $O(N)$ to $O(\log N)$ search complexity.
- **Cons**: Slows down inserts, updates, and deletes (DML) because index pages must be updated. Consumes additional storage space.

### Alternative Approaches
- **Full Table Scan (Seq Scan)**: Acceptable only for very small tables (< 1,000 rows) where loading pages into memory and scanning them is faster than index traversal.
- **BRIN (Block Range Index)**: A lightweight index that stores the min/max values of blocks. Excellent for extremely large, physical chronologically-sorted tables (e.g., millions of log entries sorted by date) with very little storage overhead.

### Concept Breakdown

#### 1. Explanation
A B-Tree index is a balanced tree data structure that allows database engines to find keys quickly.
- **Composite Index**: An index built on multiple columns. The order of columns matters because PostgreSQL searches from left to right (the "Left-Prefix Rule"). An index on `(A, B, C)` can optimize queries filtering on `A`, `(A, B)`, or `(A, B, C)`, but **cannot** optimize queries filtering on only `B` or `C`.

#### 2. Example Query
```sql
-- This query leverages the composite index idx_order_date_region_category
SELECT * FROM orders 
WHERE order_date >= '2026-04-15' 
  AND region = 'South' 
  AND category = 'Electronics';
```

#### 3. Interview Questions
1. *What is the Left-Prefix Rule in composite indexes, and how does it affect query design?*
2. *What is an Index-Only Scan in PostgreSQL, and how does it differ from an Index Scan?*
3. *How does PostgreSQL decide whether to use an index or a sequential scan?*

#### 4. Common Mistakes
- **Incorrect Column Order in Composite Indexes**: Placing high-cardinality or rarely-queried columns at the front of a composite index. Always place the most frequently filtered, equality-checked columns first.
- **Index Cardinality Abuse**: Creating indexes on columns with low cardinality (e.g., a boolean column like `is_active` or a column like `gender`). The database optimizer will usually ignore the index and perform a full table scan.

---

## 3. Common Table Expressions (CTEs)

### Problem Solved
Complex analytical queries involving aggregations, subqueries, and calculations can quickly become nesting nightmares, making them impossible to read or debug.

### Why We Needed It
To compute conversion rates, we need to aggregate orders by month, aggregate sessions by month, and then join these two aggregated sets together. Using CTEs (`WITH` clauses) makes this multi-step query clean and linear.

### Tradeoffs
- **Pros**: High readability, structured flow, reusable named query blocks.
- **Cons**: Prior to PostgreSQL 12, CTEs acted as optimization barriers (they were materialized in memory, blocking optimizer pushdown filters). In PostgreSQL 12+, they are inlined by default unless you force materialization using `AS MATERIALIZED`.

### Alternative Approaches
- **Subqueries**: Placing a SELECT statement in the FROM clause: `SELECT * FROM (SELECT ...) AS sub`.
  - *Tradeoff*: Harder to read and maintain, but historically had better optimizer performance in older database engines.
- **Database Views**: Creating a permanent virtual table.
  - *Tradeoff*: Good for global reuse, but adds schema management overhead for one-off analytics queries.

### Concept Breakdown

#### 1. Explanation
A CTE defines a temporary result set that you can reference within a subsequent SELECT, INSERT, UPDATE, or DELETE statement.

#### 2. Example Query
```sql
WITH monthly_orders AS (
    SELECT DATE_TRUNC('month', order_date)::DATE as month, COUNT(*) as order_count
    FROM orders 
    GROUP BY 1
),
monthly_sessions AS (
    SELECT DATE_TRUNC('month', session_date)::DATE as month, SUM(sessions_count) as total_sessions
    FROM sessions 
    GROUP BY 1
)
SELECT 
    mo.month,
    mo.order_count,
    ms.total_sessions,
    ROUND((mo.order_count::numeric / ms.total_sessions::numeric) * 100, 2) as conversion_rate
FROM monthly_orders mo
JOIN monthly_sessions ms ON mo.month = ms.month;
```

#### 3. Interview Questions
1. *What is the difference between a CTE and a temporary table in PostgreSQL?*
2. *How did the optimization behavior of CTEs change in PostgreSQL 12? (Explain materialized vs. inlined).*
3. *What is a Recursive CTE, and what is its typical use case?*

#### 4. Common Mistakes
- **Using CTEs for simple filters**: Writing multiple levels of CTEs just to filter rows, which can add overhead and make execution plans harder for the planner to optimize.
- **Infinite Recursion**: In recursive CTEs, failing to set a proper base condition or join condition, causing the query to run forever and crash the connection.

---

## 4. Analytical Data Aggregations

### Problem Solved
Databases store granular transactional data (e.g., individual orders of 2 items). Business decisions require high-level metrics (e.g., total revenue, average order value, overall volume).

### Why We Needed It
To detect root causes, we aggregate sales numbers across dimensions (cities, categories, segments) to compare them dynamically.

### Tradeoffs
- **Pros**: Highly efficient server-side data reduction. Prevents pulling millions of rows to the API server to perform calculations in Python.
- **Cons**: Computational resource-intensive (heavy CPU and Memory usage for sorting and hashing).

### Alternative Approaches
- **Application-Side Aggregations**: Pulling raw transactional records to FastAPI and using Python/Pandas to aggregate.
  - *Tradeoff*: Unacceptable latency and memory usage for production datasets.
- **Pre-aggregated Tables (Rollups)**: Keeping a table of daily/hourly summarized metrics.
  - *Tradeoff*: Extremely fast reads, but introduces latency in data availability and complexity in syncing.

### Concept Breakdown

#### 1. Explanation
Aggregations collapse multiple rows into a single summary row based on grouping columns using:
- `COUNT(*)`: Count rows.
- `SUM(col)`: Compute total.
- `AVG(col)`: Compute average.
- `ROUND(val, precision)`: Format numeric precision.

#### 2. Example Query
```sql
SELECT 
    category,
    COUNT(order_id) as total_orders,
    SUM(price * quantity) as total_revenue,
    AVG(quantity) as avg_quantity
FROM orders
GROUP BY category
ORDER BY total_revenue DESC;
```

#### 3. Interview Questions
1. *What is the difference between `GROUP BY` and window functions (e.g. `SUM(...) OVER(...)`)?*
2. *What is the difference between HashAggregate and GroupAggregate execution strategies in PostgreSQL?*
3. *Why can't you use an aggregate function (e.g. `SUM(price)`) inside a `WHERE` clause? (What is the purpose of `HAVING`?)*

#### 4. Common Mistakes
- **Grouping on Non-Aggregated SELECT Columns**: Trying to select columns that are not grouped: `SELECT city, category, SUM(price) FROM orders GROUP BY city`. This fails with syntax errors because PostgreSQL doesn't know how to collapse the multiple categories within a city.
- **`COUNT(column)` vs `COUNT(*)`**: `COUNT(column)` ignores `NULL` values, whereas `COUNT(*)` counts every row. This can lead to silent calculation errors if the column contains nulls.

---

## 5. Date & Time Manipulation

### Problem Solved
Transactional dates are recorded as specific timestamps (e.g., `2026-04-15 14:32:01`). Analytics requires grouping by date buckets (days, weeks, months).

### Why We Needed It
We analyze trends like "April revenue vs. March revenue" or "last two weeks of April vs. first two weeks". This requires truncating timestamps to month boundaries or filtering ranges.

### Tradeoffs
- **Pros**: Precise temporal bucketing natively inside SQL.
- **Cons**: Time zones can introduce complexity and errors if not handled uniformly.

### Alternative Approaches
- **Storing Date Keys (e.g., integer date key 20260415)**: Commonly used in traditional data warehouses (Star Schemas) to avoid timestamp functions.
  - *Tradeoff*: Fast and timezone-independent, but limits flexibility of native datetime arithmetic.

### Concept Breakdown

#### 1. Explanation
- `DATE_TRUNC(unit, column)`: Truncates a timestamp to the beginning of the specified unit (e.g., 'month' turns `2026-04-15` into `2026-04-01`).
- `INTERVAL`: Represents a duration (e.g., `NOW() - INTERVAL '30 days'`).

#### 2. Example Query
```sql
-- Find revenue for orders placed in the last 30 days
SELECT SUM(price * quantity) as rolling_revenue
FROM orders
WHERE order_date >= CURRENT_DATE - INTERVAL '30 days';
```

#### 3. Interview Questions
1. *What is the difference between `TIMESTAMP` and `TIMESTAMPTZ` in PostgreSQL? Which is preferred for production and why?*
2. *What does `DATE_TRUNC('week', order_date)` return for a Sunday transaction, and why does it matter?*
3. *How do you write a query that performs date comparisons while ensuring it remains sargable (can use indexes)?*

#### 4. Common Mistakes
- **Non-Sargable Date Filtering**: Filtering dates using functions: `WHERE EXTRACT(month FROM order_date) = 4`. This prevents PostgreSQL from using the index on `order_date`. Instead, write: `WHERE order_date >= '2026-04-01' AND order_date < '2026-05-01'`.
- **Assuming Date String Casting is Safe**: Casting strings to dates implicitly can fail depending on server locale settings (e.g., `04/12/2026` could be interpreted as April 12 or December 4). Always use ISO 8601 formatting (`YYYY-MM-DD`).

---

## 6. Denormalization (e.g., Category on Orders)

### Problem Solved
In a normalized schema, finding category-level sales requires joining `orders` with `products`. At scale, joining tables for millions of rows adds high CPU overhead.

### Why We Needed It
Our `orders` table includes a redundant `category` column. Analytics queries frequently filter or group by category. Having it directly on the `orders` table avoids joining the `products` table, cutting down join overhead during agent operations.

### Tradeoffs
- **Pros**: Supercharged query performance for category-level analytics.
- **Cons**: Higher storage size, and data anomaly risks (if a product's category changes, we must update all historical order records or accept inconsistencies).

### Alternative Approaches
- **Normalized Schema**: Remove `category` from `orders` and join `products` on `product_id` whenever category is needed.
  - *Tradeoff*: Cleaner, zero redundancy, but slower search times.

### Concept Breakdown

#### 1. Explanation
Denormalization is the process of writing duplicate data into a table to improve read performance at the expense of write performance and schema purity.

#### 2. Example Query Comparison
```sql
-- Normalized Approach (requires JOIN)
SELECT p.category, SUM(o.price * o.quantity) 
FROM orders o 
JOIN products p ON o.product_id = p.product_id 
GROUP BY 1;

-- Denormalized Approach (No JOIN)
SELECT category, SUM(price * quantity) 
FROM orders 
GROUP BY 1;
```

#### 3. Interview Questions
1. *What is the difference between 3NF (Third Normal Form) and a denormalized schema?*
2. *Under what conditions is it appropriate to denormalize database tables?*
3. *How do you prevent data anomalies (data drift) in denormalized columns? (Explain triggers or application-level transactions).*

#### 4. Common Mistakes
- **Over-denormalization**: Denormalizing columns that change frequently (e.g., customer city or name), which leads to massive updates whenever a customer changes their profile.
- **Neglecting to update denormalized data**: Changing a product's category in the `products` table but failing to update the associated records in the `orders` table, leading to conflicting aggregate reports.
