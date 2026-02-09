import os

class Settings:
    PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "your-project-id")
    LOCATION: str = os.getenv("GCP_LOCATION", "us-central1")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "gemini-1.5-pro")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "textembedding-gecko@003")
    VECTORSTORE_PATH: str = os.getenv("VECTORSTORE_PATH", "./data/vectorstore")
    PDF_PATH: str = os.getenv("PDF_PATH", "./data/ng12.pdf")
    PATIENTS_PATH: str = os.getenv("PATIENTS_PATH", "./patients.json")

settings = Settings()
