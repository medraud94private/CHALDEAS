"""
Test Ollama integration for NER Pipeline
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.extraction import HybridNERPipeline
from app.core.extraction.ner_pipeline import test_ollama_connection
from app.config import settings


SAMPLE_TEXT = """
Socrates was a classical Greek philosopher credited as the founder of Western philosophy.
He was born in Athens around 470 BCE and died in 399 BCE after being sentenced to death
by drinking hemlock. His student Plato went on to found the Academy in Athens.
"""


async def test_connection():
    """Test Ollama connection."""
    print("=" * 60)
    print("Ollama Connection Test")
    print("=" * 60)
    print(f"Base URL: {settings.ollama_base_url}")
    print(f"Model: {settings.ollama_model}")
    print()

    connected = await test_ollama_connection()
    if connected:
        print("[OK] Ollama is running and model is available!")
        return True
    else:
        print("[FAIL] Ollama connection failed")
        print()
        print("To fix:")
        print("  1. Install Ollama: https://ollama.com/download")
        print("  2. Start Ollama: ollama serve")
        print(f"  3. Pull model: ollama pull {settings.ollama_model}")
        return False


async def test_ner_with_ollama():
    """Test NER with Ollama verification."""
    print()
    print("=" * 60)
    print("NER Pipeline Test with Ollama")
    print("=" * 60)
    print()
    print(f"Text: {SAMPLE_TEXT.strip()[:80]}...")
    print()

    # Test with LLM verification
    pipeline = HybridNERPipeline(use_llm_verification=True, provider="ollama")

    print("Extracting entities (spaCy + Ollama verification)...")
    print()

    entities = await pipeline.extract_entities(SAMPLE_TEXT.strip())

    print(f"Extracted {len(entities)} entities:")
    print("-" * 60)
    for entity in entities:
        normalized = f" -> {entity.normalized}" if entity.normalized else ""
        print(f"  [{entity.entity_type.upper():8}] {entity.text:25}{normalized}")
        print(f"             Confidence: {entity.confidence:.2f}, Model: {entity.extraction_model}")
    print()


async def compare_spacy_vs_ollama():
    """Compare spaCy alone vs spaCy + Ollama."""
    print()
    print("=" * 60)
    print("Comparison: spaCy Only vs spaCy + Ollama")
    print("=" * 60)
    print()

    # spaCy only
    pipeline_spacy = HybridNERPipeline(use_llm_verification=False)
    entities_spacy = await pipeline_spacy.extract_entities(SAMPLE_TEXT.strip())

    # spaCy + Ollama
    pipeline_ollama = HybridNERPipeline(use_llm_verification=True, provider="ollama")
    entities_ollama = await pipeline_ollama.extract_entities(SAMPLE_TEXT.strip())

    print("spaCy Only:")
    print("-" * 40)
    for e in entities_spacy:
        print(f"  [{e.entity_type:8}] {e.text}")

    print()
    print("spaCy + Ollama:")
    print("-" * 40)
    for e in entities_ollama:
        normalized = f" -> {e.normalized}" if e.normalized else ""
        print(f"  [{e.entity_type:8}] {e.text}{normalized}")

    print()
    print("=" * 60)


async def main():
    # Step 1: Test connection
    connected = await test_connection()
    if not connected:
        return

    # Step 2: Test NER
    await test_ner_with_ollama()

    # Step 3: Compare
    await compare_spacy_vs_ollama()


if __name__ == "__main__":
    asyncio.run(main())
