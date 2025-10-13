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
- `app/api/v1/`: API endpoints (files, semantic processing)
- `app/services/`: Business logic services (SemanticProcessingService)
- `app/workers/`: Celery tasks for async document processing

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

The semantic processing pipeline is implemented in [app/services/semantic.py](backend/app/services/semantic.py) as `SemanticProcessingService`. This service can be used directly or via Celery tasks for async processing.

### Using the Semantic Service

**Direct Usage (Synchronous)**:
```python
from app.services.semantic import SemanticProcessingService
from app.core.database import SessionLocal

# Initialize service
service = SemanticProcessingService(
    model_name="all-MiniLM-L6-v2",
    similarity_threshold=0.5,
)

# Process documents through full pipeline
db = SessionLocal()
results = service.process_documents(
    session=db,
    files=files,  # List of File objects with text_content
    threshold=0.5,
    show_progress=True,
)

# Results contain:
# - embeddings: numpy array of embeddings
# - relationships: list of FileRelationship objects
# - clusters: list of (Cluster, files) tuples
# - adjacency: graph adjacency dict
```

**API Usage (Asynchronous via Celery)**:
```bash
# Full pipeline: embeddings + relationships + clustering
POST /api/v1/semantic/process
{
  "file_ids": ["uuid1", "uuid2", ...],
  "similarity_threshold": 0.5,
  "create_job": true
}

# Step-by-step processing
POST /api/v1/semantic/embeddings        # Step 1: Generate embeddings
POST /api/v1/semantic/relationships     # Step 2: Create relationships
POST /api/v1/semantic/cluster           # Step 3: Cluster using community detection

# Check task status
GET /api/v1/semantic/task/{task_id}
```

### Pipeline Steps

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
# SemanticProcessingService converts text → 384-dim vectors
from app.services.semantic import SemanticProcessingService

service = SemanticProcessingService()
embeddings = service.generate_embeddings(texts)
# → numpy array shape (n_docs, 384)
```

### 4. Relationship Discovery
```python
# Create relationships based on cosine similarity
relationships, adjacency = service.create_relationships_with_graph(
    session=db,
    files=files,
    embeddings=embeddings,
    threshold=0.5,  # Only relationships >= 0.5 similarity
)
# Returns: relationships list + adjacency graph for clustering
```

### 5. Community-Based Clustering
```python
# Use Louvain algorithm to find natural communities in relationship graph
clusters = service.create_clusters_from_communities(
    session=db,
    files=files,
    adjacency=adjacency,  # Graph from step 4
)

# Auto-generate semantic topic names from cluster content
# Example: "Neural Networks Learning (15 docs)"
```

### 6. Graph Visualization
```python
# Frontend receives:
# - Nodes: files with metadata
# - Edges: relationships with similarity scores
# - Clusters: communities with semantic labels
# react-force-graph renders interactive visualization
```

### Key Algorithm Changes

**Previous (DBSCAN)**: Clustered embeddings directly
- Problem: Created many small clusters, sensitive to eps parameter
- Clusters based purely on embedding distance

**Current (Community Detection)**: Clusters relationship graph
- Solution: Uses Louvain algorithm on relationship graph
- Discovers natural communities based on actual connections
- More robust, semantically meaningful clusters
- Threshold: 0.5 (default) creates appropriate sparsity

## Demo & Testing

### Run Demos

```bash
# Small demo (11 realistic documents)
make demo

# Large-scale demo (100 documents)
make demo-large

# Full scaling tests (50, 100, 250, 500 documents)
make demo-scale

# Custom size (e.g., 250 documents)
make demo-custom NUM=250
```

**Small Demo** (`make demo`):
- 11 realistic documents (ML papers, financial reports, meeting notes, HR docs)
- ~35-40 relationships (threshold: 0.3)
- 4-5 clusters with auto-generated names like "Learning & Neural", "Financial & Budget"
- 0-2 outliers (documents that don't fit any cluster)

**Large-Scale Demo** (`make demo-large`):
- 100 synthetic documents across 8 topic areas
- Performance metrics: embedding speed, database insertion, relationship creation
- Clustering analysis: discovers 5-10 semantic clusters
- Memory usage tracking
- Scalability projections for larger datasets (500-10,000 docs)

**Kaggle PDF Demo** (`make demo-kaggle`):
- Uses real PDF documents from Kaggle dataset
- Extracts text from actual PDFs (not synthetic)
- Tests system with real-world document formats
- Validates text extraction and clustering quality
- Requires Kaggle API credentials: `~/.kaggle/kaggle.json`
- Get credentials from [kaggle.com/settings](https://www.kaggle.com/settings)
- Accept [dataset terms](https://www.kaggle.com/datasets/manisha717/dataset-of-pdf-files)

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
- 35+ model tests validating constraints, indexes, and CASCADE deletes
- 40+ semantic service tests for embeddings, relationships, and clustering
- Tests use real PostgreSQL with pgvector (not SQLite)
- Validates vector embeddings, similarity bounds, community detection
- Tests located in [backend/tests/](backend/tests/)

### Visualize Results

After running a demo, visualize the semantic graph using [visualize_graph.py](backend/visualize_graph.py):

```bash
# Interactive visualization (spring layout)
make visualize

# Circular cluster layout
make visualize-circular

# Cluster statistics
make visualize-stats

# Save to file
make visualize-save FILE=my_graph.png

# Generate all visualizations
make visualize-all  # Creates graph_spring.png, graph_circular.png, graph_stats.png
```

**What you'll see**:
- **Nodes**: Documents sized by connection count
- **Edges**: Relationships with thickness = similarity strength
- **Colors**: Each community/cluster has distinct color
- **Legend**: Cluster names with document counts

**Layout Options**:
- **Spring Layout**: Force-directed positioning shows natural relationships
- **Circular Layout**: Groups clusters in circles for clear visual separation

**Statistics View**:
- Documents per cluster (horizontal bar chart)
- Relationship distribution (within vs between clusters)

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
SIMILARITY_THRESHOLD=0.7  # Higher threshold = fewer, stronger connections
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
Tasks are defined in [app/workers/tasks.py](backend/app/workers/tasks.py) and must be imported in `app/core/celery_app.py` include list. The Celery worker runs in a separate Docker container.

**Available Semantic Processing Tasks**:
- `process_files_semantically`: Full pipeline (embeddings + relationships + clustering)
- `generate_embeddings`: Step 1 - Generate embeddings for files
- `create_semantic_relationships`: Step 2 - Create relationships from embeddings
- `cluster_documents`: Step 3 - Cluster files using community detection

All tasks support:
- Automatic retry on failure (max 3 retries)
- Integration with ProcessingJob for progress tracking
- Rollback on error to maintain database consistency

### API Development
API endpoints go in `app/api/v1/`. The main FastAPI app is in `app/main.py`. CORS is configured to allow origins from ALLOWED_ORIGINS in settings.

**Semantic Processing Endpoints** ([app/api/v1/semantic.py](backend/app/api/v1/semantic.py)):
- `POST /api/v1/semantic/process` - Full semantic pipeline (async)
- `POST /api/v1/semantic/embeddings` - Generate embeddings only
- `POST /api/v1/semantic/relationships` - Create relationships only
- `POST /api/v1/semantic/cluster` - Cluster documents only
- `GET /api/v1/semantic/task/{task_id}` - Check async task status

All endpoints validate input, return task IDs for monitoring, and provide detailed error messages.

### Frontend Routing
Next.js App Router: pages are in `frontend/src/app/` with route structure based on directory names (e.g., `app/graph/page.tsx` → `/graph`).

### pgvector Setup
The pgvector extension must be enabled in PostgreSQL:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

This is automatically done in migrations and test setup. Vector columns use `VECTOR(384)` type with ivfflat index for performance.

### Clustering Algorithm
Community detection (Louvain algorithm) is used for automatic cluster discovery:
- **Input**: Relationship graph (not raw embeddings)
- **Algorithm**: Louvain community detection via NetworkX
- **Fallback**: Connected components if NetworkX unavailable
- **Resolution**: 1.0 (standard modularity optimization)

The algorithm discovers natural communities in the relationship graph, producing semantically meaningful clusters. Unlike DBSCAN, it doesn't require tuning distance parameters.

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