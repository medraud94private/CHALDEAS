"""Test book extraction with GPT-5.1-chat-latest"""
import asyncio
import json
import re
import time
import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

BOOKS = [
    ('greek_roman_myths', 'Greek/Roman Mythology'),
    ('plato_republic', 'Plato Republic - Philosophy'),
    ('marcus_aurelius_meditations', 'Marcus Aurelius Meditations - Stoicism'),
    ('bulfinch_mythology', 'Bulfinch Mythology'),
]

# Split books into chunks
def get_chunks(content, chunk_size=3000, overlap=200):
    """Split content into overlapping chunks"""
    # Skip Gutenberg header
    start_markers = ['*** START', 'CHAPTER', 'BOOK I', 'PART I', 'INTRODUCTION']
    start_idx = 0
    for marker in start_markers:
        idx = content.find(marker)
        if idx > 0 and idx < 10000:
            start_idx = idx
            break

    # Skip Gutenberg footer
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


async def extract_openai(client, text, book_title):
    """Extract entities using GPT-5.1"""
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
        response = await client.chat.completions.create(
            model='gpt-5.1-chat-latest',
            messages=[{'role': 'user', 'content': prompt}],
            max_completion_tokens=800
        )

        content = response.choices[0].message.content
        tokens_in = response.usage.prompt_tokens
        tokens_out = response.usage.completion_tokens
        cost = (tokens_in / 1e6 * 2.5) + (tokens_out / 1e6 * 10)

        # Parse JSON
        m = re.search(r'\{[\s\S]*\}', content)
        if m:
            data = json.loads(m.group())
            return data, tokens_in, tokens_out, cost

        return None, tokens_in, tokens_out, cost

    except Exception as e:
        print(f"    Error: {e}")
        return None, 0, 0, 0


async def process_book(client, filename, title):
    """Process entire book"""
    filepath = f'poc/data/book_samples/{filename}.txt'

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    chunks = get_chunks(content, chunk_size=2500)

    print(f"\n### {title}", flush=True)
    print(f"    File size: {len(content):,} chars", flush=True)
    print(f"    Chunks: {len(chunks)}", flush=True)

    all_persons = set()
    all_locations = set()
    all_concepts = set()
    all_events = set()

    total_tokens_in = 0
    total_tokens_out = 0
    total_cost = 0

    # Process ALL chunks
    max_chunks = len(chunks)

    start_time = time.time()

    for i, chunk in enumerate(chunks[:max_chunks]):
        data, t_in, t_out, cost = await extract_openai(client, chunk, title)
        total_tokens_in += t_in
        total_tokens_out += t_out
        total_cost += cost

        if data:
            all_persons.update(data.get('persons', []))
            all_locations.update(data.get('locations', []))
            all_concepts.update(data.get('concepts', []))
            all_events.update(data.get('events', []))

        # Progress every 10 chunks
        if (i + 1) % 10 == 0:
            elapsed = time.time() - start_time
            eta = elapsed / (i + 1) * (max_chunks - i - 1)
            print(f"    [{i+1}/{max_chunks}] ${total_cost:.3f} | ETA: {eta/60:.1f}min", flush=True)

    print(f"    Tokens: {total_tokens_in:,} in / {total_tokens_out:,} out")
    print(f"    Cost: ${total_cost:.4f}")
    print(f"    Results:")
    print(f"      Persons ({len(all_persons)}): {sorted(all_persons)[:10]}")
    print(f"      Locations ({len(all_locations)}): {sorted(all_locations)[:8]}")
    print(f"      Concepts ({len(all_concepts)}): {sorted(all_concepts)[:8]}")
    print(f"      Events ({len(all_events)}): {sorted(all_events)[:5]}")

    return {
        'persons': list(all_persons),
        'locations': list(all_locations),
        'concepts': list(all_concepts),
        'events': list(all_events),
        'tokens_in': total_tokens_in,
        'tokens_out': total_tokens_out,
        'cost': total_cost,
        'chunks': max_chunks
    }


async def main():
    print("=" * 70)
    print("Book Extraction with GPT-5.1-chat-latest")
    print("=" * 70)

    client = AsyncOpenAI()

    all_results = {}
    total_cost = 0
    total_chunks = 0
    total_persons = set()
    total_locations = set()

    for filename, title in BOOKS:
        result = await process_book(client, filename, title)
        all_results[filename] = result
        total_cost += result['cost']
        total_chunks += result['chunks']
        total_persons.update(result['persons'])
        total_locations.update(result['locations'])

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Books processed: {len(BOOKS)}")
    print(f"Total chunks: {total_chunks}")
    print(f"Total cost: ${total_cost:.4f}")
    print(f"Unique persons found: {len(total_persons)}")
    print(f"Unique locations found: {len(total_locations)}")

    # Save results
    with open('poc/data/book_samples/extraction_results.json', 'w', encoding='utf-8') as f:
        json.dump({
            'results': {k: {**v, 'persons': list(v['persons']) if isinstance(v['persons'], set) else v['persons']}
                       for k, v in all_results.items()},
            'total_cost': total_cost,
            'total_persons': list(total_persons),
            'total_locations': list(total_locations)
        }, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to: poc/data/book_samples/extraction_results.json")


if __name__ == "__main__":
    asyncio.run(main())
