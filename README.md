# NG12 Cancer Risk Assessor

A Clinical Decision Support Agent that assesses cancer risk using the NICE NG12 guideline *"Suspected cancer: recognition and referral"*. Built with Google Vertex AI (Gemini 1.5 Pro), FastAPI, ChromaDB, and a single-page web UI.

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  Frontend (SPA)                  │
│         static/index.html — two tabs:            │
│     [Risk Assessor]        [Chat with NG12]      │
└──────────┬─────────────────────┬────────────────┘
           │                     │
     POST /assess          POST /chat
           │                     │
┌──────────▼──────────┐ ┌───────▼───────────────┐
│  CancerRiskAssessor │ │    NG12ChatAgent       │
│                     │ │                        │
│  1. get_patient     │ │  1. search_ng12        │
│  2. search_ng12     │ │  2. generate answer    │
│  3. reason + cite   │ │  3. cite passages      │
│  4. classify risk   │ │  4. maintain history   │
└──────┬──────┬───────┘ └───────┬────────────────┘
       │      │                 │
  ┌────▼──┐ ┌─▼──────────┐ ┌───▼──────────┐
  │Patient│ │ ChromaDB   │ │ Gemini 1.5   │
  │  JSON │ │ VectorStore│ │ Pro (Vertex)  │
  └───────┘ └────────────┘ └──────────────┘
```

**Key design decisions:**

- **Dual-mode startup**: The app automatically detects whether Vertex AI credentials are available. If they are, it runs in *live mode* using the real Gemini agents. If not, it falls back to *mock mode* with simulated responses — so reviewers can run the UI without a GCP account.
- **Section-aware RAG chunking**: The PDF ingestion pipeline preserves NG12's hierarchical structure (sections, subsections, individual recommendations) rather than using naive fixed-size chunks.
- **Function calling loop**: Both agents use Vertex AI's native function calling to retrieve data (patient records, guideline passages) before generating responses, ensuring answers are grounded in source material.

## Quick Start

### Option A: Docker (recommended)

```bash
# 1. Clone and enter the project
cd ng12-cancer-assessor

# 2. (Optional) Add GCP credentials for live mode
mkdir -p credentials
cp /path/to/service-account.json credentials/

# 3. Build and run
docker compose up --build

# 4. Open http://localhost:8000
```

### Option B: Local Python

```bash
# 1. Create virtual environment
python3.11 -m venv .venv && source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) Configure GCP for live mode
export GCP_PROJECT_ID=your-project-id
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# 4. Ingest the NG12 PDF into the vector store
python scripts/ingest_pdf.py --pdf-path /path/to/ng12.pdf

# 5. Run the server
uvicorn app.main:app --reload --port 8000
```

### Option C: Mock mode (no GCP needed)

```bash
pip install fastapi uvicorn pydantic
uvicorn app.main:app --port 8000
# → Opens in mock mode with simulated responses
```

## API Endpoints

| Method   | Path                        | Description                              |
|----------|-----------------------------|------------------------------------------|
| `POST`   | `/assess`                   | Run risk assessment for a patient ID     |
| `GET`    | `/patients`                 | List all available patient IDs           |
| `POST`   | `/chat`                     | Send a message to the NG12 chat agent    |
| `GET`    | `/chat/{session_id}/history`| Retrieve conversation history            |
| `DELETE` | `/chat/{session_id}`        | Clear a chat session                     |
| `GET`    | `/health`                   | Health check (includes mode: live/mock)  |

### Example: Assess a patient

```bash
curl -X POST http://localhost:8000/assess \
  -H "Content-Type: application/json" \
  -d '{"patient_id": "P001"}'
```

### Example: Chat with NG12

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "s1", "message": "What are the referral criteria for lung cancer?"}'
```

## Project Structure

```
ng12-cancer-assessor/
├── app/
│   ├── main.py              # FastAPI app — routes, schemas, mock fallback
│   ├── config.py            # Environment-based configuration
│   ├── agents/
│   │   ├── risk_assessor.py # Part 1: Gemini function-calling risk agent
│   │   └── chat_agent.py    # Part 2: Gemini conversational RAG agent
│   ├── rag/
│   │   └── vector_store.py  # ChromaDB interface for guideline retrieval
│   └── tools/
│       ├── patient_lookup.py    # Patient data tool + Vertex AI schema
│       └── guideline_lookup.py  # RAG search tool + Vertex AI schema
├── scripts/
│   └── ingest_pdf.py        # PDF → chunks → embeddings → ChromaDB
├── static/
│   └── index.html           # Single-page UI (assessor tab + chat tab)
├── tests/
│   └── test_vector_store.py
├── patients.json            # Patient dataset
├── PROMPTS.md               # Part 1 system prompt strategy documentation
├── CHAT_PROMPTS.md          # Part 2 system prompt strategy documentation
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Prompt Strategy Documentation

The prompt engineering approach is documented in two dedicated files:

- **[PROMPTS.md](./PROMPTS.md)** — System prompt strategy for the Part 1 Risk Assessor agent: role framing, the RETRIEVE→SEARCH→REASON→CLASSIFY process chain, tool schema design, domain terminology injection, output schema enforcement, safety guardrails, and evaluation approach.

- **[CHAT_PROMPTS.md](./CHAT_PROMPTS.md)** — System prompt strategy for the Part 2 Conversational agent: retrieval-before-response pattern, two-tier citation architecture, graceful degradation, multi-turn handling, urgency-ordered response structuring, scope containment, and comparison with Part 1.

## Configuration

All settings are configurable via environment variables:

| Variable                        | Default                      | Description                          |
|---------------------------------|------------------------------|--------------------------------------|
| `GCP_PROJECT_ID`                | `your-project-id`            | Google Cloud project ID              |
| `GCP_LOCATION`                  | `us-central1`                | Vertex AI region                     |
| `MODEL_NAME`                    | `gemini-1.5-pro`             | Generative model                     |
| `EMBEDDING_MODEL`               | `textembedding-gecko@003`    | Embedding model for RAG              |
| `VECTORSTORE_PATH`              | `./data/vectorstore`         | ChromaDB persistence directory       |
| `PDF_PATH`                      | `./data/ng12.pdf`            | Path to NG12 PDF for ingestion       |
| `PATIENTS_PATH`                 | `./patients.json`            | Path to patient dataset              |
| `GOOGLE_APPLICATION_CREDENTIALS`| —                            | Path to GCP service account key      |

## Testing

```bash
# Run unit tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=term-missing
```

## Sample Data

10 test patients included in `patients.json` (per assessment spec):

| ID     | Name             | Age | Smoking        | Key Symptoms                            |
|--------|------------------|-----|----------------|-----------------------------------------|
| PT-101 | John Doe         | 55  | Current Smoker | unexplained hemoptysis, fatigue         |
| PT-102 | Jane Smith       | 25  | Never Smoked   | persistent cough, sore throat           |
| PT-103 | Robert Brown     | 45  | Ex-Smoker      | persistent cough, shortness of breath   |
| PT-104 | Sarah Connor     | 35  | Never Smoked   | dysphagia                               |
| PT-105 | Michael Chang    | 65  | Ex-Smoker      | iron-deficiency anaemia, fatigue        |
| PT-106 | Emily Blunt      | 18  | Never Smoked   | fatigue                                 |
| PT-107 | David Bowie      | 48  | Current Smoker | persistent hoarseness                   |
| PT-108 | Alice Wonderland | 32  | Never Smoked   | unexplained breast lump                 |
| PT-109 | Tom Cruise       | 45  | Never Smoked   | dyspepsia                               |
| PT-110 | Bruce Wayne      | 60  | Never Smoked   | visible haematuria                      |

## Disclaimer

This is a technical assessment project. It is **not** a certified medical device. All clinical recommendations must be reviewed by qualified healthcare professionals. The system is designed as a decision *support* tool, not a decision *making* tool.
