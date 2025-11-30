# Knowledge Graph Project - Claude Instructions

## Project Overview

This is a Knowledge Graph system that transforms unstructured Google Drive documents into an interactive, navigable semantic network. Users can explore organizational knowledge through visual connections, entity relationships, and semantic similarity rather than traditional folder hierarchies.

## System Architecture

The system consists of 4 main layers:

1. **Ingestion Layer** - Connects to Google Drive, detects changes, converts files
2. **Intelligence Layer** - Generates embeddings, extracts entities, tags documents with LLMs
3. **Data Layer** - Stores everything in Neo4j graph database with vector search
4. **Frontend Layer** - React application with 3D force-graph visualization

## Key Technologies

- **Backend:** Python FastAPI, Celery, Redis
- **Database:** Neo4j (graph + vectors), PostgreSQL (metadata)
- **AI/ML:** OpenAI (embeddings + GPT-4), spaCy (NER), LangChain
- **Frontend:** React, TypeScript, react-force-graph-3d
- **Infrastructure:** Docker, Google Drive API

## Core Concepts

### Graph Data Model

**Nodes:**

- `File` - Represents documents (properties: title, url, author, embedding vector, summary)
- `Tag` - Category labels (e.g., "Finance", "Q3 Report")
- `Entity` - Things mentioned in documents (people, projects, companies)

**Relationships:**

- `(:File)-[:HAS_TAG]->(:Tag)` - Document categorization
- `(:File)-[:MENTIONS {confidence}]->(:Entity)` - Named entity references
- `(:File)-[:SIMILAR_TO {score}]->(:File)` - Semantic similarity (cosine similarity > threshold)

### Processing Pipeline

```
Google Drive Upload
  ↓
Webhook/Polling Detection
  ↓
File Download & Conversion
  ↓
Embedding Generation (1536-dim vector)
  ↓
LLM Metadata Extraction (tags, entities, summary)
  ↓
Graph Node Creation
  ↓
Similarity Calculation (cosine similarity)
  ↓
Community Detection (Louvain algorithm)
  ↓
Visualization in UI
```

## Important Constraints & Decisions

### Threshold Tuning Strategy

- **Adaptive thresholds** by document type (technical docs: 0.92, meeting notes: 0.75)
- **Multi-tier similarity** with edge weights (strong/medium/weak)
- **User feedback loop** to auto-tune thresholds over time
- **Dynamic clustering** increases thresholds for large clusters

### Entity Recognition Approach

- **Hybrid NER:** Rule-based (regex) + Statistical (spaCy) + LLM extraction
- **Confidence scoring:** Only create nodes for entities with confidence > 0.75
- **Entity resolution:** Canonical entity registry with fuzzy matching for aliases
- **Human-in-the-loop:** UI for validating uncertain entities
- **Context-aware filtering:** Use TF-IDF to exclude overly common entities (prevent "hairball")

### Scalability Considerations

- **Asynchronous processing:** All document analysis runs in Celery workers
- **Incremental updates:** Only re-process changed documents
- **Rate limiting:** Exponential backoff for Google Drive API
- **Caching:** Store embeddings and similarity calculations
- **Graph sampling:** Frontend shows most important nodes first

## Common Development Tasks

### When Working on the Ingestion Layer:

- Focus on: OAuth flow, webhook handling, file conversion, error recovery
- Key files: `auth.py`, `webhooks.py`, `file_converter.py`
- Test with: Various Google Drive file formats (.gdoc, .pdf, .docx, .gsheet)

### When Working on the Intelligence Layer:

- Focus on: Embedding generation, LLM prompts, NER pipeline, similarity calculation
- Key files: `embedding_service.py`, `llm_processor.py`, `ner_pipeline.py`, `similarity.py`
- Test with: Sample documents of different types and lengths

### When Working on the Data Layer:

- Focus on: Neo4j schema, Cypher queries, vector indexing, community detection
- Key files: `graph_repository.py`, `migrations/`, `neo4j_config.py`
- Test with: Neo4j Browser, sample Cypher queries

### When Working on the Frontend:

- Focus on: Graph visualization, search/filter UI, document details panel
- Key files: `KnowledgeGraphVisualization.tsx`, `SearchBar.tsx`, `DocumentPanel.tsx`
- Test with: Sample graph data, various filter combinations

## Development Guidelines

### Code Quality

- Use type hints in Python (FastAPI requires them)
- Follow React/TypeScript best practices
- Write unit tests for core algorithms (similarity, NER)
- Use async/await for I/O operations
- Handle errors gracefully with try/except and user-friendly messages

### Performance Optimization

- **Batch processing:** Process multiple documents simultaneously when possible
- **Lazy loading:** Don't load entire graph at once in frontend
- **Indexes:** Create indexes on frequently queried fields (file_id, entity names)
- **Caching:** Use Redis for frequently accessed data
- **Profiling:** Monitor slow queries and optimize bottlenecks

### Security

- Store OAuth tokens encrypted
- Validate webhook signatures from Google
- Sanitize user inputs in search queries
- Rate limit API endpoints to prevent abuse
- Use environment variables for secrets (never commit them)

## Debugging Tips

### If documents aren't appearing in the graph:

1. Check `file_processing_state` table for status
2. Look at Celery worker logs for errors
3. Verify Google Drive API permissions
4. Check if file conversion succeeded
5. Confirm Neo4j connection is working

### If similarities are wrong:

1. Verify embedding generation completed
2. Check similarity threshold settings
3. Look at actual similarity scores in database
4. Confirm document types match (don't compare reports to meeting notes)
5. Check if documents have enough content (very short docs won't cluster well)

### If entities aren't being recognized:

1. Check LLM response format (must be valid JSON)
2. Verify confidence thresholds aren't too high
3. Look at spaCy NER output separately
4. Check entity canonicalization logic
5. Review entity feedback from users

### If graph visualization is slow:

1. Check number of nodes being rendered (should be < 1000)
2. Verify WebGL is enabled in browser
3. Implement graph sampling/filtering
4. Check for excessive edge count
5. Profile React component renders

## API Endpoint Reference

### Most Important Endpoints

```
GET /api/graph?filters=...
  Returns graph data (nodes + edges) with optional filters

GET /api/documents/{file_id}
  Returns full document details including entities, tags, similar docs

POST /api/documents/{file_id}/feedback
  Submit user feedback on entities (for improving NER)

GET /api/graph/search?q=...
  Search for documents by text query

GET /api/analytics/overview
  Dashboard statistics (total docs, tags, entities, communities)
```

## Known Issues & Workarounds

### Issue 1: Google Drive API Quota Exceeded

**Symptom:** 429 errors in logs, documents not being processed

**Workaround:**

- Implement exponential backoff (already in code)
- Reduce polling frequency
- Use webhook notifications instead of polling
- Spread processing across multiple days for large backlogs

### Issue 2: Neo4j Memory Issues with Large Graphs

**Symptom:** Out of memory errors, slow queries

**Workaround:**

- Increase Neo4j heap size in config
- Implement graph partitioning
- Archive old documents to separate database
- Use APOC procedures for batch operations

### Issue 3: LLM Costs Too High

**Symptom:** High OpenAI API bills

**Workaround:**

- Use GPT-3.5-turbo instead of GPT-4 for tagging
- Implement smart caching (don't re-process unchanged docs)
- Batch API calls when possible
- Use smaller context windows (truncate long documents)
- Consider self-hosted models for some tasks

### Issue 4: Graph "Hairball" Problem

**Symptom:** Too many connections, unusable visualization

**Workaround:**

- Increase similarity thresholds
- Filter out common entities (use TF-IDF)
- Implement edge bundling in visualization
- Show only top N most important connections
- Add UI controls to hide/show edge types

## Testing Strategy

### Unit Tests

- Similarity calculation (cosine_similarity function)
- Entity resolution (canonical matching)
- Text chunking (for embeddings)
- File conversion (each format)

### Integration Tests

- Full pipeline (upload → graph)
- API endpoints (all CRUD operations)
- Neo4j queries (complex Cypher)
- Frontend components (React Testing Library)

### End-to-End Tests

- Upload document → verify appears in graph
- Search functionality → verify results
- Click entity → verify related docs shown
- Update document → verify graph updates

## Deployment Checklist

Before deploying to production:

- [ ] Environment variables configured
- [ ] Neo4j database backed up
- [ ] PostgreSQL database backed up
- [ ] Google OAuth credentials set up
- [ ] Celery workers running and monitored
- [ ] Redis configured and monitored
- [ ] Logging and error tracking enabled (Sentry)
- [ ] API rate limiting configured
- [ ] Frontend build optimized (code splitting)
- [ ] SSL certificates installed
- [ ] Monitoring dashboards created (Grafana)
- [ ] Database indexes created
- [ ] Backup automation configured
- [ ] CI/CD pipeline tested

## Useful Commands

### Development

```bash
# Start backend
uvicorn main:app --reload

# Start Celery worker
celery -A tasks worker --loglevel=info

# Start Redis
redis-server

# Start Neo4j
docker run -p 7474:7474 -p 7687:7687 neo4j

# Start frontend
npm run dev
```

### Database

```bash
# Neo4j Cypher Shell
cypher-shell -u neo4j -p password

# PostgreSQL
psql -U postgres -d knowledge_graph

# Backup Neo4j
neo4j-admin dump --database=neo4j --to=/backups/graph.dump

# Restore Neo4j
neo4j-admin load --from=/backups/graph.dump --database=neo4j --force
```

### Debugging

```bash
# View Celery tasks
celery -A tasks inspect active

# Check Redis queue
redis-cli LLEN file_change_queue

# Tail logs
tail -f logs/api.log
tail -f logs/celery.log

# Monitor Neo4j queries
CALL dbms.listQueries();
```

## When Asking Claude for Help

### Provide Context Like:

- "I'm working on the entity recognition component"
- "This is for the graph visualization layer"
- "I'm debugging why similarities aren't being calculated"
- "I need to optimize this Cypher query"

### Include Relevant Information:

- Error messages and stack traces
- Relevant code snippets
- Expected vs actual behavior
- Steps already tried
- Current graph size / dataset size

### Ask Specific Questions:

✅ "How can I optimize this cosine similarity calculation for 10,000 documents?"
✅ "What's the best way to deduplicate entities with similar names?"
✅ "How should I structure this Cypher query to find documents 2 hops away?"

❌ "How do I make it faster?" (too vague)
❌ "Fix my code" (no context)
❌ "It's not working" (not specific)

## Project Resources

- **Project Proposal:** See `project_proposal.md` for full system design
- **Pipeline Walkthrough:** See `pipeline_walkthrough.md` for step-by-step processing flow
- **Original Inspiration:** See original document for initial architecture ideas

## Quick Reference: Key Algorithms

### Cosine Similarity

```python
similarity = dot(A, B) / (norm(A) * norm(B))
threshold = 0.85  # Adjustable by document type
```

### Entity Canonicalization

```python
# Fuzzy matching with Levenshtein distance
if levenshtein("Bob Smith", "Robert Smith") < 3:
    canonical = "Robert Smith"
```

### Community Detection

```cypher
// Louvain algorithm in Neo4j
CALL gds.louvain.write('graph', {
    writeProperty: 'community',
    relationshipWeightProperty: 'score'
})
```

## Success Metrics to Track

- **Processing Time:** <5 min per document average
- **Similarity Precision:** >80% relevant suggestions
- **Entity Accuracy:** >85% confirmed correct
- **User Engagement:** 3+ graph explorations per week
- **Discovery Rate:** 5+ unknown related docs found per session

---

**Remember:** This is a complex system with many moving parts. When in doubt:

1. Check the logs
2. Review the graph state in Neo4j Browser
3. Test each layer independently
4. Use the monitoring dashboards
5. Ask Claude with specific context!

Good luck building! 🚀
