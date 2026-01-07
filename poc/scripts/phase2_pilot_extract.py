"""
Phase 2 Pilot - Step 1: Sample Extraction
3000개 샘플 추출 (person 1500, location 1500)
mention_count > 1 우선, context 포함
"""
import json
import sys
import io
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from datetime import datetime
import random

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass

DATA_DIR = Path(__file__).parent.parent / "data"
PILOT_DIR = DATA_DIR / "pilot"
SOURCE_BASE = Path("C:/Projects/Chaldeas/data/raw")


@dataclass
class PilotSample:
    id: int
    text: str
    entity_type: str
    entity_key: str
    mention_count: int
    contexts: List[Dict]  # [{source_path, context_text, start, end}]


def extract_context(source_path: str, start: int, end: int, window: int = 50) -> str:
    """원본 텍스트에서 window 크기의 context 추출"""
    full_path = SOURCE_BASE / source_path

    if not full_path.exists():
        return ""

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # British Library 형식: [[page_num, text], ...]
        if isinstance(data, list):
            full_text = " ".join(
                str(item[1]) for item in data
                if isinstance(item, list) and len(item) > 1 and item[1]
            )
        elif isinstance(data, dict) and "text" in data:
            full_text = data["text"]
        else:
            full_text = str(data)

        # window 크기로 context 추출
        ctx_start = max(0, start - window)
        ctx_end = min(len(full_text), end + window)

        context = full_text[ctx_start:ctx_end]

        # 앞뒤 잘린 부분 표시
        if ctx_start > 0:
            context = "..." + context
        if ctx_end < len(full_text):
            context = context + "..."

        return context

    except Exception as e:
        return ""


def load_mentions_index(limit_per_key: int = 3) -> Dict[str, List[Dict]]:
    """
    mentions.jsonl을 entity_key별로 인덱싱
    메모리 효율을 위해 각 key당 limit_per_key개만 저장
    """
    index = {}
    mentions_file = DATA_DIR / "mentions.jsonl"

    print(f"Loading mentions index from {mentions_file}...")
    count = 0

    with open(mentions_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                m = json.loads(line)
                key = m["entity_key"]

                if key not in index:
                    index[key] = []

                # 각 key당 최대 limit_per_key개만 저장
                if len(index[key]) < limit_per_key:
                    index[key].append({
                        "source_path": m["source_path"],
                        "start": m["start"],
                        "end": m["end"]
                    })

                count += 1
                if count % 500000 == 0:
                    print(f"  Processed {count:,} mentions...")

    print(f"  Total mentions: {count:,}")
    print(f"  Unique entity keys: {len(index):,}")

    return index


def extract_samples(
    person_count: int = 1500,
    location_count: int = 1500,
    context_window: int = 50
) -> List[PilotSample]:
    """
    샘플 추출 - mention_count > 1 우선
    """

    # 1. pending_queue 전체 로드 및 분류
    print(f"\nLoading pending_queue.jsonl...")
    persons = []
    locations = []

    queue_file = DATA_DIR / "pending_queue.jsonl"
    total_count = 0

    with open(queue_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                total_count += 1

                if item["entity_type"] == "person":
                    persons.append(item)
                elif item["entity_type"] == "location":
                    locations.append(item)

                if total_count % 200000 == 0:
                    print(f"  Processed {total_count:,} items...")

    print(f"  Total items: {total_count:,}")
    print(f"  Persons: {len(persons):,}")
    print(f"  Locations: {len(locations):,}")

    # 2. mention_count 기준 정렬 (내림차순)
    print("\nSorting by mention_count...")
    persons.sort(key=lambda x: -x.get("mention_count", 1))
    locations.sort(key=lambda x: -x.get("mention_count", 1))

    # 3. 샘플링: mention_count > 1 우선, 부족하면 == 1 추가
    def select_samples(items: List[Dict], count: int) -> List[Dict]:
        high_mention = [x for x in items if x.get("mention_count", 1) > 1]
        low_mention = [x for x in items if x.get("mention_count", 1) == 1]

        print(f"    High mention (>1): {len(high_mention):,}")
        print(f"    Low mention (=1): {len(low_mention):,}")

        if len(high_mention) >= count:
            # 높은 mention_count에서 랜덤 샘플링 (상위만 뽑으면 편향됨)
            return random.sample(high_mention[:min(count*3, len(high_mention))], count)
        else:
            need = count - len(high_mention)
            low_sample = random.sample(low_mention, min(need, len(low_mention)))
            return high_mention + low_sample

    print(f"\nSelecting {person_count} persons...")
    selected_persons = select_samples(persons, person_count)

    print(f"\nSelecting {location_count} locations...")
    selected_locations = select_samples(locations, location_count)

    # 4. mentions.jsonl에서 context 추출
    mentions_index = load_mentions_index(limit_per_key=3)

    # 5. 샘플 생성
    print(f"\nExtracting contexts (window={context_window})...")
    samples = []
    selected_items = selected_persons + selected_locations

    for i, item in enumerate(selected_items):
        entity_key = item["entity_key"]
        mentions = mentions_index.get(entity_key, [])

        contexts = []
        for m in mentions[:3]:  # 최대 3개 context
            ctx = extract_context(
                m["source_path"],
                m["start"],
                m["end"],
                window=context_window
            )
            if ctx:
                contexts.append({
                    "source_path": m["source_path"],
                    "context_text": ctx,
                    "start": m["start"],
                    "end": m["end"]
                })

        samples.append(PilotSample(
            id=item["id"],
            text=item["text"],
            entity_type=item["entity_type"],
            entity_key=entity_key,
            mention_count=item.get("mention_count", 1),
            contexts=contexts
        ))

        if (i + 1) % 500 == 0:
            print(f"  Processed {i+1}/{len(selected_items)} samples...")

    return samples


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Phase 2 Pilot - Sample Extraction")
    parser.add_argument("--person-count", type=int, default=1500, help="Number of person samples")
    parser.add_argument("--location-count", type=int, default=1500, help="Number of location samples")
    parser.add_argument("--context-window", type=int, default=50, help="Context window size")
    args = parser.parse_args()

    PILOT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("       PHASE 2 PILOT - SAMPLE EXTRACTION")
    print("=" * 60)
    print(f"Target: {args.person_count} persons + {args.location_count} locations")
    print(f"Context window: {args.context_window} chars")
    print("-" * 60)

    start_time = datetime.now()

    samples = extract_samples(
        person_count=args.person_count,
        location_count=args.location_count,
        context_window=args.context_window
    )

    # 저장
    output_file = PILOT_DIR / "pilot_samples_3000.jsonl"
    with open(output_file, 'w', encoding='utf-8') as f:
        for s in samples:
            f.write(json.dumps(asdict(s), ensure_ascii=False) + '\n')

    # 통계
    elapsed = (datetime.now() - start_time).total_seconds()
    persons = [s for s in samples if s.entity_type == "person"]
    locations = [s for s in samples if s.entity_type == "location"]
    with_context = sum(1 for s in samples if s.contexts)

    print("\n" + "=" * 60)
    print("       EXTRACTION COMPLETE")
    print("=" * 60)
    print(f"Total samples: {len(samples)}")
    print(f"  Persons: {len(persons)}")
    print(f"  Locations: {len(locations)}")
    print(f"  With context: {with_context} ({with_context/len(samples)*100:.1f}%)")
    print(f"Time elapsed: {elapsed:.1f}s")
    print(f"\nSaved to: {output_file}")

    # 샘플 미리보기
    print("\n" + "-" * 60)
    print("Sample preview (first 5):")
    for s in samples[:5]:
        ctx_preview = s.contexts[0]["context_text"][:60] if s.contexts else "(no context)"
        print(f"  [{s.entity_type}] {s.text} (mentions: {s.mention_count})")
        print(f"      Context: {ctx_preview}...")


if __name__ == "__main__":
    main()
