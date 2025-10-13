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
3. Automated tag extraction identifies keywords and categorizes documents
4. Documents sharing tags are connected (minimum 2 shared tags)
5. Community detection algorithm discovers clusters based on tag relationships
6. Interactive graph visualizes connections (force-directed layout)

**The Graph:**
- **Nodes**: Individual files (size = number of connections)
- **Edges**: Shared tag count (more shared tags = stronger connection)
- **Clusters**: Auto-discovered groups of documents with similar tags
- **Interaction**: Click nodes to preview, drag to explore

Unlike folder hierarchies or keyword search, this reveals **hidden patterns** in how documents relate through shared topics and categories.

## Architecture

### Backend (`backend/`)
- **Framework**: FastAPI with SQLAlchemy ORM and Alembic migrations
- **Database**: PostgreSQL for structured data storage
- **Task Queue**: Celery workers backed by Redis for async document processing
- **NLP Pipeline**: NLTK + scikit-learn for automated tag extraction and categorization

**Database Models**:
- `File`: Documents with text content and processing status
- `Tag`: Extracted keywords with category classification (technology, finance, business, etc.)
- `FileTag`: Many-to-many mapping with relevance scores
- `FileRelationship`: Tag-based connections (shared_tag_count, Jaccard similarity)
- `Cluster`: Auto-discovered document groups (via community detection)
- `FileCluster`: Many-to-many mapping between files and clusters
- `ProcessingJob`: Tracks background job progress and errors

**Core modules**:
- `app/core/`: Configuration, database setup, Celery app
- `app/models/`: SQLAlchemy models for tags, files, and relationships
- `app/api/v1/`: API endpoints (files, tag-based processing)
- `app/services/`: Business logic services (TagExtractionService, SemanticProcessingService)
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

**files** - Document storage
```sql
id                  UUID PRIMARY KEY
google_drive_id     VARCHAR(255) UNIQUE NOT NULL (indexed)
name                VARCHAR(500) NOT NULL
mime_type           VARCHAR(100)
size_bytes          BIGINT
text_content        TEXT
processing_status   VARCHAR(50) DEFAULT 'pending' (indexed)
created_at          TIMESTAMP
modified_at         TIMESTAMP
```

**tags** - Extracted keywords with categories
```sql
id              UUID PRIMARY KEY
name            VARCHAR(100) UNIQUE NOT NULL (indexed)
category        VARCHAR(50) (indexed)  -- technology, finance, business, etc.
usage_count     INTEGER DEFAULT 0      -- number of files using this tag
created_at      TIMESTAMP
```

**file_tags** - Many-to-many file↔tag mapping
```sql
file_id          UUID FK → files.id ON DELETE CASCADE (PK)
tag_id           UUID FK → tags.id ON DELETE CASCADE (PK)
relevance_score  FLOAT DEFAULT 1.0  -- how relevant the tag is to the document
```

**file_relationships** - Tag-based connections
```sql
id                  UUID PRIMARY KEY
source_file_id      UUID FK → files.id ON DELETE CASCADE
target_file_id      UUID FK → files.id ON DELETE CASCADE
shared_tag_count    INTEGER NOT NULL (indexed)  -- number of tags in common
similarity_score    FLOAT (0.0-1.0, indexed)    -- Jaccard similarity
relationship_type   VARCHAR(50) DEFAULT 'tag_similarity'
created_at          TIMESTAMP

CONSTRAINTS:
  - source_file_id ≠ target_file_id (no self-relationships)
  - UNIQUE(source_file_id, target_file_id)
  - similarity_score BETWEEN 0.0 AND 1.0
  - shared_tag_count >= 0
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

✅ **Tag-Based Relationships**: Documents connected by shared keywords and categories
✅ **CASCADE Deletes**: Deleting files auto-removes tags, relationships, and cluster mappings
✅ **Data Integrity**: Constraints prevent self-relationships, duplicate pairs, and invalid scores
✅ **Performance Indexes**: Optimized for tag lookups, shared tag counting, and status filtering
✅ **Category Classification**: Automatic categorization into 8 broad domains (technology, finance, etc.)

## Tag-Based Processing Pipeline

The tag-based processing pipeline is implemented in [app/services/semantic.py](backend/app/services/semantic.py) as `SemanticProcessingService` (renamed but still uses this class name for backward compatibility). Tag extraction is handled by [app/services/tag_extraction.py](backend/app/services/tag_extraction.py).

### Using the Processing Service

**Direct Usage (Synchronous)**:
```python
from app.services.semantic import SemanticProcessingService
from app.core.database import SessionLocal

# Initialize service
service = SemanticProcessingService(
    min_shared_tags=2,        # Minimum shared tags for relationships
    min_tag_frequency=2,      # Minimum word frequency for tags
    max_tags_per_doc=10,      # Maximum tags per document
)

# Process documents through full pipeline
db = SessionLocal()
results = service.process_documents(
    session=db,
    files=files,  # List of File objects with text_content
    min_shared=2,
    show_progress=True,
)

# Results contain:
# - file_tags: dict mapping file_id to list of (Tag, relevance) tuples
# - relationships: list of FileRelationship objects
# - clusters: list of (Cluster, files) tuples
# - adjacency: graph adjacency dict
```

**API Usage (Asynchronous via Celery)**:
```bash
# Full pipeline: tag extraction + relationships + clustering
POST /api/v1/semantic/process
{
  "file_ids": ["uuid1", "uuid2", ...],
  "min_shared_tags": 2,
  "create_job": true
}

# Step-by-step processing
POST /api/v1/semantic/tags              # Step 1: Extract tags
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

### 3. Tag Extraction
```python
# TagExtractionService extracts keywords and categorizes documents
from app.services.tag_extraction import TagExtractionService

extractor = TagExtractionService()
tags = extractor.extract_tags(text)
# → [(tag_name, category, relevance_score), ...]
# Example: [("machine", "technology", 0.87), ("learning", "technology", 0.82)]
```

Categories detected:
- `technology`, `finance`, `business`, `human_resources`
- `legal`, `marketing`, `operations`, `research`

### 4. Relationship Discovery
```python
# Create relationships based on shared tags
relationships, adjacency = service.create_relationships_with_graph(
    session=db,
    files=files,
    min_shared=2,  # Only relationships with >= 2 shared tags
)
# Returns: relationships list + adjacency graph for clustering
# Similarity score = Jaccard similarity = |shared_tags| / |union_tags|
```

### 5. Community-Based Clustering
```python
# Use Louvain algorithm to find natural communities in relationship graph
clusters = service.create_clusters_from_communities(
    session=db,
    files=files,
    adjacency=adjacency,  # Graph from step 4
)

# Auto-generate cluster names from most common tags
# Example: "Technology & Machine & Learning (15 docs)"
# Example: "Finance & Budget (8 docs)"
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

**System Migration (2025-10-12)**: From embedding-based to tag-based
- **Previous**: ML embeddings + cosine similarity (sentence-transformers)
- **Current**: Keyword extraction + tag matching (NLTK + TF-IDF)
- **Benefits**: More transparent, explainable, and lightweight
- **See**: [TAG_SYSTEM_MIGRATION.md](TAG_SYSTEM_MIGRATION.md) for full details

**Clustering Algorithm (Community Detection)**: Uses Louvain on relationship graph
- Discovers natural communities based on tag-based connections
- More robust and semantically meaningful than distance-based clustering
- Default: min_shared_tags=2 creates appropriate sparsity

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
- Relationships based on shared tags (min_shared_tags: 2)
- 4-5 clusters with auto-generated names like "Technology & Machine & Learning", "Finance & Budget"
- 0-2 outliers (documents that don't share enough tags with others)

**Large-Scale Demo** (`make demo-large`):
- 100 synthetic documents across 8 topic areas
- Performance metrics: tag extraction speed, database insertion, relationship creation
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
- 40+ service tests for tag extraction, relationships, and clustering
- Tests use real PostgreSQL (no longer requires pgvector extension)
- Validates tag extraction quality, shared tag counting, community detection
- Tests located in [backend/tests/](backend/tests/)
- **Note**: Tests need updating after tag-based migration

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

# Tag extraction parameters (optional, have defaults)
MIN_SHARED_TAGS=2           # Minimum shared tags for relationships (default: 2)
MIN_TAG_FREQUENCY=2         # Minimum word frequency for tag extraction (default: 2)
MAX_TAGS_PER_DOC=10         # Maximum tags per document (default: 10)
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

**Available Tag-Based Processing Tasks**:
- `process_files_with_tags`: Full pipeline (tag extraction + relationships + clustering)
- `extract_tags_task`: Step 1 - Extract tags from files
- `create_tag_relationships`: Step 2 - Create relationships based on shared tags
- `cluster_documents`: Step 3 - Cluster files using community detection

**Deprecated Tasks** (for backward compatibility):
- `process_files_semantically` → redirects to `process_files_with_tags`
- `generate_embeddings` → redirects to `extract_tags_task`
- `create_semantic_relationships` → redirects to `create_tag_relationships`

All tasks support:
- Automatic retry on failure (max 3 retries)
- Integration with ProcessingJob for progress tracking
- Rollback on error to maintain database consistency

### API Development
API endpoints go in `app/api/v1/`. The main FastAPI app is in `app/main.py`. CORS is configured to allow origins from ALLOWED_ORIGINS in settings.

**Tag-Based Processing Endpoints** ([app/api/v1/semantic.py](backend/app/api/v1/semantic.py)):
- `POST /api/v1/semantic/process` - Full tag-based pipeline (async)
- `POST /api/v1/semantic/tags` - Extract tags only
- `POST /api/v1/semantic/relationships` - Create relationships based on shared tags
- `POST /api/v1/semantic/cluster` - Cluster documents only
- `GET /api/v1/semantic/task/{task_id}` - Check async task status

All endpoints validate input, return task IDs for monitoring, and provide detailed error messages.

### Frontend Routing
Next.js App Router: pages are in `frontend/src/app/` with route structure based on directory names (e.g., `app/graph/page.tsx` → `/graph`).

### Database Setup
PostgreSQL is used for structured data storage. No special extensions required (pgvector was removed in tag-based migration).

### Clustering Algorithm
Community detection (Louvain algorithm) is used for automatic cluster discovery:
- **Input**: Relationship graph based on shared tags
- **Algorithm**: Louvain community detection via NetworkX
- **Fallback**: Connected components if NetworkX unavailable
- **Resolution**: 1.0 (standard modularity optimization)

The algorithm discovers natural communities in the tag-based relationship graph, producing semantically meaningful clusters based on shared topics and categories.

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