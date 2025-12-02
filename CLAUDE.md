# Knowledge Graph Project - Claude Instructions

## Project Overview

AIRelGraph is a Knowledge Graph system that transforms unstructured Google Drive documents into an interactive, navigable semantic network. Users can explore organizational knowledge through visual connections, entity relationships, and semantic similarity rather than traditional folder hierarchies.

**Key Features:**
- Multi-tenant architecture with complete data isolation per user
- Asynchronous document processing with Celery workers
- Vector similarity search using PostgreSQL + pgvector
- LLM-powered automatic tagging and entity extraction
- D3.js force-directed graph visualization
- Google OAuth authentication via NextAuth.js

## System Architecture

The system consists of 4 main layers:

1. **Ingestion Layer** - Connects to Google Drive, detects changes, converts files
2. **Intelligence Layer** - Generates embeddings, extracts entities, tags documents with LLMs
3. **Data Layer** - Stores everything in PostgreSQL with pgvector for embeddings
4. **Frontend Layer** - Next.js 15 application with D3 force-graph visualization

## Key Technologies

- **Backend:** Python 3.10, FastAPI 0.104, Celery 5.3, Redis 7
- **Database:** PostgreSQL 15 with pgvector extension (vector similarity search)
- **AI/ML:** OpenAI (text-embedding-3-small, 1536 dims), spaCy (NER), KeyBERT, NLTK
- **Frontend:** Next.js 15, React 19, TypeScript 5, NextAuth.js 4.24
- **Visualization:** D3.js 7.9 (force-directed graph)
- **Infrastructure:** Docker, Docker Compose, Google Drive API
- **Package Managers:** Poetry (backend), pnpm (frontend)

## Project Structure

```
AIRelGraph/
├── backend/                          # Python FastAPI backend
│   ├── app/
│   │   ├── main.py                  # FastAPI app entry point
│   │   ├── api/v1/                  # API routes (v1)
│   │   │   ├── drive.py             # Google Drive endpoints
│   │   │   ├── graph.py             # Graph data endpoints
│   │   │   ├── processing.py        # Async task endpoints
│   │   │   └── users.py             # User sync endpoints
│   │   ├── core/                    # Core configuration
│   │   │   ├── config.py            # Pydantic settings
│   │   │   ├── database.py          # SQLAlchemy config
│   │   │   ├── auth.py              # JWT validation
│   │   │   └── celery_app.py        # Celery config
│   │   ├── db/models/               # SQLAlchemy ORM models
│   │   │   ├── user.py
│   │   │   ├── document.py
│   │   │   ├── tag.py
│   │   │   ├── entity.py
│   │   │   ├── document_tag.py
│   │   │   ├── document_entity.py
│   │   │   ├── document_similarity.py
│   │   │   └── processing_job.py
│   │   ├── repositories/            # Data access layer
│   │   │   ├── document_repository.py
│   │   │   ├── tag_repository.py
│   │   │   ├── entity_repository.py
│   │   │   └── similarity_repository.py
│   │   ├── services/                # Business logic
│   │   │   ├── drive_service.py
│   │   │   ├── text_extraction.py
│   │   │   ├── embedding_service.py
│   │   │   ├── similarity_service.py
│   │   │   ├── llm_tagging_service.py
│   │   │   ├── tag_hierarchy_service.py
│   │   │   └── graph_builder.py
│   │   └── workers/                 # Celery tasks
│   │       └── tasks.py
│   ├── alembic/                     # Database migrations
│   ├── pyproject.toml               # Poetry dependencies
│   └── Dockerfile                   # Backend Docker image
│
├── frontend/                        # Next.js application
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx           # Root layout
│   │   │   ├── page.tsx             # Main application UI
│   │   │   └── api/                 # API routes
│   │   │       └── auth/            # NextAuth routes
│   │   ├── components/
│   │   │   ├── GraphView.tsx        # D3 graph visualization
│   │   │   ├── DocumentManager.tsx
│   │   │   ├── FileExplorer.tsx
│   │   │   ├── DriveFileBrowser.tsx
│   │   │   └── ProcessingStatus.tsx
│   │   ├── hooks/
│   │   │   ├── useGraph.ts          # Graph data fetching
│   │   │   ├── useGoogleDrive.ts    # Drive integration
│   │   │   └── useFileProcessing.ts # Task monitoring
│   │   └── providers/
│   │       ├── SessionProvider.tsx  # NextAuth provider
│   │       └── QueryProvider.tsx    # React Query provider
│   ├── package.json                 # npm/pnpm dependencies
│   └── Dockerfile                   # Frontend Docker image
│
├── docker-compose.yml               # Development environment
├── docker-compose.prod.yml          # Production environment
└── Makefile                         # Build commands
```

## Core Concepts

### Multi-Tenant Architecture

**Critical Design Pattern:** All data is isolated by user ID.

- Every database table has a `user_id` foreign key
- Cascade deletion ensures complete data isolation
- JWT tokens contain user ID from Google OAuth
- No data can leak between users
- Each user has their own graph, tags, entities, and documents

### Database Schema (PostgreSQL + pgvector)

**User Table:**
```python
User
├── id (UUID primary key)
├── google_user_id (string, unique)
├── email (string, unique)
├── google_access_token (encrypted)
├── google_refresh_token (encrypted)
└── google_token_expires_at (timestamp)
```

**Document Table:**
```python
Document
├── id (string - Google Drive file ID)
├── user_id (FK to User) ← Multi-tenancy
├── title, url, mime_type, author
├── text_content, summary, word_count
├── embedding (vector(1536)) ← pgvector for similarity
├── is_enabled (boolean - show in graph)
├── created_at, updated_at
└── Relationships:
    ├── tags (many-to-many via DocumentTag)
    ├── entities (many-to-many via DocumentEntity)
    └── similar_documents (via DocumentSimilarity)
```

**Tag Table (Hierarchical):**
```python
Tag
├── id (auto-increment)
├── user_id (FK to User) ← Multi-tenancy
├── name (string)
├── tag_type ('high_level' | 'low_level')
├── parent_id (FK to Tag, nullable) ← Hierarchy
├── orphaned_doc_count (int) ← Auto re-split trigger
└── Relationships:
    ├── documents (many-to-many)
    ├── parent (self-referential)
    └── children (self-referential)
```

**Entity Table:**
```python
Entity
├── id (auto-increment)
├── user_id (FK to User) ← Multi-tenancy
├── name (string)
├── entity_type (string: PERSON, ORG, PRODUCT, etc.)
├── canonical_form (string) ← For deduplication
├── confidence_score (float 0-1)
└── Relationships:
    └── documents (many-to-many via DocumentEntity)
```

**DocumentSimilarity Table:**
```python
DocumentSimilarity
├── id (auto-increment)
├── source_document_id (FK to Document)
├── target_document_id (FK to Document)
├── similarity_score (float 0-1) ← Cosine similarity
└── similarity_type ('strong' | 'medium' | 'weak')
```

**Indexes:**
- `idx_documents_user_enabled` - Multi-column (user_id, is_enabled)
- `idx_documents_embedding` - IVFFlat vector index for similarity search
- `idx_tags_user_name` - Unique constraint (user_id, name)

### Processing Pipeline

```
Google Drive File Selection (UI)
  ↓
POST /api/v1/processing/start
  ↓
Celery Task: process_drive_files_task
  ├─→ Download from Google Drive API
  ├─→ Extract text (PDF, DOCX, XLSX, TXT)
  ├─→ Store Document record
  └─→ Trigger: generate_knowledge_graph_task
      ├─→ Generate embeddings (OpenAI text-embedding-3-small)
      ├─→ Extract tags via LLM (GPT-4/3.5)
      ├─→ Extract entities via hybrid NER
      ├─→ Calculate similarities (cosine distance)
      └─→ Store relationships in database
  ↓
Frontend polls GET /api/v1/processing/status/{task_id}
  ↓
Graph updates automatically via GET /api/v1/graph/data
  ↓
D3 visualization renders new nodes/edges
```

### Authentication Flow (NextAuth.js + Backend Sync)

```
1. User clicks "Sign In" in Next.js app
   ↓
2. NextAuth.js initiates Google OAuth flow
   ↓
3. Google returns access_token, refresh_token, id_token
   ↓
4. NextAuth JWT callback stores tokens in session
   ↓
5. Frontend calls POST /api/v1/users/sync with JWT
   ↓
6. Backend validates JWT, extracts user info
   ↓
7. Backend stores Google tokens in User table (encrypted)
   ↓
8. Subsequent requests include JWT in Authorization header
   ↓
9. Backend uses stored Google tokens to access Drive API
```

## Important Constraints & Decisions

### Threshold Tuning Strategy

The system uses **configurable similarity thresholds** with two modes:

1. **Fixed Threshold Mode** (default: 0.75)
   - Connect documents if cosine similarity > threshold
   - Threshold adjustable per user preferences
   - Higher threshold = fewer, stronger connections

2. **Top-K Neighbors Mode**
   - Connect each document to its K most similar documents
   - Ensures every document has connections (no orphans)
   - Default K = 5

**Similarity Tiers:**
- `strong` - Score ≥ 0.85
- `medium` - Score 0.70 - 0.84
- `weak` - Score 0.55 - 0.69

### Entity Recognition Approach

**Hybrid NER Pipeline:**
1. **Rule-based extraction** - Regex patterns for emails, dates, IDs
2. **Statistical NER** - spaCy for PERSON, ORG, GPE, PRODUCT
3. **LLM extraction** - GPT-4 for domain-specific entities
4. **KeyBERT** - Extract key phrases and topics

**Confidence Scoring:**
- Only create Entity nodes for confidence > 0.75
- Lower confidence entities stored as metadata but not visualized

**Entity Canonicalization:**
- Fuzzy matching with Levenshtein distance
- Deduplication: "Bob Smith" → "Robert Smith" (canonical)
- `canonical_form` field stores normalized name

**Context-Aware Filtering:**
- TF-IDF scoring to exclude overly common entities
- Prevents "hairball" graphs from generic terms

### Tag Hierarchy System

**Two-Level Hierarchy:**
- **High-level tags** - Broad categories (e.g., "Finance", "Engineering")
- **Low-level tags** - Subcategories (e.g., "Q3 Budget", "API Design")

**Auto Re-Split Logic:**
- Track `orphaned_doc_count` per tag
- When threshold exceeded (e.g., > 10), trigger LLM re-tagging
- Splits overloaded tags into more specific sub-tags

**Cross-Cutting Tags:**
- Tags that span multiple high-level categories
- Example: "Security" applies to both "Engineering" and "Legal"

### Scalability Considerations

- **Asynchronous processing:** All document analysis runs in Celery workers
- **Incremental updates:** Only re-process changed documents (track `updated_at`)
- **Rate limiting:** Exponential backoff for Google Drive API (implemented in `drive_service.py`)
- **Caching:** Redis for Celery results and task status
- **Vector indexing:** IVFFlat index for fast similarity search (pgvector)
- **Graph sampling:** Frontend can filter by tags, entities, similarity strength

## Common Development Tasks

### When Working on the Ingestion Layer

**Focus on:** Google OAuth, file download, text extraction, error handling

**Key files:**
- [backend/app/core/auth.py](backend/app/core/auth.py) - JWT validation
- [backend/app/api/v1/drive.py](backend/app/api/v1/drive.py) - Drive API proxy endpoints
- [backend/app/services/drive_service.py](backend/app/services/drive_service.py) - Drive API client
- [backend/app/services/text_extraction.py](backend/app/services/text_extraction.py) - File conversion
- [frontend/src/app/api/auth/[...nextauth]/route.ts](frontend/src/app/api/auth/[...nextauth]/route.ts) - NextAuth config

**Test with:** Various Google Drive file formats (`.gdoc`, `.pdf`, `.docx`, `.gsheet`, `.txt`)

**Common issues:**
- Token expiration → Check refresh token logic in `drive_service.py:39-60`
- File conversion failure → Check supported MIME types in `text_extraction.py:15-25`

### When Working on the Intelligence Layer

**Focus on:** Embedding generation, LLM prompts, NER pipeline, similarity calculation

**Key files:**
- [backend/app/services/embedding_service.py](backend/app/services/embedding_service.py) - OpenAI embeddings
- [backend/app/services/llm_tagging_service.py](backend/app/services/llm_tagging_service.py) - LLM tagging
- [backend/app/services/similarity_service.py](backend/app/services/similarity_service.py) - Cosine similarity
- [backend/app/services/graph_builder.py](backend/app/services/graph_builder.py) - Graph construction
- [backend/app/workers/tasks.py](backend/app/workers/tasks.py) - Async processing tasks

**Test with:** Sample documents of different types and lengths

**Common issues:**
- High OpenAI costs → Use GPT-3.5-turbo instead of GPT-4 for tagging
- Slow embedding generation → Batch API calls (currently single calls)
- Poor similarity results → Check embedding quality, adjust thresholds

### When Working on the Data Layer

**Focus on:** PostgreSQL schema, SQLAlchemy models, pgvector queries, migrations

**Key files:**
- [backend/app/db/models/](backend/app/db/models/) - All ORM models
- [backend/app/repositories/](backend/app/repositories/) - Data access layer
- [backend/alembic/versions/](backend/alembic/versions/) - Database migrations
- [backend/app/core/database.py](backend/app/core/database.py) - DB connection config

**Test with:** PostgreSQL client (`psql`), pgAdmin, SQL queries

**Common issues:**
- Slow queries → Check indexes, run `EXPLAIN ANALYZE`
- Migration conflicts → Resolve in Alembic with `alembic merge heads`
- Vector search accuracy → Tune IVFFlat index parameters

### When Working on the Frontend

**Focus on:** Graph visualization, Next.js App Router, React Query, authentication

**Key files:**
- [frontend/src/components/GraphView.tsx](frontend/src/components/GraphView.tsx) - D3 force-directed graph
- [frontend/src/components/DocumentManager.tsx](frontend/src/components/DocumentManager.tsx) - Document UI
- [frontend/src/hooks/useGraph.ts](frontend/src/hooks/useGraph.ts) - Graph data fetching
- [frontend/src/hooks/useFileProcessing.ts](frontend/src/hooks/useFileProcessing.ts) - Task monitoring
- [frontend/src/app/page.tsx](frontend/src/app/page.tsx) - Main app component

**Test with:** Sample graph data, various filter combinations, different screen sizes

**Common issues:**
- Slow rendering → Reduce node count, optimize D3 force simulation
- Auth issues → Check NextAuth JWT configuration
- API errors → Verify CORS settings in `backend/app/main.py:25-35`

## Development Guidelines

### Code Quality

- **Python:** Use type hints (FastAPI requires them), async/await for I/O
- **TypeScript:** Strict mode enabled, use Zod for runtime validation
- **Error handling:** Try/except in Python, error boundaries in React
- **Testing:** Jest for frontend, pytest for backend
- **Linting:** Ruff for Python, ESLint for TypeScript

### Performance Optimization

- **Batch processing:** Process multiple documents simultaneously in Celery
- **Lazy loading:** Use pagination for large document lists
- **Database indexes:** Already configured on user_id, embedding, timestamps
- **React Query caching:** 5-minute stale time for graph data
- **Vector search:** IVFFlat index provides O(log n) similarity search

### Security

- **OAuth tokens:** Stored encrypted in database (not in JWT)
- **JWT validation:** Every protected endpoint validates signature and expiration
- **Multi-tenancy:** User ID extracted from JWT, all queries filtered by user_id
- **Input sanitization:** Zod schemas validate all user inputs
- **Environment variables:** Secrets never committed (`.env` in `.gitignore`)
- **CORS:** Restricted to frontend origin only

## Debugging Tips

### If documents aren't appearing in the graph

1. Check `processing_job` table for task status:
   ```sql
   SELECT * FROM processing_job WHERE user_id = '...' ORDER BY created_at DESC;
   ```

2. Look at Celery worker logs:
   ```bash
   docker logs airelgraph-celery-worker-1
   ```

3. Verify Google Drive API permissions (OAuth scope includes `drive.readonly`)

4. Check if file conversion succeeded in [text_extraction.py](backend/app/services/text_extraction.py:30-80)

5. Confirm `is_enabled = true` for documents:
   ```sql
   SELECT id, title, is_enabled FROM document WHERE user_id = '...';
   ```

### If similarities are wrong

1. Verify embedding generation completed:
   ```sql
   SELECT id, title, embedding IS NOT NULL AS has_embedding
   FROM document WHERE user_id = '...';
   ```

2. Check similarity threshold in [similarity_service.py](backend/app/services/similarity_service.py:50-70)

3. Look at actual similarity scores:
   ```sql
   SELECT s.similarity_score, d1.title AS doc1, d2.title AS doc2
   FROM document_similarity s
   JOIN document d1 ON s.source_document_id = d1.id
   JOIN document d2 ON s.target_document_id = d2.id
   WHERE d1.user_id = '...'
   ORDER BY s.similarity_score DESC LIMIT 20;
   ```

4. Check if documents have enough content (very short docs won't cluster well)

5. Try adjusting threshold or switching to top-K mode

### If entities aren't being recognized

1. Check LLM response format in [llm_tagging_service.py](backend/app/services/llm_tagging_service.py:80-120)

2. Verify confidence threshold in entity extraction (default: 0.75)

3. Check entity records in database:
   ```sql
   SELECT e.name, e.entity_type, e.confidence_score, COUNT(de.document_id) AS doc_count
   FROM entity e
   LEFT JOIN document_entity de ON e.id = de.entity_id
   WHERE e.user_id = '...'
   GROUP BY e.id
   ORDER BY doc_count DESC;
   ```

4. Review entity canonicalization logic in [graph_builder.py](backend/app/services/graph_builder.py:150-200)

### If graph visualization is slow

1. Check number of nodes being rendered:
   ```javascript
   console.log(graphData.nodes.length, graphData.edges.length);
   ```
   - Should be < 500 nodes for smooth performance

2. Profile React component renders in Chrome DevTools

3. Implement filtering in [GraphView.tsx](frontend/src/components/GraphView.tsx:100-150):
   - Filter by tag, entity, similarity threshold
   - Hide weak edges (only show strong/medium)

4. Optimize D3 force simulation parameters:
   - Reduce iteration count
   - Increase alpha decay for faster convergence

5. Use `React.memo` and `useMemo` to prevent unnecessary re-renders

## API Endpoint Reference

### Base URL
- Development: `http://localhost:8000/api/v1`
- Production: `https://your-domain.com/api/v1`

### Graph API (`/api/v1/graph/`)

```
POST /generate
  Start async graph generation task
  Body: { file_ids: string[] }
  Returns: { task_id: string }

GET /status/{task_id}
  Check graph generation progress
  Returns: { status: 'pending'|'processing'|'completed'|'failed', progress: number }

GET /data?filters=...
  Fetch complete graph data
  Query params: tag_ids, entity_ids, similarity_threshold
  Returns: { nodes: Node[], edges: Edge[] }
```

### Processing API (`/api/v1/processing/`)

```
POST /start
  Start file processing task
  Body: { file_ids: string[] }
  Returns: { task_id: string }

GET /status/{task_id}
  Check processing progress
  Returns: { status: string, progress: number, result: any }

DELETE /cancel/{task_id}
  Cancel running task
  Returns: { message: string }
```

### Drive API (`/api/v1/drive/`)

```
GET /files
  List files from Google Drive
  Query params: page_size, page_token, mime_type
  Returns: { files: DriveFile[], nextPageToken: string }

GET /files/{file_id}
  Get file metadata
  Returns: { id, name, mimeType, size, createdTime, modifiedTime }

GET /files/{file_id}/export
  Download/export file content
  Returns: file content (binary or text)

GET /files/search?q=...
  Search files by query
  Returns: { files: DriveFile[] }
```

### Users API (`/api/v1/users/`)

```
POST /sync
  Sync user OAuth tokens to backend (called by NextAuth)
  Body: { access_token, refresh_token, expires_at, user_info }
  Returns: { user_id: string }
```

### Health Check

```
GET /health
  Health check endpoint
  Returns: { status: 'ok', database: 'connected', redis: 'connected' }
```

## Known Issues & Workarounds

### Issue 1: Google Drive API Quota Exceeded

**Symptom:** 429 errors in logs, documents not being processed

**Workaround:**
- Exponential backoff already implemented in [drive_service.py](backend/app/services/drive_service.py:100-120)
- Reduce batch size (process fewer files at once)
- Use pagination for large file lists
- Spread processing across time (manual rate limiting)

### Issue 2: PostgreSQL Out of Memory (Large Graphs)

**Symptom:** Database crashes, slow queries on large document sets

**Workaround:**
- Increase PostgreSQL `shared_buffers` in config (default: 128MB → 4GB)
- Use pagination for graph data API (limit nodes returned)
- Archive old documents (soft delete with `is_enabled = false`)
- Vacuum database regularly: `VACUUM ANALYZE;`

### Issue 3: High OpenAI API Costs

**Symptom:** Expensive bills, especially with GPT-4

**Workaround:**
- Use `gpt-3.5-turbo` instead of `gpt-4` for tagging (10x cheaper)
- Implement smart caching (check if document changed before re-processing)
- Batch embedding API calls (currently 1 request per doc)
- Truncate long documents (keep first 8000 tokens)
- Use smaller embedding model (text-embedding-3-small already used)

### Issue 4: Graph "Hairball" Problem

**Symptom:** Too many connections, unusable visualization

**Workaround:**
- Increase similarity threshold (0.75 → 0.85)
- Switch to top-K mode (limit connections per document)
- Filter common entities (use TF-IDF scoring)
- Hide weak edges in UI (show only strong/medium)
- Implement manual edge hiding in graph UI

### Issue 5: Celery Tasks Stuck in Pending State

**Symptom:** Tasks never start, Redis queue fills up

**Workaround:**
- Restart Celery worker: `docker restart airelgraph-celery-worker-1`
- Check Redis connection: `redis-cli PING`
- Clear pending tasks: `celery -A app.workers.tasks purge`
- Increase worker concurrency in `docker-compose.yml`

## Testing Strategy

### Unit Tests

**Backend:**
```bash
cd backend
poetry run pytest tests/
```

**Frontend:**
```bash
cd frontend
pnpm test
```

**Key tests to write:**
- Similarity calculation (cosine_similarity function)
- Entity resolution (canonical matching)
- Text extraction (each file format)
- Tag hierarchy logic (parent-child relationships)

### Integration Tests

- Full pipeline (file selection → processing → graph generation)
- API endpoints (all CRUD operations with real database)
- Database queries (test indexes, multi-tenancy isolation)
- Authentication flow (OAuth → JWT → backend validation)

### End-to-End Tests

- Upload document → verify appears in graph
- Search functionality → verify results
- Click node → verify details panel
- Toggle document visibility → verify graph updates
- Change similarity threshold → verify edge changes

## Deployment Checklist

Before deploying to production:

- [ ] Environment variables configured (`.env.production` files)
- [ ] PostgreSQL database provisioned and pgvector extension installed
- [ ] Database backed up (`pg_dump`)
- [ ] Google OAuth credentials set up (production redirect URIs)
- [ ] Celery workers running and monitored (systemd or Docker)
- [ ] Redis configured and persistent
- [ ] API rate limiting configured (nginx or API gateway)
- [ ] Frontend build optimized (`pnpm build`, check bundle size)
- [ ] SSL certificates installed (Let's Encrypt)
- [ ] Database indexes created (`alembic upgrade head`)
- [ ] Monitoring enabled (logs aggregation, metrics)
- [ ] Backup automation configured (daily database dumps)
- [ ] CORS configured for production domain
- [ ] Health check endpoint responding
- [ ] Docker images built and tagged
- [ ] Load balancer configured (if using multiple instances)

## Useful Commands

### Development

```bash
# Clone and setup
git clone <repo>
cd AIRelGraph

# Start entire stack with Docker Compose
docker-compose up

# Or run components individually:

# Backend (with hot reload)
cd backend
poetry install
poetry run alembic upgrade head
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Celery worker
cd backend
poetry run celery -A app.workers.tasks worker --loglevel=info

# Frontend (development mode)
cd frontend
pnpm install
pnpm dev

# Run tests
cd backend && poetry run pytest
cd frontend && pnpm test
```

### Database

```bash
# Connect to PostgreSQL
docker exec -it airelgraph-postgres-1 psql -U postgres -d semantic_graph

# Create new migration
cd backend
poetry run alembic revision --autogenerate -m "description"

# Apply migrations
poetry run alembic upgrade head

# Rollback migration
poetry run alembic downgrade -1

# Backup database
docker exec airelgraph-postgres-1 pg_dump -U postgres semantic_graph > backup.sql

# Restore database
docker exec -i airelgraph-postgres-1 psql -U postgres semantic_graph < backup.sql

# Check pgvector extension
psql -U postgres -d semantic_graph -c "SELECT * FROM pg_extension WHERE extname = 'vector';"
```

### Debugging

```bash
# View Celery tasks
cd backend
poetry run celery -A app.workers.tasks inspect active

# Check Celery registered tasks
poetry run celery -A app.workers.tasks inspect registered

# Purge all Celery tasks
poetry run celery -A app.workers.tasks purge

# Check Redis queue
docker exec -it airelgraph-redis-1 redis-cli
> KEYS *
> LLEN celery

# Tail logs (Docker)
docker logs -f airelgraph-backend-1
docker logs -f airelgraph-celery-worker-1
docker logs -f airelgraph-frontend-1

# Check container health
docker ps
docker inspect airelgraph-postgres-1 | grep Health

# Monitor PostgreSQL queries
docker exec -it airelgraph-postgres-1 psql -U postgres -d semantic_graph
=# SELECT pid, now() - pg_stat_activity.query_start AS duration, query
   FROM pg_stat_activity
   WHERE state = 'active' AND now() - pg_stat_activity.query_start > interval '5 seconds'
   ORDER BY duration DESC;
```

### Production

```bash
# Build and deploy with production config
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Restart services
docker-compose -f docker-compose.prod.yml restart backend
docker-compose -f docker-compose.prod.yml restart celery-worker

# Scale Celery workers
docker-compose -f docker-compose.prod.yml up -d --scale celery-worker=4
```

## When Asking Claude for Help

### Provide Context Like:

- "I'm working on the entity recognition component in [backend/app/services/llm_tagging_service.py](backend/app/services/llm_tagging_service.py)"
- "This is for the graph visualization layer in [frontend/src/components/GraphView.tsx](frontend/src/components/GraphView.tsx)"
- "I'm debugging why similarities aren't being calculated in [backend/app/services/similarity_service.py](backend/app/services/similarity_service.py)"
- "I need to optimize this PostgreSQL query for pgvector similarity search"

### Include Relevant Information:

- Error messages and stack traces (full traceback)
- Relevant code snippets (function definitions, not just snippets)
- Expected vs actual behavior (with examples)
- Steps already tried (what you've debugged so far)
- Current graph size / dataset size (number of documents, tags, entities)
- Database query results (if relevant)

### Ask Specific Questions:

✅ "How can I optimize the cosine similarity calculation in [similarity_service.py](backend/app/services/similarity_service.py:50) for 10,000 documents?"
✅ "What's the best way to deduplicate entities with similar names in [graph_builder.py](backend/app/services/graph_builder.py:150)?"
✅ "How should I structure this pgvector similarity query to find the top 5 similar documents?"
✅ "Why is my D3 force simulation in [GraphView.tsx](frontend/src/components/GraphView.tsx:200) slow with 500 nodes?"

❌ "How do I make it faster?" (too vague)
❌ "Fix my code" (no context)
❌ "It's not working" (not specific)

## Project Resources

- **Project Proposal:** [project_proposal.md](project_proposal.md) - Full system design
- **Pipeline Walkthrough:** [pipeline_walkthrough.md](pipeline_walkthrough.md) - Step-by-step processing flow
- **README:** [README.md](README.md) - Project overview and setup
- **Backend API:** `http://localhost:8000/docs` - FastAPI auto-generated docs (when running)

## Quick Reference: Key Algorithms

### Cosine Similarity (pgvector)

```python
# In PostgreSQL with pgvector
similarity = 1 - (embedding1 <=> embedding2)  # Cosine distance operator

# In Python (services/similarity_service.py)
from sklearn.metrics.pairwise import cosine_similarity
similarity = cosine_similarity([embedding1], [embedding2])[0][0]

# Threshold configuration
DEFAULT_THRESHOLD = 0.75  # Configurable per user
```

### Entity Canonicalization

```python
# Fuzzy matching with Levenshtein distance
from Levenshtein import distance

def canonicalize_entity(name: str, existing_entities: List[Entity]) -> Entity:
    for entity in existing_entities:
        if distance(name.lower(), entity.name.lower()) < 3:
            return entity  # Match found, use canonical form
    return create_new_entity(name)  # New entity
```

### Tag Hierarchy (SQL)

```sql
-- Get all tags for a document with hierarchy
SELECT
    t.name,
    t.tag_type,
    parent.name AS parent_name
FROM tag t
JOIN document_tag dt ON t.id = dt.tag_id
LEFT JOIN tag parent ON t.parent_id = parent.id
WHERE dt.document_id = ? AND t.user_id = ?;
```

### Vector Similarity Search (pgvector)

```sql
-- Find top K similar documents
SELECT
    d2.id,
    d2.title,
    1 - (d1.embedding <=> d2.embedding) AS similarity
FROM document d1
CROSS JOIN document d2
WHERE d1.id = ?
  AND d2.id != d1.id
  AND d1.user_id = ?
  AND d2.user_id = ?
  AND d2.is_enabled = true
ORDER BY d1.embedding <=> d2.embedding  -- Cosine distance (ascending)
LIMIT 10;
```

## Success Metrics to Track

- **Processing Time:** < 5 min per document average (target)
- **Similarity Precision:** > 80% relevant suggestions (user feedback)
- **Entity Accuracy:** > 85% confirmed correct (validation rate)
- **Graph Render Time:** < 2 seconds for 500 nodes (D3 performance)
- **API Response Time:** < 200ms for graph data endpoint (p95)
- **Database Query Time:** < 100ms for similarity search (with pgvector index)

## Architecture Decisions Record

### Why PostgreSQL + pgvector instead of Neo4j?

**Decision:** Use PostgreSQL with pgvector extension for all data storage.

**Rationale:**
- Simpler operational overhead (one database instead of two)
- pgvector provides native vector similarity search
- Relational model sufficient for current graph complexity
- SQLAlchemy ORM provides type-safe queries
- Easier multi-tenancy with row-level security

**Trade-offs:**
- Neo4j better for deep graph traversals (>3 hops)
- Cypher more intuitive for graph queries
- But: Current use case mostly 1-2 hop queries (similarity, tags, entities)

### Why Next.js 15 instead of separate React app?

**Decision:** Use Next.js 15 with App Router for frontend.

**Rationale:**
- Server-side rendering for better SEO
- API routes for NextAuth.js integration
- Built-in optimization (code splitting, image optimization)
- TypeScript support out of the box
- Simplified deployment (single frontend container)

**Trade-offs:**
- Steeper learning curve than vanilla React
- More opinionated framework

### Why Celery instead of background threads?

**Decision:** Use Celery with Redis for async tasks.

**Rationale:**
- Horizontal scalability (add more workers)
- Task retries and error handling built-in
- Task monitoring and inspection tools
- Separate process isolation (won't crash API server)

**Trade-offs:**
- Additional infrastructure complexity (Redis dependency)
- More deployment overhead

---

**Remember:** This is a complex system with many moving parts. When in doubt:

1. Check the logs (`docker logs` or `tail -f`)
2. Verify database state (psql queries)
3. Test each layer independently (API → service → repository)
4. Use the debugging commands above
5. Ask Claude with specific context and file references!

Good luck building! 🚀
