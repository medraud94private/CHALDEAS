"""
Archivist PoC Test Script
Tests entity disambiguation using real data from our collection.
"""
import asyncio
import json
import os
import sys
import random
import io
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Fix Windows console encoding for Unicode output
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.extraction.ner_pipeline import HybridNERPipeline, test_ollama_connection
from app.core.archivist import Archivist, EntityRegistry, Decision


# Data sources configuration
DATA_DIR = Path(__file__).parent.parent.parent / "data"

# Sample sources with their text files
# LARGE SCALE TEST: Control via --multiplier arg or SAMPLE_MULTIPLIER env var
# SAMPLE_MULTIPLIER=1 for quick test (~34 texts), =10 for full test (~340 texts)
def get_sample_multiplier():
    """Get sample multiplier from command line or environment."""
    # Check command line first
    for i, arg in enumerate(sys.argv):
        if arg == "--multiplier" and i + 1 < len(sys.argv):
            return int(sys.argv[i + 1])
        if arg.startswith("--multiplier="):
            return int(arg.split("=")[1])
    # Fall back to environment
    return int(os.environ.get("SAMPLE_MULTIPLIER", "1"))

SAMPLE_MULTIPLIER = get_sample_multiplier()
print(f"SAMPLE_MULTIPLIER={SAMPLE_MULTIPLIER}", flush=True)

SOURCES = {
    "gutenberg": {
        "dir": DATA_DIR / "raw" / "gutenberg",
        "pattern": "pg*.txt",
        "sample_size": 15 * SAMPLE_MULTIPLIER,  # Main source
    },
    "arthurian": {
        "dir": DATA_DIR / "raw" / "arthurian",
        "pattern": "gutenberg_pg*.txt",
        "sample_size": max(1, 1 * SAMPLE_MULTIPLIER),
    },
    "ctext": {
        "dir": DATA_DIR / "raw" / "ctext",
        "pattern": "ctp_*.json",
        "sample_size": 2 * SAMPLE_MULTIPLIER,  # Chinese classics
    },
    "theoi": {
        "dir": DATA_DIR / "raw" / "theoi",
        "pattern": "*.json",
        "sample_size": 3 * SAMPLE_MULTIPLIER,  # Greek mythology
    },
    "britannica": {
        "dir": DATA_DIR / "raw" / "britannica_1911",
        "pattern": "britannica_articles.json",
        "sample_size": 5 * SAMPLE_MULTIPLIER,  # Encyclopedia articles
    },
    "perseus": {
        "dir": DATA_DIR / "raw" / "perseus",
        "pattern": "*.json",
        "sample_size": 3 * SAMPLE_MULTIPLIER,  # Classical texts
    },
    "worldhistory": {
        "dir": DATA_DIR / "raw" / "worldhistory",
        "pattern": "*.json",
        "sample_size": 3 * SAMPLE_MULTIPLIER,  # World history articles
    },
    "stanford": {
        "dir": DATA_DIR / "raw" / "stanford_encyclopedia",
        "pattern": "*.json",
        "sample_size": 2 * SAMPLE_MULTIPLIER,  # Philosophy
    },
}


def load_text_file(filepath: Path) -> str:
    """Load text from a file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return ""


def load_json_file(filepath: Path) -> Any:
    """Load JSON from a file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return None


def get_sample_texts(source_name: str, config: dict) -> List[Dict[str, str]]:
    """Get sample texts from a data source."""
    texts = []
    source_dir = config["dir"]

    if not source_dir.exists():
        print(f"  Directory not found: {source_dir}")
        return texts

    if config["pattern"].endswith(".txt"):
        # Text files
        files = list(source_dir.glob(config["pattern"]))
        sample_files = random.sample(files, min(config["sample_size"], len(files)))

        for f in sample_files:
            content = load_text_file(f)
            if content:
                # Take first 5000 chars for speed
                texts.append({
                    "source": f"{source_name}/{f.name}",
                    "content": content[:5000]
                })

    elif config["pattern"].endswith(".json"):
        # JSON files
        if "britannica" in source_name:
            # Special handling for Britannica
            json_file = source_dir / "britannica_articles.json"
            if json_file.exists():
                data = load_json_file(json_file)
                if data and isinstance(data, list):
                    samples = random.sample(data, min(config["sample_size"], len(data)))
                    for article in samples:
                        content = article.get("content", article.get("text", ""))
                        title = article.get("title", "unknown")
                        if content:
                            texts.append({
                                "source": f"{source_name}/{title}",
                                "content": content[:5000]
                            })
        elif "ctext" in source_name or "theoi" in source_name:
            # CText or Theoi JSON files
            files = list(source_dir.glob(config["pattern"]))
            sample_files = random.sample(files, min(config["sample_size"], len(files)))

            for f in sample_files:
                data = load_json_file(f)
                if data:
                    # Extract text content
                    if isinstance(data, dict):
                        content = data.get("content", data.get("text", str(data)))
                    elif isinstance(data, list):
                        content = " ".join([
                            item.get("text", str(item)) if isinstance(item, dict) else str(item)
                            for item in data[:10]
                        ])
                    else:
                        content = str(data)

                    if content:
                        texts.append({
                            "source": f"{source_name}/{f.name}",
                            "content": content[:5000]
                        })

    print(f"  Loaded {len(texts)} samples from {source_name}")
    return texts


async def run_archivist_test():
    """Run the Archivist PoC test."""
    print("\n" + "="*60)
    print("       ARCHIVIST PoC TEST")
    print("="*60 + "\n")

    # Check Ollama
    print("Checking Ollama connection...")
    ollama_ok = await test_ollama_connection()
    if not ollama_ok:
        print("ERROR: Ollama not available. Please start Ollama with qwen3:8b model.")
        print("Run: ollama serve")
        print("Run: ollama pull qwen3:8b")
        return

    print("Ollama OK!\n")

    # Initialize components
    # NOTE: Disable LLM verification in NER for speed (use spaCy only)
    # Archivist will use Qwen for disambiguation decisions
    print("Initializing NER pipeline (spaCy only) and Archivist...")
    ner = HybridNERPipeline(use_llm_verification=False)  # spaCy only - fast
    archivist = Archivist()

    # Collect sample texts
    print("\nLoading sample texts from data sources...")
    all_texts = []
    for source_name, config in SOURCES.items():
        texts = get_sample_texts(source_name, config)
        all_texts.extend(texts)

    if not all_texts:
        print("No texts found! Check data directory.")
        return

    print(f"\nTotal samples: {len(all_texts)}")
    print("\n" + "-"*60)
    print("Starting entity extraction and archiving...")
    print("-"*60 + "\n")

    # Process each text
    total_entities = 0
    processed_texts = 0

    for i, text_info in enumerate(all_texts):
        source = text_info["source"]
        content = text_info["content"]

        print(f"[{i+1}/{len(all_texts)}] Processing: {source}")

        try:
            # Extract entities
            entities = await ner.extract_entities(content[:2000])  # Limit for speed
            print(f"  Extracted {len(entities)} entities")

            # Process each entity through Archivist
            for entity in entities:
                if entity.entity_type in ["person", "location", "event"]:
                    # Get surrounding context
                    ctx_start = max(0, entity.start - 100)
                    ctx_end = min(len(content), entity.end + 100)
                    context = content[ctx_start:ctx_end]

                    decision, record = await archivist.process_entity(
                        text=entity.text,
                        entity_type=entity.entity_type,
                        context=context,
                        source=source
                    )

                    total_entities += 1

                    # Print interesting decisions
                    if decision.decision == Decision.LINK_EXISTING:
                        print(f"    LINKED: '{entity.text}' -> Entity #{decision.linked_entity_id}")
                    elif decision.decision == Decision.PENDING:
                        print(f"    PENDING: '{entity.text}' (needs review)")

            processed_texts += 1

        except Exception as e:
            print(f"  Error: {e}")
            continue

        # Periodic stats
        if (i + 1) % 10 == 0:
            stats = archivist.get_stats()
            print(f"\n  --- Progress: {stats['decisions']['total_decisions']} decisions, "
                  f"{stats['registry']['total']} entities ---\n")

    # Final report
    print("\n" + "="*60)
    print(archivist.get_report())

    # Show some example pending items
    if archivist.pending_queue:
        print("\n[ Sample Pending Items ]")
        for item in archivist.pending_queue[:5]:
            print(f"  - '{item['text']}' ({item['entity_type']})")
            print(f"    Candidates: {len(item['candidates'])}")
            print(f"    Reason: {item['decision']['reasoning']}")
            print()

    # Show some example linked entities
    print("\n[ Sample Entities with Aliases ]")
    for entity in list(archivist.registry.entities.values())[:10]:
        if entity.aliases:
            # Handle unicode safely for Windows console
            try:
                print(f"  - {entity.normalized}")
                print(f"    Aliases: {entity.aliases}")
                print(f"    Sources: {entity.sources[:3]}")
                print()
            except UnicodeEncodeError:
                safe_name = entity.normalized.encode('ascii', 'replace').decode('ascii')
                print(f"  - {safe_name}")
                print(f"    (Unicode display error, see JSON results)")
                print()

    # Save detailed results
    results_dir = Path(__file__).parent.parent / "data" / "archivist_results"
    results_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = results_dir / f"archivist_test_{timestamp}.json"

    results = {
        "timestamp": timestamp,
        "processed_texts": processed_texts,
        "total_entities_processed": total_entities,
        "stats": archivist.get_stats(),
        "pending_items": archivist.pending_queue[:50],  # Limit for file size
        "sample_entities": [
            {
                "id": e.id,
                "text": e.text,
                "normalized": e.normalized,
                "type": e.entity_type,
                "aliases": e.aliases,
                "sources": e.sources[:5]
            }
            for e in list(archivist.registry.entities.values())[:100]
        ]
    }

    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nResults saved to: {results_file}")
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60 + "\n")


# Test with specific challenging cases
async def test_disambiguation_cases():
    """Test specific disambiguation challenges."""
    print("\n" + "="*60)
    print("       DISAMBIGUATION CHALLENGE TEST")
    print("="*60 + "\n")

    archivist = Archivist()

    # Define test cases with expected outcomes
    test_cases = [
        # Case 1: Louis XIV vs Louis XV
        {
            "entities": [
                ("Louis XIV", "person", "Louis XIV, the Sun King, ruled France from 1643 to 1715."),
                ("Louis XV", "person", "Louis XV, grandson of Louis XIV, became king in 1715."),
            ],
            "expected": ["CREATE_NEW", "CREATE_NEW"],  # Should be separate
            "description": "Different kings (XIV vs XV)"
        },
        # Case 2: Same person, different mentions
        {
            "entities": [
                ("Socrates", "person", "Socrates was a classical Greek philosopher."),
                ("Socrates", "person", "According to Plato, Socrates was his teacher."),
            ],
            "expected": ["CREATE_NEW", "LINK_EXISTING"],
            "description": "Same philosopher, different contexts"
        },
        # Case 3: Henry VII vs Henry VIII
        {
            "entities": [
                ("Henry VII", "person", "Henry VII was the first Tudor king of England."),
                ("Henry VIII", "person", "Henry VIII, son of Henry VII, had six wives."),
            ],
            "expected": ["CREATE_NEW", "CREATE_NEW"],
            "description": "Father and son with ordinals"
        },
        # Case 4: Plato philosopher vs Plato comic poet
        {
            "entities": [
                ("Plato", "person", "Plato founded the Academy in Athens and wrote philosophical dialogues."),
                ("Plato", "person", "Plato the comic poet wrote comedies in Athens during the 5th century."),
            ],
            "expected": ["CREATE_NEW", "CREATE_NEW"],  # Different people with same name
            "description": "Homonyms - philosopher vs comic poet"
        },
        # Case 5: Napoleon I vs Napoleon III
        {
            "entities": [
                ("Napoleon I", "person", "Napoleon I, also known as Napoleon Bonaparte, was Emperor of France."),
                ("Napoleon III", "person", "Napoleon III was the nephew of Napoleon I and became Emperor in 1852."),
            ],
            "expected": ["CREATE_NEW", "CREATE_NEW"],
            "description": "Different emperors with ordinals"
        },
        # Case 6: Marathon - place vs battle
        {
            "entities": [
                ("Marathon", "location", "Marathon is a town in Greece, about 40km from Athens."),
                ("Battle of Marathon", "event", "The Battle of Marathon in 490 BCE was a decisive Greek victory."),
            ],
            "expected": ["CREATE_NEW", "CREATE_NEW"],
            "description": "Location vs Event"
        },
    ]

    total_correct = 0
    total_tests = 0

    for case in test_cases:
        print(f"\nTest: {case['description']}")
        print("-" * 40)

        for i, (text, entity_type, context) in enumerate(case["entities"]):
            decision, entity = await archivist.process_entity(
                text=text,
                entity_type=entity_type,
                context=context,
                source="test"
            )

            expected = case["expected"][i]
            actual = decision.decision.value
            is_correct = actual == expected

            status = "[OK]" if is_correct else "[FAIL]"
            print(f"  {status} '{text}': {actual} (expected: {expected})")
            print(f"    Confidence: {decision.confidence:.2f}")
            print(f"    Reasoning: {decision.reasoning}")

            if is_correct:
                total_correct += 1
            total_tests += 1

    # Summary
    print("\n" + "="*60)
    print(f"DISAMBIGUATION TEST RESULTS: {total_correct}/{total_tests} correct")
    print(f"Accuracy: {total_correct/total_tests*100:.1f}%")
    print("="*60)

    return total_correct, total_tests


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Archivist PoC Test")
    parser.add_argument("--mode", choices=["full", "disambiguation"], default="full",
                       help="Test mode: 'full' for full data test, 'disambiguation' for specific cases")
    parser.add_argument("--multiplier", type=int, default=None,
                       help="Sample multiplier (1=quick ~34 texts, 10=full ~340 texts)")
    args = parser.parse_args()

    # Update SAMPLE_MULTIPLIER if provided via argparse
    if args.multiplier is not None:
        SAMPLE_MULTIPLIER = args.multiplier
        # Update SOURCES with new multiplier - use base sizes
        base_sizes = {"gutenberg": 15, "arthurian": 1, "ctext": 2, "theoi": 3,
                      "britannica": 5, "perseus": 3, "worldhistory": 3, "stanford": 2}
        for name, source in SOURCES.items():
            source["sample_size"] = base_sizes.get(name, 1) * args.multiplier
        print(f"Updated SAMPLE_MULTIPLIER={SAMPLE_MULTIPLIER}")

    if args.mode == "full":
        asyncio.run(run_archivist_test())
    else:
        asyncio.run(test_disambiguation_cases())
