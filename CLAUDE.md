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
4. DBSCAN algorithm automatically discovers clusters based on semantic similarity
5. Interactive graph visualizes connections (force-directed layout)

**The Graph:**
- **Nodes**: Individual files (size = number of connections)
- **Edges**: Semantic similarity (stronger relationships = closer positioning)
- **Clusters**: Auto-discovered groups of related documents
- **Interaction**: Click nodes to preview, drag to explore

Unlike folder hierarchies or keyword search, this reveals **hidden patterns** in how documents relate conceptually.

## Architecture

### Backend (`backend/`)
- **Framework**: FastAPI with SQLAlchemy ORM and Alembic migrations
- **Database**: PostgreSQL with pgvector extension for semantic embeddings
- **Task Queue**: Celery workers backed by Redis for async document processing
- **ML Pipeline**: sentence-transformers (all-MiniLM-L6-v2) generates 384-dim embeddings

**Database Models**:
- `File`: Documents with text content, embeddings (VECTOR(384)), and processing status
- `FileRelationship`: Semantic similarity connections (cosine similarity 0.0-1.0)
- `Cluster`: Auto-discovered document groups (via DBSCAN)
- `FileCluster`: Many-to-many mapping between files and clusters
- `ProcessingJob`: Tracks background job progress and errors

**Core modules**:
- `app/core/`: Configuration, database setup, Celery app
- `app/models/`: SQLAlchemy models with pgvector support
- `app/api/v1/`: API endpoints
- `app/workers/`: Celery tasks for document processing

### Frontend (`frontend/`)
- **Framework**: Next.js 15 with App Router (not Pages Router)
- **State**: Zustand for global state, TanStack Query for server state
- **Graph**: react-force-graph 2D for visualization
- **Styling**: Tailwind CSS v4
- **Location**: Source files in `frontend/src/app/`

### Docker Services
- `ai-rel-graph-postgres`: pgvector/pgvector:pg15 on port 5432
- `ai-rel-graph-redis`: Redis 7 on port 6379
- `ai-rel-graph-backend`: FastAPI on port 8000
- `ai-rel-graph-celery`: Background task processor
- `ai-rel-graph-frontend`: Next.js served via nginx on port 80

## Development Commands

### Initial Setup
```bash
make setup              # Copy .env files and install dependencies
make docker-up          # Start all services
sleep 10                # Wait for services to be ready
make db-upgrade         # Run database migrations
./scripts/test-setup.sh # Verify everything works
```

### Daily Development
```bash
make docker-up          # Start all Docker services
make docker-logs        # Follow logs from all services
make health-check       # Check service health
make docker-down        # Stop all services
```

### Code Quality
```bash
make format             # Format with black (backend) and prettier (frontend)
make lint               # Run ruff (backend) and eslint (frontend)
make typecheck          # Run mypy (backend) and tsc (frontend)
make check              # Run format, lint, typecheck, and test
make test               # Run all tests
```

### Database Operations
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
make docker-status      # Check container status
make clean              # Remove cache files
```

## Database Schema

### Core Tables

**files** - Document storage with embeddings
```sql
id                  UUID PRIMARY KEY
google_drive_id     VARCHAR(255) UNIQUE NOT NULL (indexed)
name                VARCHAR(500) NOT NULL
mime_type           VARCHAR(100)
size_bytes          BIGINT
text_content        TEXT
embedding           VECTOR(384)  -- pgvector, ivfflat indexed
processing_status   VARCHAR(50) DEFAULT 'pending' (indexed)
created_at          TIMESTAMP
modified_at         TIMESTAMP
```

**file_relationships** - Semantic similarity connections
```sql
id                  UUID PRIMARY KEY
source_file_id      UUID FK → files.id ON DELETE CASCADE
target_file_id      UUID FK → files.id ON DELETE CASCADE
similarity_score    FLOAT (0.0-1.0, indexed)
relationship_type   VARCHAR(50) DEFAULT 'semantic_similarity'
created_at          TIMESTAMP

CONSTRAINTS:
  - source_file_id ≠ target_file_id (no self-relationships)
  - UNIQUE(source_file_id, target_file_id)
  - similarity_score BETWEEN 0.0 AND 1.0
```

**clusters** - Auto-discovered document groups
```sql
id          UUID PRIMARY KEY
label       VARCHAR(255)  -- Auto-generated from content
created_at  TIMESTAMP
```

**file_clusters** - Many-to-many file↔cluster mapping
```sql
file_id     UUID FK → files.id ON DELETE CASCADE (PK)
cluster_id  UUID FK → clusters.id ON DELETE CASCADE (PK)
```

**processing_jobs** - Background job tracking
```sql
id                   UUID PRIMARY KEY
folder_id            VARCHAR(255)
status               VARCHAR(50) DEFAULT 'queued' (indexed)
progress_percentage  INTEGER DEFAULT 0
total_files          INTEGER DEFAULT 0
processed_files      INTEGER DEFAULT 0
error_message        TEXT
created_at           TIMESTAMP
completed_at         TIMESTAMP
```

### Key Features

✅ **pgvector Integration**: 384-dimensional embeddings with ivfflat index for fast cosine similarity search
✅ **CASCADE Deletes**: Deleting files auto-removes relationships and cluster mappings
✅ **Data Integrity**: Constraints prevent self-relationships, duplicate pairs, and invalid similarity scores
✅ **Performance Indexes**: Optimized for status filtering, similarity queries, and vector search

## Semantic Pipeline

### 1. Document Ingestion
```python
# User provides Google Drive folder → Celery job created
ProcessingJob(folder_id="...", status="queued", total_files=0)
```

### 2. Text Extraction
```python
# PDF/DOCX/XLSX → raw text
File(google_drive_id="...", text_content="...", processing_status="processing")
```

### 3. Embedding Generation
```python
# sentence-transformers converts text → 384-dim vector
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
embedding = model.encode(text)  # → [0.234, -0.567, ...]

File.embedding = embedding.tolist()
```

### 4. Relationship Discovery
```python
# Compute cosine similarity between all document pairs
from sklearn.metrics.pairwise import cosine_similarity
similarity_matrix = cosine_similarity(embeddings)

# Create relationships above threshold (e.g., 0.3)
if similarity >= 0.3:
    FileRelationship(
        source_file_id=file1.id,
        target_file_id=file2.id,
        similarity_score=similarity
    )
```

### 5. Automatic Clustering
```python
# DBSCAN discovers clusters from embeddings
from sklearn.cluster import DBSCAN
dbscan = DBSCAN(eps=0.5, min_samples=2, metric='cosine')
cluster_labels = dbscan.fit_predict(embeddings)

# Auto-generate cluster names from content
def generate_cluster_name(cluster_files):
    # Extract most common words from all files
    # Return "Learning & Neural", "Financial & Budget", etc.
```

### 6. Graph Visualization
```python
# Frontend receives:
# - Nodes: files with metadata
# - Edges: relationships with similarity scores
# - Clusters: groupings with labels
# react-force-graph renders interactive visualization
```

## Demo & Testing

### Run Schema Demo
```bash
./RUN_DEMO.sh
```

Creates 11 realistic documents, generates embeddings, discovers relationships and clusters:
- **~35-40 relationships** (threshold: 0.3)
- **4-5 clusters** with auto-generated names like "Learning & Neural", "Financial & Budget"
- **0-2 outliers** (documents that don't fit any cluster)

### Run Tests
```bash
# All tests
make test

# Backend model tests only
docker exec ai-rel-graph-backend pytest tests/models/ -v --cov=app.models

# Create test database first
docker exec ai-rel-graph-postgres psql -U postgres -c "CREATE DATABASE semantic_graph_test;"
docker exec ai-rel-graph-postgres psql -U postgres -d semantic_graph_test -c "CREATE EXTENSION vector;"
```

**Test Coverage**:
- 35+ tests validating models, constraints, indexes, and CASCADE deletes
- Tests use real PostgreSQL with pgvector (not SQLite)
- Validates vector embeddings, similarity bounds, cluster discovery

### Database Exploration
```bash
# Connect to database
docker exec -it ai-rel-graph-postgres psql -U postgres -d semantic_graph_demo

# Useful queries
SELECT * FROM clusters;
SELECT COUNT(*) FROM file_relationships;
SELECT f1.name, f2.name, fr.similarity_score
FROM file_relationships fr
JOIN files f1 ON fr.source_file_id = f1.id
JOIN files f2 ON fr.target_file_id = f2.id
ORDER BY fr.similarity_score DESC LIMIT 10;
```

## Environment Configuration

**Backend** (`backend/.env`):
```bash
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=semantic_graph

REDIS_HOST=redis
REDIS_PORT=6379

CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret

SENTENCE_TRANSFORMER_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
SIMILARITY_THRESHOLD=0.3
```

**Frontend** (`frontend/.env.local`):
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

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

### pgvector Setup
The pgvector extension must be enabled in PostgreSQL:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

This is automatically done in migrations and test setup. Vector columns use `VECTOR(384)` type with ivfflat index for performance.

### Clustering Algorithm
DBSCAN is used for automatic cluster discovery:
- **eps=0.5**: Maximum cosine distance between neighbors
- **min_samples=2**: Minimum documents to form cluster
- **metric='cosine'**: Semantic similarity measure

Adjust `eps` to control cluster tightness (lower = stricter, more outliers).

## Package Management

- **Backend**: Poetry (`poetry add <package>`, `poetry install`)
- **Frontend**: pnpm (`pnpm add <package>`, `pnpm install`)

After adding dependencies, run `make docker-rebuild` to rebuild containers.

## Service URLs
- **Frontend**: http://localhost
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **PostgreSQL**: localhost:5432 (database: semantic_graph, user: postgres)
- **Redis**: localhost:6379

## Troubleshooting

**Containers won't start**: Check Docker is running, run `make docker-status`
**Database connection errors**: Ensure PostgreSQL container is healthy, check logs
**pgvector errors**: Verify extension is enabled (`\dx` in psql)
**Import errors**: Run `make docker-rebuild` after adding dependencies
**Migration conflicts**: Check `alembic/versions/` for duplicate revisions
