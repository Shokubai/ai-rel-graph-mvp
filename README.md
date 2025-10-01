# AIRelGraph

> Semantic Document Relationship Discovery & Visualization

AIRelGraph analyzes documents to discover semantic relationships - connections based on meaning and purpose rather than explicit links. Upload a Google Drive folder and visualize how your documents relate conceptually through an interactive force-directed graph.

## 🚀 Quick Start

### Initial Setup

```bash
# 1. Setup environment and dependencies
make setup

# 2. Start all services
make docker-up

# 3. Wait for services to initialize, then run migrations
sleep 10
make db-upgrade

# 4. Verify everything works
./scripts/test-setup.sh

# 5. View service URLs
make urls
```

**Service URLs:**

- Frontend: <http://localhost>
- Backend API: <http://localhost:8000>
- API Docs: <http://localhost:8000/docs>

## 💡 How It Works

1. **Input**: Provide a Google Drive folder
2. **Extract**: System extracts text from PDFs, DOCX, XLSX, and more
3. **Embed**: ML model converts text to 384-dimensional vectors
4. **Cluster**: Documents grouped by semantic similarity
5. **Visualize**: Interactive graph shows relationships

**Examples of semantic relationships:**

- Research papers about penguin migration → linked by shared topic
- Budget spreadsheet + financial report → linked by similar purpose
- Meeting notes mentioning "Q4 strategy" → linked to strategy documents

## 🏗️ Architecture

**Backend:**

- FastAPI with PostgreSQL (pgvector extension)
- Celery + Redis for async processing
- sentence-transformers for embeddings

**Frontend:**

- Next.js 15 with React 19
- Cytoscape.js for graph visualization
- Tailwind CSS v4

**Infrastructure:**

- Docker Compose orchestrating all services
- Alembic for database migrations

## 📋 Common Commands

### Daily Development

```bash
make docker-up          # Start all services
make docker-logs        # Watch logs from all services
make health-check       # Verify service health
make docker-down        # Stop all services
```

### Code Quality

```bash
make format             # Format code (black + prettier)
make lint               # Lint code (ruff + eslint)
make typecheck          # Type check (mypy + tsc)
make test               # Run all tests
make check              # Run format, lint, typecheck, and test
```

### Database Operations

```bash
make db-migrate         # Create new migration (prompts for message)
make db-upgrade         # Apply pending migrations
make db-downgrade       # Rollback last migration
make db-shell           # Open PostgreSQL shell
make db-reset           # Reset database (⚠️ destroys data)
```

### Troubleshooting

```bash
make docker-rebuild     # Rebuild containers after dependency changes
make docker-logs-backend # View backend logs only
make docker-logs-frontend # View frontend logs only
make docker-status      # Check container status
make docker-clean       # Remove all containers/volumes (interactive)
make clean              # Remove cache files
```

## 🔧 Development

### Local Development (without Docker)

```bash
make dev-backend        # Run backend with hot reload
make dev-frontend       # Run frontend with hot reload
```

### Adding Dependencies

**Backend:**

```bash
poetry add <package>
make docker-rebuild
```

**Frontend:**

```bash
pnpm add <package>
make docker-rebuild
```

### Database Migrations

When modifying models:

```bash
make db-migrate         # Creates migration in backend/alembic/versions/
make db-upgrade         # Applies migration
```

## 📁 Project Structure

```plaintext
AIRelGraph/
├── backend/                 # FastAPI application
│   ├── app/
│   │   ├── api/v1/         # API endpoints
│   │   ├── core/           # Config, database, Celery
│   │   ├── models/         # SQLAlchemy models
│   │   └── workers/        # Celery tasks
│   └── alembic/            # Database migrations
├── frontend/               # Next.js application
│   └── src/app/           # App Router pages
├── scripts/               # Utility scripts
└── docker-compose.yml     # Service orchestration
```

## 📚 Documentation

For detailed information about the codebase, architecture, and implementation details, see [CLAUDE.md](CLAUDE.md).

## 🔐 Environment Configuration

Copy example files and configure:

- `backend/.env` - Database, Redis, Google Drive API credentials
- `frontend/.env.local` - API URLs

See [CLAUDE.md](CLAUDE.md) for complete environment variable documentation.

## 📝 License

[Add your license here]
