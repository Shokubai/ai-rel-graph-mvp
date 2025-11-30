# Knowledge Graph Pipeline: File Ingestion Walkthrough

This document walks through exactly what happens when a new document is added to Google Drive and how it flows through the entire system.

---

## Scenario: User Uploads "Q4_Strategy_2024.docx" to Google Drive

Let's trace this document's journey from upload to appearing in the knowledge graph.

---

## Step 1: Change Detection (Ingestion Layer)

### What Happens:

**1.1 Google Drive Notification**
- User uploads `Q4_Strategy_2024.docx` to their Google Drive
- Google Drive sends a webhook notification to our server at `POST /webhooks/drive`
- Webhook payload contains:
```json
{
  "kind": "api#channel",
  "id": "channel-123",
  "resourceId": "file-abc-def-456",
  "resourceUri": "https://www.googleapis.com/drive/v3/files/file-abc-def-456",
  "channelExpiration": "1638316800000"
}
```

**1.2 Webhook Handler Processing**
```python
@app.post("/webhooks/drive")
async def handle_drive_webhook(request: Request):
    """
    Receives notification from Google Drive
    """
    # 1. Validate webhook authenticity (check token/signature)
    validate_google_webhook(request)
    
    # 2. Extract file ID from payload
    file_id = extract_file_id(request)
    
    # 3. Add to Redis queue for processing
    redis_client.lpush("file_change_queue", json.dumps({
        "file_id": file_id,
        "change_type": "new",
        "timestamp": datetime.now().isoformat()
    }))
    
    # 4. Return 200 OK immediately (don't block webhook)
    return {"status": "queued"}
```

**1.3 Database State Update**
```sql
-- Create processing record
INSERT INTO file_processing_state (
    file_id, 
    user_id, 
    status, 
    last_modified
) VALUES (
    'file-abc-def-456',
    123,
    'pending',
    NOW()
);
```

**Current State:**
- ✅ File detected
- ✅ Queued for processing
- ⏳ Status: `pending`

---

## Step 2: File Download & Conversion (Ingestion Layer)

### What Happens:

**2.1 Worker Picks Up Task**
```python
# Celery worker running continuously
@celery.task(name="process_file_change")
def process_file_change(file_id: str):
    """
    Main task that orchestrates file processing
    """
    # Update status
    update_status(file_id, "processing")
    
    # Download file from Google Drive
    file_content = download_from_drive(file_id)
    
    # Convert to text
    converted_data = convert_file(file_content)
    
    # Trigger intelligence layer
    chain = (
        generate_embeddings.s(file_id, converted_data) |
        extract_metadata.s(file_id) |
        calculate_similarities.s(file_id)
    )
    chain.apply_async()
```

**2.2 Google Drive Download**
```python
def download_from_drive(file_id: str) -> dict:
    """
    Download file from Google Drive using API
    """
    # Get user's OAuth token
    user = get_user_by_file(file_id)
    credentials = get_credentials(user)
    
    # Call Google Drive API
    service = build('drive', 'v3', credentials=credentials)
    
    # Get file metadata
    file_metadata = service.files().get(
        fileId=file_id,
        fields='name,mimeType,owners,createdTime,modifiedTime,size'
    ).execute()
    
    # Export/download file content
    if file_metadata['mimeType'] == 'application/vnd.google-apps.document':
        # Google Doc - export as plain text
        content = service.files().export(
            fileId=file_id,
            mimeType='text/plain'
        ).execute()
    else:
        # Other formats - download binary
        content = service.files().get_media(fileId=file_id).execute()
    
    return {
        "content": content,
        "metadata": file_metadata
    }
```

**2.3 File Conversion**
```python
def convert_file(file_data: dict) -> dict:
    """
    Convert various file formats to plain text
    """
    mime_type = file_data['metadata']['mimeType']
    content = file_data['content']
    
    if mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        # .docx file - use python-docx
        from docx import Document
        from io import BytesIO
        
        doc = Document(BytesIO(content))
        text = '\n\n'.join([para.text for para in doc.paragraphs])
        
    elif mime_type == 'application/pdf':
        # PDF - use PyPDF2
        import PyPDF2
        from io import BytesIO
        
        pdf_reader = PyPDF2.PdfReader(BytesIO(content))
        text = ''
        for page in pdf_reader.pages:
            text += page.extract_text()
    
    else:
        # Plain text or already exported
        text = content.decode('utf-8')
    
    # Clean the text
    text = clean_text(text)
    
    return {
        "file_id": file_data['metadata']['id'],
        "title": file_data['metadata']['name'],
        "text_content": text,
        "metadata": {
            "author": file_data['metadata']['owners'][0]['emailAddress'],
            "created_at": file_data['metadata']['createdTime'],
            "modified_at": file_data['metadata']['modifiedTime'],
            "file_type": "docx",
            "word_count": len(text.split()),
            "url": f"https://drive.google.com/file/d/{file_data['metadata']['id']}"
        }
    }
```

**Output Example:**
```json
{
  "file_id": "file-abc-def-456",
  "title": "Q4_Strategy_2024.docx",
  "text_content": "Q4 Strategy Overview\n\nThis quarter we are focusing on three key initiatives:\n\n1. Project Apollo - Our new mobile application launch targeting enterprise customers...\n\n2. Market Expansion - Entering the European market with support from our partner Acme Corp...\n\n3. Team Growth - Hiring 15 new engineers led by Sarah Chen...\n\nBudget: $2.5M allocated across initiatives...",
  "metadata": {
    "author": "john.doe@company.com",
    "created_at": "2024-11-15T10:30:00Z",
    "modified_at": "2024-11-28T14:22:00Z",
    "file_type": "docx",
    "word_count": 850,
    "url": "https://drive.google.com/file/d/file-abc-def-456"
  }
}
```

**Current State:**
- ✅ File downloaded
- ✅ Converted to text
- ✅ Metadata extracted
- ⏳ Ready for intelligence processing

---

## Step 3: Embedding Generation (Intelligence Layer)

### What Happens:

**3.1 Text Chunking**
```python
@celery.task(name="generate_embeddings")
def generate_embeddings(file_id: str, converted_data: dict):
    """
    Generate vector embeddings for document
    """
    text = converted_data['text_content']
    
    # Split into chunks (OpenAI has 8191 token limit)
    chunks = chunk_text(text, max_tokens=500, overlap=50)
    # chunks = [
    #     "Q4 Strategy Overview\n\nThis quarter we are focusing...",
    #     "...three key initiatives:\n\n1. Project Apollo - Our new...",
    #     "...mobile application launch targeting enterprise...",
    #     ...
    # ]
    
    # Generate embeddings for each chunk
    chunk_embeddings = []
    for chunk in chunks:
        embedding = get_embedding(chunk)
        chunk_embeddings.append(embedding)
    
    # Aggregate into single document embedding (weighted average)
    document_embedding = aggregate_embeddings(chunk_embeddings)
    
    # Store in database
    store_embedding(file_id, document_embedding)
    
    return document_embedding
```

**3.2 OpenAI API Call**
```python
def get_embedding(text: str) -> list[float]:
    """
    Call OpenAI API to generate embedding
    """
    import openai
    
    response = openai.embeddings.create(
        model="text-embedding-3-small",
        input=text,
        encoding_format="float"
    )
    
    embedding = response.data[0].embedding
    # embedding = [0.023, -0.015, 0.089, ..., -0.042]  # 1536 dimensions
    
    return embedding
```

**3.3 Store Embedding**
```python
def store_embedding(file_id: str, embedding: list[float]):
    """
    Store embedding vector in database
    """
    # Store in PostgreSQL temporarily
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO document_embeddings (file_id, embedding, created_at)
        VALUES (%s, %s, NOW())
        ON CONFLICT (file_id) DO UPDATE SET
            embedding = EXCLUDED.embedding,
            updated_at = NOW()
    """, (file_id, embedding))
    
    conn.commit()
```

**Current State:**
- ✅ Text chunked into manageable pieces
- ✅ Embeddings generated (1536-dimensional vector)
- ✅ Stored in database
- ⏳ Ready for metadata extraction

---

## Step 4: Metadata Extraction (Intelligence Layer)

### What Happens:

**4.1 LLM Processing**
```python
@celery.task(name="extract_metadata")
def extract_metadata(file_id: str):
    """
    Use LLM to extract structured metadata
    """
    # Get document text
    doc = get_document(file_id)
    text = doc['text_content']
    
    # Truncate if too long (GPT-4 has 128k context but expensive)
    if len(text) > 4000:
        text = text[:4000] + "..."
    
    # Call LLM with structured prompt
    metadata = call_llm_for_extraction(text)
    
    # Store results
    store_metadata(file_id, metadata)
    
    return metadata
```

**4.2 LLM Prompt & Response**
```python
def call_llm_for_extraction(text: str) -> dict:
    """
    Send text to LLM for analysis
    """
    import openai
    
    prompt = f"""
Analyze this document and extract the following in JSON format:

1. **summary**: A 2-3 sentence overview of the document
2. **tags**: 5-10 category tags (e.g., "Strategy", "Finance", "Q4", "Mobile")
3. **entities**: List of important entities with type and confidence:
   - type: "person", "project", "company", "product", "location"
   - Include confidence score (0.0 to 1.0)
4. **document_type**: One of: meeting_notes, report, email, technical_doc, presentation, other

Document:
{text}

Respond with ONLY valid JSON:
{{
  "summary": "...",
  "tags": ["tag1", "tag2", ...],
  "entities": [
    {{"text": "Project Apollo", "type": "project", "confidence": 0.95}},
    {{"text": "Sarah Chen", "type": "person", "confidence": 0.88}}
  ],
  "document_type": "report"
}}
"""
    
    response = openai.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=[
            {"role": "system", "content": "You are a document analysis assistant. Always respond with valid JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,  # Lower temperature for more consistent output
        response_format={"type": "json_object"}
    )
    
    result = json.loads(response.choices[0].message.content)
    return result
```

**4.3 LLM Response Example**
```json
{
  "summary": "Q4 strategic plan focusing on three key initiatives: Project Apollo mobile app launch for enterprise customers, European market expansion with Acme Corp partnership, and team growth with 15 new engineering hires under Sarah Chen's leadership. Total budget allocation of $2.5M.",
  "tags": [
    "Q4 2024",
    "Strategy",
    "Product Launch",
    "Market Expansion",
    "Europe",
    "Mobile",
    "Enterprise",
    "Hiring",
    "Budget Planning"
  ],
  "entities": [
    {"text": "Project Apollo", "type": "project", "confidence": 0.98},
    {"text": "Acme Corp", "type": "company", "confidence": 0.95},
    {"text": "Sarah Chen", "type": "person", "confidence": 0.92},
    {"text": "Europe", "type": "location", "confidence": 0.88},
    {"text": "mobile application", "type": "product", "confidence": 0.85}
  ],
  "document_type": "report"
}
```

**4.4 Hybrid NER (Supplement LLM)**
```python
def supplement_with_spacy_ner(text: str, llm_entities: list) -> list:
    """
    Run spaCy NER to catch entities LLM might have missed
    """
    import spacy
    
    nlp = spacy.load("en_core_web_sm")
    doc = nlp(text)
    
    spacy_entities = []
    for ent in doc.ents:
        # Convert spaCy labels to our types
        entity_type_map = {
            "PERSON": "person",
            "ORG": "company",
            "GPE": "location",
            "PRODUCT": "product"
        }
        
        if ent.label_ in entity_type_map:
            spacy_entities.append({
                "text": ent.text,
                "type": entity_type_map[ent.label_],
                "confidence": 0.75,  # Lower confidence than LLM
                "source": "spacy"
            })
    
    # Merge with LLM entities (deduplicate)
    all_entities = merge_entities(llm_entities, spacy_entities)
    return all_entities
```

**Current State:**
- ✅ Summary generated
- ✅ Tags extracted
- ✅ Entities identified with confidence scores
- ✅ Document type classified
- ⏳ Ready to build graph relationships

---

## Step 5: Graph Database Population (Data Layer)

### What Happens:

**5.1 Create File Node**
```python
def create_graph_nodes(file_id: str, metadata: dict):
    """
    Create nodes and relationships in Neo4j
    """
    from neo4j import GraphDatabase
    
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    with driver.session() as session:
        # Create File node
        session.run("""
            MERGE (f:File {id: $file_id})
            SET f.title = $title,
                f.url = $url,
                f.author = $author,
                f.created_at = datetime($created_at),
                f.modified_at = datetime($modified_at),
                f.document_type = $doc_type,
                f.word_count = $word_count,
                f.summary = $summary,
                f.embedding = $embedding
        """, {
            "file_id": file_id,
            "title": metadata['title'],
            "url": metadata['url'],
            "author": metadata['author'],
            "created_at": metadata['created_at'],
            "modified_at": metadata['modified_at'],
            "doc_type": metadata['document_type'],
            "word_count": metadata['word_count'],
            "summary": metadata['summary'],
            "embedding": metadata['embedding']  # Vector stored directly
        })
```

**5.2 Create Tag Nodes & Relationships**
```python
        # Create Tag nodes and HAS_TAG relationships
        for tag in metadata['tags']:
            session.run("""
                MERGE (t:Tag {name: $tag})
                ON CREATE SET t.document_count = 0
                
                MERGE (f:File {id: $file_id})
                MERGE (f)-[:HAS_TAG]->(t)
                
                // Increment document count
                SET t.document_count = t.document_count + 1
            """, {
                "tag": tag,
                "file_id": file_id
            })
```

**5.3 Create Entity Nodes & Relationships**
```python
        # Create Entity nodes and MENTIONS relationships
        for entity in metadata['entities']:
            # Check if this entity already exists (canonicalization)
            canonical_name = find_canonical_entity(entity['text'], entity['type'])
            
            session.run("""
                MERGE (e:Entity {canonical_name: $canonical_name, type: $type})
                ON CREATE SET 
                    e.aliases = [$entity_text],
                    e.first_mentioned = datetime(),
                    e.mention_count = 0
                ON MATCH SET
                    e.aliases = 
                        CASE 
                            WHEN NOT $entity_text IN e.aliases 
                            THEN e.aliases + [$entity_text]
                            ELSE e.aliases
                        END
                
                MERGE (f:File {id: $file_id})
                MERGE (f)-[m:MENTIONS]->(e)
                SET m.confidence = $confidence,
                    m.mentioned_at = datetime()
                
                // Increment mention count
                SET e.mention_count = e.mention_count + 1
            """, {
                "canonical_name": canonical_name,
                "type": entity['type'],
                "entity_text": entity['text'],
                "file_id": file_id,
                "confidence": entity['confidence']
            })
```

**Graph State After Step 5:**
```
(:File {id: "file-abc-def-456", title: "Q4_Strategy_2024.docx"})
  ├─[:HAS_TAG]→ (:Tag {name: "Q4 2024"})
  ├─[:HAS_TAG]→ (:Tag {name: "Strategy"})
  ├─[:HAS_TAG]→ (:Tag {name: "Product Launch"})
  ├─[:MENTIONS {confidence: 0.98}]→ (:Entity {canonical_name: "Project Apollo", type: "project"})
  ├─[:MENTIONS {confidence: 0.95}]→ (:Entity {canonical_name: "Acme Corp", type: "company"})
  └─[:MENTIONS {confidence: 0.92}]→ (:Entity {canonical_name: "Sarah Chen", type: "person"})
```

**Current State:**
- ✅ File node created in graph
- ✅ Tag nodes created and linked
- ✅ Entity nodes created and linked
- ⏳ Ready to calculate similarities

---

## Step 6: Similarity Calculation (Intelligence Layer)

### What Happens:

**6.1 Find Similar Documents**
```python
@celery.task(name="calculate_similarities")
def calculate_similarities(file_id: str):
    """
    Calculate cosine similarity between this document and all others
    """
    # Get this document's embedding
    new_embedding = get_embedding_from_db(file_id)
    
    # Get embeddings of all other documents (same document type for better results)
    doc_type = get_document_type(file_id)
    existing_docs = get_all_documents_by_type(doc_type)
    
    similarities = []
    for doc in existing_docs:
        if doc['file_id'] == file_id:
            continue  # Skip self
        
        # Calculate cosine similarity
        similarity = cosine_similarity(new_embedding, doc['embedding'])
        
        # Apply threshold based on document type
        threshold = THRESHOLDS.get(doc_type, 0.85)
        
        if similarity >= threshold:
            similarities.append({
                "file_id_1": file_id,
                "file_id_2": doc['file_id'],
                "score": similarity
            })
    
    # Create SIMILAR_TO relationships in graph
    create_similarity_edges(similarities)
    
    return similarities
```

**6.2 Cosine Similarity Calculation**
```python
import numpy as np

def cosine_similarity(embedding_a: list, embedding_b: list) -> float:
    """
    Calculate cosine similarity between two vectors
    """
    a = np.array(embedding_a)
    b = np.array(embedding_b)
    
    # Cosine similarity formula
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    
    similarity = dot_product / (norm_a * norm_b)
    return float(similarity)

# Example:
# new_doc_embedding = [0.023, -0.015, 0.089, ..., -0.042]
# existing_doc_embedding = [0.019, -0.012, 0.095, ..., -0.038]
# similarity = 0.87  # High similarity!
```

**6.3 Create Similarity Edges**
```python
def create_similarity_edges(similarities: list):
    """
    Add SIMILAR_TO relationships to graph
    """
    from neo4j import GraphDatabase
    
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    with driver.session() as session:
        for sim in similarities:
            session.run("""
                MATCH (f1:File {id: $file_id_1})
                MATCH (f2:File {id: $file_id_2})
                
                MERGE (f1)-[s:SIMILAR_TO]-(f2)
                SET s.score = $score,
                    s.calculated_at = datetime()
            """, {
                "file_id_1": sim['file_id_1'],
                "file_id_2": sim['file_id_2'],
                "score": sim['score']
            })
```

**Example Results:**
```
Q4_Strategy_2024.docx is similar to:
- Q3_Strategy_2024.docx (score: 0.89) - same series
- Product_Roadmap_2024.docx (score: 0.86) - overlapping content
- Europe_Expansion_Plan.docx (score: 0.82) - mentions Europe expansion
```

**Current State:**
- ✅ Similarities calculated
- ✅ SIMILAR_TO edges created in graph
- ⏳ Ready for community detection

---

## Step 7: Community Detection (Data Layer)

### What Happens:

**7.1 Run Louvain Algorithm**
```python
def run_community_detection():
    """
    Identify clusters of related documents using Louvain algorithm
    Runs periodically (e.g., once per day) on entire graph
    """
    from neo4j import GraphDatabase
    
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    with driver.session() as session:
        # Project graph for algorithm
        session.run("""
            CALL gds.graph.project(
                'document-graph',
                'File',
                {
                    SIMILAR_TO: {orientation: 'UNDIRECTED'},
                    MENTIONS: {orientation: 'UNDIRECTED'}
                },
                {
                    relationshipProperties: 'score'
                }
            )
        """)
        
        # Run Louvain community detection
        result = session.run("""
            CALL gds.louvain.write(
                'document-graph',
                {
                    writeProperty: 'community',
                    relationshipWeightProperty: 'score'
                }
            )
            YIELD communityCount, modularity
            RETURN communityCount, modularity
        """)
        
        stats = result.single()
        print(f"Found {stats['communityCount']} communities")
        print(f"Modularity: {stats['modularity']}")
```

**7.2 Result Example**
```
Community 0: Q4 Planning Documents (15 files)
  - Q4_Strategy_2024.docx
  - Q3_Strategy_2024.docx
  - Annual_Goals_2024.docx
  - Budget_2024_Q4.docx
  ...

Community 1: Product Development (22 files)
  - Product_Roadmap_2024.docx
  - Feature_Specs_Apollo.docx
  - Design_Mockups_Mobile.pdf
  ...

Community 2: European Expansion (8 files)
  - Europe_Expansion_Plan.docx
  - GDPR_Compliance_Checklist.docx
  - EU_Market_Research.pdf
  ...
```

**Current State:**
- ✅ Document assigned to community (cluster)
- ✅ Community ID stored on File node
- ⏳ Ready for visualization

---

## Step 8: Update Processing Status

### What Happens:

**8.1 Mark as Complete**
```python
def finalize_processing(file_id: str):
    """
    Update processing state to completed
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE file_processing_state
        SET status = 'completed',
            processing_completed_at = NOW()
        WHERE file_id = %s
    """, (file_id,))
    
    conn.commit()
    
    # Log success
    logger.info(f"Successfully processed file: {file_id}")
```

**8.2 Send Notification (Optional)**
```python
    # Notify user via websocket that new file is ready
    send_websocket_message(user_id, {
        "type": "file_processed",
        "file_id": file_id,
        "title": "Q4_Strategy_2024.docx",
        "communities_updated": True
    })
```

**Final State:**
- ✅ Status: `completed`
- ✅ All data in graph database
- ✅ Ready for user to explore in UI

---

## Step 9: Frontend Visualization

### What the User Sees:

**9.1 Initial Graph Load**
```javascript
// React component fetches graph data
const loadGraph = async () => {
  const response = await fetch('/api/graph');
  const data = await response.json();
  
  // data structure:
  // {
  //   nodes: [
  //     {id: 'file-abc-def-456', title: 'Q4_Strategy_2024.docx', community: 0, ...},
  //     {id: 'file-xyz-123', title: 'Q3_Strategy_2024.docx', community: 0, ...},
  //     ...
  //   ],
  //   links: [
  //     {source: 'file-abc-def-456', target: 'file-xyz-123', type: 'SIMILAR_TO', score: 0.89},
  //     {source: 'file-abc-def-456', target: 'entity-project-apollo', type: 'MENTIONS'},
  //     ...
  //   ]
  // }
  
  setGraphData(data);
};
```

**9.2 User Clicks on New Document Node**
```javascript
const handleNodeClick = async (node) => {
  // Fetch full document details
  const response = await fetch(`/api/documents/${node.id}`);
  const doc = await response.json();
  
  // Show in sidebar panel:
  // {
  //   title: "Q4_Strategy_2024.docx",
  //   summary: "Q4 strategic plan focusing on...",
  //   tags: ["Q4 2024", "Strategy", "Product Launch", ...],
  //   entities: [
  //     {text: "Project Apollo", type: "project"},
  //     {text: "Sarah Chen", type: "person"},
  //     ...
  //   ],
  //   similar_documents: [
  //     {title: "Q3_Strategy_2024.docx", similarity: 0.89},
  //     ...
  //   ],
  //   url: "https://drive.google.com/file/d/..."
  // }
  
  setSelectedDocument(doc);
  setPanelOpen(true);
};
```

**9.3 Visual Representation**
```
┌─────────────────────────────────────────────┐
│                 Graph View                  │
│                                             │
│    ●────────●                               │
│   Q3      Q4  ← New document clustered     │
│    ╲      ╱   with similar Q3 doc          │
│     ●────●                                  │
│   Budget Annual                             │
│      ╲   ╱                                  │
│       ● ← Entity: "Project Apollo"         │
│      ╱ ╲  connects multiple docs           │
│    ●   ●                                    │
│  Specs Roadmap                              │
│                                             │
└─────────────────────────────────────────────┘
```

**9.4 User Explores Connections**
- Clicks "Project Apollo" entity node
- Graph highlights all documents mentioning it:
  - Q4_Strategy_2024.docx
  - Product_Roadmap_2024.docx
  - Feature_Specs_Apollo.docx
  - Weekly_Standup_Nov_20.docx (meeting notes)
- User discovers connections they didn't know existed!

---

## Complete Pipeline Summary

```
┌──────────────────────┐
│ Google Drive Upload  │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Webhook Received    │ ← 100ms
│  Queue Job           │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Download & Convert  │ ← 5-30 seconds (depends on file size)
│  Extract Text        │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Generate Embeddings │ ← 1-3 seconds (OpenAI API)
│  1536-dim vector     │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  LLM Metadata        │ ← 5-15 seconds (GPT-4 API)
│  Extract Tags        │
│  Extract Entities    │
│  Generate Summary    │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Create Graph Nodes  │ ← 1-2 seconds
│  File, Tags, Entities│
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Calculate Similarity│ ← 2-10 seconds (depends on # of docs)
│  Create SIMILAR_TO   │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Community Detection │ ← Runs periodically (1x/day)
│  (Optional/Batch)    │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  ✅ Available in UI   │
└──────────────────────┘

Total Time: ~15-60 seconds per document
```

---

## Error Handling & Edge Cases

### What If Something Goes Wrong?

**Scenario 1: Google API Rate Limit Hit**
```python
def download_from_drive(file_id: str):
    try:
        content = service.files().get_media(fileId=file_id).execute()
    except HttpError as e:
        if e.resp.status == 429:  # Rate limit
            # Exponential backoff
            retry_after = int(e.resp.get('Retry-After', 60))
            logger.warning(f"Rate limit hit, retrying after {retry_after}s")
            
            # Re-queue with delay
            process_file_change.apply_async(
                args=[file_id],
                countdown=retry_after
            )
            raise Retry(exc=e, countdown=retry_after)
```

**Scenario 2: LLM Returns Invalid JSON**
```python
def call_llm_for_extraction(text: str):
    try:
        result = json.loads(response.choices[0].message.content)
    except json.JSONDecodeError:
        logger.error("LLM returned invalid JSON, using fallback")
        # Use simple regex-based extraction as fallback
        result = {
            "summary": text[:200] + "...",
            "tags": extract_keywords_tfidf(text),
            "entities": [],
            "document_type": "other"
        }
    return result
```

**Scenario 3: File Conversion Fails**
```python
def convert_file(file_data: dict):
    try:
        # Attempt conversion
        text = perform_conversion(file_data)
    except Exception as e:
        logger.error(f"Conversion failed: {e}")
        
        # Update status as failed
        update_status(file_data['id'], 'failed', error=str(e))
        
        # Don't crash - just skip this file
        return None
```

---

## Monitoring & Observability

### What Gets Logged:

```python
# Throughout pipeline
logger.info("File detected", extra={
    "file_id": file_id,
    "stage": "webhook_received",
    "timestamp": datetime.now()
})

logger.info("Conversion complete", extra={
    "file_id": file_id,
    "stage": "conversion",
    "word_count": word_count,
    "duration_ms": duration
})

logger.info("Embeddings generated", extra={
    "file_id": file_id,
    "stage": "embeddings",
    "dimensions": 1536,
    "api_cost": cost
})

logger.info("Graph populated", extra={
    "file_id": file_id,
    "stage": "graph_creation",
    "entities_created": len(entities),
    "tags_created": len(tags),
    "similarities_found": len(similarities)
})
```

### Dashboard Metrics:
- Files processed per hour
- Average processing time per stage
- LLM API costs (running total)
- Error rate by stage
- Queue depth (backlog size)
- Graph size (nodes/edges)

---

## Conclusion

This walkthrough demonstrated the complete journey of a document from Google Drive upload to appearing as a fully-connected node in the knowledge graph. The pipeline handles everything automatically:

1. ✅ Detects new files via webhooks
2. ✅ Downloads and converts to text
3. ✅ Generates semantic embeddings
4. ✅ Extracts metadata with LLMs
5. ✅ Builds graph relationships
6. ✅ Finds similar documents
7. ✅ Clusters into communities
8. ✅ Makes explorable in beautiful UI

All in 15-60 seconds, completely automated, with robust error handling and monitoring.
