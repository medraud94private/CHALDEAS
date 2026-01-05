"""
Integrated NER Pipeline - LLM Extractor
OpenAI Structured Output을 사용한 엔티티 추출
"""
import json
import os
import asyncio
import httpx
from pathlib import Path
from typing import Optional, Tuple, List
from dataclasses import dataclass

# Load .env file
def load_env():
    env_path = Path(__file__).parent.parent.parent.parent / ".env"
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

load_env()

from schema import DocumentExtraction


# 모델 폴백 순서 (Batch API 가격 기준, per 1M tokens)
MODELS = [
    ("gpt-5-nano", 0.05, 0.40),           # 기본: $0.05 input, $0.40 output
    ("gpt-5-mini", 0.25, 2.00),           # 폴백 1: $0.25 input, $2.00 output
    ("gpt-5.1-chat-latest", 1.25, 10.00), # 폴백 2: $1.25 input, $10.00 output
]

OPENAI_URL = "https://api.openai.com/v1"


EXTRACTION_PROMPT = """You are a historical entity extraction expert.
Extract all historical entities from this document text.

EXTRACTION RULES:
1. Persons: Only clear, identifiable names. Skip titles alone (Mr, Dr, St), abbreviations, partial names.
2. Locations: Cities, regions, countries, landmarks. Include historical and modern names.
3. Polities: Empires, kingdoms, dynasties, republics, city-states.
4. Periods: Named historical eras (Renaissance, Victorian Era, Bronze Age).
5. Events: Battles, treaties, revolutions, discoveries.

DATE RULES:
- Use negative numbers for BCE (e.g., -490 for 490 BCE)
- Set year_precision based on certainty:
  - "exact": specific year mentioned
  - "circa": approximate (around, about)
  - "decade": 1920s, 330s BCE
  - "century": 4th century, 1800s
  - "period": only era name known
  - "unknown": no date information

CONFIDENCE SCORING:
- 1.0: Explicitly stated with full context
- 0.7-0.9: Clearly identifiable from context
- 0.4-0.6: Inferred or partially mentioned
- 0.1-0.3: Uncertain, may need verification

DOCUMENT TEXT:
{document_text}

Extract all entities following the schema. Be thorough but accurate."""


@dataclass
class ExtractionResult:
    success: bool
    model_used: str
    extraction: Optional[DocumentExtraction]
    error: Optional[str]
    tokens_used: int
    cost: float


class IntegratedNERExtractor:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")

    def _build_json_schema(self) -> dict:
        """OpenAI Structured Output용 JSON Schema - strict mode 호환"""
        return {
            "type": "object",
            "properties": {
                "persons": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "role": {"type": ["string", "null"]},
                            "birth_year": {"type": ["integer", "null"]},
                            "death_year": {"type": ["integer", "null"]},
                            "era": {"type": ["string", "null"]},
                            "confidence": {"type": "number"}
                        },
                        "required": ["name", "role", "birth_year", "death_year", "era", "confidence"],
                        "additionalProperties": False
                    }
                },
                "locations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "location_type": {"type": ["string", "null"]},
                            "modern_name": {"type": ["string", "null"]},
                            "confidence": {"type": "number"}
                        },
                        "required": ["name", "location_type", "modern_name", "confidence"],
                        "additionalProperties": False
                    }
                },
                "polities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "polity_type": {"type": ["string", "null"]},
                            "start_year": {"type": ["integer", "null"]},
                            "end_year": {"type": ["integer", "null"]},
                            "confidence": {"type": "number"}
                        },
                        "required": ["name", "polity_type", "start_year", "end_year", "confidence"],
                        "additionalProperties": False
                    }
                },
                "periods": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "start_year": {"type": ["integer", "null"]},
                            "end_year": {"type": ["integer", "null"]},
                            "region": {"type": ["string", "null"]},
                            "confidence": {"type": "number"}
                        },
                        "required": ["name", "start_year", "end_year", "region", "confidence"],
                        "additionalProperties": False
                    }
                },
                "events": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "year": {"type": ["integer", "null"]},
                            "persons_involved": {"type": "array", "items": {"type": "string"}},
                            "locations_involved": {"type": "array", "items": {"type": "string"}},
                            "confidence": {"type": "number"}
                        },
                        "required": ["name", "year", "persons_involved", "locations_involved", "confidence"],
                        "additionalProperties": False
                    }
                }
            },
            "required": ["persons", "locations", "polities", "periods", "events"],
            "additionalProperties": False
        }

    async def extract_with_model(
        self,
        document_text: str,
        model: str
    ) -> Tuple[bool, Optional[DocumentExtraction], Optional[str], int]:
        """특정 모델로 추출 시도"""

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    f"{OPENAI_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a historical entity extraction expert. Extract entities and return valid JSON."
                            },
                            {
                                "role": "user",
                                "content": EXTRACTION_PROMPT.format(document_text=document_text[:8000])
                            }
                        ],
                        "response_format": {
                            "type": "json_schema",
                            "json_schema": {
                                "name": "document_extraction",
                                "strict": True,
                                "schema": self._build_json_schema()
                            }
                        },
                        "max_tokens": 4000
                    }
                )

                if response.status_code != 200:
                    return False, None, f"API error: {response.status_code}", 0

                data = response.json()
                content = data["choices"][0]["message"]["content"]
                tokens = data.get("usage", {}).get("total_tokens", 0)

                # Parse JSON - return as dict directly
                extraction_dict = json.loads(content)
                # Return dict directly instead of Pydantic model
                return True, extraction_dict, None, tokens

            except json.JSONDecodeError as e:
                return False, None, f"JSON parse error: {e}", 0
            except Exception as e:
                return False, None, f"Error: {e}", 0

    async def extract(self, document_text: str) -> ExtractionResult:
        """폴백 로직으로 추출"""

        for model, cost_per_m in MODELS:
            success, extraction, error, tokens = await self.extract_with_model(
                document_text, model
            )

            if success and extraction:
                # 빈 결과 체크 (extraction is now a dict)
                total_entities = (
                    len(extraction.get("persons", [])) +
                    len(extraction.get("locations", [])) +
                    len(extraction.get("polities", [])) +
                    len(extraction.get("periods", [])) +
                    len(extraction.get("events", []))
                )

                if total_entities == 0 and len(document_text) > 100:
                    # 문서가 있는데 결과가 없으면 다음 모델 시도
                    continue

                cost = tokens * cost_per_m / 1_000_000
                return ExtractionResult(
                    success=True,
                    model_used=model,
                    extraction=extraction,
                    error=None,
                    tokens_used=tokens,
                    cost=cost
                )

        return ExtractionResult(
            success=False,
            model_used="all_failed",
            extraction=None,
            error="All models failed",
            tokens_used=0,
            cost=0.0
        )


async def test_single_document(doc_path: Path):
    """단일 문서 테스트"""
    extractor = IntegratedNERExtractor()

    # 문서 로드
    with open(doc_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 텍스트 추출 (British Library 형식)
    if isinstance(data, list):
        text = " ".join(item[1] if len(item) > 1 else "" for item in data)
    else:
        text = str(data)

    print(f"Document: {doc_path.name}")
    print(f"Text length: {len(text)} chars")
    print("-" * 50)

    result = await extractor.extract(text)

    if result.success:
        print(f"Model: {result.model_used}")
        print(f"Tokens: {result.tokens_used}")
        print(f"Cost: ${result.cost:.4f}")
        print()

        ext = result.extraction
        print(f"Persons: {len(ext.persons)}")
        for p in ext.persons[:5]:
            print(f"  - {p.name} ({p.role or 'unknown role'}), conf: {p.confidence}")

        print(f"\nLocations: {len(ext.locations)}")
        for loc in ext.locations[:5]:
            print(f"  - {loc.name} ({loc.location_type or 'unknown'}), conf: {loc.confidence}")

        print(f"\nPolities: {len(ext.polities)}")
        for pol in ext.polities[:3]:
            print(f"  - {pol.name} ({pol.polity_type or 'unknown'})")

        print(f"\nPeriods: {len(ext.periods)}")
        for per in ext.periods[:3]:
            print(f"  - {per.name} ({per.start_year} ~ {per.end_year})")

        print(f"\nEvents: {len(ext.events)}")
        for ev in ext.events[:3]:
            print(f"  - {ev.name} ({ev.year})")
    else:
        print(f"Failed: {result.error}")

    return result


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        doc_path = Path(sys.argv[1])
    else:
        # 기본 테스트 문서
        doc_path = Path("C:/Projects/Chaldeas/data/raw/british_library/extracted/json/0000/000000037_01_text.json")

    asyncio.run(test_single_document(doc_path))
