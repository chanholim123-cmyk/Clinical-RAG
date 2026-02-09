# Quick Start Guide

## 30 Second Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Application
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Open in Browser
```
http://localhost:8000
```

## What You'll See

### Frontend Layout
- **Header**: "NG12 Cancer Risk Assessor" with blue gradient
- **Two Tabs**:
  1. Risk Assessor - Select a patient and run assessment
  2. Chat with NG12 - Ask questions about guidelines

### Tab 1: Risk Assessor

1. **Patient Selection**
   - Click dropdown to see available patients (P001-P005)
   - Includes patient name and ID

2. **Run Assessment**
   - Click "Assess Risk" button
   - Wait for results (mock data is instant)

3. **View Results**
   - Patient summary card with name, ID, assessment date
   - Risk badge (red=urgent, orange=consider, green=no criteria)
   - Clinical reasoning bullets
   - Citation references from NICE NG12
   - Medical disclaimer

### Tab 2: Chat with NG12

1. **Session ID**
   - Auto-generated UUID displayed at top
   - "New Session" button to start fresh conversation

2. **Ask Questions**
   - Type in text input box
   - Press Enter or click Send
   - Messages appear with timestamps

3. **View Responses**
   - Assistant responses in gray boxes
   - Inline citations shown below each response
   - Full conversation history maintained

## Sample Patients

- **P001**: James Smith (68M) - Smoking history, family history of lung cancer
- **P002**: Sarah Johnson (55F) - No significant history
- **P003**: Robert Brown (72M) - Diabetic, hypertensive, long-term smoker
- **P004**: Mary Wilson (60F) - Asthma, family history colorectal cancer
- **P005**: David Lee (45M) - No significant history

## Sample Chat Questions

Try asking:
- "What are the urgent referral criteria?"
- "How do I assess cancer risk in elderly patients?"
- "What symptoms require immediate investigation?"
- "What is the NG12 guideline?"
- "How do I interpret the risk assessment?"

## API Endpoints (for testing)

### Get All Patients
```bash
curl http://localhost:8000/patients
```

### Assess a Patient
```bash
curl -X POST http://localhost:8000/assess \
  -H "Content-Type: application/json" \
  -d '{"patient_id": "P001"}'
```

### Send Chat Message
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-session-123",
    "message": "What is urgent referral?",
    "top_k": 5
  }'
```

### Check Health
```bash
curl http://localhost:8000/health
```

## API Documentation

Auto-generated interactive docs available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Directory Structure

```
ng12-cancer-assessor/
├── app/
│   ├── main.py           # FastAPI app with all endpoints
│   ├── config.py         # Configuration
│   └── [agents/, tools/, rag/]  # For future integration
├── static/
│   └── index.html        # Frontend (single file)
├── patients.json         # Patient database
├── requirements.txt      # Dependencies
├── SETUP.md             # Detailed setup guide
└── QUICKSTART.md        # This file
```

## Troubleshooting

**"Port 8000 already in use"**
```bash
python -m uvicorn app.main:app --reload --port 8001
```

**"Module not found" error**
```bash
pip install --upgrade -r requirements.txt
```

**Frontend not loading**
- Check terminal for errors
- Browser console (F12) for JavaScript errors
- Make sure uvicorn is running

**Patient not found**
- Check patient ID matches ones in patients.json
- Valid IDs: P001, P002, P003, P004, P005

## Next Steps

1. **Customize Patients**: Edit `patients.json` to add your own patients
2. **Modify Risk Logic**: Update `_get_mock_assessment()` in `app/main.py`
3. **Add Real RAG**: Implement vector store integration
4. **Connect LLM**: Integrate with Gemini API for real responses
5. **Deploy**: Use Docker for production deployment

See `SETUP.md` for detailed documentation.
