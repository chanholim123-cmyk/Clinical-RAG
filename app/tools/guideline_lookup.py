"""
Guideline vector store lookup module for NG12 Cancer Risk Assessor.

Provides RAG-based search over NICE NG12 clinical guidelines and tool
definitions for Vertex AI function calling.
"""

from typing import Any, Dict, List, Optional

try:
    from app.rag.vector_store import NG12VectorStore as VectorStore
except ImportError:
    VectorStore = None


class GuidelineSearchError(Exception):
    """Raised when guideline search fails."""
    pass


class GuidelineLookup:
    """Wrapper for vector store guideline search."""

    def __init__(self, vector_store: Optional[Any] = None):
        """
        Initialize guideline lookup.

        Args:
            vector_store: Optional VectorStore instance. If not provided,
                         will attempt to load from default location.

        Raises:
            GuidelineSearchError: If vector store cannot be initialized.
        """
        if vector_store is not None:
            self.vector_store = vector_store
        else:
            try:
                self.vector_store = VectorStore()
            except Exception as e:
                raise GuidelineSearchError(
                    f"Failed to initialize vector store: {str(e)}. "
                    "Ensure the vector store is properly configured and indexed."
                )

    def search_ng12_guidelines(
        self,
        query: str,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Search NICE NG12 clinical guidelines using vector similarity.

        Searches the vector store for guideline passages matching the clinical
        query. Returns structured results with passage text, source information,
        and confidence scores.

        Args:
            query: Clinical search query. Be specific - include symptom names,
                   cancer types, or referral pathway types.
                   Example: "unexplained hemoptysis lung cancer referral criteria"
            top_k: Number of guideline passages to retrieve (default 5, max 20)

        Returns:
            Dictionary with keys:
                - "results": List of matched passages, each with:
                    - "passage": Full text of the guideline passage
                    - "page": Page number in NG12 PDF
                    - "section": Section identifier (e.g., "1.1.1")
                    - "score": Similarity score (0-1, higher is better)
                - "total_results": Count of results returned
                - "query": The search query used
                - "error": (optional) Error message if search failed

        Example:
            >>> lookup = GuidelineLookup()
            >>> results = lookup.search_ng12_guidelines(
            ...     "persistent cough shortness of breath lung cancer referral aged 45",
            ...     top_k=3
            ... )
            >>> for r in results["results"]:
            ...     print(f"Page {r['page']}: {r['passage'][:100]}...")
        """
        if not self.vector_store:
            return {
                "error": True,
                "message": "Vector store not initialized",
                "results": [],
                "total_results": 0
            }

        try:
            # Perform vector search
            matches = self.vector_store.search(query, top_k=min(top_k, 20))

            if not matches:
                return {
                    "query": query,
                    "results": [],
                    "total_results": 0,
                    "message": "No matching passages found. Try different keywords."
                }

            # Format results with citation information
            formatted_results = []
            for match in matches:
                formatted_results.append({
                    "passage": match.get("text", ""),
                    "page": match.get("metadata", {}).get("page"),
                    "section": match.get("metadata", {}).get("section"),
                    "score": match.get("score", 0),
                    "recommendation_id": match.get("metadata", {}).get("recommendation_id")
                })

            return {
                "query": query,
                "results": formatted_results,
                "total_results": len(formatted_results),
                "error": False
            }

        except Exception as e:
            return {
                "query": query,
                "results": [],
                "total_results": 0,
                "error": True,
                "message": f"Error searching guidelines: {str(e)}"
            }


# Global instance for function calling
_guideline_lookup_instance: Optional[GuidelineLookup] = None


def _get_guideline_lookup() -> GuidelineLookup:
    """Get or create the global guideline lookup instance."""
    global _guideline_lookup_instance

    if _guideline_lookup_instance is None:
        try:
            _guideline_lookup_instance = GuidelineLookup()
        except GuidelineSearchError as e:
            raise e

    return _guideline_lookup_instance


def search_ng12_guidelines(
    query: str,
    top_k: int = 5
) -> Dict[str, Any]:
    """
    Module-level function for searching NG12 guidelines.

    This function is designed to be called by Vertex AI's function calling
    mechanism. It wraps the GuidelineLookup class method.

    Args:
        query: Clinical search query
        top_k: Number of results to retrieve (default 5)

    Returns:
        Dictionary with search results and metadata
    """
    try:
        lookup = _get_guideline_lookup()
        return lookup.search_ng12_guidelines(query, top_k)
    except GuidelineSearchError as e:
        return {
            "query": query,
            "results": [],
            "total_results": 0,
            "error": True,
            "message": str(e)
        }


# Function tool definitions for Vertex AI
GUIDELINE_TOOLS = [
    {
        "name": "search_ng12_guidelines",
        "description": "Searches the NICE NG12 'Suspected cancer: recognition and referral' clinical guidelines. Use this to find specific referral criteria, urgency levels, age thresholds, and symptom-based recommendations. Query with specific clinical terms for best results.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Clinical search query. Be specific - include symptom names, cancer types, or referral pathway types. Example: 'unexplained hemoptysis lung cancer referral criteria age threshold'"
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of guideline passages to retrieve (default 5)",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    }
]
