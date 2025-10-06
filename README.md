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

- 🤖 **AI-Powered**: Uses sentence-transformers to generate semantic embeddings
- 🔍 **Auto-Discovery**: DBSCAN clustering automatically groups related documents
- 📊 **Interactive Graph**: Force-directed visualization with drag, zoom, and click
- ⚡ **Async Processing**: Celery + Redis for background document processing
- 🎨 **Named Clusters**: Auto-generated descriptive names like "Learning & Neural"
- 🔗 **Smart Relationships**: Cosine similarity scores (0.0-1.0) measure semantic closeness

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Make

### Setup & Run

```bash
# 1. Clone repository
git clone <your-repo-url>
cd ai-rel-graph-mvp

# 2. Setup environment files and dependencies
make setup

# 3. Start all services (PostgreSQL, Redis, FastAPI, Next.js, Celery)
make docker-up

# 4. Wait for services to initialize, then run database migrations
sleep 10
make db-upgrade

# 5. Verify everything works
./scripts/test-setup.sh
```

**Access the application:**
- 🌐 Frontend: http://localhost
- 🔌 Backend API: http://localhost:8000
- 📖 API Docs: http://localhost:8000/docs

### Try the Demo

See the system in action with realistic mock data:

```bash
./RUN_DEMO.sh
```

This creates 11 documents, generates embeddings, discovers ~35 relationships, and forms 4-5 auto-named clusters.

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
2. Embedding generation (384-dimensional vectors)
3. Similarity computation (cosine distance)
4. Cluster discovery (DBSCAN algorithm)
5. Graph construction & visualization

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

### 1. Document Ingestion
User provides Google Drive folder → System creates processing job

### 2. Text Extraction
PDFs, DOCX, XLSX files → Raw text content

### 3. Embedding Generation
```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
embedding = model.encode(text)  # 384-dimensional vector
```

### 4. Relationship Discovery
```python
from sklearn.metrics.pairwise import cosine_similarity
similarity = cosine_similarity(embedding1, embedding2)
if similarity >= 0.3:
    create_relationship(file1, file2, similarity)
```

### 5. Automatic Clustering
```python
from sklearn.cluster import DBSCAN
dbscan = DBSCAN(eps=0.5, min_samples=2, metric='cosine')
clusters = dbscan.fit_predict(embeddings)
```

### 6. Visualization
Interactive force-directed graph with:
- **Nodes**: Files (size = number of connections)
- **Edges**: Relationships (thickness = similarity score)
- **Colors**: Clusters (auto-discovered groups)

## 🗂️ Project Structure

```
AIRelGraph/
├── backend/                 # FastAPI application
│   ├── app/
│   │   ├── api/v1/         # API endpoints
│   │   ├── core/           # Config, database, Celery
│   │   ├── models/         # SQLAlchemy models with pgvector
│   │   └── workers/        # Celery tasks
│   ├── alembic/            # Database migrations
│   ├── tests/              # 35+ model tests
│   └── demo_schema.py      # Demo script with realistic data
├── frontend/               # Next.js application
│   └── src/app/           # App Router pages
├── scripts/               # Utility scripts
├── RUN_DEMO.sh           # Run schema demo
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
SIMILARITY_THRESHOLD=0.3
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

35+ comprehensive tests covering:
- ✅ Vector embedding storage & retrieval
- ✅ Cosine similarity computations
- ✅ Constraint validations (no self-relationships, score bounds)
- ✅ CASCADE deletes
- ✅ Index performance
- ✅ Cluster discovery

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

For detailed technical documentation, see:
- **[CLAUDE.md](CLAUDE.md)** - Complete architecture, database schema, and implementation details
- **[RUN_DEMO.sh](RUN_DEMO.sh)** - Demo script to test the system
- **API Docs** - http://localhost:8000/docs (when running)

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
