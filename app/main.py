"""
NG12 Cancer Risk Assessor — FastAPI Application.

Provides two main capabilities:
  Part 1: POST /assess — structured risk assessment for a patient ID
  Part 2: POST /chat   — multi-turn conversational Q&A over NG12 guidelines
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uvicorn
import json
import logging
import os
from pathlib import Path
from datetime import datetime

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Try to import the real Vertex AI-powered agents; fall back to mock mode
# ---------------------------------------------------------------------------
_USE_REAL_AGENTS = False

try:
    from app.agents.risk_assessor import CancerRiskAssessor
    from app.agents.chat_agent import NG12ChatAgent
    _risk_assessor = CancerRiskAssessor(
        project_id=settings.PROJECT_ID,
        location=settings.LOCATION,
    )
    _chat_agent = NG12ChatAgent(
        project_id=settings.PROJECT_ID,
        location=settings.LOCATION,
    )
    _USE_REAL_AGENTS = True
    logger.info("Vertex AI agents initialised — running in LIVE mode")
except Exception as e:
    logger.warning(
        f"Could not initialise Vertex AI agents ({e}). "
        "Running in MOCK mode — responses will be simulated."
    )
    _risk_assessor = None
    _chat_agent = None

# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="NG12 Cancer Risk Assessor",
    description="Clinical Decision Support Agent using NICE NG12 Guidelines",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class AssessRequest(BaseModel):
    patient_id: str


class ChatRequest(BaseModel):
    session_id: str
    message: str
    top_k: Optional[int] = 5


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    citations: List[Dict[str, Any]]
    retrieved_passages_count: int


class PatientInfo(BaseModel):
    patient_id: str
    name: str
    age: Optional[int] = None
    gender: Optional[str] = None


class RiskAssessmentResult(BaseModel):
    patient_id: str
    patient_name: str
    assessment_date: str
    risk_level: str
    urgency_color: str
    summary: str
    reasoning: List[str]
    citations: List[Dict[str, Any]]
    disclaimer: str


class ChatHistoryEntry(BaseModel):
    role: str
    message: str
    timestamp: str
    citations: Optional[List[Dict[str, Any]]] = None


# ---------------------------------------------------------------------------
# In-memory stores (chat sessions, patient cache)
# ---------------------------------------------------------------------------
_chat_sessions: Dict[str, List[ChatHistoryEntry]] = {}


def _load_patients() -> Dict[str, Dict[str, Any]]:
    """Load patient records from the JSON file on disk."""
    try:
        if os.path.exists(settings.PATIENTS_PATH):
            with open(settings.PATIENTS_PATH, "r") as f:
                data = json.load(f)
                # Support both dict-of-dicts and list-of-dicts formats
                if isinstance(data, list):
                    return {p.get("patient_id", f"P{i:03d}"): p for i, p in enumerate(data)}
                return data
    except Exception as e:
        logger.error(f"Could not load patients: {e}")
    return {}


# ---------------------------------------------------------------------------
# Part 1 — Risk Assessment
# ---------------------------------------------------------------------------

def _assess_with_agent(patient_id: str) -> RiskAssessmentResult:
    """Run the real Vertex AI risk-assessment agent."""
    raw = _risk_assessor.assess(patient_id)

    if raw.get("error"):
        raise RuntimeError(raw.get("message", "Agent returned an error"))

    # Map the agent's structured JSON into our API schema
    risk = raw.get("risk_assessment", {})
    urgency = risk.get("overall_urgency", "no_criteria_met")

    # Derive colour from urgency string
    urgency_lower = urgency.lower()
    if any(k in urgency_lower for k in ["suspected cancer pathway", "very urgent", "urgent"]):
        color = "red"
    elif "consider" in urgency_lower or "non-urgent" in urgency_lower:
        color = "orange"
    else:
        color = "green"

    citations = [
        {
            "section": c.get("section", c.get("source", "")),
            "page": c.get("page", 0),
            "content": c.get("excerpt", ""),
            "recommendation_id": c.get("recommendation_id", ""),
        }
        for c in raw.get("citations", [])
    ]

    ps = raw.get("patient_summary", {})

    return RiskAssessmentResult(
        patient_id=patient_id,
        patient_name=ps.get("name", patient_id),
        assessment_date=datetime.now().isoformat(),
        risk_level=urgency,
        urgency_color=color,
        summary=risk.get("referral_recommendation", urgency),
        reasoning=[raw.get("reasoning", "See citations for detail.")],
        citations=citations,
        disclaimer=(
            "This assessment is generated by an AI system and must be "
            "reviewed by a qualified healthcare professional."
        ),
    )


def _assess_mock(patient_id: str) -> RiskAssessmentResult:
    """Simulated assessment when Vertex AI is not available."""
    patients = _load_patients()
    if patient_id not in patients:
        raise ValueError(f"Patient {patient_id} not found")

    patient = patients[patient_id]
    age = patient.get("age", 0)
    symptoms = [s.lower() for s in patient.get("symptoms", [])]
    smoking = patient.get("smoking_history", "").lower()
    duration = patient.get("symptom_duration_days", 0)

    risk_level = "no_criteria_met"
    urgency_color = "green"
    summary = "No urgent cancer risk criteria identified based on available data."
    reasoning: List[str] = []

    # NG12 1.1.1 — Suspected cancer pathway referral for lung cancer
    if "unexplained hemoptysis" in symptoms and age >= 40:
        risk_level = "suspected_cancer_pathway_referral"
        urgency_color = "red"
        summary = "Suspected cancer pathway referral (2WW) for lung cancer."
        reasoning.append(
            f"Patient aged {age} with unexplained haemoptysis meets NG12 1.1.1 "
            "criteria for suspected cancer pathway referral for lung cancer."
        )

    # NG12 1.1.2 — Urgent chest X-ray for lung cancer symptoms
    lung_symptoms = {"cough", "fatigue", "shortness of breath", "chest pain",
                     "weight loss", "appetite loss"}
    matching_lung = [s for s in symptoms if s in lung_symptoms or
                     any(s.startswith(ls) for ls in lung_symptoms)]
    if len(matching_lung) >= 2 and age >= 40 and "smok" in smoking:
        if risk_level not in ("suspected_cancer_pathway_referral",):
            risk_level = "urgent_investigation"
            urgency_color = "red"
            summary = "Urgent chest X-ray (within 2 weeks) to assess for lung cancer."
        reasoning.append(
            f"Patient aged {age}, {smoking}, with {len(matching_lung)} "
            f"unexplained symptoms ({', '.join(matching_lung)}) meets NG12 1.1.2 "
            "criteria for urgent chest X-ray."
        )

    # NG12 1.8 — Head and neck: persistent hoarseness
    if any("hoarseness" in s for s in symptoms) and duration >= 21:
        if urgency_color != "red":
            risk_level = "suspected_cancer_pathway_referral"
            urgency_color = "red"
            summary = "Suspected cancer pathway referral for laryngeal cancer."
        reasoning.append(
            f"Persistent hoarseness for {duration} days meets NG12 1.8 criteria "
            "for suspected cancer pathway referral for laryngeal cancer."
        )

    # NG12 1.4 — Breast lump
    if any("breast lump" in s for s in symptoms):
        if urgency_color != "red":
            risk_level = "suspected_cancer_pathway_referral"
            urgency_color = "red"
            summary = "Suspected cancer pathway referral for breast cancer."
        reasoning.append(
            "Unexplained breast lump meets NG12 1.4 criteria for suspected "
            "cancer pathway referral for breast cancer."
        )

    # NG12 1.6.1 — Visible haematuria
    if any("haematuria" in s for s in symptoms) and age >= 45:
        if urgency_color != "red":
            risk_level = "suspected_cancer_pathway_referral"
            urgency_color = "red"
            summary = "Suspected cancer pathway referral for bladder/renal cancer."
        reasoning.append(
            f"Patient aged {age} with visible haematuria meets NG12 1.6.1 "
            "criteria for suspected cancer pathway referral for urological cancer."
        )

    # NG12 1.2 — Dysphagia
    if any("dysphagia" in s for s in symptoms):
        if urgency_color != "red":
            risk_level = "suspected_cancer_pathway_referral"
            urgency_color = "red"
            summary = "Suspected cancer pathway referral for oesophageal/stomach cancer."
        reasoning.append(
            "Dysphagia meets NG12 1.2.1 criteria for suspected cancer pathway "
            "referral for oesophageal or stomach cancer."
        )

    # NG12 1.3 — Iron-deficiency anaemia in older patients
    if any("iron-deficiency" in s or "anaemia" in s for s in symptoms) and age >= 60:
        if urgency_color != "red":
            risk_level = "suspected_cancer_pathway_referral"
            urgency_color = "red"
            summary = "Suspected cancer pathway referral for colorectal cancer."
        reasoning.append(
            f"Patient aged {age} with iron-deficiency anaemia meets NG12 1.3 "
            "criteria for suspected cancer pathway referral for colorectal cancer."
        )

    # Smoking as general risk factor
    if "current" in smoking or "ex" in smoking:
        reasoning.append(
            f"Smoking history ({patient.get('smoking_history', 'unknown')}) noted "
            "— relevant modifier for lung, head & neck, and bladder cancer "
            "referral criteria (NG12 sections 1.1, 1.8, 1.6)."
        )

    # Age awareness
    if age >= 40 and not reasoning:
        reasoning.append(
            f"Patient aged {age} — many NG12 suspected cancer pathway "
            "thresholds apply from age 40+. No specific symptom criteria met."
        )

    if not reasoning:
        reasoning.append(
            "No specific NG12 risk factors identified from available data. "
            "Standard care with safety-netting advice (NG12 1.15.2)."
        )

    return RiskAssessmentResult(
        patient_id=patient_id,
        patient_name=patient.get("name", patient_id),
        assessment_date=datetime.now().isoformat(),
        risk_level=risk_level,
        urgency_color=urgency_color,
        summary=summary,
        reasoning=reasoning,
        citations=[
            {
                "source": "NG12 PDF",
                "section": "NG12 — Suspected cancer: recognition and referral",
                "page": 9,
                "chunk_id": "ng12_p9_c0",
                "excerpt": "Recommendations organised by site of cancer",
            },
            {
                "source": "NG12 PDF",
                "section": "NG12 1.15 — Safety netting",
                "page": 35,
                "chunk_id": "ng12_p35_c0",
                "excerpt": "Consider a review for people with any symptom associated with increased cancer risk",
            },
        ],
        disclaimer=(
            "MOCK MODE — Vertex AI is not configured. This simulated assessment "
            "must not be used for clinical decisions. Please set GCP_PROJECT_ID "
            "and authenticate to enable the full agent."
        ),
    )


@app.post("/assess", response_model=RiskAssessmentResult)
async def assess_patient(request: AssessRequest):
    """Accept a Patient ID, run the risk-assessment agent, return structured results."""
    pid = request.patient_id.strip()
    if not pid:
        raise HTTPException(status_code=400, detail="Patient ID cannot be empty")

    try:
        if _USE_REAL_AGENTS:
            return _assess_with_agent(pid)
        else:
            return _assess_mock(pid)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Assessment failed for {pid}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Assessment failed: {e}")


@app.get("/patients", response_model=List[PatientInfo])
async def list_patients():
    """Return all patient IDs for the UI dropdown."""
    patients = _load_patients()
    return [
        PatientInfo(
            patient_id=pid,
            name=p.get("name", "Unknown"),
            age=p.get("age"),
            gender=p.get("gender"),
        )
        for pid, p in patients.items()
    ]


# ---------------------------------------------------------------------------
# Part 2 — Conversational Chat
# ---------------------------------------------------------------------------

def _chat_with_agent(session_id: str, message: str, top_k: int) -> ChatResponse:
    """Route message through the real NG12 chat agent."""
    result = _chat_agent.chat(session_id, message, top_k)

    if result.get("error"):
        raise RuntimeError(result.get("message", "Chat agent returned an error"))

    return ChatResponse(
        session_id=session_id,
        answer=result["answer"],
        citations=result.get("citations", []),
        retrieved_passages_count=result.get("retrieved_passages_count", 0),
    )


def _chat_mock(session_id: str, message: str, _top_k: int) -> ChatResponse:
    """Simulated chat when Vertex AI is not available."""
    msg = message.lower()

    if "lung" in msg or "cough" in msg or "haemoptysis" in msg:
        answer = (
            "According to NG12 section 1.1, a suspected cancer pathway referral "
            "for lung cancer should be offered if the patient has chest X-ray "
            "findings suggestive of lung cancer, or is aged 40+ with unexplained "
            "haemoptysis. An urgent chest X-ray (within 2 weeks) should be offered "
            "for patients aged 40+ with 2 or more unexplained symptoms such as "
            "cough, fatigue, shortness of breath, chest pain, weight loss, or "
            "appetite loss [NG12 Rec 1.1.1-1.1.2, p.9]."
        )
        citations = [{"source": "NG12 PDF", "page": 9, "chunk_id": "ng12_p9_s1.1",
                       "excerpt": "Refer people using a suspected cancer pathway referral for lung cancer if they have chest X-ray findings that suggest lung cancer or are aged 40 and over with unexplained haemoptysis."}]
    elif "breast" in msg:
        answer = (
            "NG12 section 1.4 covers breast cancer. A suspected cancer pathway "
            "referral should be considered for people with an unexplained breast "
            "lump (with or without pain), or aged 30+ with an unexplained lump in "
            "the axilla [NG12 Rec 1.4, p.16]."
        )
        citations = [{"source": "NG12 PDF", "page": 16, "chunk_id": "ng12_p16_s1.4",
                       "excerpt": "Refer people using a suspected cancer pathway referral for breast cancer if they have an unexplained breast lump with or without pain."}]
    elif "colorectal" in msg or "bowel" in msg or "rectal" in msg:
        answer = (
            "NG12 section 1.3 addresses lower gastrointestinal tract cancers. "
            "Key criteria include: aged 40+ with unexplained weight loss AND "
            "abdominal pain, aged 50+ with unexplained rectal bleeding, or "
            "aged 60+ with iron-deficiency anaemia or changes in bowel habit "
            "[NG12 Rec 1.3.1-1.3.5, p.14-15]."
        )
        citations = [{"source": "NG12 PDF", "page": 14, "chunk_id": "ng12_p14_s1.3",
                       "excerpt": "Refer people using a suspected cancer pathway referral for colorectal cancer if aged 40 and over with unexplained weight loss and abdominal pain."}]
    elif "urgent" in msg or "referral" in msg or "pathway" in msg:
        answer = (
            "NG12 defines several urgency tiers: 'suspected cancer pathway referral' "
            "(2-week wait — aimed at diagnosis/rule-out within 28 days), "
            "'very urgent' (within 48 hours, e.g. acute leukaemia), "
            "'urgent' (investigation within 2 weeks), and 'non-urgent'. "
            "The guideline also covers 'safety netting' for patients whose symptoms "
            "don't meet referral thresholds but warrant review [NG12 p.83-84]."
        )
        citations = [{"source": "NG12 PDF", "page": 83, "chunk_id": "ng12_p83_terms",
                       "excerpt": "Suspected cancer pathway referral: referral arranged by the GP so that the patient will be seen within a maximum of 2 weeks."}]
    else:
        answer = (
            "NICE NG12 covers the recognition and referral of suspected cancer "
            "across 13 cancer site categories (lung, upper GI, lower GI, breast, "
            "gynaecological, urological, skin, head & neck, brain/CNS, haematological, "
            "sarcomas, childhood cancers) plus non-site-specific symptoms. "
            "Could you ask about a specific cancer type, symptom, or referral pathway?"
        )
        citations = [{"source": "NG12 PDF", "page": 6, "chunk_id": "ng12_p6_overview",
                       "excerpt": "This guideline covers identifying children, young people and adults with symptoms that could be caused by cancer."}]

    return ChatResponse(
        session_id=session_id,
        answer=f"[MOCK MODE] {answer}",
        citations=citations,
        retrieved_passages_count=len(citations),
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Multi-turn conversational endpoint over NG12 guidelines."""
    sid = request.session_id.strip()
    msg = request.message.strip()
    top_k = request.top_k or 5

    if not sid:
        raise HTTPException(status_code=400, detail="Session ID cannot be empty")
    if not msg:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # Track history
    if sid not in _chat_sessions:
        _chat_sessions[sid] = []
    _chat_sessions[sid].append(
        ChatHistoryEntry(role="user", message=msg, timestamp=datetime.now().isoformat())
    )

    try:
        if _USE_REAL_AGENTS:
            resp = _chat_with_agent(sid, msg, top_k)
        else:
            resp = _chat_mock(sid, msg, top_k)

        _chat_sessions[sid].append(
            ChatHistoryEntry(
                role="assistant",
                message=resp.answer,
                timestamp=datetime.now().isoformat(),
                citations=resp.citations,
            )
        )
        return resp

    except Exception as e:
        logger.error(f"Chat failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {e}")


@app.get("/chat/{session_id}/history")
async def get_chat_history(session_id: str):
    """Return conversation history for a session."""
    sid = session_id.strip()
    if sid not in _chat_sessions:
        raise HTTPException(status_code=404, detail=f"Session {sid} not found")
    return _chat_sessions[sid]


@app.delete("/chat/{session_id}")
async def clear_chat(session_id: str):
    """Clear conversation history for a session."""
    sid = session_id.strip()
    if sid not in _chat_sessions:
        raise HTTPException(status_code=404, detail=f"Session {sid} not found")
    del _chat_sessions[sid]
    return {"status": "success", "message": f"Session {sid} cleared"}


# ---------------------------------------------------------------------------
# UI + health
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the single-page frontend."""
    index = Path(__file__).parent.parent / "static" / "index.html"
    if not index.exists():
        raise HTTPException(status_code=500, detail="Frontend not found")
    return index.read_text(encoding="utf-8")


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "mode": "live" if _USE_REAL_AGENTS else "mock",
        "model": settings.MODEL_NAME,
        "version": "1.0.0",
    }


# Mount static assets
_static = Path(__file__).parent.parent / "static"
if _static.exists():
    app.mount("/static", StaticFiles(directory=str(_static)), name="static")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
