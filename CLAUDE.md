# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Core Concept

AIRelGraph analyzes documents to discover **semantic relationships** - connections based on meaning and purpose rather than explicit links. For example:

- Two research papers about penguin migration → linked by shared topic
- A budget spreadsheet and financial report → linked by similar purpose/domain
- Meeting notes mentioning "Q4 strategy" → linked to strategy documents

**How it works:**
1. User provides a Google Drive folder
2. System extracts text from all documents
3. ML model (sentence-transformers) converts text to 384-dimensional vectors (embeddings)
4. Documents are clustered by purpose/topic
5. Interactive graph visualizes connections (Obsidian-style force-directed layout)

**The Graph:**
- **Nodes**: Individual files (size = number of connections)
- **Edges**: Semantic similarity (stronger relationships = closer positioning)
- **Clusters**: Groups of related documents
- **Interaction**: Click nodes to preview, drag to explore

Unlike folder hierarchies or keyword search, this reveals **hidden patterns** in how documents relate conceptually.

The system consists of:
- **Backend**: FastAPI application with PostgreSQL (pgvector), Redis, and Celery workers for async processing
- **Frontend**: Next.js 15 application with React 19, using Cytoscape for graph visualization
- **Infrastructure**: Docker Compose orchestrating backend, frontend, database, Redis, and Celery workers

## Architecture

### Backend (`backend/`)
- **Framework**: FastAPI with SQLAlchemy ORM and Alembic migrations
- **Database**: PostgreSQL with pgvector extension for semantic embeddings
- **Task Queue**: Celery workers backed by Redis for async document processing
- **ML Pipeline**: Uses sentence-transformers (all-MiniLM-L6-v2) for generating 384-dim embeddings
- **Key Models**:
  - `File`: Stores documents from Google Drive with text content and processing status
  - `FileRelationship`: Tracks semantic similarity between documents (cosine similarity scores)
  - `Cluster`: Groups semantically similar documents
  - `Job`: Tracks background processing jobs

**Core modules**:
- `app/core/`: Configuration, database setup, Celery app
- `app/models/`: SQLAlchemy models
- `app/api/v1/`: API endpoints (currently minimal)
- `app/workers/`: Celery tasks for document processing and embedding generation

### Frontend (`frontend/`)
- **Framework**: Next.js 15 with App Router (not Pages Router)
- **State**: Zustand for global state, TanStack Query for server state
- **Graph**: Cytoscape.js with cola layout for force-directed graphs
- **Styling**: Tailwind CSS v4
- **Location**: Source files in `frontend/src/app/`

### Docker Services
- `postgres`: pgvector/pgvector:pg15 on port 5432
- `redis`: Redis 7 on port 6379
- `backend`: FastAPI on port 8000
- `celery_worker`: Background task processor
- `frontend`: Next.js production build served via nginx on port 80

## Development Commands

### Initial Setup
```bash
make setup              # Copy .env files and install dependencies
make docker-up          # Start all services
sleep 10                # Wait for services to be ready
make db-upgrade         # Run database migrations
./scripts/test-setup.sh # Verify everything works
make urls               # Show all service URLs
```

### Daily Development
```bash
make docker-up          # Start all Docker services
make docker-logs        # Follow logs from all services
make health-check       # Check service health
make docker-down        # Stop all services
```

### Local Development (without Docker)
```bash
make dev-backend        # Run backend with uvicorn --reload (requires local DB)
make dev-frontend       # Run frontend with pnpm dev
```

### Code Quality
```bash
make format             # Format with black (backend) and prettier (frontend)
make lint               # Run ruff (backend) and eslint (frontend)
make typecheck          # Run mypy (backend) and tsc (frontend)
make check              # Run format, lint, typecheck, and test
```

### Testing
```bash
make test               # Run all tests
make backend-test       # Run pytest
make backend-test-cov   # Run pytest with coverage report
make frontend-test      # Run jest
```

### Database
```bash
make db-migrate         # Create new Alembic migration (prompts for message)
make db-upgrade         # Apply pending migrations
make db-downgrade       # Rollback last migration
make db-shell           # Open psql shell to semantic_graph database
make db-reset           # Destroy and recreate database (WARNING: data loss)
```

### Troubleshooting
```bash
make docker-rebuild     # Rebuild containers after dependency changes
make docker-logs-backend # View backend logs only
make docker-logs-frontend # View frontend logs only
make docker-status      # Check container status
make docker-clean       # Remove all containers, volumes, images (interactive)
make clean              # Remove Python cache files and .next
```

## Package Management

- **Backend**: Poetry (`poetry add <package>`, `poetry install`)
- **Frontend**: pnpm (`pnpm add <package>`, `pnpm install`)

After adding dependencies, run `make docker-rebuild` to rebuild containers.

## Environment Configuration

Backend requires `.env` with:
- PostgreSQL credentials (POSTGRES_USER, POSTGRES_PASSWORD, etc.)
- Redis connection (REDIS_HOST, REDIS_PORT)
- Celery broker URLs
- Google Drive API credentials (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET)
- ML model settings (SENTENCE_TRANSFORMER_MODEL, EMBEDDING_DIMENSION, SIMILARITY_THRESHOLD)

Frontend requires `.env.local` with:
- NEXT_PUBLIC_API_URL
- NEXT_PUBLIC_WS_URL

## Important Implementation Details

### Database Migrations
Always create migrations when modifying models:
```bash
make db-migrate  # Creates migration in backend/alembic/versions/
make db-upgrade  # Applies migration
```

### Celery Tasks
Tasks are defined in `app/workers/tasks.py` and must be imported in `app/core/celery_app.py` include list. The Celery worker runs in a separate Docker container.

### API Development
API endpoints go in `app/api/v1/`. The main FastAPI app is in `app/main.py`. CORS is configured to allow origins from ALLOWED_ORIGINS in settings.

### Frontend Routing
Next.js App Router: pages are in `frontend/src/app/` with route structure based on directory names (e.g., `app/graph/page.tsx` → `/graph`).

### Semantic Similarity Pipeline
1. Text extraction: PDFs, DOCX, XLSX → raw text
2. Embedding generation: sentence-transformers creates vector representation
3. Clustering: DBSCAN/K-means groups documents by semantic proximity
4. Graph construction: Nodes (files) + edges (relationships) → Cytoscape visualization

## Service URLs
- Frontend: http://localhost
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- PostgreSQL: localhost:5432 (database: semantic_graph, user: postgres)
- Redis: localhost:6379
