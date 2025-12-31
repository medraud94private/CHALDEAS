"""
VectorStore - pgvector-based vector storage and retrieval.
Part of SHEBA (Observer) system.
"""

import os
from typing import List, Optional, Tuple, Any
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import execute_values, RealDictCursor
from pgvector.psycopg2 import register_vector


class VectorStore:
    """
    Vector storage using PostgreSQL with pgvector extension.

    Handles:
    - Storing embeddings with metadata
    - Semantic similarity search
    - Hybrid search (vector + keyword)
    """

    def __init__(
        self,
        connection_string: Optional[str] = None,
        embedding_dimension: int = 1536  # text-embedding-3-small
    ):
        self.connection_string = connection_string or os.getenv("DATABASE_URL")
        self.embedding_dimension = embedding_dimension

        if not self.connection_string:
            raise ValueError("DATABASE_URL is required")

    @contextmanager
    def get_connection(self):
        """Get a database connection with pgvector registered."""
        conn = psycopg2.connect(self.connection_string)
        register_vector(conn)
        try:
            yield conn
        finally:
            conn.close()

    def initialize(self):
        """
        Initialize the database with pgvector extension and tables.
        Should be called once during setup.
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Enable pgvector extension
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")

                # Create embeddings table
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS embeddings (
                        id SERIAL PRIMARY KEY,
                        content_type VARCHAR(50) NOT NULL,
                        content_id INTEGER NOT NULL,
                        content_text TEXT,
                        embedding vector({self.embedding_dimension}),
                        metadata JSONB DEFAULT '{{}}',
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        UNIQUE(content_type, content_id)
                    )
                """)

                # Skip vector index for high-dimensional embeddings (>2000)
                # For datasets under 100k rows, brute force search is fast enough
                # For larger datasets, consider using text-embedding-3-small (1536 dim)
                if self.embedding_dimension <= 2000:
                    cur.execute(f"""
                        CREATE INDEX IF NOT EXISTS embeddings_vector_idx
                        ON embeddings
                        USING ivfflat (embedding vector_cosine_ops)
                        WITH (lists = 100)
                    """)

                # Create index for content lookup
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS embeddings_content_idx
                    ON embeddings (content_type, content_id)
                """)

                conn.commit()

    def upsert_embedding(
        self,
        content_type: str,
        content_id: int,
        embedding: List[float],
        content_text: Optional[str] = None,
        metadata: Optional[dict] = None
    ):
        """
        Insert or update an embedding.

        Args:
            content_type: Type of content ('event', 'person', 'location')
            content_id: ID of the content
            embedding: Vector embedding
            content_text: Original text used for embedding
            metadata: Additional metadata (JSON)
        """
        import json

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO embeddings (content_type, content_id, embedding, content_text, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (content_type, content_id)
                    DO UPDATE SET
                        embedding = EXCLUDED.embedding,
                        content_text = EXCLUDED.content_text,
                        metadata = EXCLUDED.metadata,
                        created_at = NOW()
                """, (
                    content_type,
                    content_id,
                    embedding,
                    content_text,
                    json.dumps(metadata or {})
                ))
                conn.commit()

    def upsert_embeddings_batch(
        self,
        items: List[Tuple[str, int, List[float], Optional[str], Optional[dict]]]
    ):
        """
        Batch insert/update embeddings.

        Args:
            items: List of tuples (content_type, content_id, embedding, content_text, metadata)
        """
        import json

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Prepare data
                values = [
                    (ct, cid, emb, txt, json.dumps(meta or {}))
                    for ct, cid, emb, txt, meta in items
                ]

                execute_values(
                    cur,
                    """
                    INSERT INTO embeddings (content_type, content_id, embedding, content_text, metadata)
                    VALUES %s
                    ON CONFLICT (content_type, content_id)
                    DO UPDATE SET
                        embedding = EXCLUDED.embedding,
                        content_text = EXCLUDED.content_text,
                        metadata = EXCLUDED.metadata,
                        created_at = NOW()
                    """,
                    values,
                    template="(%s, %s, %s, %s, %s)"
                )
                conn.commit()

    def search_similar(
        self,
        query_embedding: List[float],
        content_type: Optional[str] = None,
        limit: int = 10,
        min_similarity: float = 0.5,
        filters: Optional[dict] = None
    ) -> List[dict]:
        """
        Search for similar content using cosine similarity.

        Args:
            query_embedding: Query vector
            content_type: Filter by content type (optional)
            limit: Maximum results to return
            min_similarity: Minimum similarity threshold (0-1)
            filters: Metadata filters (optional)
                - category: str (e.g., "battle", "treaty")
                - date_from: int (e.g., -500 for 500 BCE)
                - date_to: int (e.g., 1500 for 1500 CE)

        Returns:
            List of results with similarity scores
        """
        import numpy as np

        # Convert to numpy array for pgvector
        query_vec = np.array(query_embedding, dtype=np.float32)

        # Build WHERE clauses dynamically
        conditions = []
        params = []

        # Base similarity condition
        conditions.append("1 - (embedding <=> %(vec)s::vector) >= %(min_sim)s")

        if content_type:
            conditions.append("content_type = %(content_type)s")

        if filters:
            if filters.get("category"):
                conditions.append("metadata->>'category' = %(category)s")

            if filters.get("date_from") is not None:
                conditions.append("(metadata->>'date_start')::int >= %(date_from)s")

            if filters.get("date_to") is not None:
                conditions.append("(metadata->>'date_start')::int <= %(date_to)s")

        where_clause = " AND ".join(conditions)

        # Build params dict
        query_params = {
            "vec": query_vec,
            "min_sim": min_similarity,
            "limit": limit,
        }
        if content_type:
            query_params["content_type"] = content_type
        if filters:
            if filters.get("category"):
                query_params["category"] = filters["category"]
            if filters.get("date_from") is not None:
                query_params["date_from"] = filters["date_from"]
            if filters.get("date_to") is not None:
                query_params["date_to"] = filters["date_to"]

        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f"""
                    SELECT
                        content_type,
                        content_id,
                        content_text,
                        metadata,
                        1 - (embedding <=> %(vec)s::vector) as similarity
                    FROM embeddings
                    WHERE {where_clause}
                    ORDER BY embedding <=> %(vec)s::vector
                    LIMIT %(limit)s
                """, query_params)

                results = cur.fetchall()
                return [dict(r) for r in results]

    def search_by_text(
        self,
        query_text: str,
        embedding_service: Any,
        content_type: Optional[str] = None,
        limit: int = 10
    ) -> List[dict]:
        """
        Search using text query (embeds the query first).

        Args:
            query_text: Text query
            embedding_service: EmbeddingService instance
            content_type: Filter by content type
            limit: Maximum results

        Returns:
            List of search results
        """
        query_embedding = embedding_service.embed_query(query_text)
        return self.search_similar(
            query_embedding,
            content_type=content_type,
            limit=limit
        )

    def get_stats(self) -> dict:
        """Get statistics about stored embeddings."""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        content_type,
                        COUNT(*) as count
                    FROM embeddings
                    GROUP BY content_type
                """)
                type_counts = {r['content_type']: r['count'] for r in cur.fetchall()}

                cur.execute("SELECT COUNT(*) as total FROM embeddings")
                total = cur.fetchone()['total']

                return {
                    "total": total,
                    "by_type": type_counts
                }

    def delete_embedding(self, content_type: str, content_id: int):
        """Delete an embedding."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM embeddings
                    WHERE content_type = %s AND content_id = %s
                """, (content_type, content_id))
                conn.commit()

    def clear_all(self):
        """Delete all embeddings. Use with caution!"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE embeddings")
                conn.commit()
