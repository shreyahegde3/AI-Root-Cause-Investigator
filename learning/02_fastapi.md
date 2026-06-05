# FastAPI Deep Dive - Learning Module

This document outlines the FastAPI concepts utilized in the **AI SQL Root Cause Investigator** project.

---

## 1. Web Framework Selection & Routing

### What problem does it solve?
To make database analytics and AI agents accessible to frontends and external integrations, we need to expose them via HTTP endpoints. A web framework handles incoming HTTP requests (routing), parses payload data, manages execution threads, and formats responses as JSON.

### Why did we need it?
Our React UI and test scripts need to query health, view schema, and submit questions to the agent network. We used **FastAPI** to build these REST endpoints (`/api/health`, `/api/schema`, `/api/investigate`).

### Tradeoffs
- **Pros**:
  - **Asynchronous Execution (ASGI)**: Handles concurrent requests natively using Python's `async/await`, which is crucial for long-running LLM calls.
  - **Auto-generated Documentation**: Out-of-the-box Swagger interactive documentation (`/docs`) based on OpenAPI standards.
  - **Speed**: Built on Starlette and Pydantic, making it one of the fastest Python frameworks.
- **Cons**: 
  - Relatively new compared to Flask/Django, meaning fewer legacy third-party plugins.
  - Requires understanding asynchronous execution patterns to avoid blocking the main event loop.

### Alternative Approaches
- **Flask**: A synchronous WSGI framework.
  - *Tradeoff*: Simple and mature, but lacks built-in async support. For long-running AI/LLM requests, Flask would require complex worker setups (like Gunicorn with gevent) to prevent locking the server for other users.
- **Django**: A full-featured "batteries-included" framework.
  - *Tradeoff*: Excellent if we need built-in auth, admin panels, and heavy SQL ORM integration, but excessively heavy for an AI-agent API with no user accounts.

### Concept Breakdown

#### 1. Explanation
FastAPI routes map HTTP methods (`GET`, `POST`, etc.) and paths to Python functions:
```python
@app.post("/api/investigate")
def investigate(payload: dict, db: Session = Depends(get_db)):
    # Business logic here
    return {"summary": "done"}
```

#### 2. Interview Questions
1. *What is the difference between ASGI (used by FastAPI) and WSGI (used by Flask)?*
2. *How does FastAPI generate its OpenAPI schema and Swagger UI under the hood?*
3. *How should you choose between defining a route handler with `def` vs. `async def` in FastAPI?*

#### 3. Failure Cases / Common Mistakes
- **Blocking the Event Loop**: Declaring a route with `async def` but running synchronous, blocking code inside it (like a heavy SQL query or a blocking `time.sleep()`). This freezes the entire application, preventing other requests from processing.
  - *Solution*: Either define database-heavy routes with normal `def` (FastAPI will execute them in a separate thread pool) or use an asynchronous database driver (like `asyncpg`) with `async def`.

---

## 2. Dependency Injection (`Depends`)

### What problem does it solve?
Connecting endpoints to database sessions, configuration settings, or security contexts requires instantiating objects. Hardcoding these resources inside each route handler violates the DRY (Don't Repeat Yourself) principle and makes testing difficult.

### Why did we need it?
Every API request needs a database connection. We used FastAPI's dependency injection (`Depends(get_db)`) to inject a PostgreSQL connection into our endpoints, ensuring that connections are opened when the request starts and closed/released back to the pool when the request finishes.

### Tradeoffs
- **Pros**: Clean code separation, centralized setup, and easy mock injection during testing.
- **Cons**: Can make tracking variable origins slightly harder for developers new to the framework.

### Alternative Approaches
- **Global Database Context**: Instantiating a single global database object and importing it.
  - *Tradeoff*: Prone to connection leaks, thread safety issues, and hard to isolate during unit testing.

### Concept Breakdown

#### 1. Explanation
FastAPI's `Depends` accepts a callable (like a function). FastAPI calls this helper before executing the route, passes the returned value as an argument, and cleans it up afterward.

#### 2. Example Code
```python
# The dependency generator
def get_db():
    db = SessionLocal()
    try:
        yield db  # Injects the session into the route
    finally:
        db.close()  # Closes the connection after the route returns

# Injecting the dependency
@app.get("/api/schema")
def schema(db: Session = Depends(get_db)):
    # db is now an active SQLAlchemy session
    return {"tables": []}
```

#### 3. Interview Questions
1. *How does FastAPI handle cleanup in dependency generators that use `yield`?*
2. *What are the benefits of Dependency Injection for writing unit tests? (How do you override dependencies)?*
3. *How do database connection pools (like SQLAlchemy's queue pool) prevent database exhaustion?*

#### 4. Common Mistakes
- **Connection Leakage**: Opening a session manually inside a route function (`db = SessionLocal()`) and forgetting to close it in a `finally` block. This leads to Postgres throwing "Too many clients" errors. Always use the `Depends(get_db)` pattern.

---

## 3. CORS Middleware (`CORSMiddleware`)

### What problem does it solve?
By default, web browsers enforce the **Same-Origin Policy**, which blocks frontends running on one domain/origin (e.g. React on `http://localhost:5173`) from sending HTTP requests to APIs running on a different domain/origin (e.g. FastAPI on `http://localhost:8000`).

### Why did we need it?
Our frontend Vite server runs on port `5173` and calls the FastAPI backend on port `8000`. Without configuring Cross-Origin Resource Sharing (CORS), the user's browser would block all requests from the React interface to our investigator endpoints.

### Tradeoffs
- **Pros**: Protects users from malicious cross-site scripting (CSRF) attempts.
- **Cons**: Can be tricky to debug during development, and setting it to wildcard `*` (allow all origins) in production is a security risk.

### Concept Breakdown

#### 1. Explanation
CORS middleware appends specific headers (like `Access-Control-Allow-Origin`) to API responses, signaling to the browser that it is safe to allow cross-origin requests.

#### 2. Example Code
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],             # In production, restrict this to the actual frontend domain
    allow_credentials=True,
    allow_methods=["*"],             # Allows GET, POST, OPTIONS, etc.
    allow_headers=["*"],             # Allows headers like Content-Type or Authorization
)
```

#### 3. Interview Questions
1. *What is a CORS preflight request, and which HTTP method does it use?*
2. *Why is `allow_origins=["*"]` dangerous in production, and how would you lock it down?*
3. *How does CORS differ from authentication/authorization?*

#### 4. Common Mistakes
- **Wildcards with Credentials**: Setting `allow_origins=["*"]` while setting `allow_credentials=True`. Browsers will block this combination for security. You must specify exact origin domains (e.g. `["http://localhost:5173"]`) if cookies or auth headers are exchanged.

---

## 4. Request Payload Parsing & Query Heuristics

### What problem does it solve?
In HTTP POST requests, the request body is transmitted as a raw string of bytes (usually JSON). Manually reading the socket stream, decoding bytes, and parsing JSON inside route handlers is repetitive and error-prone.

### Why did we need it?
Our `/api/investigate` route receives a JSON body containing the question (e.g. `{"question": "..."}`). FastAPI automatically parses this raw JSON string into a Python dictionary (`payload: dict`) for us.

### Tradeoffs
- **Pros**: Zero parsing boilerplate, automatic validation of JSON formatting.
- **Cons**: Using a generic `dict` type offers no schema enforcement. In a production app, utilizing Pydantic models for request bodies is preferred.

### Concept Breakdown

#### 1. Explanation
If you declare a parameter in a FastAPI path function that is not part of the URL path, FastAPI automatically reads it from the HTTP request body.

#### 2. Example Code
```python
# FastAPI parses incoming JSON and populates the `payload` parameter
@app.post("/api/investigate")
def investigate(payload: dict):
    question = payload.get("question", "")
    return {"status": "received", "question": question}
```

#### 3. Interview Questions
1. *How does FastAPI differentiate between query parameters, path parameters, and request body variables in a path function definition?*
2. *What is Pydantic, and why is it preferred over raw dictionaries for request body validation in FastAPI?*

#### 4. Common Mistakes
- **Forgetting Content-Type Header**: Sending client requests without the `Content-Type: application/json` header. If missing, FastAPI will fail to parse the body as JSON and return a `422 Unprocessable Entity` or `400 Bad Request` error.

---

## 5. Structured HTTP Exception Handling

### What problem does it solve?
When errors happen (e.g., missing fields, server errors, db connection losses), returning a standard Python traceback (500 error) or raw HTML is bad practice. The API should return a standardized, clean JSON error format with the correct HTTP status code.

### Why did we need it?
If a user makes a request without a question, we must return a clean `400 Bad Request` status code rather than allowing the application to throw a Python key error. We raise FastAPI's native `HTTPException` to do this.

### Concept Breakdown

#### 1. Explanation
Raising `HTTPException` stops route execution immediately and routes the response through Starlette's exception handler, formatting it as a JSON payload: `{"detail": "..."}`.

#### 2. Example Code
```python
if not question:
    raise HTTPException(
        status_code=400, 
        detail="Question is required"
    )
```

#### 3. Interview Questions
1. *How do you write a global, custom exception handler in FastAPI to catch database errors and return a custom JSON schema?*
2. *What is the difference between raising a standard Python `Exception` and raising a FastAPI `HTTPException`?*

#### 4. Common Mistakes
- **Leaking Database Internals**: Raising HTTPExceptions that output raw SQL errors in the `detail` parameter (e.g. `detail=str(sql_error)`). This exposes your database schema, keys, and table layouts, presenting a severe security vulnerability.
