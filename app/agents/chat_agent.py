"""
NG12 Guidelines Chat Agent (Part 2).

This module implements a conversational agent that allows users to ask
questions about NICE NG12 guidelines, with RAG-powered responses backed
by the guideline vector store and conversation history management.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

try:
    import vertexai
    from vertexai.generative_models import (
        GenerativeModel,
        Tool,
        FunctionDeclaration,
    )
except ImportError as e:
    raise ImportError(
        "vertexai package is required. Install with: pip install google-cloud-aiplatform"
    ) from e

from app.tools.guideline_lookup import (
    search_ng12_guidelines,
    GUIDELINE_TOOLS
)

logger = logging.getLogger(__name__)

# System prompt for the chat agent
CHAT_SYSTEM_PROMPT = """You are an NG12 Clinical Guidelines Expert. You answer questions about the NICE NG12 guideline "Suspected cancer: recognition and referral" using ONLY the content retrieved from the guideline document.

## Core Rules
1. ALWAYS search the guidelines before answering using `search_ng12_guidelines`.
2. Base your answer EXCLUSIVELY on retrieved passages. Never rely on general medical knowledge.
3. CITE every clinical statement with [Section X.X.X, p.XX].
4. If retrieval returns no relevant passages, say: "I could not find specific guidance on this in the NG12 document. Please verify with the full guideline or a clinical specialist."
5. If the retrieved text is ambiguous or partially relevant, qualify your answer: "Based on the available passages, NG12 appears to suggest... however, the full context may differ."

## Response Style
- Use clear, professional clinical language
- Structure longer answers with the referral pathway hierarchy: suspected cancer pathway referral > very urgent > urgent > non-urgent > consider/safety netting
- When listing criteria, preserve the exact conditional logic (AND/OR, age thresholds, symptom combinations)
- For multi-turn follow-ups, reference previous context naturally

## Citation Format
When citing guideline recommendations, use: [NG12 Rec X.X.X, p.XX]
When citing general guideline text, use: [NG12 p.XX]
Always include a brief excerpt from the source passage.

## What You Cannot Do
- Diagnose patients or provide personalized medical advice
- Recommend treatments beyond the scope of NG12 (which covers recognition and referral only)
- Answer questions about guidelines other than NG12
"""


class ConversationMessage:
    """Represents a single message in the conversation history."""

    def __init__(self, role: str, content: str, timestamp: Optional[str] = None):
        """
        Initialize a conversation message.

        Args:
            role: "user" or "assistant"
            content: Message text
            timestamp: ISO format timestamp (auto-generated if not provided)
        """
        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, str]:
        """Convert message to dictionary."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp
        }

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "ConversationMessage":
        """Create message from dictionary."""
        return cls(
            role=data.get("role", "user"),
            content=data.get("content", ""),
            timestamp=data.get("timestamp")
        )


class NG12ChatAgent:
    """
    Conversational agent for NG12 guideline Q&A.

    This agent manages multi-turn conversations about NICE NG12 guidelines,
    using RAG retrieval to ground responses in guideline content and
    maintaining conversation history per session.
    """

    def __init__(self, project_id: Optional[str] = None, location: str = "us-central1"):
        """
        Initialize the NG12 Chat Agent.

        Args:
            project_id: GCP project ID. If not provided, uses default from
                       environment (GOOGLE_CLOUD_PROJECT).
            location: GCP region (default: us-central1)

        Raises:
            ValueError: If vertexai cannot be initialized
        """
        self.project_id = project_id
        self.location = location

        # Initialize Vertex AI
        try:
            if project_id:
                vertexai.init(project=project_id, location=location)
        except Exception as e:
            logger.warning(f"Could not initialize vertexai: {e}")

        # Initialize the model with function calling
        self.model = GenerativeModel(
            model_name="gemini-1.5-pro",
            system_instruction=CHAT_SYSTEM_PROMPT
        )

        # Prepare tools (guideline lookup only)
        self.tools = self._prepare_tools()

        # Session-based conversation history
        self.sessions: Dict[str, List[ConversationMessage]] = {}

    def _prepare_tools(self) -> List[Tool]:
        """
        Prepare Vertex AI Tool objects from guideline tool definitions.

        Returns:
            List of Tool objects configured for function calling
        """
        tools = []

        for tool_def in GUIDELINE_TOOLS:
            func_decl = FunctionDeclaration(
                name=tool_def["name"],
                description=tool_def["description"],
                parameters=tool_def["parameters"]
            )
            tools.append(Tool(function_declarations=[func_decl]))

        return tools

    def _execute_function(self, function_name: str, function_args: Dict[str, Any]) -> Any:
        """
        Execute a function by name with the given arguments.

        Args:
            function_name: Name of the function to execute
            function_args: Dictionary of function arguments

        Returns:
            Function result

        Raises:
            ValueError: If function is not recognized
        """
        if function_name == "search_ng12_guidelines":
            return search_ng12_guidelines(
                query=function_args.get("query", ""),
                top_k=function_args.get("top_k", 5)
            )

        else:
            raise ValueError(f"Unknown function: {function_name}")

    def chat(
        self,
        session_id: str,
        message: str,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Process a user message and return an AI response.

        This method manages conversation history, handles function calling
        for RAG retrieval, and returns a response with citations.

        Args:
            session_id: Unique session identifier for conversation tracking
            message: User's question or message
            top_k: Number of guideline passages to retrieve per search (default 5)

        Returns:
            Dictionary with keys:
                - session_id: The session ID
                - answer: The AI's response text
                - citations: List of cited guideline passages
                - retrieved_passages_count: Total passages retrieved
                - timestamp: ISO format timestamp
                - error: (optional) Error message if chat failed

        Example:
            >>> agent = NG12ChatAgent(project_id="my-project")
            >>> result = agent.chat("session-123", "What are the referral criteria for lung cancer?")
            >>> print(result['answer'])
            >>> for cite in result['citations']:
            ...     print(f"[{cite['section']}] {cite['excerpt']}")
        """
        try:
            # Initialize session history if needed
            if session_id not in self.sessions:
                self.sessions[session_id] = []

            # Add user message to history
            user_msg = ConversationMessage(role="user", content=message)
            self.sessions[session_id].append(user_msg)

            # Build conversation for model
            conversation = [msg.to_dict() for msg in self.sessions[session_id]]

            # Send to model with tools
            response = self.model.generate_content(
                conversation,
                tools=self.tools,
                stream=False
            )

            # Function calling loop
            max_iterations = 5
            iteration = 0
            all_retrieved_passages = []

            while iteration < max_iterations:
                iteration += 1
                logger.debug(f"Chat iteration {iteration}")

                # Check for function calls
                function_calls = []
                for part in response.candidates[0].content.parts:
                    if hasattr(part, "function_call"):
                        function_calls.append(part.function_call)

                if not function_calls:
                    # No more function calls
                    break

                # Execute functions and collect results
                function_results = []
                for fc in function_calls:
                    logger.debug(f"Executing function: {fc.name}")
                    try:
                        result = self._execute_function(
                            fc.name,
                            dict(fc.args)
                        )

                        # Track retrieved passages for citations
                        if fc.name == "search_ng12_guidelines":
                            if isinstance(result, dict) and "results" in result:
                                all_retrieved_passages.extend(result["results"])

                        function_results.append({
                            "name": fc.name,
                            "result": result
                        })
                    except Exception as e:
                        logger.error(f"Error executing function {fc.name}: {e}")
                        function_results.append({
                            "name": fc.name,
                            "error": str(e)
                        })

                # Send function results back to model
                response = self.model.generate_content(
                    conversation + [
                        {
                            "role": "assistant",
                            "content": response.candidates[0].content
                        },
                        {
                            "role": "user",
                            "parts": [
                                {
                                    "function_response": {
                                        "name": fr["name"],
                                        "response": fr.get("result", {"error": fr.get("error")})
                                    }
                                }
                                for fr in function_results
                            ]
                        }
                    ],
                    tools=self.tools,
                    stream=False
                )

            # Extract final response text
            answer_text = ""
            for part in response.candidates[0].content.parts:
                if hasattr(part, "text"):
                    answer_text += part.text

            # Add assistant response to history
            assistant_msg = ConversationMessage(role="assistant", content=answer_text)
            self.sessions[session_id].append(assistant_msg)

            # Format citations from retrieved passages
            citations = self._format_citations(all_retrieved_passages)

            return {
                "session_id": session_id,
                "answer": answer_text,
                "citations": citations,
                "retrieved_passages_count": len(all_retrieved_passages),
                "timestamp": datetime.utcnow().isoformat(),
                "error": False
            }

        except Exception as e:
            logger.error(f"Chat failed: {e}", exc_info=True)
            return {
                "session_id": session_id,
                "answer": "",
                "citations": [],
                "retrieved_passages_count": 0,
                "error": True,
                "message": f"Chat failed: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }

    @staticmethod
    def _format_citations(passages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Format retrieved passages into citation objects.

        Args:
            passages: List of passage dicts from search results

        Returns:
            List of formatted citation dicts
        """
        citations = []
        seen = set()  # Deduplicate by passage content

        for passage in passages:
            # Create unique key for deduplication
            key = (passage.get("page"), passage.get("section"))

            if key in seen:
                continue

            seen.add(key)

            citation = {
                "source": "NG12",
                "page": passage.get("page"),
                "section": passage.get("section"),
                "recommendation_id": passage.get("recommendation_id"),
                "excerpt": passage.get("passage", "")[:200],  # Truncate for display
                "score": passage.get("score")
            }
            citations.append(citation)

        return citations

    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        """
        Retrieve conversation history for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of message dicts with role, content, and timestamp

        Example:
            >>> history = agent.get_history("session-123")
            >>> for msg in history:
            ...     print(f"{msg['role']}: {msg['content'][:50]}...")
        """
        if session_id not in self.sessions:
            return []

        return [msg.to_dict() for msg in self.sessions[session_id]]

    def clear_session(self, session_id: str) -> bool:
        """
        Clear conversation history for a session.

        Args:
            session_id: Session identifier

        Returns:
            True if session existed and was cleared, False otherwise

        Example:
            >>> success = agent.clear_session("session-123")
            >>> if success:
            ...     print("Session history cleared")
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Cleared session: {session_id}")
            return True

        logger.warning(f"Session not found: {session_id}")
        return False
