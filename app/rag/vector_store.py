"""
Vector Store Module for NG12 Cancer Risk Assessor

Provides a reusable RAG interface for querying the NICE NG12 guideline vector store.
"""

import logging
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)


class NG12VectorStore:
    """
    Interface for querying the NG12 cancer guideline vector store.

    This class provides methods to query the ChromaDB vector store containing
    NICE NG12 guidelines with rich metadata about sections, subsections,
    recommendations, and urgency levels.

    Attributes:
        persist_dir: Path to the ChromaDB persistent directory
        collection: ChromaDB collection containing NG12 guidelines
    """

    def __init__(self, persist_dir: str = "./data/vectorstore") -> None:
        """
        Initialize the vector store, loading from persistent storage.

        Args:
            persist_dir: Directory containing the ChromaDB vector store
                        (default: ./data/vectorstore)

        Raises:
            ValueError: If the vector store directory doesn't exist or is empty
            RuntimeError: If unable to connect to ChromaDB
        """
        self.persist_dir = Path(persist_dir)

        if not self.persist_dir.exists():
            raise ValueError(
                f"Vector store directory does not exist: {self.persist_dir}"
            )

        logger.info(f"Initializing NG12VectorStore from {self.persist_dir}")

        try:
            # Initialize ChromaDB with persistent storage
            settings = Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=str(self.persist_dir),
                anonymized_telemetry=False,
            )

            self.client = chromadb.Client(settings)

            # Get the collection (should exist from ingestion)
            self.collection = self.client.get_collection(
                name="ng12_cancer_guidelines"
            )

            count = self.collection.count()
            logger.info(f"Loaded vector store with {count} chunks")

            if count == 0:
                raise ValueError(
                    "Vector store is empty. Run ingest_pdf.py first."
                )

        except Exception as e:
            logger.error(f"Error initializing vector store: {e}")
            raise RuntimeError(f"Failed to initialize vector store: {e}")

    def query(
        self,
        query_text: str,
        top_k: int = 5
    ) -> list[dict]:
        """
        Query the vector store for relevant guideline chunks.

        Args:
            query_text: The query text (symptom, risk factor, clinical question, etc.)
            top_k: Number of top results to return (default: 5)

        Returns:
            List of result dictionaries, each containing:
                - text: The guideline chunk text
                - page: Page number in the original PDF
                - section: Main section (e.g., "1.1")
                - subsection: Subsection (e.g., "1.1.1")
                - recommendation_id: Recommendation identifier
                - chunk_id: Unique chunk identifier
                - urgency_level: Detected urgency level (if present)
                - relevance_score: Similarity score (higher = more relevant)

        Raises:
            ValueError: If query_text is empty
            RuntimeError: If query fails
        """
        if not query_text or not query_text.strip():
            raise ValueError("Query text cannot be empty")

        logger.debug(f"Querying vector store: {query_text[:100]}...")

        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=top_k,
                include=["embeddings", "documents", "metadatas", "distances"]
            )

            # Convert ChromaDB results to standardized format
            formatted_results = []

            if results and results["documents"] and len(results["documents"]) > 0:
                documents = results["documents"][0]
                metadatas = results["metadatas"][0]
                distances = results["distances"][0]

                for doc, metadata, distance in zip(documents, metadatas, distances):
                    # Convert distance to relevance score (closer = lower distance = higher score)
                    # For cosine distance, we normalize: score = 1 - distance
                    relevance_score = 1.0 - distance if distance is not None else 0.0
                    relevance_score = max(0.0, min(1.0, relevance_score))

                    result = {
                        "text": doc,
                        "page": int(metadata.get("page", 0)),
                        "section": metadata.get("section", "unknown"),
                        "subsection": metadata.get("subsection", "unknown"),
                        "recommendation_id": metadata.get("recommendation_id", "unknown"),
                        "chunk_id": metadata.get("chunk_id", "unknown"),
                        "urgency_level": metadata.get("urgency_level"),
                        "relevance_score": relevance_score,
                    }
                    formatted_results.append(result)

            logger.debug(f"Found {len(formatted_results)} results")
            return formatted_results

        except Exception as e:
            logger.error(f"Error querying vector store: {e}")
            raise RuntimeError(f"Query failed: {e}")

    def query_by_symptoms(
        self,
        symptoms: list[str],
        age: int,
        gender: str,
        top_k: int = 5
    ) -> list[dict]:
        """
        Query the vector store optimized for patient symptoms and context.

        This method builds a comprehensive query by combining:
        1. Individual symptom terms
        2. Patient demographics (age, gender)
        3. Common cancer risk factors

        This approach improves relevance by providing clinical context
        alongside specific symptoms.

        Args:
            symptoms: List of symptom strings (e.g., ["persistent cough", "chest pain"])
            age: Patient age in years
            gender: Patient gender ("M", "F", or "Other")
            top_k: Number of top results to return (default: 5)

        Returns:
            List of result dictionaries with the same format as query()

        Raises:
            ValueError: If symptoms list is empty or age is invalid
            RuntimeError: If query fails
        """
        if not symptoms or len(symptoms) == 0:
            raise ValueError("Symptoms list cannot be empty")

        if age < 0 or age > 150:
            raise ValueError(f"Invalid age: {age}")

        if gender not in ("M", "F", "Other"):
            raise ValueError(f"Invalid gender: {gender}")

        logger.debug(
            f"Querying with symptoms: {symptoms}, age: {age}, gender: {gender}"
        )

        # Build an optimized query combining symptoms and patient context
        query_components = []

        # Add individual symptoms
        query_components.extend(symptoms)

        # Add age-related context
        if age < 40:
            query_components.append("young patient")
        elif age < 60:
            query_components.append("middle-aged")
        else:
            query_components.append("older adult elderly")

        # Add gender-specific considerations
        if gender == "F":
            query_components.append("women female")
        elif gender == "M":
            query_components.append("men male")

        # Add common cancer risk factors that often appear in guidelines
        query_components.extend([
            "smoking history",
            "family history",
            "cancer risk factors",
            "referral pathway"
        ])

        # Build query string with symptoms prioritized
        # Format: primary symptoms + secondary context
        primary_query = " ".join(symptoms[:3])  # Main symptoms
        context_query = " ".join(query_components[len(symptoms):])  # Context

        # Combine with more weight on primary symptoms
        combined_query = f"{primary_query} {context_query}"

        logger.debug(f"Combined query: {combined_query[:150]}...")

        try:
            # Query the vector store
            results = self.query(combined_query, top_k=top_k)

            # Sort results by relevance score (higher is better)
            results.sort(key=lambda x: x["relevance_score"], reverse=True)

            logger.debug(f"Symptom-based query returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Error in symptom-based query: {e}")
            raise RuntimeError(f"Symptom-based query failed: {e}")

    def get_section_context(self, section: str) -> Optional[list[dict]]:
        """
        Retrieve all chunks from a specific guideline section.

        Args:
            section: Section identifier (e.g., "1.1", "1.2")

        Returns:
            List of all chunks in that section, or None if section not found

        Raises:
            RuntimeError: If query fails
        """
        if not section:
            raise ValueError("Section identifier cannot be empty")

        logger.debug(f"Retrieving context for section: {section}")

        try:
            # Query by the section identifier
            results = self.collection.get(
                where={"section": {"$eq": section}},
                include=["documents", "metadatas", "distances"]
            )

            if not results or not results["documents"]:
                logger.debug(f"No chunks found for section: {section}")
                return None

            # Format results
            formatted_results = []
            documents = results["documents"]
            metadatas = results["metadatas"]

            for doc, metadata in zip(documents, metadatas):
                result = {
                    "text": doc,
                    "page": int(metadata.get("page", 0)),
                    "section": metadata.get("section", "unknown"),
                    "subsection": metadata.get("subsection", "unknown"),
                    "recommendation_id": metadata.get("recommendation_id", "unknown"),
                    "chunk_id": metadata.get("chunk_id", "unknown"),
                    "urgency_level": metadata.get("urgency_level"),
                }
                formatted_results.append(result)

            logger.debug(f"Retrieved {len(formatted_results)} chunks for section {section}")
            return formatted_results

        except Exception as e:
            logger.error(f"Error retrieving section context: {e}")
            raise RuntimeError(f"Failed to retrieve section context: {e}")

    def get_urgent_recommendations(self, top_k: int = 10) -> list[dict]:
        """
        Retrieve all recommendations marked as urgent or very urgent.

        Args:
            top_k: Maximum number of results to return (default: 10)

        Returns:
            List of urgent/very urgent recommendations

        Raises:
            RuntimeError: If query fails
        """
        logger.debug("Retrieving urgent recommendations...")

        try:
            # Query for urgent recommendations
            results = self.collection.get(
                where={
                    "$or": [
                        {"urgency_level": {"$eq": "urgent"}},
                        {"urgency_level": {"$eq": "very_urgent"}},
                        {"urgency_level": {"$eq": "suspected_cancer"}}
                    ]
                },
                limit=top_k,
                include=["documents", "metadatas"]
            )

            if not results or not results["documents"]:
                logger.debug("No urgent recommendations found")
                return []

            # Format results
            formatted_results = []
            documents = results["documents"]
            metadatas = results["metadatas"]

            for doc, metadata in zip(documents, metadatas):
                result = {
                    "text": doc,
                    "page": int(metadata.get("page", 0)),
                    "section": metadata.get("section", "unknown"),
                    "subsection": metadata.get("subsection", "unknown"),
                    "recommendation_id": metadata.get("recommendation_id", "unknown"),
                    "chunk_id": metadata.get("chunk_id", "unknown"),
                    "urgency_level": metadata.get("urgency_level"),
                }
                formatted_results.append(result)

            logger.debug(f"Retrieved {len(formatted_results)} urgent recommendations")
            return formatted_results

        except Exception as e:
            logger.error(f"Error retrieving urgent recommendations: {e}")
            raise RuntimeError(f"Failed to retrieve urgent recommendations: {e}")

    def get_statistics(self) -> dict:
        """
        Get statistics about the vector store.

        Returns:
            Dictionary containing:
                - total_chunks: Total number of chunks in the store
                - sections: List of unique section identifiers
                - subsections: List of unique subsection identifiers
                - has_urgency_metadata: Whether urgency levels are available
        """
        try:
            count = self.collection.count()

            # Try to get unique sections and subsections
            all_results = self.collection.get(
                include=["metadatas"]
            )

            sections = set()
            subsections = set()
            has_urgency = False

            if all_results and all_results["metadatas"]:
                for metadata in all_results["metadatas"]:
                    section = metadata.get("section")
                    if section and section != "unknown":
                        sections.add(section)

                    subsection = metadata.get("subsection")
                    if subsection and subsection != "unknown":
                        subsections.add(subsection)

                    if metadata.get("urgency_level"):
                        has_urgency = True

            return {
                "total_chunks": count,
                "sections": sorted(list(sections)),
                "subsections": sorted(list(subsections)),
                "has_urgency_metadata": has_urgency,
            }

        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            raise RuntimeError(f"Failed to get statistics: {e}")
