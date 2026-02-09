"""
Patient data retrieval module for NG12 Cancer Risk Assessor.

Provides functions to retrieve patient records from the patients.json dataset
and tool definitions for Vertex AI function calling.
"""

import json
import os
from typing import Any, Dict, List, Optional

# Load patients at module level
PATIENTS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "patients.json"
)

_PATIENTS_CACHE: Optional[Dict[str, Any]] = None


def _load_patients() -> Dict[str, Any]:
    """Load patients from JSON file."""
    global _PATIENTS_CACHE

    if _PATIENTS_CACHE is not None:
        return _PATIENTS_CACHE

    try:
        with open(PATIENTS_FILE, 'r') as f:
            _PATIENTS_CACHE = json.load(f)
        return _PATIENTS_CACHE
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Patients file not found at {PATIENTS_FILE}. "
            "Please ensure app/data/patients.json exists."
        )
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in patients file: {e}")


def get_patient_record(patient_id: str) -> Dict[str, Any]:
    """
    Retrieve the complete medical record for a patient.

    Args:
        patient_id: The unique patient identifier (e.g., "PT-101")

    Returns:
        Dictionary containing patient demographics, smoking history,
        current symptoms, and symptom duration. If patient not found,
        returns error dict with 'error' and 'message' keys.

    Example:
        >>> record = get_patient_record("PT-101")
        >>> print(record['name'], record['age'])
    """
    try:
        patients = _load_patients()

        if patient_id not in patients:
            return {
                "error": True,
                "message": f"Patient {patient_id} not found in database",
                "available_ids": list_patient_ids()
            }

        return patients[patient_id]

    except Exception as e:
        return {
            "error": True,
            "message": f"Error retrieving patient record: {str(e)}"
        }


def list_patient_ids() -> List[str]:
    """
    Retrieve all available patient IDs.

    Returns:
        List of all patient IDs in the database, sorted alphabetically.

    Example:
        >>> ids = list_patient_ids()
        >>> print(f"Available patients: {', '.join(ids)}")
    """
    try:
        patients = _load_patients()
        return sorted(patients.keys())
    except Exception as e:
        return []


# Function tool definitions for Vertex AI
PATIENT_TOOLS = [
    {
        "name": "get_patient_record",
        "description": "Retrieves the complete medical record for a patient given their Patient ID. Returns demographics (age, gender), smoking history, current symptoms, and symptom duration.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {
                    "type": "string",
                    "description": "The unique patient identifier (e.g., PT-101)"
                }
            },
            "required": ["patient_id"]
        }
    }
]
