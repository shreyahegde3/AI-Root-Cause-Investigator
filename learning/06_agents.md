# Agent Workflows Deep Dive - Learning Module

This document outlines the Agent Workflow concepts utilized in Phase 3 of the **AI SQL Root Cause Investigator** project.

---

## 1. Multi-Agent Systems & Separation of Concerns

### What problem does it solve?
A single LLM prompt trying to:
1. Parse user queries
2. Recall database layouts
3. Generate valid SQL
4. Execute SQL
5. Perform analytical calculations
6. Write a business summary

will quickly hit context window limits, suffer from "attention degradation," write bad SQL, and make math errors.

### Why did we need it?
We separated these tasks into **4 specialized agents**:
- **Query Understanding Agent**: Focuses strictly on semantic parsing of dates, metrics, and filters.
- **SQL Agent**: Focuses on translation of metrics/filters into optimized PostgreSQL queries.
- **Analytics Agent**: Focuses on raw mathematical operations (MoM, WoW, contributions).
- **RCA Agent**: Focuses on explaining mathematical metrics in business terms and generating recommendations.

### Tradeoffs
- **Pros**:
  - High accuracy per agent (narrow focus).
  - Prompts are modular, clean, and easily maintainable.
  - Calculations are kept completely separate from the LLM, preventing LLM hallucinated math.
- **Cons**:
  - High token cost (multiple LLM calls).
  - High response latency (serial API roundtrips).

### Alternative Approaches
- **Single Agent with Tool Calling (ReAct Framework)**: A single agent that has access to database tools and calculators, calling them in a loop.
  - *Tradeoff*: High autonomy, but unpredictable execution path, prone to tool loop locks, and hard to enforce a strict structured API schema.

### Concept Breakdown

#### 1. Agent Prompts & Separation
Each agent has a system prompt defining:
1. **Role Profile**: "You are an expert SQL Analytics Translator..."
2. **Context boundaries**: Providing schema information to the SQL agent, but *not* to the RCA agent.
3. **Structured Constraints**: Instructing output format exactly.

#### 2. Interview Questions
1. *Why is separation of concerns beneficial in LLM applications?*
2. *What is attention degradation in LLMs, and how does multi-agent architecture mitigate it?*
3. *How do you choose between a multi-agent orchestration pipeline (like LangGraph) and an autonomous tool-using agent (ReAct)?*

#### 3. Common Mistakes
- **Prompt Bleeding**: Giving agents unnecessary context (e.g. giving database table details to the RCA agent). Keep prompts lean and restricted strictly to what the agent needs to perform its immediate task.

---

## 2. Safe SQL Generation & Execution

### What problem does it solve?
Executing LLM-generated SQL directly on database engines presents extreme security vulnerabilities:
1. **SQL Injection**: Malicious user input translated into queries.
2. **Data Destruction**: LLMs generating `DROP TABLE` or `DELETE` statements (hallucinations or adversarial prompt injections).
3. **Database Exhaustion**: LLMs writing poorly structured queries (e.g. Cartesian joins) that lock tables and consume all RAM.

### Why did we need it?
Our SQL Agent must write database queries dynamically based on user questions. We enforce strict safety rules on both prompt levels and execution wrappers.

### Concept Breakdown

#### 1. SQL Security Guardrails
We apply multiple layers of safety:
- **System Prompt Restrictions**: Instructing the SQL agent: *"You are read-only. DO NOT execute writes (INSERT, UPDATE, DELETE, DROP)."*
- **Parameterization**: Passing dates and filters as values linked to SQL bind parameters (`:start_date`, `:end_date`), preventing SQL injections.
- **Read-Only Credentials (Production Best Practice)**: Running database executions under a restricted PostgreSQL user account that has only `SELECT` privileges.

#### 2. Example Parameterized Query (SQL Agent Output)
```sql
SELECT region as val, SUM(price * quantity) as metric_val 
FROM orders 
WHERE order_date BETWEEN :start_date AND :end_date 
GROUP BY 1
```

#### 3. Interview Questions
1. *How do dynamic SQL generation agents present security risks, and how do you mitigate them at the database layer?*
2. *What is SQL Parameterization (bound parameters), and how does it prevent SQL injection?*
3. *How do you prevent an LLM from generating run-away query joins that crash your server? (Explain query timeouts and resource limits).*

#### 4. Common Mistakes
- **String Interpolation**: Generating SQL using python f-strings: `f"SELECT * FROM orders WHERE city = '{city}'"`. This is highly vulnerable to SQL injection. Always use database bind parameters: `WHERE city = :filter_city`.
