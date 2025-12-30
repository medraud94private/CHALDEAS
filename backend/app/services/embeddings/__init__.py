"""
Embedding services for SHEBA (Observer) system.
Handles vector embeddings for semantic search.
"""

from .embedding_service import EmbeddingService
from .vector_store import VectorStore

__all__ = ["EmbeddingService", "VectorStore"]
