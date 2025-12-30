"""
EmbeddingService - Creates vector embeddings using OpenAI.
Part of SHEBA (Observer) system.
"""

import os
from typing import List, Optional
from openai import OpenAI


class EmbeddingService:
    """
    Service for creating text embeddings using OpenAI's embedding models.

    Uses text-embedding-3-small by default (1536 dimensions).
    Can switch to text-embedding-3-large (3072 dimensions) for better quality.
    """

    def __init__(
        self,
        model: str = "text-embedding-3-large",
        api_key: Optional[str] = None
    ):
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required")

        self.client = OpenAI(api_key=self.api_key)

        # Embedding dimensions by model
        self.dimensions = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }

    @property
    def embedding_dimension(self) -> int:
        """Get the embedding dimension for the current model."""
        return self.dimensions.get(self.model, 1536)

    def embed_text(self, text: str) -> List[float]:
        """
        Create embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        response = self.client.embeddings.create(
            model=self.model,
            input=text
        )
        return response.data[0].embedding

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Create embeddings for multiple texts in batch.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        # OpenAI API supports batch embedding
        response = self.client.embeddings.create(
            model=self.model,
            input=texts
        )

        # Sort by index to maintain order
        embeddings = sorted(response.data, key=lambda x: x.index)
        return [e.embedding for e in embeddings]

    def embed_event(self, event: dict) -> List[float]:
        """
        Create embedding for a historical event.
        Combines title, description, and metadata for richer context.

        Args:
            event: Event dictionary with title, description, etc.

        Returns:
            Embedding vector
        """
        # Build rich text representation
        parts = []

        if event.get("title"):
            parts.append(f"제목: {event['title']}")

        if event.get("description"):
            parts.append(f"설명: {event['description']}")

        if event.get("date_start"):
            year = event["date_start"]
            era = "BCE" if year < 0 else "CE"
            parts.append(f"시기: {abs(year)} {era}")

        if event.get("category"):
            cat = event["category"]
            if isinstance(cat, dict):
                cat = cat.get("name", cat.get("slug", ""))
            parts.append(f"분류: {cat}")

        if event.get("location"):
            loc = event["location"]
            if isinstance(loc, dict):
                loc = loc.get("name", "")
            parts.append(f"장소: {loc}")

        text = "\n".join(parts)
        return self.embed_text(text)

    def embed_query(self, query: str) -> List[float]:
        """
        Create embedding for a search query.

        Args:
            query: User's search query

        Returns:
            Embedding vector
        """
        return self.embed_text(query)
