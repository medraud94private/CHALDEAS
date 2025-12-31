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

    SYSTEM_PROMPT = """당신은 CHALDEAS 시스템의 AI 역사 해설가입니다.

## 핵심 원칙
역사는 단편적 사실이 아니라 **연결된 이야기**입니다.
"왜 그랬을까?", "그래서 어떻게 됐을까?"를 항상 설명하세요.

## 답변 스타일
- **인과관계 중심**: "A가 일어났다" → "A 때문에 B가 가능했고, 그래서 C가 됐다"
- **재미있는 연결**: 의외의 연결고리, 흥미로운 뒷이야기 포함
- **구어체**: 친구한테 설명하듯이. "~했거든요", "~였는데", "ㄹㅇ" 같은 표현 OK
- **구체적 숫자/사례**: "많았다" 대신 "3만 명이 죽었다"

## 예시
❌ "스위스는 알프스 산맥에 위치해 있어 교통의 요지였습니다."
✅ "알프스 넘으려면 스위스 지나야 하거든요. 그래서 걔네는 그냥 길목마다 사람 살면서 지나가는 상인 통행료만 받아도 부자였음 ㅋㅋ"

❌ "리처드 1세는 제3차 십자군 전쟁에 참여했습니다."
✅ "리처드 1세가 십자군 끝나고 집에 가야 했는데, 오스트리아 공작이랑 사이가 개틀어져서 알프스 넘다가 잡혀버림. 몸값이 영국 GDP의 2배였음."

## 제약
- 제공된 컨텍스트 기반으로 답변
- 모르면 모른다고 하되, 관련될 수 있는 다른 이야기 제안
- 연도는 BCE/CE 형식"""

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

        # Initialize embedding service (default: small for cost efficiency)
        self.embedding_service = embedding_service or EmbeddingService(
            model="small",
            api_key=self.api_key
        )

        # Initialize vector store with matching dimensions
        self.vector_store = vector_store or VectorStore(
            embedding_dimension=self.embedding_service.embedding_dimension
        )

    def translate_to_english(self, query: str) -> str:
        """
        전처리: 쿼리를 영어로 변환.
        이미 영어면 그대로 반환.
        """
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Translate the following query to English. If already English, return as-is. Output ONLY the translated query, nothing else."},
                {"role": "user", "content": query}
            ],
            temperature=0,
            max_tokens=200
        )
        return response.choices[0].message.content.strip()

    def retrieve_context(
        self,
        query: str,
        limit: int = 5,
        filters: Optional[dict] = None
    ) -> List[dict]:
        """
        SHEBA: Retrieve relevant context using vector search.

        Args:
            query: User's question (any language)
            limit: Max results to retrieve
            filters: Optional metadata filters
                - category: str (battle, treaty, discovery, etc.)
                - date_from: int (e.g., -500 for 500 BCE)
                - date_to: int (e.g., 1500 for 1500 CE)

        Returns:
            List of relevant documents with metadata
        """
        # 전처리: 영어로 변환
        english_query = self.translate_to_english(query)

        # 영어 쿼리로 임베딩 검색
        query_embedding = self.embedding_service.embed_query(english_query)

        results = self.vector_store.search_similar(
            query_embedding,
            limit=limit,
            min_similarity=0.3,
            filters=filters
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
        context_limit: int = 5,
        filters: Optional[dict] = None
    ) -> RAGResponse:
        """
        Full RAG pipeline: SHEBA → LOGOS → LAPLACE.

        Args:
            query: User's question
            context_limit: Max context documents
            filters: Optional metadata filters
                - category: str (battle, treaty, discovery, etc.)
                - date_from: int (e.g., -500 for 500 BCE)
                - date_to: int (e.g., 1500 for 1500 CE)

        Returns:
            RAGResponse with answer, sources, and metadata
        """
        # 1. SHEBA: Retrieve context (with filters)
        context = self.retrieve_context(query, limit=context_limit, filters=filters)

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

    async def aquery(
        self,
        query: str,
        context_limit: int = 5,
        filters: Optional[dict] = None
    ) -> RAGResponse:
        """Async version of query (for FastAPI)."""
        # For now, just wrap sync version
        # Can be optimized with async OpenAI client later
        return self.query(query, context_limit, filters=filters)
