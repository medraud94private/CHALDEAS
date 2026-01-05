"""
Hybrid NER Pipeline for PoC
Step 1: spaCy (free, fast)
Step 2: LLM verification (Ollama local FREE, or OpenAI cloud)
"""
import json
import httpx
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

from app.config import settings


@dataclass
class ExtractedEntity:
    """An extracted named entity."""
    text: str
    entity_type: str  # person, location, event, time
    start: int
    end: int
    confidence: float
    normalized: Optional[str] = None
    extraction_model: str = "spacy"


class HybridNERPipeline:
    """
    Hybrid NER Pipeline:
    1. spaCy for initial extraction (free, fast)
    2. LLM verification:
       - Ollama (local, FREE) - default
       - OpenAI (cloud, paid) - fallback
    """

    # spaCy label to our entity type mapping
    SPACY_LABEL_MAP = {
        "PERSON": "person",
        "GPE": "location",
        "LOC": "location",
        "FAC": "location",
        "ORG": "location",
        "DATE": "time",
        "TIME": "time",
        "EVENT": "event",
    }

    def __init__(self, use_llm_verification: bool = True, provider: str = None):
        self.use_llm_verification = use_llm_verification
        self.provider = provider or settings.llm_provider
        self.nlp = None
        self.openai_client = None

    async def _load_spacy(self):
        """Lazy load spaCy model."""
        if self.nlp is None:
            import spacy
            try:
                self.nlp = spacy.load("en_core_web_lg")
            except OSError:
                try:
                    self.nlp = spacy.load("en_core_web_sm")
                except OSError:
                    raise RuntimeError(
                        "No spaCy model found. Run: python -m spacy download en_core_web_sm"
                    )
        return self.nlp

    async def _call_ollama(self, prompt: str) -> Optional[str]:
        """Call Ollama API (local, FREE) using /api/chat with think:false."""
        import asyncio
        json_prompt = prompt + "\n\nIMPORTANT: Respond with valid JSON only, no other text."

        # Retry up to 3 times with exponential backoff
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=300.0) as client:  # 5 min for first load
                    # Use /api/chat with think:false to disable Qwen3 thinking mode
                    response = await client.post(
                        f"{settings.ollama_base_url}/api/chat",
                        json={
                            "model": settings.ollama_model,
                            "messages": [{"role": "user", "content": json_prompt}],
                            "stream": False,
                            "think": False,  # Critical: disable Qwen3 thinking mode
                            "options": {
                                "temperature": 0.1  # Low temperature for consistent output
                            }
                        }
                    )
                    if response.status_code == 200:
                        result = response.json()
                        # /api/chat returns message.content instead of response
                        response_text = result.get("message", {}).get("content", "")

                        # Extract JSON from response (may have extra text)
                        if response_text:
                            # Find JSON object in response
                            start = response_text.find("{")
                            end = response_text.rfind("}") + 1
                            if start != -1 and end > start:
                                return response_text[start:end]
                        return response_text
                    elif response.status_code >= 500:
                        # Server error, retry after delay
                        await asyncio.sleep(2 ** attempt)
                        continue
                    else:
                        return None
            except httpx.ConnectError:
                await asyncio.sleep(2 ** attempt)
                continue
            except httpx.TimeoutException:
                await asyncio.sleep(2 ** attempt)
                continue
            except Exception as e:
                if attempt < 2:
                    await asyncio.sleep(1)
                    continue
        return None

    async def _call_openai(self, prompt: str) -> Optional[str]:
        """Call OpenAI API (cloud, paid)."""
        if not settings.openai_api_key:
            return None

        if self.openai_client is None:
            from openai import AsyncOpenAI
            self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

        try:
            response = await self.openai_client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=1000
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"OpenAI error: {e}")
            return None

    async def _call_llm(self, prompt: str) -> Optional[str]:
        """Call LLM based on configured provider."""
        if self.provider == "ollama":
            result = await self._call_ollama(prompt)
            if result:
                return result
            # Fallback to OpenAI if Ollama fails
            print("Falling back to OpenAI...")
            return await self._call_openai(prompt)
        else:
            return await self._call_openai(prompt)

    async def extract_entities(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[ExtractedEntity]:
        """Extract named entities from text."""
        # Step 1: spaCy extraction
        nlp = await self._load_spacy()
        doc = nlp(text)

        candidates = []
        for ent in doc.ents:
            if ent.label_ in self.SPACY_LABEL_MAP:
                entity = ExtractedEntity(
                    text=ent.text,
                    entity_type=self.SPACY_LABEL_MAP[ent.label_],
                    start=ent.start_char,
                    end=ent.end_char,
                    confidence=0.7,
                    extraction_model="spacy"
                )
                candidates.append(entity)

        # Step 2: LLM verification (optional)
        if self.use_llm_verification and candidates:
            candidates = await self._verify_with_llm(text, candidates, context)

        return candidates

    async def _verify_with_llm(
        self,
        text: str,
        candidates: List[ExtractedEntity],
        context: Optional[Dict[str, Any]] = None
    ) -> List[ExtractedEntity]:
        """Verify and enhance entities using LLM."""
        candidates_json = [asdict(c) for c in candidates]

        prompt = f"""You are a historical entity extraction expert.

Text: {text}

NER candidates extracted by spaCy:
{json.dumps(candidates_json, ensure_ascii=False, indent=2)}

Historical context: {json.dumps(context, ensure_ascii=False) if context else "None"}

Tasks:
1. Verify each candidate is a real historical entity
2. Fix misclassifications:
   - "Julius Caesar", "Socrates", "Plato" = person (NOT location)
   - "BCE", "399 BCE" = time (NOT location)
   - "Roman Empire", "Athens" = location
3. Add normalized names (e.g., "Caesar" -> "Julius Caesar")
4. Adjust confidence (0.0-1.0)

Return ONLY a JSON object with "entities" array:
{{"entities": [{{"text": "...", "entity_type": "person|location|event|time", "start": 0, "end": 0, "confidence": 0.9, "normalized": "..."}}]}}
"""

        result_str = await self._call_llm(prompt)
        if not result_str:
            return candidates

        try:
            result = json.loads(result_str)
            entities_data = result.get("entities", result if isinstance(result, list) else [])

            verified = []
            model_name = f"{self.provider}-verified"
            for e in entities_data:
                if isinstance(e, dict) and "text" in e:
                    verified.append(ExtractedEntity(
                        text=e.get("text", ""),
                        entity_type=e.get("entity_type", "unknown"),
                        start=e.get("start", 0),
                        end=e.get("end", 0),
                        confidence=float(e.get("confidence", 0.5)),
                        normalized=e.get("normalized"),
                        extraction_model=model_name
                    ))
            return verified if verified else candidates

        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            return candidates

    async def extract_from_document(
        self,
        text: str,
        chunk_size: int = 2000,
        overlap: int = 200
    ) -> List[ExtractedEntity]:
        """Extract entities from a long document by chunking."""
        all_entities = []
        offset = 0

        while offset < len(text):
            chunk_end = min(offset + chunk_size, len(text))
            chunk = text[offset:chunk_end]

            entities = await self.extract_entities(chunk)

            for entity in entities:
                entity.start += offset
                entity.end += offset

            all_entities.extend(entities)
            offset += chunk_size - overlap

        return self._deduplicate_entities(all_entities)

    def _deduplicate_entities(
        self,
        entities: List[ExtractedEntity]
    ) -> List[ExtractedEntity]:
        """Remove duplicate entities."""
        seen = set()
        unique = []

        for entity in entities:
            key = (entity.normalized or entity.text, entity.entity_type)
            if key not in seen:
                seen.add(key)
                unique.append(entity)

        return unique


async def test_ollama_connection() -> bool:
    """Test if Ollama is running and model is available."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Check if Ollama is running
            response = await client.get(f"{settings.ollama_base_url}/api/tags")
            if response.status_code != 200:
                return False

            # Check if model is available
            models = response.json().get("models", [])
            model_names = [m.get("name", "") for m in models]

            target_model = settings.ollama_model
            if target_model not in model_names and f"{target_model}:latest" not in model_names:
                print(f"Model {target_model} not found. Available: {model_names}")
                print(f"Run: ollama pull {target_model}")
                return False

            return True
    except Exception as e:
        print(f"Ollama connection failed: {e}")
        return False
