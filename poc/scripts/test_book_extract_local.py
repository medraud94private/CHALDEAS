"""Test book extraction with Local Model (llama3.1)"""
import asyncio
import json
import re
import time
import httpx

BOOKS = [
    ('greek_roman_myths', 'Greek/Roman Mythology'),
    ('plato_republic', 'Plato Republic - Philosophy'),
    ('marcus_aurelius_meditations', 'Marcus Aurelius Meditations - Stoicism'),
    ('bulfinch_mythology', 'Bulfinch Mythology'),
]

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.1:8b-instruct-q4_0"


def get_chunks(content, chunk_size=3000, overlap=200):
    """Split content into overlapping chunks"""
    start_markers = ['*** START', 'CHAPTER', 'BOOK I', 'PART I', 'INTRODUCTION']
    start_idx = 0
    for marker in start_markers:
        idx = content.find(marker)
        if idx > 0 and idx < 10000:
            start_idx = idx
            break

    end_markers = ['*** END', 'End of the Project', 'End of Project']
    end_idx = len(content)
    for marker in end_markers:
        idx = content.find(marker)
        if idx > 0:
            end_idx = idx
            break

    text = content[start_idx:end_idx]

    chunks = []
    pos = 0
    while pos < len(text):
        chunk = text[pos:pos + chunk_size]
        if chunk.strip():
            chunks.append(chunk)
        pos += chunk_size - overlap

    return chunks


async def extract_local(client, text, book_title):
    """Extract entities using local llama3.1"""
    prompt = f"""Extract named entities from this text about {book_title}.

TEXT:
{text}

Return ONLY a JSON object with these exact keys:
{{"persons": ["name1"], "locations": ["place1"], "concepts": ["idea1"], "events": ["event1"]}}

Include:
- persons: historical figures, philosophers, gods, mythological beings
- locations: cities, countries, regions, mythological places
- concepts: philosophical ideas, abstract concepts
- events: historical events, mythological events

JSON:"""

    try:
        response = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                'model': OLLAMA_MODEL,
                'prompt': prompt,
                'stream': False,
                'options': {'num_predict': 800, 'temperature': 0.1}
            },
            timeout=120.0
        )

        content = response.json().get('response', '')

        # Parse JSON
        m = re.search(r'\{[\s\S]*\}', content)
        if m:
            try:
                data = json.loads(m.group())
                return data
            except json.JSONDecodeError:
                # Try to fix common issues
                pass

        return None

    except Exception as e:
        print(f"    Error: {e}")
        return None


async def process_book(client, filename, title):
    """Process entire book"""
    filepath = f'poc/data/book_samples/{filename}.txt'

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    chunks = get_chunks(content, chunk_size=2500)

    print(f"\n### {title}")
    print(f"    File size: {len(content):,} chars")
    print(f"    Chunks: {len(chunks)}")
    print(flush=True)

    all_persons = set()
    all_locations = set()
    all_concepts = set()
    all_events = set()

    max_chunks = len(chunks)
    start_time = time.time()

    for i, chunk in enumerate(chunks[:max_chunks]):
        data = await extract_local(client, chunk, title)

        if data:
            all_persons.update(data.get('persons', []))
            all_locations.update(data.get('locations', []))
            all_concepts.update(data.get('concepts', []))
            all_events.update(data.get('events', []))

        # Progress every 10 chunks
        if (i + 1) % 10 == 0:
            elapsed = time.time() - start_time
            eta = elapsed / (i + 1) * (max_chunks - i - 1)
            print(f"    [{i+1}/{max_chunks}] {elapsed/60:.1f}min elapsed | ETA: {eta/60:.1f}min", flush=True)

    total_time = time.time() - start_time
    print(f"    Time: {total_time/60:.1f} min")
    print(f"    Results:")
    print(f"      Persons ({len(all_persons)}): {sorted(all_persons)[:10]}")
    print(f"      Locations ({len(all_locations)}): {sorted(all_locations)[:8]}")
    print(f"      Concepts ({len(all_concepts)}): {sorted(all_concepts)[:8]}")
    print(f"      Events ({len(all_events)}): {sorted(all_events)[:5]}")
    print(flush=True)

    return {
        'persons': list(all_persons),
        'locations': list(all_locations),
        'concepts': list(all_concepts),
        'events': list(all_events),
        'time_sec': total_time,
        'chunks': max_chunks
    }


async def main():
    print("=" * 70)
    print("Book Extraction with Local Model (llama3.1)")
    print("=" * 70)
    print(flush=True)

    async with httpx.AsyncClient() as client:
        all_results = {}
        total_time = 0
        total_chunks = 0
        total_persons = set()
        total_locations = set()

        for filename, title in BOOKS:
            result = await process_book(client, filename, title)
            all_results[filename] = result
            total_time += result['time_sec']
            total_chunks += result['chunks']
            total_persons.update(result['persons'])
            total_locations.update(result['locations'])

        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Books processed: {len(BOOKS)}")
        print(f"Total chunks: {total_chunks}")
        print(f"Total time: {total_time/60:.1f} min ({total_time/3600:.2f} hours)")
        print(f"Cost: $0 (local model)")
        print(f"Unique persons found: {len(total_persons)}")
        print(f"Unique locations found: {len(total_locations)}")

        # Save results
        with open('poc/data/book_samples/extraction_results_local.json', 'w', encoding='utf-8') as f:
            json.dump({
                'results': all_results,
                'total_time_sec': total_time,
                'total_persons': list(total_persons),
                'total_locations': list(total_locations)
            }, f, indent=2, ensure_ascii=False)

        print(f"\nResults saved to: poc/data/book_samples/extraction_results_local.json")


if __name__ == "__main__":
    asyncio.run(main())
