# NG12 Cancer Risk Assessor - PDF Ingestion and Vector Store Guide

## Overview

This guide covers the PDF ingestion pipeline and vector store interface for the NICE NG12 Cancer Risk Assessor project.

The system consists of two main components:

1. **`scripts/ingest_pdf.py`** - Ingests the NICE NG12 PDF and creates a ChromaDB vector store
2. **`app/rag/vector_store.py`** - Provides the RAG query interface for the vector store

## Architecture

### Ingestion Pipeline

The ingestion process performs:

1. **PDF Text Extraction**: Uses PyMuPDF (fitz) to extract text from each page
2. **Hierarchical Structure Detection**:
   - Identifies section headers (e.g., "1.1 Lung and pleural cancers")
   - Identifies subsection headers (e.g., "1.1.1 Lung cancer")
   - Identifies individual recommendations by numbering pattern
3. **Section-Aware Chunking**:
   - Creates chunks that preserve hierarchical context
   - Implements overlapping chunks (~33% overlap) for boundary context
   - Each chunk contains full context (page, section, subsection, recommendation ID)
4. **Urgency Detection**:
   - Scans text for urgency keywords (urgent, very urgent, suspected cancer pathway, etc.)
   - Adds urgency_level metadata to chunks
5. **Embedding Generation**:
   - Supports Google Vertex AI embeddings (textembedding-gecko@003, 768-dim vectors)
   - Falls back to ChromaDB's default embedding function if Vertex AI unavailable
6. **Vector Store Creation**:
   - Stores chunks in ChromaDB with rich metadata
   - Uses cosine similarity for semantic search
   - Persists to disk for reuse

### Metadata Structure

Each chunk includes:

```python
{
    "id": "ng12_p5_c0",                    # Unique chunk ID
    "text": "...",                         # Full recommendation text
    "page": 5,                             # Page number (1-indexed)
    "section": "1.1",                      # Main section identifier
    "subsection": "1.1.1",                 # Subsection identifier
    "recommendation_id": "1.1.1",          # Recommendation number
    "urgency_level": "urgent",             # One of: urgent, very_urgent, suspected_cancer, non_urgent, consider, direct_access
}
```

## Installation

### Dependencies

```bash
pip install pymupdf chromadb google-cloud-aiplatform
```

### Optional: Google Cloud Setup

If using Vertex AI embeddings:

```bash
gcloud auth application-default login
export GOOGLE_CLOUD_PROJECT=your-project-id
```

## Usage

### Step 1: Ingest PDF

```bash
# Basic usage (ChromaDB default embeddings)
python scripts/ingest_pdf.py --pdf-path /path/to/NG12.pdf

# With Vertex AI embeddings
python scripts/ingest_pdf.py \
    --pdf-path /path/to/NG12.pdf \
    --use-vertex-ai \
    --project-id my-gcp-project

# Custom output directory
python scripts/ingest_pdf.py \
    --pdf-path /path/to/NG12.pdf \
    --output-dir /custom/path/vectorstore

# Debug mode
python scripts/ingest_pdf.py \
    --pdf-path /path/to/NG12.pdf \
    --log-level DEBUG
```

### Step 2: Query the Vector Store

#### Basic Semantic Search

```python
from app.rag.vector_store import NG12VectorStore

# Initialize
vs = NG12VectorStore(persist_dir="./data/vectorstore")

# Simple query
results = vs.query("persistent cough in elderly patient", top_k=5)

for result in results:
    print(f"Page {result['page']}: {result['text'][:200]}")
    print(f"  Urgency: {result['urgency_level']}")
    print(f"  Relevance: {result['relevance_score']:.2f}\n")
```

#### Symptom-Based Query with Patient Context

```python
# Query optimized for symptoms and patient context
symptoms = ["persistent cough", "weight loss", "chest pain"]
results = vs.query_by_symptoms(
    symptoms=symptoms,
    age=68,
    gender="M",
    top_k=10
)

for result in results:
    print(f"Section {result['section']}: {result['recommendation_id']}")
    print(f"  Score: {result['relevance_score']:.2f}")
    print(f"  Urgency: {result['urgency_level']}")
```

#### Retrieve Section Context

```python
# Get all recommendations in a specific section
section_chunks = vs.get_section_context("1.1")

if section_chunks:
    for chunk in section_chunks:
        print(f"{chunk['recommendation_id']}: {chunk['text'][:100]}...")
```

#### Get Urgent Recommendations

```python
# Retrieve all urgent/very urgent recommendations
urgent = vs.get_urgent_recommendations(top_k=20)

for item in urgent:
    print(f"[{item['urgency_level'].upper()}] {item['recommendation_id']}")
    print(f"  {item['text'][:150]}...\n")
```

#### Get Statistics

```python
stats = vs.get_statistics()

print(f"Total chunks: {stats['total_chunks']}")
print(f"Sections: {stats['sections']}")
print(f"Has urgency metadata: {stats['has_urgency_metadata']}")
```

## Ingestion Script Details

### Command-Line Options

```
usage: ingest_pdf.py [-h] --pdf-path PDF_PATH
                     [--output-dir OUTPUT_DIR]
                     [--use-vertex-ai]
                     [--no-vertex-ai]
                     [--project-id PROJECT_ID]
                     [--location LOCATION]
                     [--log-level {DEBUG,INFO,WARNING,ERROR}]

Options:
  --pdf-path PDF_PATH          Path to NICE NG12 PDF (required)
  --output-dir OUTPUT_DIR      ChromaDB output directory (default: ./data/vectorstore)
  --use-vertex-ai              Use Vertex AI for embeddings (default)
  --no-vertex-ai               Use ChromaDB default embeddings
  --project-id PROJECT_ID      GCP project ID for Vertex AI
  --location LOCATION          GCP region (default: us-central1)
  --log-level LEVEL            Logging verbosity (default: INFO)
```

### Chunking Strategy

The ingestion uses a sophisticated chunking strategy:

1. **Target Size**: ~500 tokens per chunk (approximately 2000 characters)
2. **Overlap**: ~33% overlap between adjacent chunks for context preservation
3. **Boundary Preservation**: Respects section and subsection boundaries
4. **Recommendation Detection**: Preserves complete recommendations with their context

Example chunk structure:
```
[Section 1.1: Lung and pleural cancers]
[Subsection 1.1.1: Lung cancer]

1.1.1 Primary recommendation text...
1.1.1.1 Supporting detail...
1.1.1.2 Additional detail...

[Overlap with next chunk begins...]
```

### Urgency Level Detection

The ingestion automatically detects and tags urgency levels based on keywords:

| Keyword Pattern | Urgency Level | Use Case |
|---|---|---|
| "urgent referral" | `urgent` | Urgent referral pathways |
| "very urgent referral" | `very_urgent` | Very urgent referral pathways |
| "suspected cancer pathway" | `suspected_cancer` | Suspected cancer referral |
| "consider" | `consider` | Optional considerations |
| "direct access" | `direct_access` | Direct access to specialists |
| "non-urgent" | `non_urgent` | Routine follow-up |

## Vector Store Interface Details

### NG12VectorStore Class

**Methods:**

#### `__init__(persist_dir: str = "./data/vectorstore")`
Initializes the vector store from persistent ChromaDB storage.

**Raises:**
- `ValueError`: If directory doesn't exist or store is empty
- `RuntimeError`: If unable to connect to ChromaDB

#### `query(query_text: str, top_k: int = 5) -> list[dict]`
Semantic search for relevant guideline chunks.

**Returns:** List of results with:
- `text`: Chunk content
- `page`: PDF page number
- `section`: Main section ID
- `subsection`: Subsection ID
- `recommendation_id`: Recommendation number
- `chunk_id`: Unique chunk identifier
- `urgency_level`: Detected urgency (if present)
- `relevance_score`: Similarity score (0.0-1.0)

#### `query_by_symptoms(symptoms: list[str], age: int, gender: str, top_k: int = 5) -> list[dict]`
Query optimized for patient symptoms and demographics.

Automatically:
- Combines individual symptom terms
- Adds age-appropriate context
- Adds gender-specific considerations
- Includes common cancer risk factors

**Returns:** Same format as `query()`, sorted by relevance

#### `get_section_context(section: str) -> Optional[list[dict]]`
Retrieve all chunks from a specific guideline section.

**Example:** `vs.get_section_context("1.1")` returns all chunks in section 1.1

#### `get_urgent_recommendations(top_k: int = 10) -> list[dict]`
Retrieve all recommendations marked urgent or very urgent.

**Returns:** List of urgent/very urgent chunks

#### `get_statistics() -> dict`
Get overview statistics about the vector store.

**Returns:**
```python
{
    "total_chunks": 150,
    "sections": ["1.1", "1.2", "1.3", ...],
    "subsections": ["1.1.1", "1.1.2", ...],
    "has_urgency_metadata": True
}
```

## Error Handling

### Common Errors and Solutions

**"Vector store directory does not exist"**
```python
# Run ingestion first
# python scripts/ingest_pdf.py --pdf-path /path/to/NG12.pdf
```

**"Vector store is empty"**
- The ingestion script didn't run successfully
- Check logs: `--log-level DEBUG`
- Verify PDF file exists and is readable

**"Query failed: RuntimeError"**
- Vector store may be corrupted
- Try re-running ingestion
- Check ChromaDB logs for details

**Vertex AI embedding errors**
```bash
# Verify GCP authentication
gcloud auth application-default login

# Check project is set
gcloud config get-value project
```

## Performance Considerations

### Ingestion Time

- **Small PDF** (10-20 pages): ~1-2 minutes
- **Medium PDF** (50-100 pages): ~5-10 minutes
- **Large PDF** (200+ pages): ~15-30 minutes

*Times vary based on:*
- PDF complexity (scanned vs. text)
- Embedding method (Vertex AI slower than ChromaDB default)
- Hardware performance

### Query Performance

- **Single semantic query**: ~50-200ms
- **Symptom-based query**: ~100-300ms
- **Section context retrieval**: ~50-100ms
- **Urgent recommendations**: ~50-100ms

*Optimized by:*
- ChromaDB's HNSW indexing (approximate nearest neighbors)
- In-memory caching of collection metadata
- Batch processing for embeddings

## Best Practices

1. **Always check urgency_level**
   ```python
   if result['urgency_level'] in ['urgent', 'very_urgent', 'suspected_cancer']:
       # Escalate to clinical decision support
   ```

2. **Use symptom-based queries for patient input**
   ```python
   # Better than raw text
   vs.query_by_symptoms(symptoms, age, gender)
   # Rather than
   vs.query("patient with symptoms...")
   ```

3. **Combine with section context**
   ```python
   # Get initial results
   results = vs.query(query_text)

   # Expand with full section context
   if results:
       section = results[0]['section']
       full_section = vs.get_section_context(section)
   ```

4. **Log all queries for audit trail**
   ```python
   import logging
   logging.getLogger().setLevel(logging.DEBUG)
   ```

5. **Handle metadata gracefully**
   ```python
   # Metadata may be incomplete for some chunks
   urgency = result.get('urgency_level') or 'not_specified'
   ```

## Troubleshooting

### Vector Store Corruption

If you suspect the vector store is corrupted:

```bash
# Delete and re-create
rm -rf ./data/vectorstore
python scripts/ingest_pdf.py --pdf-path /path/to/NG12.pdf
```

### Memory Issues

If running on limited memory:

```bash
# Process smaller batches (modify in ingest_pdf.py)
# Change VERTEX_AI_BATCH_SIZE from 5 to 1
```

### Embedding Quality Issues

If embeddings seem low quality:

```bash
# Use Vertex AI for better results (if available)
python scripts/ingest_pdf.py \
    --pdf-path /path/to/NG12.pdf \
    --use-vertex-ai \
    --project-id your-project
```

## Integration Examples

### Flask Web Application

```python
from flask import Flask, request, jsonify
from app.rag.vector_store import NG12VectorStore

app = Flask(__name__)
vs = NG12VectorStore()

@app.route('/api/query', methods=['POST'])
def query():
    data = request.json
    symptoms = data.get('symptoms', [])
    age = data.get('age')
    gender = data.get('gender')

    results = vs.query_by_symptoms(symptoms, age, gender, top_k=10)

    return jsonify({
        'results': results,
        'count': len(results)
    })
```

### FastAPI Application

```python
from fastapi import FastAPI
from pydantic import BaseModel
from app.rag.vector_store import NG12VectorStore

app = FastAPI()
vs = NG12VectorStore()

class PatientQuery(BaseModel):
    symptoms: list[str]
    age: int
    gender: str
    top_k: int = 5

@app.post("/query")
async def query_guidelines(query: PatientQuery):
    results = vs.query_by_symptoms(
        symptoms=query.symptoms,
        age=query.age,
        gender=query.gender,
        top_k=query.top_k
    )
    return {"results": results}
```

## Advanced Configuration

### Custom Embeddings

To use a different embedding model (modify vector_store.py):

```python
# Use OpenAI embeddings
from openai import OpenAI

client = OpenAI()
embedding = client.embeddings.create(
    model="text-embedding-3-large",
    input=text
).data[0].embedding
```

### Custom Similarity Metric

ChromaDB supports different distance metrics (modify HNSW configuration):

```python
collection = client.get_or_create_collection(
    name="ng12_cancer_guidelines",
    metadata={"hnsw:space": "l2"}  # l2, cosine, or ip
)
```

## License

These scripts are part of the NG12 Cancer Risk Assessor project.
The NICE NG12 guideline content is subject to NICE's licensing terms.
