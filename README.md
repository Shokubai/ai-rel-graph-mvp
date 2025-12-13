# AIRelGraph

> **Semantic Document Relationship Discovery & Visualization**

Discover hidden connections in your documents through AI-powered semantic analysis. Upload a Google Drive folder and visualize how your documents relate conceptually through an interactive force-directed graph.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Node](https://img.shields.io/badge/node-18+-green.svg)

## ✨ What It Does

AIRelGraph analyzes documents to discover **semantic relationships** - connections based on meaning and purpose rather than explicit links:

- 📄 Two research papers about machine learning → **linked by shared topic**
- 💰 Budget spreadsheet + financial report → **linked by similar purpose**
- 📋 Meeting notes mentioning "Q4 strategy" → **linked to strategy documents**

Unlike folder hierarchies or keyword search, AIRelGraph reveals **hidden patterns** in how your documents relate conceptually.

## 🎯 Key Features

- 🤖 **AI-Powered**: Uses sentence-transformers to generate 384-dim semantic embeddings
- 🔍 **Community Detection**: Louvain algorithm discovers natural document clusters
- 📊 **Interactive Graph**: Force-directed visualization with drag, zoom, and click
- ⚡ **Async Processing**: Celery + Redis for background document processing
- 🎨 **Smart Naming**: Auto-generated semantic cluster names from document content
- 🔗 **Relationship Graph**: Cosine similarity (threshold: 0.5) creates meaningful connections
- 🏗️ **Service Architecture**: Reusable `SemanticProcessingService` with REST API

## 🚀 Quick Start

### Prerequisites

**For Docker deployment (recommended):**
- Docker & Docker Compose
- Python 3.10+ (tested up to 3.13)
- Node.js 18+
- Alembic
- Poetry (Python package manager)
- pnpm (Node package manager)
- Make

### Setup & Run

```bash
# 1. Clone repository
git clone <your-repo-url>
cd ai-rel-graph-mvp

# 2. Setup frontend environment
cp frontend/.env.example frontend/.env.production
```

Edit `frontend/.env.production` with your configuration:

```bash
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000

# NextAuth Configuration
# IMPORTANT: This MUST match the backend NEXTAUTH_SECRET exactly
NEXTAUTH_SECRET=your-secret-key-here
NEXTAUTH_URL=http://localhost

# Google OAuth Configuration
# IMPORTANT: These MUST match the backend values exactly
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Internal API URL (for server-side requests from NextAuth)
# This is used by the NextAuth callbacks to sync tokens to the backend
INTERNAL_API_URL=http://localhost:8000
```

```bash
# 3. Setup backend environment
cp backend/.env.example backend/.env
```

Edit `backend/.env` with your configuration:

```bash
# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=semantic_graph

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Google OAuth Configuration (MUST match frontend values)
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret

# NextAuth JWT Secret (MUST match frontend NEXTAUTH_SECRET)
NEXTAUTH_SECRET=your-secret-key-here

# CORS
ALLOWED_ORIGINS=["http://localhost:3000","http://localhost"]

# OpenAI API Key (for LLM tagging)
OPENAI_API_KEY=your-openai-api-key
```

```bash
# 4. Setup dependencies
make setup

# 5. Start all services (PostgreSQL, Redis, FastAPI, Next.js, Celery)
make docker-up

# 6. Wait for services to initialize, then run database migrations
docker exec ai-rel-graph-backend poetry run alembic upgrade head
```

**Access the application:**
- 🌐 Frontend: http://localhost
- 🔌 Backend API: http://localhost:8000
- 📖 API Docs: http://localhost:8000/docs

## 🏗️ Architecture

### Tech Stack

**Backend:**
- FastAPI with SQLAlchemy ORM
- PostgreSQL with **pgvector** extension
- Celery + Redis for async tasks
- sentence-transformers (all-MiniLM-L6-v2)

**Frontend:**
- Next.js 15 with App Router
- react-force-graph for visualization
- Zustand + TanStack Query
- Tailwind CSS v4

**ML Pipeline:**
1. Text extraction (PDF, DOCX, XLSX)
2. Embedding generation (384-dimensional vectors via sentence-transformers)
3. Relationship creation (cosine similarity ≥ 0.5)
4. Community detection (Louvain algorithm on relationship graph)
5. Semantic topic naming (embedding-based analysis)
6. Graph visualization (force-directed layout)

### Database Schema

```
files → Stores documents with embeddings (VECTOR(384))
file_relationships → Semantic similarity connections (0.0-1.0)
clusters → Auto-discovered document groups
file_clusters → Many-to-many file↔cluster mapping
processing_jobs → Background job tracking
```

**Key Features:**
- ✅ pgvector integration with ivfflat index
- ✅ CASCADE deletes (removing files auto-cleans relationships)
- ✅ Constraints (no self-relationships, similarity bounded 0.0-1.0)
- ✅ Performance indexes on status, similarity, embeddings

## 📋 Common Commands

### Development

```bash
make docker-up          # Start all services
make docker-logs        # View logs from all services
make docker-down        # Stop all services
make docker-rebuild     # Rebuild after dependency changes
```

### Code Quality

```bash
make format             # Format code (black + prettier)
make lint               # Lint code (ruff + eslint)
make typecheck          # Type check (mypy + tsc)
make test               # Run all tests
make check              # Run format, lint, typecheck, test
```

### Database

```bash
make db-migrate         # Create new migration
make db-upgrade         # Apply migrations
make db-shell           # Open PostgreSQL shell
make db-reset           # Reset database (⚠️ destroys data)
```

### Testing

```bash
# Run all tests
make test

# Run backend model tests (35+ tests)
docker exec ai-rel-graph-backend pytest tests/models/ -v --cov=app.models

# Setup test database first
docker exec ai-rel-graph-postgres psql -U postgres -c "CREATE DATABASE semantic_graph_test;"
docker exec ai-rel-graph-postgres psql -U postgres -d semantic_graph_test -c "CREATE EXTENSION vector;"
```

## 🔍 How It Works

AIRelGraph uses a **relationship-first** approach with community detection for clustering:

### 1. Document Ingestion
```python
# User uploads documents → Files created in database
File(text_content=text, processing_status="pending")
```

### 2. Embedding Generation
```python
from app.services.semantic import SemanticProcessingService

service = SemanticProcessingService()
embeddings = service.generate_embeddings(texts)
# → numpy array shape (n_docs, 384)
```

### 3. Relationship Discovery
```python
# Build relationship graph from semantic similarity
relationships, adjacency = service.create_relationships_with_graph(
    files=files,
    embeddings=embeddings,
    threshold=0.5  # Only similarities ≥ 0.5
)
# Creates graph edges for clustering
```

### 4. Community Detection
```python
# Louvain algorithm finds natural communities in the graph
clusters = service.create_clusters_from_communities(
    files=files,
    adjacency=adjacency  # Relationship graph from step 3
)
# Auto-generates semantic topic names like "Neural Networks Learning (15 docs)"
```

### 5. Visualization
Interactive force-directed graph with:
- **Nodes**: Files (size = number of connections)
- **Edges**: Relationships (thickness = similarity score)
- **Colors**: Communities (discovered by Louvain algorithm)

### Why Community Detection?

**Previous (DBSCAN)**: Clustered embeddings directly
- Problem: Sensitive to parameters, many small clusters

**Current (Louvain)**: Clusters relationship graph
- ✅ Discovers natural communities from actual connections
- ✅ No parameter tuning required
- ✅ More semantically meaningful clusters
- ✅ Better scalability

## 🗂️ Project Structure

```
AIRelGraph/
├── backend/                 # FastAPI application
│   ├── app/
│   │   ├── api/v1/         # API endpoints (files, semantic)
│   │   ├── core/           # Config, database, Celery
│   │   ├── models/         # SQLAlchemy models with pgvector
│   │   ├── services/       # Business logic (SemanticProcessingService)
│   │   └── workers/        # Celery tasks (async processing)
│   ├── alembic/            # Database migrations
│   ├── tests/              # 75+ tests (models + services)
│   └── demo.py             # Unified demo script
├── frontend/               # Next.js application
│   └── src/app/           # App Router pages
├── scripts/               # Utility scripts
└── docker-compose.yml    # Service orchestration
```

## 🔧 Configuration

### Backend Environment (`backend/.env`)

```bash
POSTGRES_HOST=postgres
POSTGRES_DB=semantic_graph
REDIS_HOST=redis
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
SENTENCE_TRANSFORMER_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
SIMILARITY_THRESHOLD=0.5  # Relationship threshold (0.0-1.0)
```

### Frontend Environment (`frontend/.env.local`)

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

## 📊 Database Exploration

```bash
# Connect to database
docker exec -it ai-rel-graph-postgres psql -U postgres -d semantic_graph_demo

# View clusters
SELECT * FROM clusters;

# Top 10 relationships by similarity
SELECT f1.name, f2.name, fr.similarity_score
FROM file_relationships fr
JOIN files f1 ON fr.source_file_id = f1.id
JOIN files f2 ON fr.target_file_id = f2.id
ORDER BY fr.similarity_score DESC LIMIT 10;

# Files by cluster
SELECT c.label, COUNT(fc.file_id) as file_count
FROM clusters c
LEFT JOIN file_clusters fc ON c.id = fc.cluster_id
GROUP BY c.label;
```

## 🧪 Testing

75+ comprehensive tests covering:

**Model Tests (35+ tests)**:
- ✅ Vector embedding storage & retrieval
- ✅ Cosine similarity computations
- ✅ Constraint validations (no self-relationships, score bounds)
- ✅ CASCADE deletes
- ✅ Index performance

**Service Tests (40+ tests)**:
- ✅ Embedding generation and similarity
- ✅ Relationship creation and graph building
- ✅ Community detection algorithms (Louvain)
- ✅ Semantic topic naming
- ✅ Full pipeline integration
- ✅ Edge cases and error handling

All tests use real PostgreSQL with pgvector (not mocks or SQLite).

## 🛠️ Troubleshooting

**Containers won't start**
```bash
make docker-status  # Check container health
make docker-rebuild # Rebuild if needed
```

**Database connection errors**
```bash
docker logs ai-rel-graph-postgres  # Check PostgreSQL logs
docker exec ai-rel-graph-postgres psql -U postgres -c "\dx"  # Verify pgvector
```

**Import errors after adding packages**
```bash
make docker-rebuild  # Rebuild containers with new dependencies
```

## 📚 Documentation

- **[CLAUDE.md](CLAUDE.md)** - Complete architecture, database schema, semantic pipeline, and implementation details
- **API Docs** - http://localhost:8000/docs (interactive OpenAPI documentation)
- **Semantic Processing API** - `/api/v1/semantic/` endpoints for embeddings, relationships, and clustering
- **[backend/demo.py](backend/demo.py)** - Unified demo script with synthetic and real PDF support

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Run `make check` before committing
4. Submit a pull request

## 📄 License

[MIT License](LICENSE)

## 🎯 Roadmap

- [ ] Google Drive OAuth integration
- [ ] Advanced graph filtering & search
- [ ] LLM-powered cluster naming
- [ ] Document preview in graph
- [ ] Export graph as image/JSON
- [ ] Multi-user support
- [ ] Real-time collaboration

---

**Built with ❤️ using FastAPI, Next.js, and pgvector**
