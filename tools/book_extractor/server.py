"""
Book Extractor - Local Management Tool
ZIM 파일에서 책을 추출하고 Ollama/OpenAI로 엔티티 추출

Usage:
    cd tools/book_extractor
    python server.py

    Then open: http://localhost:8200
"""

import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Optional, List
from collections import defaultdict
from datetime import datetime

import httpx
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import entity matcher
from entity_matcher import EntityMatcher, MatchResult

# Paths
BASE_DIR = Path(__file__).parent
PROJECT_ROOT = BASE_DIR.parent.parent
BOOKS_DIR = PROJECT_ROOT / "poc" / "data" / "book_samples"
RESULTS_DIR = BOOKS_DIR / "extraction_results"
ZIM_PATH = PROJECT_ROOT / "data" / "kiwix" / "gutenberg_en_all.zim"
ZIM_RESULTS_PATH = BASE_DIR / "zim_search_results.json"
PRIORITY_PATH = BASE_DIR / "extraction_priority.json"
QUEUE_STATE_PATH = BASE_DIR / "queue_state.json"

def safe_filename(name: str) -> str:
    """Remove/replace characters that are invalid in Windows filenames"""
    # Replace invalid characters: \ / : * ? " < > |
    invalid_chars = r'\/:*?"<>|'
    for c in invalid_chars:
        name = name.replace(c, '_')
    return name

# Model settings
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.1:8b-instruct-q4_0"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Available models (prices per 1M tokens)
MODELS = {
    "ollama": {"name": "Ollama (llama3.1:8b)", "type": "ollama", "input_price": 0, "output_price": 0},
    "gpt-5-mini": {"name": "GPT-5-mini (~$38)", "type": "openai", "model_id": "gpt-5-mini", "input_price": 0.25, "output_price": 2.00},
    "gpt-5.1-chat-latest": {"name": "GPT-5.1 (~$190)", "type": "openai", "model_id": "gpt-5.1-chat-latest", "input_price": 1.25, "output_price": 10.00},
}

# Create dirs
RESULTS_DIR.mkdir(exist_ok=True)

# ZIM Archive (lazy loaded)
_zim_archive = None

def get_zim_archive():
    """Get ZIM archive (lazy loading)"""
    global _zim_archive
    if _zim_archive is None:
        try:
            from libzim.reader import Archive
            if ZIM_PATH.exists():
                _zim_archive = Archive(str(ZIM_PATH))
                print(f"ZIM loaded: {_zim_archive.entry_count:,} entries")
        except Exception as e:
            print(f"Failed to load ZIM: {e}")
    return _zim_archive


app = FastAPI(title="Book Extractor", version="2.0")

# Speed modes: high/medium/low/quiet - num_gpu controls how many layers on GPU
SPEED_MODES = {
    "turbo": {"chunk_delay": 0.1, "num_gpu": 50, "num_ctx": 4096, "description": "Turbo (50 layers)"},
    "high": {"chunk_delay": 0.2, "num_gpu": 30, "num_ctx": 4096, "description": "High (30 layers)"},
    "medium": {"chunk_delay": 0.3, "num_gpu": 20, "num_ctx": 4096, "description": "Medium (20 layers)"},
    "low": {"chunk_delay": 1.0, "num_gpu": 10, "num_ctx": 4096, "description": "Low (10 layers)"},
    "quiet": {"chunk_delay": 2.0, "num_gpu": 0, "num_ctx": 4096, "description": "Quiet (CPU only)"},
}

# Chunk extraction settings
CHUNK_TIMEOUT = 300  # 5 minutes max per chunk
MAX_CHUNK_RETRIES = 3  # Max retries per chunk before skipping

# State
extraction_tasks = {}
queue_state = {
    "running": False,
    "paused": False,
    "current_model": "ollama",
    "current_book": None,
    "completed": 0,
    "total": 0,
    "start_time": None,
    "books_queue": [],
    "total_cost": 0.0,
    "errors": [],
    "speed_mode": "high",
    # Chunk progress tracking
    "current_chunk": 0,
    "total_chunks": 0,
    "chunk_start_time": None,
    "book_start_time": None,
}

# Statistics tracking
extraction_stats = {
    "completed_books": [],  # List of {title, size, duration, chunks, speed}
    "session_start": None,
    "total_chunks_processed": 0,
    "total_chars_processed": 0,
}

# Matching state
matching_tasks = {}  # book_id -> {status, progress, results, ...}
matching_settings = {
    "auto_match": False,  # Auto-start matching after extraction
    "auto_confirm_threshold": 0.95,  # Auto-confirm matches above this confidence
}

# Auto-processing state
auto_state = {
    "mode": None,  # 'extraction', 'matching', 'duplicates'
    "running": False,
    "paused": False,
    "progress": 0,
    "total": 0,
    "current_item": None,
    "completed": 0,
    "errors": [],
    "start_time": None,
}

# Post-processing settings
post_process_settings = {
    "auto_context": True,   # Auto extract context after extraction
    "auto_db_match": True,  # Auto match to DB after context extraction
}

# Post-processing stats
post_process_stats = {
    "contexts_created": 0,
    "mentions_created": 0,
    "last_processed": None,
}

# Model info for display
MODEL_INFO = {
    "extraction": {
        "primary": "Ollama llama3.1:8b-instruct-q4_0",
        "fallback": "OpenAI gpt-5-mini",
        "cost": "Free (local) / ~$0.25/1M tokens",
    },
    "matching": {
        "embedding": "OpenAI text-embedding-3-small (1536 dim)",
        "llm": "OpenAI gpt-5-mini",
        "cost": "~$0.25/1M tokens + ~$0.02/1M embed tokens",
    },
    "duplicates": {
        "method": "Wikidata QID merge",
        "cost": "Free (DB only)",
    }
}


def save_queue_state():
    """Save queue state to file for persistence"""
    state = {**queue_state, "books_queue": queue_state["books_queue"][:100]}  # Limit saved queue
    with open(QUEUE_STATE_PATH, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2)


def load_queue_state():
    """Load queue state from file"""
    global queue_state
    if QUEUE_STATE_PATH.exists():
        try:
            with open(QUEUE_STATE_PATH, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                queue_state.update(saved)
        except:
            pass


def load_zim_books():
    """Load books from ZIM search results"""
    if not ZIM_RESULTS_PATH.exists():
        return {"categories": {}, "total": 0}

    with open(ZIM_RESULTS_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Group by servant/category for display
    by_servant = data.get("by_servant", {})

    # Also load priority list
    priority_books = {}
    if PRIORITY_PATH.exists():
        with open(PRIORITY_PATH, 'r', encoding='utf-8') as f:
            priority_data = json.load(f)
            priority_books = priority_data.get("by_category", {})

    return {
        "by_servant": by_servant,
        "by_category": priority_books,
        "summary": data.get("summary", {})
    }


def get_book_content_from_zim(path: str) -> Optional[str]:
    """Get book content from ZIM file"""
    zim = get_zim_archive()
    if not zim:
        return None

    try:
        entry = zim.get_entry_by_path(path)
        item = entry.get_item()
        content = bytes(item.content).decode('utf-8', errors='replace')

        # Clean HTML while preserving structure
        if '<html' in content.lower() or '<body' in content.lower():
            # Remove script and style
            content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
            content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)

            # Convert block elements to newlines (preserves structure)
            content = re.sub(r'</?(h[1-6]|p|div|br|tr|li)[^>]*>', '\n', content, flags=re.IGNORECASE)

            # Remove remaining HTML tags
            content = re.sub(r'<[^>]+>', '', content)

            # Normalize whitespace while preserving newlines
            content = re.sub(r'[ \t]+', ' ', content)  # Collapse spaces/tabs only
            content = re.sub(r'\n\s*\n+', '\n\n', content)  # Normalize multiple newlines

        return content.strip()
    except Exception as e:
        print(f"Error reading ZIM entry {path}: {e}")
        return None


def detect_book_structure(content: str) -> dict:
    """Detect what kind of structure a book has"""
    # Patterns to detect (in priority order)
    patterns = [
        ("book", r'\nBOOK [IVXLC]+[.:]?\s*\n'),   # Epic poetry: BOOK I, BOOK II
        ("chapter", r'\nCHAPTER [IVXLC0-9]+[.:]?\s*\n'),  # Standard chapters
        ("part", r'\nPART [IVXLC0-9]+[.:]?\s*\n'),     # Multi-part works
        ("act", r'\nACT [IVXLC]+[.:]?\s*\n'),          # Plays
        ("section", r'\nSECTION [IVXLC0-9]+[.:]?\s*\n'),  # Academic works
    ]

    for struct_type, pattern in patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        if len(matches) >= 3:  # At least 3 occurrences for main patterns
            cleaned = [m.strip() for m in matches]
            # Deduplicate while preserving order
            unique_sections = []
            seen = set()
            for s in cleaned:
                s_upper = s.upper()
                if s_upper not in seen:
                    seen.add(s_upper)
                    unique_sections.append(s)
            return {
                "type": struct_type,
                "pattern": pattern,
                "count": len(matches),
                "sections": unique_sections
            }

    # Check for Plutarch-style ALL CAPS headers (names in uppercase)
    # These are standalone lines with 4-25 uppercase letters
    caps_pattern = r'\n([A-Z][A-Z ]{3,24})\n'
    matches = re.findall(caps_pattern, content)
    if matches:
        # Filter to likely chapter titles (not random text)
        # Must be followed by substantial content
        valid_headers = []
        for m in matches:
            name = m.strip()
            # Skip common non-header words
            skip_words = ['CONTENTS', 'INDEX', 'PREFACE', 'INTRODUCTION', 'FOOTNOTES', 'THE END', 'FINIS']
            if name not in skip_words and len(name) > 4:
                valid_headers.append(name)

        if len(valid_headers) >= 5:  # Need at least 5 for this pattern
            unique = list(dict.fromkeys(valid_headers))
            return {
                "type": "caps_title",
                "pattern": caps_pattern,
                "count": len(valid_headers),
                "sections": unique
            }

    return {"type": "none", "pattern": None, "count": 0, "sections": []}


def split_into_sections(content: str, structure: dict) -> list:
    """Split content into sections based on detected structure"""
    if structure["type"] == "none":
        return [{"name": "main", "content": content, "start": 0, "end": len(content)}]

    pattern = structure["pattern"]
    sections = []

    # Handle caps_title differently - need to match the exact pattern
    if structure["type"] == "caps_title":
        # Find all ALL CAPS headers
        for match in re.finditer(pattern, content):
            section_name = match.group(1).strip()  # Group 1 is the captured name
            # Skip common non-headers
            skip_words = ['CONTENTS', 'INDEX', 'PREFACE', 'INTRODUCTION', 'FOOTNOTES', 'THE END', 'FINIS']
            if section_name not in skip_words and len(section_name) > 4:
                start_pos = match.start()
                sections.append({
                    "name": section_name,
                    "start": start_pos
                })
    else:
        # Find all section markers with positions
        for match in re.finditer(pattern, content, re.IGNORECASE):
            section_name = match.group().strip()
            start_pos = match.start()
            sections.append({
                "name": section_name,
                "start": start_pos
            })

    if not sections:
        return [{"name": "main", "content": content, "start": 0, "end": len(content)}]

    # Sort by position and add content
    sections.sort(key=lambda x: x["start"])

    # Filter out TOC entries (sections that are too close together)
    filtered = []
    prev_start = -10000
    for section in sections:
        # Skip if too close to previous (likely TOC)
        if section["start"] - prev_start < 500:
            continue
        filtered.append(section)
        prev_start = section["start"]

    sections = filtered

    result = []
    for i, section in enumerate(sections):
        start = section["start"]
        end = sections[i + 1]["start"] if i + 1 < len(sections) else len(content)

        section_content = content[start:end]

        # Skip very short sections (likely TOC remnants)
        if len(section_content) < 500:
            continue

        result.append({
            "name": section["name"],
            "content": section_content,
            "start": start,
            "end": end
        })

    return result if result else [{"name": "main", "content": content, "start": 0, "end": len(content)}]


def get_hierarchical_chunks(content: str, chunk_size: int = 2500, overlap: int = 200) -> list:
    """Split content into chunks with hierarchical structure info"""
    # Find actual content start
    start_idx = 0
    for marker in ['*** START', '*** START OF THIS PROJECT', '*** START OF THE PROJECT']:
        idx = content.find(marker)
        if 0 < idx < 15000:
            # Find end of the start marker line
            newline = content.find('\n', idx)
            if newline > 0:
                start_idx = newline + 1
            else:
                start_idx = idx
            break

    # Find actual content end
    end_idx = len(content)
    for marker in ['*** END', 'End of the Project', 'End of Project']:
        idx = content.find(marker)
        if idx > start_idx:
            end_idx = idx
            break

    text = content[start_idx:end_idx].strip()

    # Detect book structure
    structure = detect_book_structure(text)

    # Split into sections
    sections = split_into_sections(text, structure)

    # Create chunks within each section
    chunks = []
    for section in sections:
        section_text = section["content"]
        section_name = section["name"]

        # Chunk within this section
        pos = 0
        chunk_in_section = 0
        while pos < len(section_text):
            chunk_text = section_text[pos:pos + chunk_size]
            if chunk_text.strip():
                chunks.append({
                    "text": chunk_text,
                    "section": section_name,
                    "section_type": structure["type"],
                    "chunk_in_section": chunk_in_section,
                    "global_char_start": section["start"] + pos + start_idx,
                    "section_char_start": pos
                })
                chunk_in_section += 1
            pos += chunk_size - overlap

    return chunks


def get_chunks(content: str, chunk_size: int = 2500, overlap: int = 200) -> list:
    """Split content into chunks (legacy - returns just text list)"""
    hierarchical = get_hierarchical_chunks(content, chunk_size, overlap)
    return [c["text"] for c in hierarchical]


def get_extraction_prompt(text: str, book_title: str) -> str:
    """Generate extraction prompt"""
    return f"""Extract named entities from this text about {book_title}.

TEXT:
{text}

Return ONLY a JSON object with these exact keys:
{{"persons": ["name1"], "locations": ["place1"], "events": ["event1"]}}

Include:
- persons: historical figures, gods, heroes, mythological beings
- locations: cities, countries, regions
- events: historical events, battles, mythological events

JSON:"""


async def extract_with_ollama(client: httpx.AsyncClient, text: str, book_title: str) -> Optional[dict]:
    """Extract entities from text using Ollama"""
    prompt = get_extraction_prompt(text, book_title)

    # Get speed mode settings
    mode = queue_state.get("speed_mode", "high")
    mode_settings = SPEED_MODES.get(mode, SPEED_MODES["high"])

    try:
        response = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                'model': OLLAMA_MODEL,
                'prompt': prompt,
                'stream': False,
                'options': {
                    'num_predict': 600,
                    'temperature': 0.1,
                    'num_ctx': mode_settings.get('num_ctx', 4096),
                    'num_gpu': mode_settings.get('num_gpu', 99),
                }
            },
            timeout=180.0
        )

        content = response.json().get('response', '')
        return parse_json_response(content)
    except Exception as e:
        print(f"Ollama error: {e}")
        return None


async def extract_with_openai(client: httpx.AsyncClient, text: str, book_title: str, model_key: str = "gpt-5-mini") -> Optional[dict]:
    """Extract entities from text using OpenAI"""
    if not OPENAI_API_KEY:
        print("OpenAI API key not set")
        return None

    # Get model ID from MODELS dict
    model_info = MODELS.get(model_key, {})
    model_id = model_info.get("model_id", model_key)

    prompt = get_extraction_prompt(text, book_title)

    try:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                'model': model_id,
                'messages': [
                    {"role": "system", "content": "You are an entity extraction assistant. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                'temperature': 0.1,
                'max_tokens': 500
            },
            timeout=60.0
        )

        data = response.json()
        if 'error' in data:
            print(f"OpenAI API error: {data['error']}")
            return None
        content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
        return parse_json_response(content)
    except Exception as e:
        print(f"OpenAI error: {e}")
        return None


def parse_json_response(content: str) -> Optional[dict]:
    """Parse JSON from model response"""
    m = re.search(r'\{[\s\S]*\}', content)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return None


async def extract_chunk(client: httpx.AsyncClient, text: str, book_title: str, model: str = "ollama") -> Optional[dict]:
    """Extract entities using selected model"""
    if model == "ollama":
        return await extract_with_ollama(client, text, book_title)
    else:
        return await extract_with_openai(client, text, book_title, model)


async def extract_chunk_with_retry(client: httpx.AsyncClient, text: str, book_title: str, model: str, chunk_num: int) -> tuple[Optional[dict], str]:
    """Extract chunk with timeout and retry logic
    Returns: (result, status) where status is 'success', 'skipped', or 'failed'
    """
    for attempt in range(MAX_CHUNK_RETRIES):
        try:
            result = await asyncio.wait_for(
                extract_chunk(client, text, book_title, model),
                timeout=CHUNK_TIMEOUT
            )
            if result:
                return result, "success"
            # Empty result, retry
            print(f"[Chunk {chunk_num}] Empty response, attempt {attempt + 1}/{MAX_CHUNK_RETRIES}")
        except asyncio.TimeoutError:
            print(f"[Chunk {chunk_num}] Timeout after {CHUNK_TIMEOUT}s, attempt {attempt + 1}/{MAX_CHUNK_RETRIES}")
        except Exception as e:
            print(f"[Chunk {chunk_num}] Error: {e}, attempt {attempt + 1}/{MAX_CHUNK_RETRIES}")

        # Wait before retry
        if attempt < MAX_CHUNK_RETRIES - 1:
            await asyncio.sleep(5)

    print(f"[Chunk {chunk_num}] Skipped after {MAX_CHUNK_RETRIES} failed attempts")
    return None, "skipped"


async def run_extraction(book_id: str, zim_path: str, title: str, model: str = "ollama"):
    """Background task to extract entities from a ZIM book"""
    global extraction_tasks, queue_state, extraction_stats

    # Get content from ZIM
    content = get_book_content_from_zim(zim_path)
    if not content:
        extraction_tasks[book_id] = {"status": "error", "error": f"Failed to read from ZIM: {zim_path}"}
        return

    # Use hierarchical chunking
    hierarchical_chunks = get_hierarchical_chunks(content)
    total_chunks = len(hierarchical_chunks)
    content_size = len(content)

    # Detect structure for metadata
    structure = detect_book_structure(content)

    # Update queue state with chunk info
    queue_state["total_chunks"] = total_chunks
    queue_state["current_chunk"] = 0
    queue_state["book_start_time"] = time.time()

    extraction_tasks[book_id] = {
        "status": "running",
        "progress": 0,
        "total": total_chunks,
        "start_time": time.time(),
        "model": model,
        "structure": structure,
        "persons": set(),
        "locations": set(),
        "events": set(),
        "chunk_results": []  # Track per-chunk results for source attribution
    }

    async with httpx.AsyncClient() as client:
        for i, chunk_info in enumerate(hierarchical_chunks):
            # Update current chunk in queue state
            queue_state["current_chunk"] = i + 1
            if extraction_tasks[book_id]["status"] == "cancelled":
                break

            # Check if queue is paused
            if queue_state["paused"] and queue_state["running"]:
                while queue_state["paused"]:
                    await asyncio.sleep(1)

            chunk_text = chunk_info["text"]
            data, chunk_status = await extract_chunk_with_retry(client, chunk_text, title, model, i + 1)

            # Track skipped chunks
            if chunk_status == "skipped":
                extraction_tasks[book_id].setdefault("skipped_chunks", []).append(i + 1)

            if data:
                # Handle both strings and dicts (LLM sometimes returns dicts like {"name": "Zeus"})
                def extract_name(item):
                    if isinstance(item, str):
                        return item
                    elif isinstance(item, dict):
                        return item.get('name') or item.get('title') or item.get('location') or next(iter(item.values()), None)
                    return None

                persons = [n for n in (extract_name(p) for p in data.get('persons', [])) if n]
                locations = [n for n in (extract_name(l) for l in data.get('locations', [])) if n]
                events = [n for n in (extract_name(e) for e in data.get('events', [])) if n]

                extraction_tasks[book_id]["persons"].update(persons)
                extraction_tasks[book_id]["locations"].update(locations)
                extraction_tasks[book_id]["events"].update(events)

                # Save chunk-level results with hierarchical structure
                extraction_tasks[book_id]["chunk_results"].append({
                    "chunk_id": i,
                    "section": chunk_info["section"],
                    "section_type": chunk_info["section_type"],
                    "chunk_in_section": chunk_info["chunk_in_section"],
                    "global_char_start": chunk_info["global_char_start"],
                    "section_char_start": chunk_info["section_char_start"],
                    "text_preview": chunk_text[:200] + "..." if len(chunk_text) > 200 else chunk_text,
                    "persons": persons,
                    "locations": locations,
                    "events": events
                })

            extraction_tasks[book_id]["progress"] = i + 1

            # Delay based on speed mode
            delay = SPEED_MODES.get(queue_state["speed_mode"], SPEED_MODES["high"])["chunk_delay"]
            if model != "ollama":
                delay = max(delay, 0.2)  # Rate limit for OpenAI
            await asyncio.sleep(delay)

    # Save results
    elapsed = time.time() - extraction_tasks[book_id]["start_time"]
    results = {
        "book_id": book_id,
        "zim_path": zim_path,
        "title": title,
        "model": model,
        "structure": {
            "type": structure["type"],
            "section_count": structure["count"],
            "sections": structure["sections"][:50]  # Limit to 50 section names
        },
        "persons": list(extraction_tasks[book_id]["persons"]),
        "locations": list(extraction_tasks[book_id]["locations"]),
        "events": list(extraction_tasks[book_id]["events"]),
        "chunk_results": extraction_tasks[book_id]["chunk_results"],  # Include chunk-level data with hierarchy
        "chunks_processed": extraction_tasks[book_id]["progress"],
        "total_chunks": total_chunks,
        "skipped_chunks": extraction_tasks[book_id].get("skipped_chunks", []),
        "elapsed_seconds": elapsed,
        "source": "gutenberg_zim"
    }

    result_path = RESULTS_DIR / f"{safe_filename(book_id)}_extraction.json"
    result_size = 0
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
        result_size = f.tell()

    extraction_tasks[book_id]["status"] = "completed"
    extraction_tasks[book_id]["results"] = results

    # Update statistics
    book_duration = time.time() - queue_state.get("book_start_time", time.time())
    speed = (result_size / 1024) / (book_duration / 60) if book_duration > 0 else 0
    extraction_stats["completed_books"].append({
        "title": title[:60],
        "book_id": book_id,
        "size_kb": result_size / 1024,
        "duration_min": book_duration / 60,
        "chunks": total_chunks,
        "speed_kb_per_min": speed,
        "content_chars": content_size,
        "completed_at": datetime.now().isoformat()
    })
    extraction_stats["total_chunks_processed"] += total_chunks
    extraction_stats["total_chars_processed"] += content_size
    # Keep only last 100 books in stats
    if len(extraction_stats["completed_books"]) > 100:
        extraction_stats["completed_books"] = extraction_stats["completed_books"][-100:]


async def run_post_processing(book_id: str, title: str):
    """Run post-processing: context extraction + DB matching"""
    global post_process_stats

    if not post_process_settings["auto_context"] and not post_process_settings["auto_db_match"]:
        return

    print(f"[PostProcess] Starting for: {title[:50]}...")

    try:
        # Import post-processing modules
        import sys
        cleanup_path = PROJECT_ROOT / "poc" / "scripts" / "cleanup"
        sys.path.insert(0, str(cleanup_path))

        from extract_book_contexts import extract_contexts_from_book
        from match_books_local import match_book_entities, get_wiki_archive
        import psycopg2
        from psycopg2.extras import RealDictCursor

        # 1. Extract context from extraction result
        if post_process_settings["auto_context"]:
            extraction_file = RESULTS_DIR / f"{safe_filename(book_id)}_extraction.json"
            if extraction_file.exists():
                context_result = extract_contexts_from_book(extraction_file)

                # Save context file
                contexts_dir = PROJECT_ROOT / "poc" / "data" / "book_contexts"
                contexts_dir.mkdir(parents=True, exist_ok=True)
                context_file = contexts_dir / f"{safe_filename(book_id)}_contexts.json"

                with open(context_file, 'w', encoding='utf-8') as f:
                    json.dump(context_result, f, ensure_ascii=False, indent=2)

                post_process_stats["contexts_created"] += 1
                print(f"[PostProcess] Context extracted: {context_result['stats']['persons']} persons")

        # 2. Match to DB
        if post_process_settings["auto_db_match"]:
            context_file = PROJECT_ROOT / "poc" / "data" / "book_contexts" / f"{safe_filename(book_id)}_contexts.json"
            if context_file.exists():
                # Initialize Wikipedia ZIM
                get_wiki_archive()

                conn = psycopg2.connect(
                    host='localhost', port=5432, dbname='chaldeas',
                    user='chaldeas', password='chaldeas_dev'
                )

                stats = {
                    'db_match': 0,
                    'wiki_to_db': 0,
                    'wiki_new': 0,
                    'not_found': 0,
                    'mentions_created': 0
                }

                match_book_entities(context_file, conn, stats, dry_run=False)
                conn.close()

                post_process_stats["mentions_created"] += stats["mentions_created"]
                print(f"[PostProcess] DB matched: {stats['db_match']} DB, {stats['wiki_to_db']} Wiki, {stats['mentions_created']} mentions")

        post_process_stats["last_processed"] = title

    except Exception as e:
        print(f"[PostProcess] Error: {e}")
        import traceback
        traceback.print_exc()


async def run_queue():
    """Process the extraction queue"""
    global queue_state

    queue_state["running"] = True
    queue_state["start_time"] = time.time()
    save_queue_state()

    while queue_state["books_queue"] and queue_state["running"]:
        if queue_state["paused"]:
            await asyncio.sleep(1)
            continue

        book = queue_state["books_queue"].pop(0)
        queue_state["current_book"] = book

        book_id = book["id"]
        zim_path = book["path"]
        title = book["title"]
        model = queue_state["current_model"]

        print(f"[Queue] Starting: {title.encode('ascii', 'replace').decode()} with {model}")

        try:
            await run_extraction(book_id, zim_path, title, model)
            queue_state["completed"] += 1

            # Run post-processing after successful extraction
            await run_post_processing(book_id, title)

        except Exception as e:
            queue_state["errors"].append({"book": title, "error": str(e)})
            print(f"[Queue] Error: {e}")

        queue_state["current_book"] = None
        save_queue_state()

        # Small delay between books
        await asyncio.sleep(1)

    queue_state["running"] = False
    queue_state["current_book"] = None
    save_queue_state()
    print(f"[Queue] Completed {queue_state['completed']} books")


# ============ API Endpoints ============

@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve main page"""
    html_path = BASE_DIR / "index.html"
    if html_path.exists():
        return FileResponse(html_path)
    return HTMLResponse("<h1>index.html not found</h1>")


@app.get("/api/books")
async def get_books():
    """Get all books from ZIM search results"""
    data = load_zim_books()

    # Format for frontend - group by category
    result = {
        "by_category": {},
        "by_servant": {},
        "summary": data.get("summary", {})
    }

    # Priority categories
    for category, books in data.get("by_category", {}).items():
        book_list = []
        for book in books:
            book_id = book["path"].replace("/", "_").replace(".", "_")
            # Use safe_filename for checking (same as when saving)
            status = "done" if (RESULTS_DIR / f"{safe_filename(book_id)}_extraction.json").exists() else "pending"

            book_entry = {
                "id": book_id,
                "title": book["title"],
                "path": book["path"],
                "status": status,
                "source": "zim"
            }

            # Add extraction status if running
            if book_id in extraction_tasks:
                task = extraction_tasks[book_id]
                book_entry["extraction_status"] = task["status"]
                book_entry["extraction_progress"] = task.get("progress", 0)
                book_entry["extraction_total"] = task.get("total", 0)

            book_list.append(book_entry)

        result["by_category"][category] = {
            "description": category,
            "books": book_list,
            "count": len(book_list)
        }

    # Servant-based (top 20)
    servant_counts = []
    for servant, books in data.get("by_servant", {}).items():
        servant_counts.append((servant, len(books), books))

    servant_counts.sort(key=lambda x: -x[1])

    for servant, count, books in servant_counts[:20]:
        book_list = []
        for book in books[:10]:  # Max 10 per servant
            book_id = book["path"].replace("/", "_").replace(".", "_")
            # Use safe_filename for checking (same as when saving)
            status = "done" if (RESULTS_DIR / f"{safe_filename(book_id)}_extraction.json").exists() else "pending"

            book_list.append({
                "id": book_id,
                "title": book["title"],
                "path": book["path"],
                "status": status,
                "query": book.get("query", ""),
                "source": "zim"
            })

        result["by_servant"][servant] = {
            "description": f"{servant} ({count} books)",
            "books": book_list,
            "count": count
        }

    return result


@app.get("/api/ollama/status")
async def ollama_status():
    """Check Ollama status and models"""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags", timeout=5.0)
            models = resp.json().get("models", [])
            return {
                "status": "online",
                "models": [m["name"] for m in models],
                "current_model": OLLAMA_MODEL
            }
    except:
        return {"status": "offline", "models": [], "current_model": OLLAMA_MODEL}


@app.get("/api/zim/status")
async def zim_status():
    """Check ZIM file status"""
    zim = get_zim_archive()
    if zim:
        return {
            "status": "loaded",
            "path": str(ZIM_PATH),
            "entry_count": zim.entry_count,
            "article_count": zim.article_count
        }
    return {
        "status": "not_loaded",
        "path": str(ZIM_PATH),
        "exists": ZIM_PATH.exists()
    }


@app.get("/api/zim/content/{path:path}")
async def get_zim_content(path: str):
    """Get content preview from ZIM"""
    content = get_book_content_from_zim(path)
    if content:
        return {
            "path": path,
            "length": len(content),
            "preview": content[:2000] + "..." if len(content) > 2000 else content
        }
    return {"error": "Not found"}


@app.get("/api/zim/structure/{path:path}")
async def get_zim_structure(path: str):
    """Analyze book structure from ZIM"""
    content = get_book_content_from_zim(path)
    if not content:
        return {"error": "Not found"}

    structure = detect_book_structure(content)
    hierarchical_chunks = get_hierarchical_chunks(content)

    # Group chunks by section
    sections_summary = {}
    for chunk in hierarchical_chunks:
        section = chunk["section"]
        if section not in sections_summary:
            sections_summary[section] = {"chunk_count": 0, "first_preview": chunk["text"][:150]}
        sections_summary[section]["chunk_count"] += 1

    return {
        "path": path,
        "length": len(content),
        "structure": {
            "type": structure["type"],
            "section_count": len(sections_summary),
            "sections": structure["sections"][:30]  # First 30 section names
        },
        "total_chunks": len(hierarchical_chunks),
        "sections_summary": sections_summary
    }


class ExtractRequest(BaseModel):
    book_id: str
    zim_path: str
    title: str


@app.post("/api/extract/start")
async def start_extraction(req: ExtractRequest, background_tasks: BackgroundTasks):
    """Start extraction for a book"""
    if req.book_id in extraction_tasks and extraction_tasks[req.book_id]["status"] == "running":
        return {"error": "Already running", "book_id": req.book_id}

    background_tasks.add_task(run_extraction, req.book_id, req.zim_path, req.title)
    return {"status": "started", "book_id": req.book_id}


@app.post("/api/extract/cancel/{book_id}")
async def cancel_extraction(book_id: str):
    """Cancel running extraction"""
    if book_id in extraction_tasks:
        extraction_tasks[book_id]["status"] = "cancelled"
        return {"status": "cancelled", "book_id": book_id}
    return {"error": "Not found"}


@app.get("/api/extract/status/{book_id}")
async def extraction_status(book_id: str):
    """Get extraction status"""
    if book_id in extraction_tasks:
        task = extraction_tasks[book_id]
        return {
            "book_id": book_id,
            "status": task["status"],
            "progress": task.get("progress", 0),
            "total": task.get("total", 0),
            "persons_count": len(task.get("persons", [])),
            "locations_count": len(task.get("locations", [])),
            "events_count": len(task.get("events", []))
        }
    return {"error": "Not found"}


@app.get("/api/results/{book_id}")
async def get_results(book_id: str):
    """Get extraction results"""
    result_path = RESULTS_DIR / f"{safe_filename(book_id)}_extraction.json"
    if result_path.exists():
        with open(result_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"error": "Results not found"}


@app.get("/api/results")
async def list_results():
    """List all available results"""
    results = []
    for f in RESULTS_DIR.glob("*_extraction.json"):
        with open(f, 'r', encoding='utf-8') as file:
            data = json.load(file)
            results.append({
                "book_id": data["book_id"],
                "title": data.get("title", ""),
                "persons_count": len(data.get("persons", [])),
                "locations_count": len(data.get("locations", [])),
                "events_count": len(data.get("events", []))
            })
    return results


# ============ Queue API Endpoints ============

class QueueStartRequest(BaseModel):
    model: str = "ollama"
    category: Optional[str] = None  # None = all priority books


@app.get("/api/queue/status")
async def get_queue_status():
    """Get queue status"""
    elapsed = 0
    if queue_state["start_time"]:
        elapsed = time.time() - queue_state["start_time"]

    # Calculate book progress
    book_elapsed = 0
    if queue_state.get("book_start_time"):
        book_elapsed = time.time() - queue_state["book_start_time"]

    return {
        "running": queue_state["running"],
        "paused": queue_state["paused"],
        "model": queue_state["current_model"],
        "current_book": queue_state["current_book"],
        "completed": queue_state["completed"],
        "remaining": len(queue_state["books_queue"]),
        "total": queue_state["total"],
        "elapsed_seconds": elapsed,
        "errors_count": len(queue_state["errors"]),
        # Chunk progress
        "current_chunk": queue_state.get("current_chunk", 0),
        "total_chunks": queue_state.get("total_chunks", 0),
        "book_elapsed_seconds": book_elapsed
    }


@app.post("/api/queue/start")
async def start_queue(req: QueueStartRequest, background_tasks: BackgroundTasks):
    """Start processing queue"""
    global queue_state

    if queue_state["running"]:
        return {"error": "Queue already running"}

    # Build queue from priority books
    data = load_zim_books()
    books_to_process = []

    priority_books = data.get("by_category", {})
    for category, books in priority_books.items():
        if req.category and category != req.category:
            continue

        for book in books:
            book_id = book["path"].replace("/", "_").replace(".", "_")
            # Skip already extracted (use safe_filename to match saved files)
            if (RESULTS_DIR / f"{safe_filename(book_id)}_extraction.json").exists():
                continue

            books_to_process.append({
                "id": book_id,
                "path": book["path"],
                "title": book["title"],
                "category": category
            })

    if not books_to_process:
        return {"error": "No books to process", "message": "All books already extracted"}

    # Initialize queue
    queue_state["books_queue"] = books_to_process
    queue_state["total"] = len(books_to_process)
    queue_state["completed"] = 0
    queue_state["current_model"] = req.model
    queue_state["errors"] = []
    queue_state["paused"] = False

    background_tasks.add_task(run_queue)

    return {
        "status": "started",
        "model": req.model,
        "total_books": len(books_to_process)
    }


@app.post("/api/queue/pause")
async def pause_queue():
    """Pause queue processing"""
    queue_state["paused"] = True
    save_queue_state()
    return {"status": "paused"}


@app.post("/api/queue/resume")
async def resume_queue():
    """Resume queue processing"""
    queue_state["paused"] = False
    save_queue_state()
    return {"status": "resumed"}


@app.post("/api/queue/stop")
async def stop_queue():
    """Stop queue processing"""
    global queue_state
    queue_state["running"] = False
    queue_state["paused"] = False

    # Cancel current extraction if any
    if queue_state["current_book"]:
        book_id = queue_state["current_book"]["id"]
        if book_id in extraction_tasks:
            extraction_tasks[book_id]["status"] = "cancelled"

    save_queue_state()
    return {"status": "stopped"}


@app.get("/api/models")
async def get_models():
    """Get available models"""
    models_list = []
    for model_id, info in MODELS.items():
        available = True
        if info["type"] == "openai" and not OPENAI_API_KEY:
            available = False

        models_list.append({
            "id": model_id,
            "name": info["name"],
            "type": info["type"],
            "available": available,
            "input_price": info.get("input_price", 0),
            "output_price": info.get("output_price", 0)
        })
    return models_list


@app.get("/api/speed")
async def get_speed():
    """Get current speed mode"""
    mode = queue_state["speed_mode"]
    return {
        "mode": mode,
        "modes": {k: v["description"] for k, v in SPEED_MODES.items()},
        **SPEED_MODES[mode]
    }


@app.post("/api/speed/{mode}")
async def set_speed(mode: str):
    """Set speed mode (high/low)"""
    if mode not in SPEED_MODES:
        return {"error": f"Invalid mode. Use: {list(SPEED_MODES.keys())}"}

    queue_state["speed_mode"] = mode
    save_queue_state()
    return {
        "status": "ok",
        "mode": mode,
        **SPEED_MODES[mode]
    }


@app.get("/api/stats")
async def get_stats():
    """Get extraction statistics"""
    completed_books = extraction_stats.get("completed_books", [])

    # Calculate averages
    if completed_books:
        recent_30 = completed_books[-30:]
        avg_duration = sum(b["duration_min"] for b in recent_30) / len(recent_30)
        avg_speed = sum(b["speed_kb_per_min"] for b in recent_30) / len(recent_30)
        avg_chunks = sum(b["chunks"] for b in recent_30) / len(recent_30)
    else:
        avg_duration = avg_speed = avg_chunks = 0

    # Speed trend (compare first 10 vs last 10)
    speed_trend = "stable"
    if len(completed_books) >= 20:
        first_10 = completed_books[:10]
        last_10 = completed_books[-10:]
        first_avg = sum(b["speed_kb_per_min"] for b in first_10) / 10
        last_avg = sum(b["speed_kb_per_min"] for b in last_10) / 10
        if last_avg < first_avg * 0.8:
            speed_trend = "slowing"
        elif last_avg > first_avg * 1.2:
            speed_trend = "improving"

    return {
        "session_start": extraction_stats.get("session_start"),
        "total_books_completed": len(completed_books),
        "total_chunks_processed": extraction_stats.get("total_chunks_processed", 0),
        "total_chars_processed": extraction_stats.get("total_chars_processed", 0),
        "averages": {
            "duration_min": round(avg_duration, 1),
            "speed_kb_per_min": round(avg_speed, 1),
            "chunks_per_book": round(avg_chunks, 0)
        },
        "speed_trend": speed_trend,
        "recent_books": completed_books[-30:][::-1]  # Latest first
    }


@app.get("/api/stats/history")
async def get_stats_history():
    """Get detailed stats from extraction results files"""
    import os

    files = []
    for f in RESULTS_DIR.glob("*_extraction.json"):
        mtime = os.path.getmtime(f)
        size = os.path.getsize(f)
        files.append({
            "name": f.stem.replace("_extraction", ""),
            "size_kb": size / 1024,
            "completed_at": datetime.fromtimestamp(mtime).isoformat(),
            "timestamp": mtime
        })

    # Sort by time
    files.sort(key=lambda x: -x["timestamp"])

    # Calculate time between files (processing duration)
    for i in range(len(files) - 1):
        files[i]["duration_min"] = (files[i]["timestamp"] - files[i + 1]["timestamp"]) / 60
        if files[i]["duration_min"] > 0:
            files[i]["speed_kb_per_min"] = files[i]["size_kb"] / files[i]["duration_min"]
        else:
            files[i]["speed_kb_per_min"] = 0

    return {
        "total_files": len(files),
        "recent_50": files[:50]
    }


ADDITIONAL_BOOKS_PATH = BASE_DIR / "additional_books_final.json"

@app.get("/api/additional-books")
async def get_additional_books():
    """Get additional books list"""
    if not ADDITIONAL_BOOKS_PATH.exists():
        return {"error": "No additional books file"}

    with open(ADDITIONAL_BOOKS_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return {
        "total": data.get("summary", {}).get("total", 0),
        "tiers": {
            "tier1": len(data.get("by_tier", {}).get("tier1_non_overlap", [])),
            "tier2": len(data.get("by_tier", {}).get("tier2_high_coverage", [])),
            "tier3": len(data.get("by_tier", {}).get("tier3_new_categories", []))
        },
        "books": data.get("all_books", [])[:200]  # Limit response
    }


@app.post("/api/queue/add-additional")
async def add_additional_books():
    """Add additional books to queue"""
    if not ADDITIONAL_BOOKS_PATH.exists():
        return {"error": "No additional books file"}

    with open(ADDITIONAL_BOOKS_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    added = 0
    for book in data.get("all_books", []):
        book_id = book["path"].replace("/", "_").replace(".", "_")

        # Skip already extracted
        if (RESULTS_DIR / f"{safe_filename(book_id)}_extraction.json").exists():
            continue

        # Skip if already in queue
        if any(b["id"] == book_id for b in queue_state["books_queue"]):
            continue

        queue_state["books_queue"].append({
            "id": book_id,
            "path": book["path"],
            "title": book["title"],
            "category": book.get("category", "Additional")
        })
        added += 1

    queue_state["total"] = queue_state["completed"] + len(queue_state["books_queue"])
    save_queue_state()

    return {"status": "ok", "added": added, "new_total": queue_state["total"]}


# ============ Matching API Endpoints ============

class MatchDecision(BaseModel):
    entity_type: str  # 'person', 'location', 'event'
    name: str
    decision: str  # 'accept', 'reject', 'create'
    entity_id: Optional[int] = None  # For accept/reject

class MatchDecisions(BaseModel):
    decisions: List[MatchDecision]


async def run_matching(book_id: str):
    """Background task to match extracted entities with DB"""
    global matching_tasks

    # Load extraction results
    result_path = RESULTS_DIR / f"{safe_filename(book_id)}_extraction.json"
    if not result_path.exists():
        matching_tasks[book_id] = {"status": "error", "error": "Extraction not found"}
        return

    with open(result_path, 'r', encoding='utf-8') as f:
        extraction = json.load(f)

    # Initialize matching task
    total_entities = (
        len(extraction.get("persons", [])) +
        len(extraction.get("locations", [])) +
        len(extraction.get("events", []))
    )

    matching_tasks[book_id] = {
        "status": "running",
        "progress": 0,
        "total": total_entities,
        "start_time": time.time(),
        "results": {
            "matched": [],
            "new": [],
            "merged": []
        }
    }

    matcher = EntityMatcher()

    try:
        processed = 0

        # Match persons
        for name in extraction.get("persons", []):
            if matching_tasks[book_id]["status"] == "cancelled":
                break
            result = matcher.match_person(name)
            _add_match_result(book_id, "person", name, result)
            processed += 1
            matching_tasks[book_id]["progress"] = processed

        # Match locations
        for name in extraction.get("locations", []):
            if matching_tasks[book_id]["status"] == "cancelled":
                break
            result = matcher.match_location(name)
            _add_match_result(book_id, "location", name, result)
            processed += 1
            matching_tasks[book_id]["progress"] = processed

        # Match events
        for name in extraction.get("events", []):
            if matching_tasks[book_id]["status"] == "cancelled":
                break
            result = matcher.match_event(name)
            _add_match_result(book_id, "event", name, result)
            processed += 1
            matching_tasks[book_id]["progress"] = processed

        matching_tasks[book_id]["status"] = "completed"
        matching_tasks[book_id]["elapsed_seconds"] = time.time() - matching_tasks[book_id]["start_time"]

        # Save matching results
        match_result_path = RESULTS_DIR / f"{safe_filename(book_id)}_matching.json"
        with open(match_result_path, 'w', encoding='utf-8') as f:
            json.dump(matching_tasks[book_id]["results"], f, indent=2, ensure_ascii=False)

    except Exception as e:
        matching_tasks[book_id]["status"] = "error"
        matching_tasks[book_id]["error"] = str(e)
    finally:
        matcher.close()


def _add_match_result(book_id: str, entity_type: str, name: str, result: MatchResult):
    """Add match result to task results"""
    entry = {
        "entity_type": entity_type,
        "name": name,
        "matched": result.matched,
        "entity_id": result.entity_id,
        "confidence": result.confidence,
        "method": result.method
    }

    if result.matched:
        if result.merged:
            matching_tasks[book_id]["results"]["merged"].append(entry)
        else:
            matching_tasks[book_id]["results"]["matched"].append(entry)
    else:
        entry["wikidata_qid"] = result.details.get("wikidata_qid") if result.details else None
        matching_tasks[book_id]["results"]["new"].append(entry)


@app.post("/api/match/start/{book_id}")
async def start_matching(book_id: str, background_tasks: BackgroundTasks):
    """Start entity matching for an extracted book"""
    # Check if extraction exists
    result_path = RESULTS_DIR / f"{safe_filename(book_id)}_extraction.json"
    if not result_path.exists():
        return {"error": "Extraction not found", "book_id": book_id}

    # Check if already running
    if book_id in matching_tasks and matching_tasks[book_id]["status"] == "running":
        return {"error": "Matching already running", "book_id": book_id}

    background_tasks.add_task(run_matching, book_id)
    return {"status": "started", "book_id": book_id}


@app.get("/api/match/status/{book_id}")
async def get_match_status(book_id: str):
    """Get matching progress"""
    if book_id in matching_tasks:
        task = matching_tasks[book_id]
        return {
            "book_id": book_id,
            "status": task["status"],
            "progress": task.get("progress", 0),
            "total": task.get("total", 0),
            "matched_count": len(task.get("results", {}).get("matched", [])),
            "new_count": len(task.get("results", {}).get("new", [])),
            "merged_count": len(task.get("results", {}).get("merged", []))
        }

    # Check for saved results
    match_result_path = RESULTS_DIR / f"{safe_filename(book_id)}_matching.json"
    if match_result_path.exists():
        with open(match_result_path, 'r', encoding='utf-8') as f:
            results = json.load(f)
        return {
            "book_id": book_id,
            "status": "completed",
            "matched_count": len(results.get("matched", [])),
            "new_count": len(results.get("new", [])),
            "merged_count": len(results.get("merged", []))
        }

    return {"error": "Not found"}


@app.get("/api/match/results/{book_id}")
async def get_match_results(book_id: str):
    """Get matching results for review"""
    # Try in-memory first
    if book_id in matching_tasks:
        return matching_tasks[book_id].get("results", {})

    # Try saved file
    match_result_path = RESULTS_DIR / f"{safe_filename(book_id)}_matching.json"
    if match_result_path.exists():
        with open(match_result_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    return {"error": "Results not found"}


@app.post("/api/match/confirm/{book_id}")
async def confirm_matches(book_id: str, body: MatchDecisions):
    """Confirm or reject matches"""
    matcher = EntityMatcher(auto_create=True)

    confirmed = 0
    created = 0
    rejected = 0

    try:
        for decision in body.decisions:
            if decision.decision == "accept":
                # Alias already saved during matching, just count
                confirmed += 1
            elif decision.decision == "create":
                # Create new entity
                result = matcher.match(decision.entity_type, decision.name)
                if result.method == "new":
                    created += 1
            elif decision.decision == "reject":
                rejected += 1

        return {
            "status": "ok",
            "confirmed": confirmed,
            "created": created,
            "rejected": rejected
        }
    finally:
        matcher.close()


@app.post("/api/match/cancel/{book_id}")
async def cancel_matching(book_id: str):
    """Cancel running matching"""
    if book_id in matching_tasks:
        matching_tasks[book_id]["status"] = "cancelled"
        return {"status": "cancelled", "book_id": book_id}
    return {"error": "Not found"}


# ============ Duplicates API Endpoints ============

@app.get("/api/duplicates/status")
async def get_duplicate_status():
    """Get DB duplicate status"""
    import psycopg2
    from psycopg2.extras import RealDictCursor

    try:
        conn = psycopg2.connect(
            host='localhost', port=5432, dbname='chaldeas',
            user='chaldeas', password='chaldeas_dev'
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Count duplicates by QID
        cur.execute("""
            SELECT COUNT(*) as dup_qid_count FROM (
                SELECT wikidata_id FROM persons
                WHERE wikidata_id IS NOT NULL
                GROUP BY wikidata_id
                HAVING COUNT(*) > 1
            ) t
        """)
        dup_qids = cur.fetchone()["dup_qid_count"]

        # Count merged aliases
        cur.execute("SELECT COUNT(*) as merged_count FROM entity_aliases WHERE alias_type = 'merged'")
        merged = cur.fetchone()["merged_count"]

        # Total persons
        cur.execute("SELECT COUNT(*) as total FROM persons")
        total = cur.fetchone()["total"]

        # Recent merges (top entities with most merged aliases)
        cur.execute("""
            SELECT ea.entity_id, p.name, COUNT(*) as alias_count
            FROM entity_aliases ea
            JOIN persons p ON ea.entity_id = p.id AND ea.entity_type = 'person'
            WHERE ea.alias_type = 'merged'
            GROUP BY ea.entity_id, p.name
            ORDER BY alias_count DESC
            LIMIT 10
        """)
        recent_merges = cur.fetchall()

        conn.close()

        return {
            "total_persons": total,
            "duplicate_qids": dup_qids,
            "merged_aliases": merged,
            "recent_merges": [dict(r) for r in recent_merges]
        }

    except Exception as e:
        return {"error": str(e)}


@app.get("/api/duplicates/top")
async def get_top_duplicates():
    """Get top duplicate entries"""
    import psycopg2
    from psycopg2.extras import RealDictCursor

    try:
        conn = psycopg2.connect(
            host='localhost', port=5432, dbname='chaldeas',
            user='chaldeas', password='chaldeas_dev'
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT wikidata_id, COUNT(*) as cnt, array_agg(name) as names
            FROM persons
            WHERE wikidata_id IS NOT NULL
            GROUP BY wikidata_id
            HAVING COUNT(*) > 1
            ORDER BY cnt DESC
            LIMIT 20
        """)
        duplicates = cur.fetchall()

        conn.close()

        return {
            "duplicates": [dict(d) for d in duplicates]
        }

    except Exception as e:
        return {"error": str(e)}


@app.post("/api/duplicates/merge/{qid}")
async def merge_duplicate_qid(qid: str):
    """Manually trigger merge for a specific QID"""
    import psycopg2
    from psycopg2.extras import RealDictCursor

    try:
        conn = psycopg2.connect(
            host='localhost', port=5432, dbname='chaldeas',
            user='chaldeas', password='chaldeas_dev'
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Find all persons with this QID
        cur.execute("""
            SELECT id, name, wikidata_id
            FROM persons
            WHERE wikidata_id = %s
        """, (qid,))
        entities = cur.fetchall()
        conn.close()

        if len(entities) <= 1:
            return {"error": "No duplicates found", "qid": qid}

        # Use EntityMatcher to merge
        matcher = EntityMatcher()
        primary = matcher._merge_duplicates("person", [dict(e) for e in entities])
        matcher.close()

        return {
            "status": "merged",
            "qid": qid,
            "merged_count": len(entities),
            "primary_id": primary["id"],
            "primary_name": primary["name"]
        }

    except Exception as e:
        return {"error": str(e)}


# ============ Matching Settings API ============

class MatchingSettings(BaseModel):
    auto_match: Optional[bool] = None
    auto_confirm_threshold: Optional[float] = None


@app.get("/api/match/settings")
async def get_matching_settings():
    """Get matching settings"""
    return matching_settings


@app.post("/api/match/settings")
async def update_matching_settings(settings: MatchingSettings):
    """Update matching settings"""
    if settings.auto_match is not None:
        matching_settings["auto_match"] = settings.auto_match
    if settings.auto_confirm_threshold is not None:
        matching_settings["auto_confirm_threshold"] = settings.auto_confirm_threshold
    return matching_settings


# ============ Model Info API ============

@app.get("/api/models/info")
async def get_model_info():
    """Get model configuration info for all phases"""
    return MODEL_INFO


# ============ Post-Processing API ============

@app.get("/api/postprocess/settings")
async def get_postprocess_settings():
    """Get post-processing settings"""
    return post_process_settings


@app.post("/api/postprocess/settings")
async def update_postprocess_settings(auto_context: bool = None, auto_db_match: bool = None):
    """Update post-processing settings"""
    if auto_context is not None:
        post_process_settings["auto_context"] = auto_context
    if auto_db_match is not None:
        post_process_settings["auto_db_match"] = auto_db_match
    return post_process_settings


@app.get("/api/postprocess/stats")
async def get_postprocess_stats():
    """Get post-processing statistics"""
    return post_process_stats


# ============ Auto Processing API ============

@app.get("/api/auto/status")
async def get_auto_status():
    """Get auto-processing status"""
    elapsed = 0
    if auto_state["start_time"]:
        elapsed = time.time() - auto_state["start_time"]

    return {
        **auto_state,
        "elapsed_seconds": elapsed
    }


async def run_auto_matching():
    """Auto-match all unmatched extracted books"""
    global auto_state

    # Get all extracted books
    extracted_books = []
    for f in RESULTS_DIR.glob("*_extraction.json"):
        book_id = f.stem.replace("_extraction", "")
        # Check if already matched
        match_file = RESULTS_DIR / f"{book_id}_matching.json"
        if not match_file.exists():
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)
                extracted_books.append({
                    "book_id": book_id,
                    "title": data.get("title", book_id),
                    "entity_count": len(data.get("persons", [])) + len(data.get("locations", [])) + len(data.get("events", []))
                })

    if not extracted_books:
        auto_state["running"] = False
        return

    auto_state["total"] = len(extracted_books)
    auto_state["mode"] = "matching"
    auto_state["start_time"] = time.time()

    for i, book in enumerate(extracted_books):
        if not auto_state["running"]:
            break

        while auto_state["paused"]:
            await asyncio.sleep(1)

        auto_state["current_item"] = book["title"]
        auto_state["progress"] = i

        try:
            # Run matching for this book
            await run_matching(book["book_id"])
            auto_state["completed"] += 1
        except Exception as e:
            auto_state["errors"].append({"book": book["title"], "error": str(e)})

        await asyncio.sleep(0.5)  # Brief pause between books

    auto_state["running"] = False
    auto_state["current_item"] = None


async def run_auto_duplicates():
    """Auto-merge all duplicate QIDs"""
    global auto_state
    import psycopg2
    from psycopg2.extras import RealDictCursor

    try:
        conn = psycopg2.connect(
            host='localhost', port=5432, dbname='chaldeas',
            user='chaldeas', password='chaldeas_dev'
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get all duplicate QIDs
        cur.execute("""
            SELECT wikidata_id, COUNT(*) as cnt
            FROM persons
            WHERE wikidata_id IS NOT NULL
            GROUP BY wikidata_id
            HAVING COUNT(*) > 1
            ORDER BY cnt DESC
        """)
        duplicates = cur.fetchall()
        conn.close()

        if not duplicates:
            auto_state["running"] = False
            return

        auto_state["total"] = len(duplicates)
        auto_state["mode"] = "duplicates"
        auto_state["start_time"] = time.time()

        matcher = EntityMatcher()

        for i, dup in enumerate(duplicates):
            if not auto_state["running"]:
                break

            while auto_state["paused"]:
                await asyncio.sleep(1)

            qid = dup["wikidata_id"]
            auto_state["current_item"] = qid
            auto_state["progress"] = i

            try:
                # Get all persons with this QID
                conn = psycopg2.connect(
                    host='localhost', port=5432, dbname='chaldeas',
                    user='chaldeas', password='chaldeas_dev'
                )
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute("""
                    SELECT id, name, wikidata_id
                    FROM persons
                    WHERE wikidata_id = %s
                """, (qid,))
                entities = cur.fetchall()
                conn.close()

                if len(entities) > 1:
                    matcher._merge_duplicates("person", [dict(e) for e in entities])
                    auto_state["completed"] += 1

            except Exception as e:
                auto_state["errors"].append({"qid": qid, "error": str(e)})

            await asyncio.sleep(0.1)  # Brief pause

        matcher.close()

    except Exception as e:
        auto_state["errors"].append({"error": str(e)})

    auto_state["running"] = False
    auto_state["current_item"] = None


class AutoStartRequest(BaseModel):
    mode: str  # 'extraction', 'matching', 'duplicates'


@app.post("/api/auto/start")
async def start_auto_processing(req: AutoStartRequest, background_tasks: BackgroundTasks):
    """Start auto-processing"""
    global auto_state

    if auto_state["running"]:
        return {"error": "Auto-processing already running"}

    # Reset state
    auto_state = {
        "mode": req.mode,
        "running": True,
        "paused": False,
        "progress": 0,
        "total": 0,
        "current_item": None,
        "completed": 0,
        "errors": [],
        "start_time": time.time(),
    }

    if req.mode == "extraction":
        # Use existing queue
        background_tasks.add_task(run_queue)
    elif req.mode == "matching":
        background_tasks.add_task(run_auto_matching)
    elif req.mode == "duplicates":
        background_tasks.add_task(run_auto_duplicates)
    else:
        return {"error": f"Invalid mode: {req.mode}"}

    return {"status": "started", "mode": req.mode}


@app.post("/api/auto/pause")
async def pause_auto_processing():
    """Pause auto-processing"""
    auto_state["paused"] = True
    return {"status": "paused"}


@app.post("/api/auto/resume")
async def resume_auto_processing():
    """Resume auto-processing"""
    auto_state["paused"] = False
    return {"status": "resumed"}


@app.post("/api/auto/stop")
async def stop_auto_processing():
    """Stop auto-processing"""
    global auto_state
    auto_state["running"] = False
    auto_state["paused"] = False

    # Also stop extraction queue if running
    if auto_state.get("mode") == "extraction":
        queue_state["running"] = False

    return {"status": "stopped"}


@app.get("/api/auto/unmatched")
async def get_unmatched_books():
    """Get count of extracted but unmatched books"""
    count = 0
    for f in RESULTS_DIR.glob("*_extraction.json"):
        book_id = f.stem.replace("_extraction", "")
        match_file = RESULTS_DIR / f"{book_id}_matching.json"
        if not match_file.exists():
            count += 1
    return {"unmatched_count": count}


if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("CHALDEAS Book Extractor v2.0")
    print("=" * 60)
    print(f"ZIM file: {ZIM_PATH}")
    print(f"Results: {RESULTS_DIR}")
    print(f"Ollama: {OLLAMA_URL}")
    print(f"Model: {OLLAMA_MODEL}")
    print("=" * 60)

    # Pre-load ZIM
    zim = get_zim_archive()
    if zim:
        print(f"ZIM loaded: {zim.entry_count:,} entries, {zim.article_count:,} articles")
    else:
        print("Warning: ZIM file not loaded")

    print("=" * 60)
    print("Open http://localhost:8200 in your browser")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8200)
