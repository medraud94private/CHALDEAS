"""Test book extraction with Local Model (llama3.1) - Batch 2

Features:
- Chunk-by-chunk incremental saving
- Auto-resume from last processed chunk
"""
import asyncio
import json
import os
import re
import time
import httpx

BOOKS = [
    # Already processed:
    # ('arabian_nights', 'Arabian Nights - Middle Eastern Tales'),
    # ('odyssey_homer', 'Homer Odyssey - Greek Epic'),
    # ('herodotus_histories', 'Herodotus Histories - Ancient History'),
    # ('norse_mythology', 'Norse Mythology - Scandinavian Myths'),
    ('plutarch_lives', 'Plutarch Lives - Greek/Roman Biography'),
]

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.1:8b-instruct-q4_0"
TEMP_DIR = "poc/data/book_samples/temp"


def get_temp_path(filename):
    """Get temp file path for incremental saving"""
    os.makedirs(TEMP_DIR, exist_ok=True)
    return f"{TEMP_DIR}/{filename}_progress.json"


def load_progress(filename):
    """Load existing progress if available"""
    temp_path = get_temp_path(filename)
    if os.path.exists(temp_path):
        with open(temp_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def save_progress(filename, data):
    """Save current progress"""
    temp_path = get_temp_path(filename)
    with open(temp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)


def clear_progress(filename):
    """Clear temp file after completion"""
    temp_path = get_temp_path(filename)
    if os.path.exists(temp_path):
        os.remove(temp_path)


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
                'options': {
                    'num_predict': 800,
                    'temperature': 0.1,
                    'num_ctx': 4096,      # 컨텍스트 제한 (기본 8192 → 절반)
                    'num_gpu': 99,        # 모든 레이어 GPU에
                }
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
                pass

        return None

    except Exception as e:
        print(f"    Error: {e}")
        return None


async def process_book(client, filename, title):
    """Process entire book with incremental saving"""
    filepath = f'poc/data/book_samples/{filename}.txt'

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    chunks = get_chunks(content, chunk_size=2500)
    max_chunks = len(chunks)

    # Load existing progress
    progress = load_progress(filename)
    start_chunk = 0
    elapsed_before = 0

    if progress:
        start_chunk = progress.get('last_chunk', 0) + 1
        elapsed_before = progress.get('elapsed_sec', 0)
        all_persons = set(progress.get('persons', []))
        all_locations = set(progress.get('locations', []))
        all_concepts = set(progress.get('concepts', []))
        all_events = set(progress.get('events', []))
        print(f"\n### {title} (RESUMING from chunk {start_chunk}/{max_chunks})")
    else:
        all_persons = set()
        all_locations = set()
        all_concepts = set()
        all_events = set()
        print(f"\n### {title}")

    print(f"    File size: {len(content):,} chars")
    print(f"    Chunks: {len(chunks)}")
    if start_chunk > 0:
        print(f"    Skipping {start_chunk} already processed chunks")
    print(flush=True)

    start_time = time.time()

    for i in range(start_chunk, max_chunks):
        chunk = chunks[i]
        data = await extract_local(client, chunk, title)

        if data:
            all_persons.update(data.get('persons', []))
            all_locations.update(data.get('locations', []))
            all_concepts.update(data.get('concepts', []))
            all_events.update(data.get('events', []))

        # Save progress after each chunk
        current_elapsed = time.time() - start_time + elapsed_before
        save_progress(filename, {
            'last_chunk': i,
            'elapsed_sec': current_elapsed,
            'persons': list(all_persons),
            'locations': list(all_locations),
            'concepts': list(all_concepts),
            'events': list(all_events)
        })

        # Progress every 10 chunks
        if (i + 1) % 10 == 0:
            elapsed = time.time() - start_time
            remaining = max_chunks - i - 1
            if i > start_chunk:
                rate = elapsed / (i - start_chunk + 1)
                eta = rate * remaining
            else:
                eta = 0
            print(f"    [{i+1}/{max_chunks}] {current_elapsed/60:.1f}min total | ETA: {eta/60:.1f}min", flush=True)

    total_time = time.time() - start_time + elapsed_before

    # Clear temp file on completion
    clear_progress(filename)

    print(f"    Time: {total_time/60:.1f} min")
    print(f"    Results:")
    # Safe ASCII printing to avoid encoding issues
    persons_sample = [p.encode('ascii', 'replace').decode() for p in sorted(all_persons)[:10]]
    locations_sample = [l.encode('ascii', 'replace').decode() for l in sorted(all_locations)[:8]]
    concepts_sample = [c.encode('ascii', 'replace').decode() for c in sorted(all_concepts)[:8]]
    events_sample = [e.encode('ascii', 'replace').decode() for e in sorted(all_events)[:5]]
    print(f"      Persons ({len(all_persons)}): {persons_sample}")
    print(f"      Locations ({len(all_locations)}): {locations_sample}")
    print(f"      Concepts ({len(all_concepts)}): {concepts_sample}")
    print(f"      Events ({len(all_events)}): {events_sample}")
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
    print("Book Extraction with Local Model (llama3.1) - Batch 2")
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
        with open('poc/data/book_samples/extraction_results_local_batch2.json', 'w', encoding='utf-8') as f:
            json.dump({
                'results': all_results,
                'total_time_sec': total_time,
                'total_persons': list(total_persons),
                'total_locations': list(total_locations)
            }, f, indent=2, ensure_ascii=False)

        print(f"\nResults saved to: poc/data/book_samples/extraction_results_local_batch2.json")


if __name__ == "__main__":
    asyncio.run(main())
