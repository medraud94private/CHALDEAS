"""
Test script for NER Pipeline
Tests entity extraction from sample texts
"""
import asyncio
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.extraction import HybridNERPipeline


# Sample historical texts for testing
SAMPLE_TEXTS = [
    """
    Socrates was a classical Greek philosopher credited as the founder of Western philosophy.
    He was born in Athens around 470 BCE and died in 399 BCE after being sentenced to death
    by drinking hemlock. His student Plato went on to found the Academy in Athens.
    """,

    """
    Julius Caesar crossed the Rubicon River in 49 BCE, sparking a civil war in Rome.
    He became dictator and was later assassinated on the Ides of March (March 15) in 44 BCE
    in the Theatre of Pompey by a group of senators including Brutus and Cassius.
    """,

    """
    Leonardo da Vinci, born in 1452 in Vinci, Italy, was a polymath of the Renaissance era.
    He painted the Mona Lisa and The Last Supper in Florence and Milan. He died in 1519
    in Amboise, France, while serving King Francis I.
    """
]


async def test_ner_pipeline():
    """Test the NER pipeline with sample texts."""
    print("=" * 60)
    print("CHALDEAS V1 PoC - NER Pipeline Test")
    print("=" * 60)

    # Initialize pipeline (without LLM verification for basic test)
    pipeline = HybridNERPipeline(use_llm_verification=False)

    for i, text in enumerate(SAMPLE_TEXTS, 1):
        print(f"\n--- Sample Text {i} ---")
        print(text.strip()[:100] + "...")

        try:
            entities = await pipeline.extract_entities(text.strip())

            print(f"\nExtracted {len(entities)} entities:")
            for entity in entities:
                print(f"  [{entity.entity_type.upper():8}] {entity.text:30} (conf: {entity.confidence:.2f})")

        except Exception as e:
            print(f"Error: {e}")
            print("Note: Run 'python -m spacy download en_core_web_sm' to install spaCy model")

    print("\n" + "=" * 60)
    print("Test complete!")


async def test_ner_with_llm():
    """Test the NER pipeline with LLM verification."""
    print("=" * 60)
    print("CHALDEAS V1 PoC - NER Pipeline with LLM Verification")
    print("=" * 60)

    # Initialize pipeline with LLM verification
    pipeline = HybridNERPipeline(use_llm_verification=True)

    text = SAMPLE_TEXTS[0]  # Use first sample
    print(f"\nTest text: {text.strip()[:100]}...")

    context = {
        "era": "Classical Greece",
        "region": "Mediterranean",
        "year_range": (-500, -300)
    }

    try:
        entities = await pipeline.extract_entities(text.strip(), context=context)

        print(f"\nExtracted {len(entities)} entities (with LLM verification):")
        for entity in entities:
            normalized = f" -> {entity.normalized}" if entity.normalized else ""
            print(f"  [{entity.entity_type.upper():8}] {entity.text:30}{normalized}")
            print(f"             Model: {entity.extraction_model}, Confidence: {entity.confidence:.2f}")

    except Exception as e:
        print(f"Error: {e}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--llm":
        asyncio.run(test_ner_with_llm())
    else:
        asyncio.run(test_ner_pipeline())
