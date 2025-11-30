# Knowledge Graph for Google Drive: Project Proposal

## Executive Summary

This project aims to transform unstructured Google Drive documents into an intelligent, navigable knowledge graph. Instead of rigid folder hierarchies, users will explore their organizational knowledge through semantic relationships, visual clustering, and entity-based connections. The system automatically analyzes documents to extract meaning, identify relationships, and surface insights that would be impossible to discover through traditional search.

**Key Value Propositions:**
- Discover hidden connections between documents and projects
- Navigate knowledge by meaning, not just keywords
- Automatically tag and categorize new documents
- Visualize organizational knowledge as an interactive network
- Find related documents through semantic similarity

---

## System Architecture Overview

The system follows an event-driven ETL (Extract, Transform, Load) pipeline with four main layers:

```
┌─────────────────┐
│  Google Drive   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 1. INGESTION    │  ← OAuth, Webhooks, File Conversion
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 2. INTELLIGENCE │  ← Embeddings, LLM Processing, NER
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 3. DATA LAYER   │  ← Neo4j Graph Database + Vectors
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 4. FRONTEND     │  ← React + Force Graph Visualization
└─────────────────┘
```

---

## Layer 1: Ingestion System

### Purpose
Connect to Google Drive, detect changes, and convert various file formats into processable text.

### Components to Build

#### 1.1 OAuth 2.0 Authentication Service
**Technology:** Python FastAPI + Google OAuth Libraries

**What needs to be done:**
- Implement OAuth 2.0 flow for Google Drive API access
- Store user credentials securely (encrypted database or secret manager)
- Handle token refresh automatically
- Support multiple user accounts for team deployments
- Create admin dashboard for managing connected accounts

**Deliverables:**
- `/auth/google/login` endpoint
- `/auth/google/callback` endpoint
- Token refresh background job
- User credential database schema

#### 1.2 Change Detection Service
**Technology:** Python + Google Drive API + Redis

**What needs to be done:**
- Implement Google Drive Push Notifications (webhook receiver)
- Set up fallback polling mechanism for the Changes API
- Create a change event queue to handle bursts of updates
- Implement deduplication logic (same file modified multiple times)
- Track processing state per file (new, updated, deleted, processing, completed)

**Deliverables:**
- `/webhooks/drive` endpoint to receive Google notifications
- Polling service that runs every 5 minutes as backup
- Redis queue for change events
- Database table: `file_processing_state`

#### 1.3 File Conversion Service
**Technology:** Apache Tika or Unstructured.io API

**What needs to be done:**
- Create conversion pipeline for multiple formats:
  - Google Docs (.gdoc) → Plain text
  - PDF → Extracted text + metadata
  - Word (.docx) → Plain text
  - Sheets (.gsheet) → CSV or structured data
  - Slides (.gslides) → Text from slides
- Extract metadata (author, created date, modified date, title)
- Handle conversion errors gracefully (log and skip corrupted files)
- Implement file size limits (e.g., skip files >100MB)
- Create standardized JSON output format

**Deliverables:**
- `FileConverter` class with format-specific handlers
- Conversion job that processes files from the change queue
- Standardized output schema:
```json
{
  "file_id": "google_drive_id",
  "title": "Document Title",
  "text_content": "Full extracted text...",
  "metadata": {
    "author": "user@company.com",
    "created_at": "2024-01-15T10:30:00Z",
    "modified_at": "2024-03-20T14:22:00Z",
    "file_type": "gdoc",
    "word_count": 1250
  }
}
```

#### 1.4 Rate Limiting & Error Handling
**What needs to be done:**
- Implement exponential backoff for Google API calls
- Track API quota usage (Google Drive has limits per user per day)
- Create retry logic with maximum attempt limits
- Set up monitoring alerts for quota warnings
- Implement circuit breaker pattern (stop calling if API is down)

**Deliverables:**
- Rate limiter middleware
- Retry decorator for API calls
- Monitoring dashboard for API quota usage

---

## Layer 2: Intelligence System

### Purpose
Process document text to generate embeddings, extract entities, and create tags using AI/ML models.

### Components to Build

#### 2.1 Task Queue System
**Technology:** Celery + Redis

**What needs to be done:**
- Set up Celery workers to process documents asynchronously
- Configure Redis as message broker
- Create task priorities (new documents vs. updated documents)
- Implement task result storage
- Set up worker monitoring and auto-scaling
- Configure task timeouts and failure handling

**Deliverables:**
- Celery configuration files
- Worker deployment scripts
- Task monitoring dashboard
- Dead letter queue for failed tasks

#### 2.2 Embedding Generation Service
**Technology:** OpenAI API or HuggingFace Sentence Transformers

**What needs to be done:**
- Choose embedding model:
  - **Option A:** OpenAI `text-embedding-3-small` (1536 dimensions, $0.02/1M tokens)
  - **Option B:** HuggingFace `all-MiniLM-L6-v2` (384 dimensions, self-hosted, free)
- Implement chunking strategy for long documents (embeddings have token limits)
  - Split documents into chunks (e.g., 512 tokens with 50 token overlap)
  - Generate embeddings for each chunk
  - Aggregate chunk embeddings (average or weighted by position)
- Cache embeddings to avoid recomputation
- Implement batch processing for efficiency

**Deliverables:**
- `EmbeddingGenerator` class
- Chunking utility functions
- Celery task: `generate_embeddings(file_id)`
- Database table: `document_embeddings`

#### 2.3 LLM Processing Service (Tagger & Summarizer)
**Technology:** LangChain + OpenAI GPT-4 or Llama 3

**What needs to be done:**
- Design LLM prompt for structured extraction:
```python
prompt = """
Analyze this document and extract:
1. Summary: 2-3 sentence overview
2. Tags: 5-10 category tags (e.g., "Finance", "Q3 Report", "Strategy")
3. Entities: People, projects, companies, products mentioned
4. Document type: (meeting_notes, technical_doc, report, email, etc.)

Document:
{text}

Respond in JSON format:
{
  "summary": "...",
  "tags": ["tag1", "tag2"],
  "entities": [
    {"text": "Project Apollo", "type": "project", "confidence": 0.95},
    {"text": "Sarah Chen", "type": "person", "confidence": 0.88}
  ],
  "document_type": "report"
}
"""
```
- Implement JSON parsing and validation
- Handle LLM API errors and retries
- Set up cost tracking for API usage
- Create fallback logic if LLM fails (use simpler NER)

**Deliverables:**
- `LLMProcessor` class
- Prompt templates library
- Celery task: `extract_metadata(file_id)`
- Cost tracking dashboard

#### 2.4 Named Entity Recognition (NER) Service
**Technology:** spaCy + Custom Rules

**What needs to be done:**
- Set up hybrid NER pipeline:
  1. **Rule-based extraction:**
     - Email addresses (regex)
     - URLs (regex)
     - Dates (regex + dateparser)
     - Document IDs (custom patterns like "DOC-12345")
  2. **Statistical NER:**
     - Use spaCy's pre-trained model for persons, organizations, locations
  3. **LLM-based extraction:**
     - Domain-specific entities (projects, products, initiatives)
- Implement confidence scoring for each entity
- Create entity deduplication logic
- Build canonical entity registry

**Deliverables:**
- `NERPipeline` class
- Custom spaCy pipeline with rules
- Entity resolution function
- Database table: `canonical_entities`

#### 2.5 Similarity Calculation Service
**Technology:** NumPy + scikit-learn

**What needs to be done:**
- Implement cosine similarity calculation between embeddings
- Create batch comparison (compare new document against all existing)
- Apply adaptive thresholds by document type
- Generate similarity edges for graph database
- Optimize for performance (use approximate nearest neighbors for large datasets)

**Deliverables:**
- `SimilarityCalculator` class
- Celery task: `calculate_similarities(file_id)`
- Database table: `similarity_edges`

---

## Layer 3: Data Layer

### Purpose
Store documents, embeddings, entities, and relationships in a graph database optimized for both vector search and graph traversal.

### Components to Build

#### 3.1 Neo4j Graph Database Setup
**Technology:** Neo4j (with Graph Data Science plugin)

**What needs to be done:**
- Install and configure Neo4j server
- Enable Vector Index support (Neo4j 5.11+)
- Design graph schema with node types and relationship types
- Create indexes for performance:
  - Full-text index on document titles
  - Vector index on embeddings
  - Index on entity names
- Set up backup and recovery procedures
- Configure memory settings for large graphs

**Deliverables:**
- Neo4j deployment (Docker or cloud)
- Cypher scripts for schema creation
- Index creation scripts
- Backup automation

#### 3.2 Graph Data Model Implementation

**Node Types:**
```cypher
// File node
CREATE (f:File {
  id: 'gdrive_123',
  title: 'Q3 Strategy Document',
  url: 'https://drive.google.com/...',
  author: 'user@company.com',
  created_at: datetime(),
  modified_at: datetime(),
  document_type: 'report',
  word_count: 1250,
  summary: '...'
})

// Tag node
CREATE (t:Tag {
  name: 'Finance',
  document_count: 0  // maintained by triggers
})

// Entity node
CREATE (e:Entity {
  canonical_name: 'Project Apollo',
  type: 'project',
  aliases: ['Apollo', 'Apollo Initiative'],
  first_mentioned: datetime(),
  mention_count: 0
})
```

**Relationship Types:**
```cypher
// File to Tag
CREATE (f:File)-[:HAS_TAG]->(t:Tag)

// File mentions Entity
CREATE (f:File)-[:MENTIONS {confidence: 0.95}]->(e:Entity)

// File similar to File
CREATE (f1:File)-[:SIMILAR_TO {score: 0.87, calculated_at: datetime()}]->(f2:File)

// Entity co-occurs with Entity (optional)
CREATE (e1:Entity)-[:CO_OCCURS_WITH {frequency: 15}]->(e2:Entity)
```

**What needs to be done:**
- Implement data access layer (Neo4j driver wrapper)
- Create CRUD operations for each node type
- Implement relationship creation logic
- Build query functions:
  - Find similar documents
  - Find documents by entity
  - Find documents by tag
  - Get entity co-occurrence network
  - Run community detection algorithms
- Set up vector similarity search

**Deliverables:**
- `GraphRepository` class with all query methods
- Cypher query library
- Database migration scripts

#### 3.3 Vector Index Integration
**What needs to be done:**
- Store embeddings directly in Neo4j File nodes
- Create vector index:
```cypher
CREATE VECTOR INDEX file_embeddings
FOR (f:File)
ON f.embedding
OPTIONS {indexConfig: {
  `vector.dimensions`: 1536,
  `vector.similarity_function`: 'cosine'
}}
```
- Implement k-NN search for similar documents
- Benchmark performance and tune index settings

**Deliverables:**
- Vector index creation scripts
- `find_similar_documents(embedding, k=10)` function

#### 3.4 Community Detection Pipeline
**Technology:** Neo4j Graph Data Science

**What needs to be done:**
- Set up Graph Data Science library
- Implement Louvain or Leiden algorithm for clustering
- Run community detection periodically (e.g., daily)
- Store community IDs on File nodes
- Create API to retrieve community statistics

**Deliverables:**
- Cypher scripts for running community detection
- Scheduled job for re-clustering
- Community analytics dashboard

---

## Layer 4: Frontend & Visualization

### Purpose
Provide an interactive web interface for exploring the knowledge graph with rich visualizations.

### Components to Build

#### 4.1 React Application Setup
**Technology:** React 18 + TypeScript + Vite

**What needs to be done:**
- Initialize React project with TypeScript
- Set up routing (React Router)
- Configure build pipeline
- Set up state management (Zustand or Redux Toolkit)
- Implement authentication flow (Google OAuth)
- Create responsive layout

**Deliverables:**
- React application scaffold
- Authentication components
- Main layout and navigation

#### 4.2 Graph Visualization Component
**Technology:** React-Force-Graph (3D version for WebGL acceleration)

**What needs to be done:**
- Install and configure react-force-graph-3d
- Create graph data fetching from backend API
- Implement node rendering:
  - Different colors by document type or community
  - Node size by importance (mention count, similarity degree)
  - Node labels showing document titles
- Implement edge rendering:
  - Different line styles for different relationship types
  - Edge thickness by similarity score
  - Option to hide/show edge types
- Add interaction handlers:
  - Click node → open document details panel
  - Hover node → show tooltip with summary
  - Click edge → show relationship details
  - Drag nodes to reposition
- Implement force simulation tuning:
  - Adjust link distance
  - Adjust charge force (repulsion)
  - Center force to keep graph contained

**Deliverables:**
- `KnowledgeGraphVisualization` component
- Graph controls (zoom, pan, reset)
- Node and edge styling logic

#### 4.3 Search & Filter Interface
**What needs to be done:**
- Create search bar with autocomplete
- Implement filters:
  - By document type (checkboxes)
  - By date range (date picker)
  - By author (dropdown)
  - By tags (multi-select)
  - By entities (autocomplete)
- Show search results in sidebar
- Highlight matching nodes in graph
- Implement "focus mode" (hide unrelated nodes)

**Deliverables:**
- `SearchBar` component
- `FilterPanel` component
- Search results list
- Graph highlighting logic

#### 4.4 Document Details Panel
**What needs to be done:**
- Create sliding panel that appears when node is clicked
- Display:
  - Document title and link to Google Drive
  - Summary
  - Tags (clickable to filter graph)
  - Entities mentioned (clickable to find related docs)
  - Author and dates
  - Similar documents list
  - Full text preview (collapsible)
- Add actions:
  - Open in Google Drive (new tab)
  - Edit tags manually
  - Mark entities as correct/incorrect (feedback)

**Deliverables:**
- `DocumentPanel` component
- Tag editing interface
- Entity feedback UI

#### 4.5 Analytics Dashboard
**What needs to be done:**
- Create dashboard showing:
  - Total documents indexed
  - Most common tags (bar chart)
  - Most mentioned entities (word cloud or list)
  - Community sizes (pie chart)
  - Recent activity timeline
  - Indexing queue status
- Add export functionality (download graph data as JSON)

**Deliverables:**
- `AnalyticsDashboard` component
- Chart components (using Recharts or D3)
- Export functionality

#### 4.6 Settings & Configuration
**What needs to be done:**
- Create settings page for:
  - Similarity threshold adjustment (slider)
  - Graph layout settings (force strength, link distance)
  - Entity filtering (exclude common entities)
  - Refresh Google Drive connection
  - Trigger full re-index
- Save user preferences to backend

**Deliverables:**
- `Settings` page component
- User preferences API
- Preference persistence

---

## Backend API Design

### Technology Stack
- **Framework:** Python FastAPI
- **Database:** Neo4j (graph) + PostgreSQL (user accounts, jobs)
- **Task Queue:** Celery + Redis
- **Authentication:** OAuth 2.0 (Google)

### API Endpoints to Implement

#### Authentication
```
POST   /api/auth/google/login       # Initiate OAuth flow
GET    /api/auth/google/callback    # Handle OAuth callback
POST   /api/auth/logout             # Logout user
GET    /api/auth/me                 # Get current user info
```

#### Graph Data
```
GET    /api/graph                   # Get full graph (with filters)
GET    /api/graph/node/{id}         # Get single node details
GET    /api/graph/search            # Search nodes by text
GET    /api/graph/similar/{id}      # Get similar documents
GET    /api/graph/entity/{name}     # Get docs mentioning entity
```

#### Documents
```
GET    /api/documents               # List all documents
GET    /api/documents/{id}          # Get document details
PATCH  /api/documents/{id}/tags     # Update tags manually
POST   /api/documents/{id}/feedback # Submit entity feedback
```

#### Analytics
```
GET    /api/analytics/overview      # Dashboard stats
GET    /api/analytics/tags          # Tag distribution
GET    /api/analytics/entities      # Entity frequency
GET    /api/analytics/communities   # Community info
```

#### Admin
```
POST   /api/admin/reindex           # Trigger full re-index
GET    /api/admin/jobs              # View processing queue
DELETE /api/admin/cache             # Clear caches
GET    /api/admin/quotas            # Google API quota usage
```

#### Settings
```
GET    /api/settings                # Get user settings
PATCH  /api/settings                # Update user settings
```

---

## Database Schema

### PostgreSQL (Metadata & State)

```sql
-- User accounts
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    google_access_token TEXT,
    google_refresh_token TEXT,
    token_expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    settings JSONB
);

-- File processing state
CREATE TABLE file_processing_state (
    file_id VARCHAR(255) PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    status VARCHAR(50),  -- 'pending', 'processing', 'completed', 'failed'
    last_modified TIMESTAMP,
    processing_started_at TIMESTAMP,
    processing_completed_at TIMESTAMP,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0
);

-- Processing jobs (Celery results)
CREATE TABLE processing_jobs (
    job_id VARCHAR(255) PRIMARY KEY,
    file_id VARCHAR(255),
    task_type VARCHAR(100),
    status VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    result JSONB,
    error TEXT
);

-- API quota tracking
CREATE TABLE api_quotas (
    user_id INTEGER REFERENCES users(id),
    date DATE,
    endpoint VARCHAR(100),
    request_count INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, date, endpoint)
);

-- Entity feedback (for improving NER)
CREATE TABLE entity_feedback (
    id SERIAL PRIMARY KEY,
    file_id VARCHAR(255),
    entity_text VARCHAR(500),
    entity_type VARCHAR(100),
    is_correct BOOLEAN,
    user_id INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## Development Phases

### Phase 1: Foundation (Weeks 1-3)
**Goal:** Build basic ingestion and authentication

- Set up development environment
- Implement OAuth 2.0 flow
- Build file conversion service
- Test with sample Google Drive documents
- Set up PostgreSQL database

**Deliverables:**
- Users can connect Google Drive account
- System can fetch and convert documents to text
- Basic API skeleton with authentication

### Phase 2: Intelligence Layer (Weeks 4-6)
**Goal:** Add AI/ML processing capabilities

- Set up Celery task queue
- Implement embedding generation
- Build LLM processing service
- Create NER pipeline
- Test on 100 sample documents

**Deliverables:**
- Documents are automatically tagged
- Entities are extracted
- Embeddings are generated
- All processed data stored in PostgreSQL

### Phase 3: Graph Database (Weeks 7-9)
**Goal:** Build knowledge graph storage

- Set up Neo4j
- Implement graph data model
- Build data access layer
- Migrate processed documents to graph
- Implement similarity calculation
- Run community detection

**Deliverables:**
- Full knowledge graph in Neo4j
- Similarity relationships computed
- Community clusters identified
- Graph query API endpoints

### Phase 4: Frontend (Weeks 10-12)
**Goal:** Build visualization interface

- Create React application
- Implement graph visualization
- Build search and filter UI
- Create document details panel
- Add analytics dashboard

**Deliverables:**
- Interactive graph visualization
- Search and filter functionality
- Document exploration interface

### Phase 5: Polish & Optimization (Weeks 13-14)
**Goal:** Improve performance and UX

- Optimize graph queries
- Implement caching strategies
- Add loading states and error handling
- Performance testing with large datasets (1000+ documents)
- UI/UX refinement
- Documentation

**Deliverables:**
- Production-ready application
- Performance benchmarks
- User documentation

### Phase 6: Deployment (Week 15)
**Goal:** Launch to production

- Set up production infrastructure
- Configure monitoring and logging
- Deploy backend services
- Deploy frontend
- Set up CI/CD pipeline

**Deliverables:**
- Live production application
- Monitoring dashboards
- Deployment automation

---

## Technical Challenges & Mitigation

### Challenge 1: Scalability with Large Document Sets
**Problem:** Processing 10,000+ documents takes significant time and computing resources.

**Mitigation:**
- Implement incremental processing (only new/changed documents)
- Use distributed Celery workers (scale horizontally)
- Cache embeddings and similarity calculations
- Implement pagination in API responses
- Use graph database partitioning for very large graphs

### Challenge 2: Graph Visualization Performance
**Problem:** Rendering 1000+ nodes in browser can cause lag.

**Mitigation:**
- Use WebGL rendering (react-force-graph-3d)
- Implement level-of-detail (hide labels when zoomed out)
- Add view filters to reduce visible nodes
- Implement virtual scrolling for document lists
- Use graph sampling (show most important nodes first)

### Challenge 3: Entity Recognition Accuracy
**Problem:** NER produces false positives and misses entities.

**Mitigation:**
- Hybrid NER approach (rules + statistical + LLM)
- Confidence thresholds (only show high-confidence entities)
- User feedback loop to improve over time
- Manual entity editing in UI
- Entity validation dashboard for admins

### Challenge 4: Cost of LLM Processing
**Problem:** Running GPT-4 on every document is expensive.

**Mitigation:**
- Use cheaper models for initial tagging (GPT-3.5-turbo)
- Batch document processing
- Cache LLM responses
- Implement smart re-processing (only if document changed significantly)
- Allow users to choose processing tiers (fast/cheap vs. accurate/expensive)

### Challenge 5: Google Drive API Rate Limits
**Problem:** Google limits API calls per user per day.

**Mitigation:**
- Implement exponential backoff
- Queue requests and process in batches
- Use webhooks instead of polling
- Monitor quota usage
- Spread processing across multiple days if needed

---

## Success Metrics

### Technical Metrics
- **Processing Speed:** <5 minutes per document (average)
- **API Response Time:** <500ms for graph queries
- **Similarity Accuracy:** >80% of suggested similar docs rated as relevant by users
- **Entity Precision:** >85% of extracted entities confirmed accurate
- **System Uptime:** >99.5%

### User Metrics
- **Adoption Rate:** 70% of users connect their Google Drive within first week
- **Engagement:** Users explore graph at least 3x per week
- **Discovery:** Users discover average of 5 related documents they didn't know existed per session
- **Search Success:** 80% of searches result in finding desired document within 3 clicks
- **User Satisfaction:** >4.0/5.0 average rating

---

## Budget Estimate

### Infrastructure Costs (Monthly)
- **Neo4j Cloud:** $200-500 (depends on dataset size)
- **Compute (Backend API + Celery Workers):** $300-600
- **PostgreSQL Database:** $50-100
- **Redis:** $25-50
- **Frontend Hosting:** $20-50
- **Monitoring & Logging:** $50-100

**Total Infrastructure:** ~$645-1,400/month

### AI/ML API Costs (Monthly, for 1000 documents/month)
- **OpenAI Embeddings:** ~$2-5
- **OpenAI GPT-4 (tagging):** ~$50-150
- **Total AI Costs:** ~$52-155/month

### Development Costs
- **3 Full-time developers for 15 weeks**
- Estimated: $150,000 - $225,000

### Total First Year Cost
- Development: $150,000 - $225,000
- Infrastructure & AI (12 months): $8,400 - $18,660
- **Grand Total:** ~$158,400 - $243,660

---

## Risks & Contingency Plans

### Risk 1: Poor Entity Recognition Quality
**Likelihood:** Medium | **Impact:** High

**Contingency:**
- Pivot to simpler keyword-based tagging initially
- Gradually introduce NER as accuracy improves
- Focus on user-generated tags as primary navigation

### Risk 2: Graph Becomes Too Dense (Hairball Problem)
**Likelihood:** High | **Impact:** Medium

**Contingency:**
- Implement aggressive entity filtering
- Use higher similarity thresholds
- Add UI controls to reduce graph density
- Focus on specific sub-graphs (filter by date range, project)

### Risk 3: Low User Adoption
**Likelihood:** Medium | **Impact:** High

**Contingency:**
- Conduct user research early
- Implement user feedback continuously
- Start with power users / early adopters
- Provide training and onboarding materials

### Risk 4: Google API Changes or Restrictions
**Likelihood:** Low | **Impact:** High

**Contingency:**
- Abstract Google Drive access behind interface (easy to swap)
- Implement alternative data sources (Dropbox, OneDrive)
- Maintain local cache of document metadata

---

## Next Steps

1. **Stakeholder Approval:** Review proposal with leadership and secure budget
2. **Team Assembly:** Hire or assign 2-3 developers (1 backend, 1 ML/AI, 1 frontend)
3. **Environment Setup:** Provision cloud infrastructure and development environments
4. **Sprint 0 (Week 1):** Project kickoff, detailed technical design, setup repositories
5. **Begin Phase 1:** Start development on ingestion layer

---

## Appendix: Technology Reference

### Core Dependencies
```
Backend:
- fastapi==0.104.0
- celery==5.3.4
- redis==5.0.1
- neo4j==5.14.0
- psycopg2-binary==2.9.9
- langchain==0.1.0
- openai==1.3.0
- spacy==3.7.2
- apache-tika==2.9.0
- google-auth==2.23.0
- google-api-python-client==2.108.0

Frontend:
- react==18.2.0
- react-force-graph-3d==1.24.0
- react-router-dom==6.20.0
- zustand==4.4.7
- recharts==2.10.3
```

### Development Tools
- **IDE:** VS Code with Python/React extensions
- **API Testing:** Postman
- **Graph Exploration:** Neo4j Browser
- **Monitoring:** Grafana + Prometheus
- **Logging:** ELK Stack (Elasticsearch, Logstash, Kibana)
- **CI/CD:** GitHub Actions
- **Version Control:** Git + GitHub

---

**Prepared by:** AI Architecture Team  
**Date:** November 2024  
**Version:** 1.0
