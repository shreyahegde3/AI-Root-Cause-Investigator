# Docker Configuration & Orchestration Deep Dive - Learning Module

This document outlines the Docker and container orchestration concepts utilized in Phase 4 of the **AI SQL Root Cause Investigator** project.

---

## 1. Containerization & Compose Orchestration

### What problem does it solve?
Deploying a modern web application requires compiling and configuring multiple separate technologies (FastAPI backend, PostgreSQL database, Redis cache, React frontend, Node.js environment). 

Running these services manually on a host machine leads to "works on my machine" compatibility errors, conflicting package versions, and tedious startup procedures.

### Why did we need it?
We need all services (database, cache, API server, UI client) to start deterministically with a single command. We use **Docker Compose** to containerize, network, configure, and launch our entire 4-service microservice stack.

### Tradeoffs
- **Pros**:
  - **Environment Parity**: The exact same container image runs in local development, testing, and production, eliminating dependency drift.
  - **Service Isolation**: Each service runs in its own lightweight namespace, preventing resource leakage or dependency pollution.
  - **Easy Portability**: A developer can clone the repo, run `docker compose up`, and have the entire system active within seconds.
- **Cons**:
  - Incremental build overhead (waiting for image compilations during local edits).
  - Storage space consumed by cached Docker layers and base OS filesystem layers.

### Alternative Approaches
- **Virtual Machines (e.g. VMware, VirtualBox)**: Running each service in its own isolated guest operating system.
  - *Tradeoff*: Massive memory and storage overhead, slow start times, hard to orchestrate.
- **Bare-Metal Manual Install**: Installing PostgreSQL, Redis, Node, and Python on the host OS.
  - *Tradeoff*: Low CPU overhead, but highly complex to manage, prone to version conflicts, and hard for interviewers to test.

---

## 2. Multi-Service Networking & Depends-On Conditions

### What problem does it solve?
Containers are isolated by default. To talk to one another, they need to join a common virtual network. 

Additionally, if the `backend` container starts before `postgres` is fully initialized and listening, the backend will fail to connect and crash. We need to control container startup ordering based on the actual *health* of the dependencies, not just their process state.

### Concept Breakdown

#### 1. Compose Internal DNS
Docker Compose creates a default network for our services. Every container can resolve other containers by their service name (e.g. the backend connects to `postgresql://postgres:postgres@postgres:5432` where `postgres` resolves to the IP address of the db container).

#### 2. Healthcheck & Depends-On Lifecycle
We define custom tests to verify when databases are fully initialized, and block dependent containers from starting until those tests pass:
```yaml
  postgres:
    image: postgres:15-alpine
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d rca_db"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    build: ./backend
    depends_on:
      postgres:
        condition: service_healthy  # Ensures postgres is ready before backend boots
```

#### 3. Interview Questions
1. *What is the difference between `depends_on` (default process check) and `depends_on` with `condition: service_healthy`?*
2. *How does Docker handle network resolution between containers in the same Compose file?*
3. *What is a bridge network in Docker, and how does it differ from a host network?*

#### 4. Common Mistakes
- **Process vs. Health Check Dependency**: Using standard `depends_on: [postgres]` without a health check condition. The database container process starts instantly, but it takes 3-10 seconds to create schemas and listen on port 5432. The backend will start immediately, fail to connect, and exit.

---

## 3. Persistent Volumes

### What problem does it solve?
Docker containers are **ephemeral** (stateless). Any data written inside a container's filesystem (like database records or user uploads) is permanently destroyed when the container is deleted or rebuilt.

### Why did we need it?
We generated 128,000 orders and loaded them into PostgreSQL. We don't want to re-run the 15-second data generator script every time we restart the containers. We use **Named Docker Volumes** (`postgres_data` and `redis_data`) to map database directories on the host disk, keeping the data safe across restarts and builds.

### Concept Breakdown

#### 1. Named Volumes Configuration
```yaml
services:
  postgres:
    image: postgres:15-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data # Persists the PostgreSQL data directory

volumes:
  postgres_data: # Declares the named volume
```

#### 2. Interview Questions
1. *What is the difference between a Named Volume and a Bind Mount? When would you use each?*
2. *Where does Docker physically store Named Volumes on the host filesystem under Linux and Windows (WSL)?*

#### 3. Common Mistakes
- **Permission Denied inside Volumes**: Binding a host folder to a container database directory where the container database user (e.g. `uid 70` for postgres) does not have write access. Using Docker Named Volumes avoids this by automatically setting correct permissions.
