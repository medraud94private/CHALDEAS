"""
RAG Service - Retrieval Augmented Generation for CHALDEAS.

Integrates:
- SHEBA (Observer): Query understanding + Vector retrieval
- LOGOS (Actor): LLM response generation
- LAPLACE (Explainer): Source citation
"""

import os
from typing import List, Optional
from dataclasses import dataclass
from openai import OpenAI

from app.services.embeddings import EmbeddingService, VectorStore


@dataclass
class RAGResponse:
    """Response from RAG pipeline."""
    answer: str
    sources: List[dict]
    confidence: float
    related_events: List[dict]
    query_interpretation: str


class RAGService:
    """
    RAG Service combining SHEBA + LOGOS + LAPLACE.

    Flow:
    1. SHEBA: Embed query → Vector search → Retrieve relevant context
    2. LOGOS: Generate response using GPT-4o-mini with context
    3. LAPLACE: Attach sources and citations
    """

    SYSTEM_PROMPT = """당신은 CHALDEAS 시스템의 AI 역사 전문가입니다.
Fate/Grand Order의 칼데아 시스템처럼, 역사적 사건과 인물에 대해 정확하고 상세한 정보를 제공합니다.

당신의 역할:
1. 사용자의 역사 관련 질문에 답변
2. 제공된 컨텍스트(검색된 역사 데이터)를 기반으로 답변
3. 출처와 관련 정보를 명시
4. 모르는 내용은 솔직히 모른다고 답변

답변 스타일:
- 정확하고 학술적이지만 친근한 톤
- 연도는 BCE/CE 형식 사용
- 관련 인물, 사건, 장소 언급
- 한국어로 답변

중요: 제공된 컨텍스트에 없는 내용을 지어내지 마세요."""

    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        vector_store: Optional[VectorStore] = None,
        chat_model: str = "gpt-5-nano",
        api_key: Optional[str] = None
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required")

        self.client = OpenAI(api_key=self.api_key)
        self.chat_model = chat_model

        # Initialize embedding service
        self.embedding_service = embedding_service or EmbeddingService(
            model="text-embedding-3-large",
            api_key=self.api_key
        )

        # Initialize vector store
        self.vector_store = vector_store or VectorStore(
            embedding_dimension=3072
        )

    def retrieve_context(
        self,
        query: str,
        limit: int = 5
    ) -> List[dict]:
        """
        SHEBA: Retrieve relevant context using vector search.

        Args:
            query: User's question
            limit: Max results to retrieve

        Returns:
            List of relevant documents with metadata
        """
        # Embed the query
        query_embedding = self.embedding_service.embed_query(query)

        # Search vector store
        results = self.vector_store.search_similar(
            query_embedding,
            limit=limit,
            min_similarity=0.3
        )

        return results

    def generate_response(
        self,
        query: str,
        context: List[dict]
    ) -> str:
        """
        LOGOS: Generate response using LLM with retrieved context.

        Args:
            query: User's question
            context: Retrieved documents

        Returns:
            Generated answer
        """
        # Build context string
        context_parts = []
        for i, doc in enumerate(context, 1):
            ctx = f"[{i}] "
            if doc.get("content_text"):
                ctx += doc["content_text"]
            if doc.get("metadata"):
                meta = doc["metadata"]
                if meta.get("title"):
                    ctx += f"\n제목: {meta['title']}"
                if meta.get("date"):
                    ctx += f"\n시기: {meta['date']}"
            context_parts.append(ctx)

        context_str = "\n\n".join(context_parts) if context_parts else "관련 데이터가 없습니다."

        # Generate response
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": f"""다음 역사 데이터를 참고하여 질문에 답변해주세요.

## 검색된 역사 데이터:
{context_str}

## 질문:
{query}

## 답변:"""}
        ]

        response = self.client.chat.completions.create(
            model=self.chat_model,
            messages=messages,
            temperature=0.7,
            max_tokens=1000
        )

        return response.choices[0].message.content

    def query(
        self,
        query: str,
        context_limit: int = 5
    ) -> RAGResponse:
        """
        Full RAG pipeline: SHEBA → LOGOS → LAPLACE.

        Args:
            query: User's question
            context_limit: Max context documents

        Returns:
            RAGResponse with answer, sources, and metadata
        """
        # 1. SHEBA: Retrieve context
        context = self.retrieve_context(query, limit=context_limit)

        # 2. LOGOS: Generate response
        answer = self.generate_response(query, context)

        # 3. LAPLACE: Prepare sources
        sources = []
        related_events = []

        for doc in context:
            source = {
                "type": doc.get("content_type"),
                "id": doc.get("content_id"),
                "similarity": doc.get("similarity", 0),
                "text": doc.get("content_text", "")[:200]  # Truncate
            }
            sources.append(source)

            if doc.get("content_type") == "event":
                related_events.append({
                    "id": doc.get("content_id"),
                    "title": doc.get("metadata", {}).get("title", ""),
                    "date": doc.get("metadata", {}).get("date", "")
                })

        # Calculate confidence based on best similarity
        confidence = max([s["similarity"] for s in sources]) if sources else 0.0

        return RAGResponse(
            answer=answer,
            sources=sources,
            confidence=confidence,
            related_events=related_events,
            query_interpretation=f"검색어: {query}"
        )

    async def aquery(self, query: str, context_limit: int = 5) -> RAGResponse:
        """Async version of query (for FastAPI)."""
        # For now, just wrap sync version
        # Can be optimized with async OpenAI client later
        return self.query(query, context_limit)
