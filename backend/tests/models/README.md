# Database Model Tests

Comprehensive test suite for validating the AIRelGraph database schema and constraints.

## Prerequisites

1. **PostgreSQL with pgvector** must be running
2. **Test database** must exist: `semantic_graph_test`

### Setup Test Database

```bash
# Start Docker services
make docker-up

# Create test database
docker exec -i ai-rel-graph-mvp-postgres-1 psql -U postgres -c "CREATE DATABASE semantic_graph_test;"

# Enable pgvector extension
docker exec -i ai-rel-graph-mvp-postgres-1 psql -U postgres -d semantic_graph_test -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

Or set `TEST_DATABASE_URL` environment variable:
```bash
export TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/semantic_graph_test"
```

## Running Tests

```bash
# Run all model tests
make backend-test tests/models/

# Run specific test file
pytest backend/tests/models/test_file.py -v

# Run with coverage
pytest backend/tests/models/ --cov=app.models --cov-report=html
```

## Test Coverage

### [test_file.py](test_file.py)
Tests for the `File` model:
- ✅ Basic file creation
- ✅ File creation with 384-dimensional embeddings
- ✅ Google Drive ID uniqueness constraint
- ✅ Automatic timestamp generation
- ✅ Processing status indexing
- ✅ Vector similarity search (pgvector)

### [test_relationship.py](test_relationship.py)
Tests for the `FileRelationship` model:
- ✅ Basic relationship creation
- ✅ Self-relationship prevention (CHECK constraint)
- ✅ Similarity score bounds (0.0 - 1.0)
- ✅ Unique relationship pairs (no duplicates)
- ✅ CASCADE delete on source file deletion
- ✅ CASCADE delete on target file deletion
- ✅ Similarity score index queries

### [test_cluster.py](test_cluster.py)
Tests for `Cluster` and `FileCluster` models:
- ✅ Cluster creation
- ✅ File-to-cluster mapping
- ✅ Duplicate mapping prevention
- ✅ CASCADE delete when file deleted
- ✅ CASCADE delete when cluster deleted
- ✅ Many-to-many relationships (file in multiple clusters)
- ✅ One-to-many relationships (cluster with multiple files)

### [test_job.py](test_job.py)
Tests for the `ProcessingJob` model:
- ✅ Job creation with default values
- ✅ Error message storage (TEXT field)
- ✅ Progress tracking (percentage, file counts)
- ✅ Job completion timestamps
- ✅ Status indexing
- ✅ Long error message handling
- ✅ Multiple jobs per folder

## Key Test Scenarios

### Vector Embeddings
```python
# Creates 384-dim vector and verifies pgvector storage
embedding_vector = np.random.rand(384).tolist()
file = File(google_drive_id="test", embedding=embedding_vector)
```

### Constraint Validation
```python
# Tests that self-relationships are blocked
relationship = FileRelationship(
    source_file_id=file.id,
    target_file_id=file.id,  # Same file!
)
# Raises: IntegrityError with "ck_no_self_relationship"
```

### Cascade Deletes
```python
# Verifies relationships are auto-deleted
db.delete(file1)  # Source file
db.commit()
assert db.query(FileRelationship).count() == 0  # Gone!
```

## Mock Data Examples

All tests use realistic mock data:
- **Files**: Google Drive IDs, mime types, file sizes, text content
- **Embeddings**: 384-dimensional numpy arrays (matching sentence-transformers)
- **Relationships**: Cosine similarity scores (0.0-1.0)
- **Clusters**: Labeled topic groups
- **Jobs**: Folder processing with progress tracking

## Troubleshooting

### pgvector Extension Missing
```
ERROR: type "vector" does not exist
```
**Fix**: Enable pgvector in test database:
```bash
docker exec -i ai-rel-graph-mvp-postgres-1 psql -U postgres -d semantic_graph_test -c "CREATE EXTENSION vector;"
```

### Test Database Doesn't Exist
```
FATAL: database "semantic_graph_test" does not exist
```
**Fix**: Create test database:
```bash
docker exec -i ai-rel-graph-mvp-postgres-1 psql -U postgres -c "CREATE DATABASE semantic_graph_test;"
```

### Connection Refused
```
could not connect to server: Connection refused
```
**Fix**: Start Docker services:
```bash
make docker-up
```

## CI/CD Integration

Add to `.github/workflows/test.yml`:
```yaml
- name: Run model tests
  run: |
    docker exec backend pytest tests/models/ -v --cov=app.models
```
