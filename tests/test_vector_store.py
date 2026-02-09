"""
Unit tests for NG12VectorStore

Tests the vector store query interface and data retrieval methods.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from app.rag.vector_store import NG12VectorStore


class TestNG12VectorStoreInitialization:
    """Test vector store initialization and configuration."""

    def test_init_missing_directory(self):
        """Test that initialization fails with non-existent directory."""
        with pytest.raises(ValueError, match="Vector store directory does not exist"):
            NG12VectorStore(persist_dir="/nonexistent/path")

    @patch('chromadb.Client')
    def test_init_empty_store(self, mock_client):
        """Test that initialization fails with empty vector store."""
        # Setup mock collection with count=0
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0

        mock_client_instance = MagicMock()
        mock_client_instance.get_collection.return_value = mock_collection
        mock_client.return_value = mock_client_instance

        # Create temporary directory
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError, match="Vector store is empty"):
                NG12VectorStore(persist_dir=tmpdir)

    @patch('chromadb.Client')
    def test_init_success(self, mock_client):
        """Test successful initialization with valid store."""
        # Setup mock collection with data
        mock_collection = MagicMock()
        mock_collection.count.return_value = 100

        mock_client_instance = MagicMock()
        mock_client_instance.get_collection.return_value = mock_collection
        mock_client.return_value = mock_client_instance

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            vs = NG12VectorStore(persist_dir=tmpdir)
            assert vs.collection is not None
            assert vs.persist_dir == Path(tmpdir)


class TestNG12VectorStoreQuery:
    """Test semantic query functionality."""

    @patch('chromadb.Client')
    def test_query_empty_text(self, mock_client):
        """Test that empty query text raises ValueError."""
        mock_collection = MagicMock()
        mock_collection.count.return_value = 100
        mock_client_instance = MagicMock()
        mock_client_instance.get_collection.return_value = mock_collection
        mock_client.return_value = mock_client_instance

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            vs = NG12VectorStore(persist_dir=tmpdir)

            with pytest.raises(ValueError, match="Query text cannot be empty"):
                vs.query("")

            with pytest.raises(ValueError, match="Query text cannot be empty"):
                vs.query("   ")

    @patch('chromadb.Client')
    def test_query_success(self, mock_client):
        """Test successful semantic query."""
        mock_collection = MagicMock()
        mock_collection.count.return_value = 100

        # Mock query results
        mock_collection.query.return_value = {
            "documents": [[
                "1.1.1 Lung cancer recommendation text...",
                "1.2.1 Mesothelioma recommendation text...",
            ]],
            "metadatas": [[
                {
                    "page": "5",
                    "section": "1.1",
                    "subsection": "1.1.1",
                    "recommendation_id": "1.1.1",
                    "chunk_id": "ng12_p5_c0",
                    "urgency_level": "urgent"
                },
                {
                    "page": "8",
                    "section": "1.2",
                    "subsection": "1.2.1",
                    "recommendation_id": "1.2.1",
                    "chunk_id": "ng12_p8_c0",
                }
            ]],
            "distances": [[0.2, 0.4]]
        }

        mock_client_instance = MagicMock()
        mock_client_instance.get_collection.return_value = mock_collection
        mock_client.return_value = mock_client_instance

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            vs = NG12VectorStore(persist_dir=tmpdir)
            results = vs.query("persistent cough", top_k=5)

            assert len(results) == 2
            assert results[0]["text"] == "1.1.1 Lung cancer recommendation text..."
            assert results[0]["page"] == 5
            assert results[0]["section"] == "1.1"
            assert results[0]["urgency_level"] == "urgent"
            assert 0.0 <= results[0]["relevance_score"] <= 1.0

            # Second result should not have urgency_level
            assert results[1].get("urgency_level") is None

    @patch('chromadb.Client')
    def test_query_no_results(self, mock_client):
        """Test query with no results."""
        mock_collection = MagicMock()
        mock_collection.count.return_value = 100
        mock_collection.query.return_value = {
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]]
        }

        mock_client_instance = MagicMock()
        mock_client_instance.get_collection.return_value = mock_collection
        mock_client.return_value = mock_client_instance

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            vs = NG12VectorStore(persist_dir=tmpdir)
            results = vs.query("obscure medical term xyz")

            assert results == []


class TestNG12VectorStoreSymptomQuery:
    """Test symptom-based query functionality."""

    @patch('chromadb.Client')
    def test_symptom_query_invalid_input(self, mock_client):
        """Test symptom query with invalid inputs."""
        mock_collection = MagicMock()
        mock_collection.count.return_value = 100
        mock_client_instance = MagicMock()
        mock_client_instance.get_collection.return_value = mock_collection
        mock_client.return_value = mock_client_instance

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            vs = NG12VectorStore(persist_dir=tmpdir)

            # Empty symptoms
            with pytest.raises(ValueError, match="Symptoms list cannot be empty"):
                vs.query_by_symptoms([], age=50, gender="M")

            # Invalid age
            with pytest.raises(ValueError, match="Invalid age"):
                vs.query_by_symptoms(["cough"], age=-1, gender="M")

            with pytest.raises(ValueError, match="Invalid age"):
                vs.query_by_symptoms(["cough"], age=200, gender="M")

            # Invalid gender
            with pytest.raises(ValueError, match="Invalid gender"):
                vs.query_by_symptoms(["cough"], age=50, gender="X")

    @patch.object(NG12VectorStore, 'query')
    @patch('chromadb.Client')
    def test_symptom_query_success(self, mock_client, mock_query):
        """Test successful symptom-based query."""
        mock_collection = MagicMock()
        mock_collection.count.return_value = 100
        mock_client_instance = MagicMock()
        mock_client_instance.get_collection.return_value = mock_collection
        mock_client.return_value = mock_client_instance

        # Mock the underlying query method
        mock_results = [
            {
                "text": "Lung cancer recommendation",
                "page": 5,
                "section": "1.1",
                "subsection": "1.1.1",
                "recommendation_id": "1.1.1",
                "chunk_id": "ng12_p5_c0",
                "urgency_level": "urgent",
                "relevance_score": 0.95
            }
        ]
        mock_query.return_value = mock_results

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            vs = NG12VectorStore(persist_dir=tmpdir)
            results = vs.query_by_symptoms(
                symptoms=["persistent cough", "weight loss"],
                age=65,
                gender="M",
                top_k=5
            )

            assert len(results) == 1
            assert results[0]["urgency_level"] == "urgent"

            # Verify query was called with combined terms
            mock_query.assert_called_once()
            call_args = mock_query.call_args
            assert "cough" in call_args[0][0].lower()
            assert "weight loss" in call_args[0][0].lower()


class TestNG12VectorStoreSectionContext:
    """Test section context retrieval."""

    @patch('chromadb.Client')
    def test_section_context_invalid_input(self, mock_client):
        """Test section context with invalid input."""
        mock_collection = MagicMock()
        mock_collection.count.return_value = 100
        mock_client_instance = MagicMock()
        mock_client_instance.get_collection.return_value = mock_collection
        mock_client.return_value = mock_client_instance

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            vs = NG12VectorStore(persist_dir=tmpdir)

            with pytest.raises(ValueError, match="Section identifier cannot be empty"):
                vs.get_section_context("")

    @patch('chromadb.Client')
    def test_section_context_success(self, mock_client):
        """Test successful section context retrieval."""
        mock_collection = MagicMock()
        mock_collection.count.return_value = 100
        mock_collection.get.return_value = {
            "documents": [
                "1.1.1 Recommendation 1",
                "1.1.2 Recommendation 2",
            ],
            "metadatas": [
                {
                    "page": "5",
                    "section": "1.1",
                    "subsection": "1.1.1",
                    "recommendation_id": "1.1.1",
                    "chunk_id": "ng12_p5_c0",
                },
                {
                    "page": "6",
                    "section": "1.1",
                    "subsection": "1.1.2",
                    "recommendation_id": "1.1.2",
                    "chunk_id": "ng12_p6_c0",
                }
            ]
        }

        mock_client_instance = MagicMock()
        mock_client_instance.get_collection.return_value = mock_collection
        mock_client.return_value = mock_client_instance

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            vs = NG12VectorStore(persist_dir=tmpdir)
            results = vs.get_section_context("1.1")

            assert results is not None
            assert len(results) == 2
            assert results[0]["recommendation_id"] == "1.1.1"
            assert results[1]["recommendation_id"] == "1.1.2"

    @patch('chromadb.Client')
    def test_section_context_not_found(self, mock_client):
        """Test section context when section not found."""
        mock_collection = MagicMock()
        mock_collection.count.return_value = 100
        mock_collection.get.return_value = {
            "documents": [],
            "metadatas": []
        }

        mock_client_instance = MagicMock()
        mock_client_instance.get_collection.return_value = mock_collection
        mock_client.return_value = mock_client_instance

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            vs = NG12VectorStore(persist_dir=tmpdir)
            results = vs.get_section_context("9.9")

            assert results is None


class TestNG12VectorStoreUrgent:
    """Test urgent recommendations retrieval."""

    @patch('chromadb.Client')
    def test_urgent_recommendations(self, mock_client):
        """Test retrieving urgent recommendations."""
        mock_collection = MagicMock()
        mock_collection.count.return_value = 100
        mock_collection.get.return_value = {
            "documents": [
                "1.1.1 Urgent recommendation 1",
                "1.2.1 Very urgent recommendation 2",
            ],
            "metadatas": [
                {
                    "page": "5",
                    "section": "1.1",
                    "subsection": "1.1.1",
                    "recommendation_id": "1.1.1",
                    "chunk_id": "ng12_p5_c0",
                    "urgency_level": "urgent"
                },
                {
                    "page": "8",
                    "section": "1.2",
                    "subsection": "1.2.1",
                    "recommendation_id": "1.2.1",
                    "chunk_id": "ng12_p8_c0",
                    "urgency_level": "very_urgent"
                }
            ]
        }

        mock_client_instance = MagicMock()
        mock_client_instance.get_collection.return_value = mock_collection
        mock_client.return_value = mock_client_instance

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            vs = NG12VectorStore(persist_dir=tmpdir)
            results = vs.get_urgent_recommendations(top_k=10)

            assert len(results) == 2
            assert results[0]["urgency_level"] == "urgent"
            assert results[1]["urgency_level"] == "very_urgent"


class TestNG12VectorStoreStatistics:
    """Test statistics retrieval."""

    @patch('chromadb.Client')
    def test_statistics(self, mock_client):
        """Test getting vector store statistics."""
        mock_collection = MagicMock()
        mock_collection.count.return_value = 150
        mock_collection.get.return_value = {
            "metadatas": [
                {
                    "section": "1.1",
                    "subsection": "1.1.1",
                    "urgency_level": "urgent"
                },
                {
                    "section": "1.1",
                    "subsection": "1.1.2",
                    "urgency_level": "urgent"
                },
                {
                    "section": "1.2",
                    "subsection": "1.2.1",
                }
            ]
        }

        mock_client_instance = MagicMock()
        mock_client_instance.get_collection.return_value = mock_collection
        mock_client.return_value = mock_client_instance

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            vs = NG12VectorStore(persist_dir=tmpdir)
            stats = vs.get_statistics()

            assert stats["total_chunks"] == 150
            assert "1.1" in stats["sections"]
            assert "1.2" in stats["sections"]
            assert "1.1.1" in stats["subsections"]
            assert stats["has_urgency_metadata"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
