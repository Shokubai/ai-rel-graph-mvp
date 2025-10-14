# ML-Based Tag Extraction System

## Overview

AIRelGraph now uses **ML-based semantic tag extraction** with automatic tag consolidation to discover meaningful relationships between documents.

### Key Features

✅ **Semantic Tag Extraction** - Uses KeyBERT to extract meaningful keywords/phrases based on semantic understanding
✅ **Multi-word Phrases** - Captures concepts like "machine learning", "neural networks" (not just single words)
✅ **Automatic Tag Consolidation** - Merges similar tags (e.g., "ML", "machine learning", "deep learning" → "machine learning")
✅ **Auto-discovered Categories** - Cluster names emerge from content, not hardcoded categories
✅ **Explainable** - Tags are readable phrases, not black-box embeddings

## Architecture

### 1. ML Tag Extraction ([ml_tag_extraction.py](backend/app/services/ml_tag_extraction.py))

**Model**: `all-MiniLM-L6-v2` sentence transformer (384-dim embeddings)

**Library**: KeyBERT with Maximal Marginal Relevance (MMR)

**Process**:
```python
# Extract semantic tags from document
tags = extractor.extract_tags(text)
# Returns: [("machine learning", 0.87), ("neural networks", 0.82), ...]
```

**Parameters**:
- `max_tags_per_doc: int = 15` - Maximum tags per document
- `diversity: float = 0.7` - Balance between relevance and diversity (0.0-1.0)
- `keyphrase_ngram_range: (1, 3)` - Extract 1-3 word phrases

### 2. Tag Consolidation ([tag_consolidation.py](backend/app/services/tag_consolidation.py))

**Purpose**: Merge semantically similar tags to reduce redundancy and improve clustering

**Algorithm**:
1. Compute embeddings for all unique tags
2. Calculate cosine similarity matrix
3. Find groups of similar tags (threshold: 0.6)
4. Choose "parent" tag (most used, shortest, most general)
5. Reassign all documents from child tags to parent
6. Delete child tags

**Example**:
```
"deep learning" (5 docs) + "deep neural networks" (3 docs) → "deep learning" (8 docs)
"ML" (2 docs) + "machine learning" (7 docs) → "machine learning" (9 docs)
```

**Parameters**:
- `similarity_threshold: float = 0.6` - Cosine similarity threshold (0.6 = somewhat similar)

### 3. Processing Pipeline ([semantic.py](backend/app/services/semantic.py))

**Full Pipeline**:
```
Documents → ML Tag Extraction → Tag Consolidation → Relationships → Clustering
```

**Steps**:
1. **ML Tag Extraction**: KeyBERT extracts semantic tags from each document
2. **Tag Consolidation**: Similar tags are merged (optional, enabled by default)
3. **Relationship Creation**: Documents sharing ≥2 tags are connected
4. **Community Detection**: Louvain algorithm discovers clusters
5. **Semantic Naming**: Clusters named from their most common tags

## Database Schema Changes

### Tag Model Updates

```python
class Tag(Base):
    name = Column(String(255))        # Increased from 100 to support phrases
    category = Column(String(50), nullable=True)  # Now optional (auto-discovered)
    embedding = Column(ARRAY(REAL))   # Store semantic embedding for consolidation
    usage_count = Column(Integer)     # Track document count
```

**Migration**: [002_ml_based_tags_with_embeddings.py](backend/alembic/versions/002_ml_based_tags_with_embeddings.py)

## Usage

### Running the Demo

```bash
# Default: 11 realistic documents with ML extraction + consolidation
make demo

# Skip tag consolidation
docker exec ai-rel-graph-backend python demo.py --no-consolidate

# Adjust consolidation threshold (0.6 = somewhat similar, 0.8 = very similar)
docker exec ai-rel-graph-backend python demo.py --consolidation-threshold 0.7

# Large-scale demo (100 documents)
make demo-large

# Real Kaggle PDFs
make demo-kaggle
```

### Programmatic Usage

```python
from app.services.semantic import SemanticProcessingService

# Initialize service
service = SemanticProcessingService(
    min_shared_tags=2,              # Min shared tags for relationships
    max_tags_per_doc=15,            # Max tags per document
    consolidation_threshold=0.6,    # Similarity threshold for merging
    diversity=0.7,                  # KeyBERT diversity parameter
)

# Process documents
results = service.process_documents(
    session=db,
    files=files,
    show_progress=True,
    consolidate_tags=True,          # Enable consolidation
)

# Results contain:
# - file_tags: Tag assignments
# - relationships: Document connections
# - clusters: Discovered communities
# - consolidated_tags: Child → parent mapping
```

## Comparison: Frequency-Based vs ML-Based

| Aspect | Frequency-Based (Old) | ML-Based (New) |
|--------|----------------------|----------------|
| **Method** | Word counting + TF-IDF | KeyBERT + sentence embeddings |
| **Tags** | Single words ("machine", "learning") | Multi-word phrases ("machine learning") |
| **Categories** | 8 hardcoded categories | Auto-discovered from content |
| **Consolidation** | Synonym mapping (manual) | Semantic similarity (automatic) |
| **Explainability** | High (frequency counts) | High (readable phrases) |
| **Semantic Understanding** | Low | High |
| **Examples** | "neural", "network", "deep" | "neural networks", "deep learning" |

## Benefits

### 1. Better Semantic Understanding
- Captures concepts, not just keywords
- Example: "climate change" vs separate "climate" + "change"

### 2. Automatic Generalization
- Medical + Veterinary documents → "Health" cluster
- Finance + Accounting documents → "Financial" cluster
- No hardcoded categories needed!

### 3. Cleaner Tag Space
- Reduces tag proliferation (100s of tags → 50s of consolidated tags)
- Documents with "ML", "machine learning", "deep learning" all share same tag

### 4. Improved Clustering
- More documents share consolidated tags
- Stronger, more meaningful connections
- Better community detection results

## Configuration

### Environment Variables

```bash
# Optional: Override ML model
ML_MODEL_NAME=all-MiniLM-L6-v2  # Default

# Tag extraction parameters
MAX_TAGS_PER_DOC=15             # Default: 15
TAG_DIVERSITY=0.7               # Default: 0.7 (MMR diversity)

# Consolidation parameters
TAG_CONSOLIDATION_THRESHOLD=0.6 # Default: 0.6 (cosine similarity)
MIN_SHARED_TAGS=2               # Default: 2
```

### Tuning Guide

**`consolidation_threshold`**:
- `0.8-1.0`: Very similar tags only (conservative, more tags remain)
- `0.6-0.8`: Somewhat similar tags (recommended, good balance)
- `0.4-0.6`: Loosely similar tags (aggressive, fewer tags remain)

**`diversity`** (KeyBERT MMR):
- `0.0`: Maximize relevance (may get redundant tags)
- `0.7`: Balanced (recommended)
- `1.0`: Maximize diversity (may get unrelated tags)

**`max_tags_per_doc`**:
- `5-10`: Focused on core concepts
- `10-15`: Good balance (recommended)
- `15-20`: Comprehensive coverage

## Performance

### Small Dataset (11 docs)
- **Tag Extraction**: ~2-3 seconds
- **Consolidation**: ~0.5 seconds
- **Total**: ~5 seconds

### Large Dataset (100 docs)
- **Tag Extraction**: ~20-30 seconds
- **Consolidation**: ~2-3 seconds
- **Total**: ~40 seconds

### Scaling
- ML model loads once at startup (~2 seconds)
- Tag extraction: ~0.2s per document (CPU)
- Consolidation: O(n²) similarity computation (one-time per batch)

## Migration Guide

### From Frequency-Based System

1. **Run migration**:
```bash
make db-migrate
make db-upgrade
```

2. **Update code**:
   - `TagExtractionService` → `MLTagExtractionService` (automatic in `SemanticProcessingService`)
   - No code changes needed if using `SemanticProcessingService`

3. **Rebuild Docker** (for KeyBERT dependency):
```bash
make docker-rebuild
```

4. **Test**:
```bash
make demo
```

### Backward Compatibility

- Old `SemanticProcessingService` API remains the same
- Optional `consolidate_tags=True` parameter (default: enabled)
- Existing endpoints work without changes
- Database migration is additive (no data loss)

## Future Enhancements

### Potential Improvements
1. **GPU Acceleration**: Use CUDA for faster embeddings
2. **Hierarchical Tags**: Parent → child tag relationships (if needed)
3. **Domain-Specific Models**: Fine-tune on specific document types
4. **Multilingual Support**: Use multilingual sentence transformers
5. **Tag Suggestions**: Recommend tags for user review before consolidation

### Alternative Models
- `all-mpnet-base-v2` (768-dim, slower but more accurate)
- `paraphrase-MiniLM-L6-v2` (optimized for paraphrase detection)
- Domain-specific BERT models for technical/medical/legal documents

## Troubleshooting

### Issue: Tags too generic after consolidation
**Solution**: Increase `consolidation_threshold` to 0.7 or 0.8

### Issue: Too many tags, weak connections
**Solution**: Decrease `consolidation_threshold` to 0.5

### Issue: Single-word tags instead of phrases
**Solution**: Check KeyBERT is properly installed and using correct ngram range

### Issue: Slow processing
**Solution**:
- Reduce `max_tags_per_doc`
- Use GPU if available
- Batch process fewer documents at once

### Issue: Model download fails
**Solution**: Pre-download model:
```python
from sentence_transformers import SentenceTransformer
SentenceTransformer('all-MiniLM-L6-v2')  # Downloads once
```

## References

- **KeyBERT**: https://github.com/MaartenGr/KeyBERT
- **Sentence Transformers**: https://www.sbert.net/
- **all-MiniLM-L6-v2**: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
- **Maximal Marginal Relevance**: Balances relevance and diversity in keyword extraction
