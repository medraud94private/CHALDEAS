"""Test book extraction with local model"""
import asyncio
import httpx
import json
import re

BOOKS = [
    ('greek_roman_myths', 'CHAPTER II', 'Greek Myths'),
    ('plato_republic', 'BOOK I', 'Plato Republic'),
    ('marcus_aurelius_meditations', 'THE FIRST BOOK', 'Marcus Aurelius'),
    ('bulfinch_mythology', 'CHAPTER I', 'Bulfinch Mythology'),
]

async def extract(text, title):
    prompt = f"""Extract named entities from this text about {title}.

TEXT:
{text[:1800]}

Respond with ONLY a JSON object, no other text:
{{"persons": ["name1", "name2"], "locations": ["place1"], "concepts": ["idea1"]}}"""

    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post('http://localhost:11434/api/generate', json={
            'model': 'llama3.1:8b-instruct-q4_0',
            'prompt': prompt,
            'stream': False,
            'options': {'num_predict': 800, 'temperature': 0.1}
        })
        raw = r.json().get('response', '')

        # Debug: show raw
        print(f"  Raw ({len(raw)} chars): {raw[:200]}...")

        # Try to extract JSON
        # Pattern 1: Simple object
        m = re.search(r'\{[^{}]*"persons"[^{}]*\}', raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except:
                pass

        # Pattern 2: Any JSON object
        m = re.search(r'\{[\s\S]*?\}', raw)
        if m:
            try:
                return json.loads(m.group())
            except:
                pass

        return None


async def main():
    print("=" * 60)
    print("Book Extraction Test")
    print("=" * 60)
    print()

    for filename, marker, title in BOOKS:
        print(f"### {title}")

        with open(f'poc/data/book_samples/{filename}.txt', 'r', encoding='utf-8') as f:
            content = f.read()

        start = content.find(marker)
        if start == -1:
            start = 5000
        sample = content[start:start+2000]

        data = await extract(sample, title)

        if data:
            print(f"  Persons: {data.get('persons', [])[:8]}")
            print(f"  Locations: {data.get('locations', [])[:5]}")
            print(f"  Concepts: {data.get('concepts', [])[:5]}")
        else:
            print("  Parse FAILED")
        print()


if __name__ == "__main__":
    asyncio.run(main())
