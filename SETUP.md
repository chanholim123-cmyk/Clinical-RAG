# NG12 Cancer Risk Assessor - Setup & Usage Guide

## Project Structure

```
ng12-cancer-assessor/
├── app/
│   ├── __init__.py              # Empty package marker
│   ├── main.py                  # FastAPI application with all endpoints
│   ├── config.py                # Configuration management
│   ├── agents/                  # AI agents for risk assessment and chat
│   ├── rag/                     # Vector store and RAG components
│   ├── tools/                   # Lookup tools for patient and guideline data
│   └── models/                  # Data models
├── static/
│   └── index.html               # Single-page frontend application
├── data/
│   └── ng12.pdf                 # NICE NG12 guideline PDF
├── patients.json                # Patient database
└── requirements.txt             # Python dependencies
```

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

Key dependencies:
- **fastapi**: Web framework
- **uvicorn**: ASGI server
- **pydantic**: Data validation
- **google-cloud-aiplatform**: Gemini API access
- **langchain**: LLM orchestration
- **pymupdf**: PDF parsing for NICE NG12

### 2. Set Environment Variables

```bash
export GCP_PROJECT_ID="your-gcp-project-id"
export GCP_LOCATION="us-central1"
export MODEL_NAME="gemini-1.5-pro"
export EMBEDDING_MODEL="textembedding-gecko@003"
export VECTORSTORE_PATH="./data/vectorstore"
export PDF_PATH="./data/ng12.pdf"
export PATIENTS_PATH="./patients.json"
```

### 3. Prepare Data

#### NICE NG12 PDF
Place the NICE NG12 guideline PDF at `./data/ng12.pdf`. The system will automatically:
1. Parse the PDF
2. Extract text and structure
3. Build a vector store for RAG

#### Patient Database
Create `./patients.json`:

```json
{
  "P001": {
    "name": "James Smith",
    "age": 68,
    "gender": "Male",
    "medical_history": ["Smoking history", "Family history of lung cancer"]
  },
  "P002": {
    "name": "Sarah Johnson",
    "age": 55,
    "gender": "Female",
    "medical_history": []
  }
}
```

## Running the Application

### Development Server

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Access the frontend at: http://localhost:8000

### Production Server

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Documentation

### Auto-generated Docs
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Endpoints

#### Risk Assessment

**POST /assess**
```json
{
  "patient_id": "P001"
}
```

Response:
```json
{
  "patient_id": "P001",
  "patient_name": "James Smith",
  "assessment_date": "2024-01-15T10:30:00",
  "risk_level": "consider",
  "urgency_color": "orange",
  "summary": "Consider further investigation based on NICE NG12 guidelines.",
  "reasoning": [
    "Age over 60 identified as potential risk factor",
    "Smoking history noted - relevant for lung cancer risk assessment"
  ],
  "citations": [
    {
      "section": "NICE NG12 - Suspected cancer: recognition and referral",
      "page": 1,
      "content": "This guideline helps healthcare professionals..."
    }
  ],
  "disclaimer": "This is a clinical decision support tool..."
}
```

**GET /patients**
```json
[
  {
    "patient_id": "P001",
    "name": "James Smith",
    "age": 68,
    "gender": "Male"
  }
]
```

#### Chat

**POST /chat**
```json
{
  "session_id": "uuid-here",
  "message": "What are the urgent referral criteria?",
  "top_k": 5
}
```

Response:
```json
{
  "session_id": "uuid-here",
  "answer": "According to NICE NG12 guidelines, urgent referral...",
  "citations": [
    {
      "section": "NICE NG12 - General principles",
      "page": 2,
      "relevance": 0.95
    }
  ],
  "retrieved_passages_count": 3
}
```

**GET /chat/{session_id}/history**
Returns conversation history for a session.

**DELETE /chat/{session_id}**
Clears conversation history for a session.

**GET /health**
Health check endpoint.

## Frontend Features

### Tab 1: Risk Assessor
- **Patient Selection**: Dropdown populated from `/patients` endpoint
- **Assessment**: Runs risk assessment agent with patient data
- **Results Display**:
  - Patient summary card with demographics
  - Risk level badge (color-coded: red/urgent, orange/consider, green/no criteria)
  - Clinical reasoning with bullet points
  - Citations from NICE NG12
  - Medical disclaimer

### Tab 2: Chat with NG12
- **Multi-turn Conversation**: Ask questions about NICE NG12 guidelines
- **Session Management**: Auto-generated UUID for session tracking
- **Message History**: Persistent conversation history per session
- **Citations**: Each assistant message includes relevant guideline citations
- **New Session**: Clear conversation and start fresh

## Design Architecture

### FastAPI Backend (`app/main.py`)

**Endpoints Structure**:
1. **Risk Assessment Endpoints**
   - `POST /assess`: Main assessment endpoint
   - `GET /patients`: List available patients

2. **Chat Endpoints**
   - `POST /chat`: Send message and get response
   - `GET /chat/{session_id}/history`: Retrieve conversation history
   - `DELETE /chat/{session_id}`: Clear session

3. **UI & Health**
   - `GET /`: Serve frontend HTML
   - `GET /health`: Health check

### Configuration (`app/config.py`)

Settings class with environment variable support:
- GCP Project ID and Location
- Model selection (Gemini variants)
- Embedding model for RAG
- File paths for vector store and PDF

### Frontend (`static/index.html`)

**Single HTML file** with embedded CSS and JavaScript:
- **No external dependencies** (except optional icon library)
- **Vanilla JavaScript** using fetch API
- **Professional clinical aesthetic** with:
  - Muted blue and green color scheme
  - System font stack
  - Responsive grid layouts
  - Loading spinners during API calls
  - Error handling with user-friendly messages

**Key JavaScript Functions**:
- `performAssessment()`: Call /assess endpoint
- `sendChatMessage()`: Send chat messages
- `loadPatients()`: Populate patient dropdown
- `displayAssessmentResult()`: Render assessment results
- `startNewSession()`: Initialize new chat session

## Error Handling

### Backend
- **404 Not Found**: Patient not found, session not found
- **400 Bad Request**: Invalid input (empty patient ID, empty message)
- **500 Internal Server Error**: Processing failures

All errors return JSON with descriptive messages.

### Frontend
- Try/catch blocks on all fetch calls
- User-friendly error alerts
- Loading state management with disabled buttons
- Graceful fallbacks for missing data

## Mock Data & Testing

The application includes mock implementations for:
1. **Patient loading**: Sample patients with medical histories
2. **Risk assessment**: Logic based on age, smoking history, family history
3. **Chat responses**: Context-aware answers about NG12 guidelines
4. **Citations**: Sample citations from NG12 guideline sections

To switch to real implementations:
1. Replace `_get_mock_assessment()` with actual agent
2. Replace `_get_mock_chat_response()` with RAG pipeline
3. Connect to real vector store and LLM

## Performance Considerations

- **Async endpoints**: All FastAPI endpoints are async for concurrency
- **Session storage**: In-memory dict (can be replaced with Redis/database)
- **Vector store**: Initialize once on startup, reuse for all queries
- **CORS**: Enabled for all origins (restrict in production)

## Security Considerations

### Development Notes
- Current implementation uses in-memory storage (not persistent)
- CORS is open (restrict to specific origins in production)
- No authentication (add JWT or OAuth for production)
- Mock data only (not real medical records)

### Production Recommendations
1. **Database**: Replace in-memory storage with PostgreSQL or MongoDB
2. **Authentication**: Implement OAuth2 or OIDC with healthcare systems
3. **CORS**: Restrict to specific frontend domains
4. **HTTPS**: Always use HTTPS in production
5. **Rate limiting**: Add rate limiting to prevent abuse
6. **Audit logging**: Log all assessment and chat interactions
7. **Data encryption**: Encrypt patient data at rest and in transit
8. **Compliance**: Ensure HIPAA/GDPR compliance for healthcare data

## Testing

### Unit Tests
```bash
python -m pytest tests/ -v
```

### Manual Testing
```bash
# Start the server
python -m uvicorn app.main:app --reload

# In another terminal, test endpoints
curl http://localhost:8000/health
curl http://localhost:8000/patients
curl -X POST http://localhost:8000/assess -H "Content-Type: application/json" -d '{"patient_id": "P001"}'
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" -d '{"session_id": "test", "message": "What is urgent referral?"}'
```

## Customization

### Adding New Patients
Edit `patients.json` and add new entries with the same structure.

### Modifying Risk Assessment Logic
Update `_get_mock_assessment()` in `app/main.py` to implement custom logic.

### Updating Chat Responses
Replace `_get_mock_chat_response()` with a real RAG pipeline using LangChain.

### Styling Changes
Modify the CSS in `<style>` section of `static/index.html`.

## Troubleshooting

### FastAPI Import Error
```
ModuleNotFoundError: No module named 'fastapi'
```
Solution: Run `pip install -r requirements.txt`

### Port Already in Use
```
OSError: [Errno 48] Address already in use
```
Solution: Change port with `--port 8001` or kill process on port 8000

### Patient Not Found
Ensure patient ID in `patients.json` matches the ID used in assessment request.

### Chat Not Working
Check that session_id is not empty and message content is valid.

## Support

For issues or questions:
1. Check error messages in browser console (F12)
2. Check FastAPI logs in terminal
3. Review endpoint response in Swagger UI (/docs)
4. Check JSON formatting in API requests

## License

Clinical Decision Support Tool - NICE NG12 Guidelines
For use in healthcare professional training and decision support only.
