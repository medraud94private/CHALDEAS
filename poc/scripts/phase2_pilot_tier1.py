"""
Phase 2 Pilot - Step 2: Tier 1 Rule-based Filtering
규칙 기반 필터링 및 병합
- 노이즈 필터링 (짧은 문자, 일반 명사 등)
- Royal number 처리 (Charles VII != Charles VIII)
- Exact match 병합
"""
import json
import sys
import io
import re
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Tuple, Optional, Set
from datetime import datetime

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass

DATA_DIR = Path(__file__).parent.parent / "data"
PILOT_DIR = DATA_DIR / "pilot"

# ============================================================
# 필터링 규칙
# ============================================================

# 노이즈 패턴 (정규식)
NOISE_PATTERNS = [
    r'^[A-Z]$',                      # 단일 대문자: A, B, C
    r'^[0-9]+$',                     # 숫자만: 123, 456
    r'^[0-9]+\s*[&,]\s*[0-9]+$',     # 주소 번호: "56 & 58", "12, 14"
    r'^[A-Z]{2,4}$',                 # 짧은 약어: USA, UK, NYC (애매함)
    r'^\d+\s*(st|nd|rd|th)$',        # 서수: 1st, 2nd, 3rd
]

# 블랙리스트 단어 (대소문자 무시)
BLOCKLIST_WORDS = {
    # 관사/전치사
    "the", "a", "an", "and", "or", "of", "in", "on", "at", "to", "for", "by", "with",
    # 일반 호칭
    "mr", "mrs", "ms", "dr", "st", "ltd", "co", "inc", "son", "sons",
    # 일반 명사 (NER 오류로 자주 잡히는 것들)
    "limited", "company", "brother", "brothers", "works", "factory",
    "street", "road", "lane", "square", "court", "place",
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    # 재료/제품 (British Library OCR 오류)
    "oak", "ash", "elm", "pine", "walnut", "mahogany", "brass", "iron", "steel",
}

# Royal number 패턴 (로마 숫자)
# I, II, III, IV, V, VI, VII, VIII, IX, X, XI, XII, XIII, XIV, XV, XVI, XVII, XVIII, XIX, XX
ROYAL_NUMBER_PATTERN = re.compile(
    r'^(.+?)\s+(I{1,3}|IV|V?I{0,3}|IX|X{0,3}I{0,3}|XI{1,3}|XIV|XV|XVI{0,3}|XIX|XX)$',
    re.IGNORECASE
)

# 정규화 규칙
NORMALIZATION_RULES = [
    (r'\bSt\.\s*', 'Saint '),
    (r'\bMt\.\s*', 'Mount '),
    (r'\s+', ' '),  # 다중 공백 제거
]


@dataclass
class Tier1Result:
    id: int
    text: str
    entity_type: str
    entity_key: str
    mention_count: int
    decision: str  # FILTER_OUT, MERGE_EXACT, SEPARATE, PASS_TO_TIER2
    reason: str
    merged_with: Optional[str] = None  # 병합 대상 entity_key
    base_name: Optional[str] = None    # Royal number 분리 시 base name
    royal_number: Optional[str] = None # Royal number
    contexts: List[Dict] = field(default_factory=list)


def normalize_text(text: str) -> str:
    """텍스트 정규화"""
    result = text.strip()
    for pattern, replacement in NORMALIZATION_RULES:
        result = re.sub(pattern, replacement, result)
    return result.lower().strip()


def extract_royal_number(name: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Royal number 추출
    "Charles VII" → ("Charles", "VII")
    "Napoleon" → (None, None)
    """
    match = ROYAL_NUMBER_PATTERN.match(name.strip())
    if match:
        base = match.group(1).strip()
        number = match.group(2).upper()
        # 너무 짧은 base name은 제외 (오탐 방지)
        if len(base) >= 3:
            return base, number
    return None, None


def is_noise(text: str) -> Tuple[bool, str]:
    """노이즈 여부 판단"""
    # 1. 너무 짧은 이름
    if len(text) < 2:
        return True, "Too short (len < 2)"

    # 2. 너무 긴 이름 (문장일 가능성)
    if len(text) > 100:
        return True, "Too long (len > 100, likely sentence)"

    # 3. 정규식 패턴 매칭
    for pattern in NOISE_PATTERNS:
        if re.match(pattern, text, re.IGNORECASE):
            return True, f"Matches noise pattern: {pattern}"

    # 4. 블랙리스트 단어
    text_lower = text.lower().strip()
    if text_lower in BLOCKLIST_WORDS:
        return True, f"In blocklist: {text_lower}"

    # 5. 전체가 숫자+특수문자로만 구성
    if not re.search(r'[a-zA-Z]', text):
        return True, "No alphabetic characters"

    return False, ""


def build_exact_match_index(samples: List[Dict]) -> Dict[str, List[Dict]]:
    """정규화된 텍스트 기준 exact match 인덱스"""
    index = {}
    for s in samples:
        # entity_type별로 분리 (person과 location이 같은 이름일 수 있음)
        key = (s["entity_type"], normalize_text(s["text"]))
        if key not in index:
            index[key] = []
        index[key].append(s)
    return index


def process_tier1(samples: List[Dict]) -> List[Tier1Result]:
    """Tier 1 처리"""
    results = []

    # 1. Exact match 인덱스 구축
    print("Building exact match index...")
    exact_index = build_exact_match_index(samples)

    # 2. Royal number별 그룹화 (SEPARATE 판단용)
    print("Building royal number groups...")
    royal_groups = {}  # (entity_type, base_name_lower) -> [(entity_key, royal_number, original_text)]
    for s in samples:
        base, num = extract_royal_number(s["text"])
        if base and num:
            key = (s["entity_type"], base.lower())
            if key not in royal_groups:
                royal_groups[key] = []
            royal_groups[key].append((s["entity_key"], num, s["text"]))

    # 3. 처리된 항목 추적 (중복 방지)
    processed_keys: Set[str] = set()
    merge_targets: Dict[str, str] = {}  # merged_key -> primary_key

    print(f"Processing {len(samples)} samples...")

    for i, s in enumerate(samples):
        entity_key = s["entity_key"]

        if entity_key in processed_keys:
            continue

        text = s["text"]
        entity_type = s["entity_type"]
        mention_count = s.get("mention_count", 1)
        contexts = s.get("contexts", [])

        # Rule 1: 노이즈 필터링
        is_noise_flag, noise_reason = is_noise(text)
        if is_noise_flag:
            results.append(Tier1Result(
                id=s["id"],
                text=text,
                entity_type=entity_type,
                entity_key=entity_key,
                mention_count=mention_count,
                decision="FILTER_OUT",
                reason=noise_reason,
                contexts=contexts
            ))
            processed_keys.add(entity_key)
            continue

        # Rule 2: Royal number 체크
        base_name, royal_num = extract_royal_number(text)
        if base_name and royal_num:
            key = (entity_type, base_name.lower())
            group = royal_groups.get(key, [])

            # 같은 base name에 다른 number가 있으면 SEPARATE
            other_numbers = [num for ek, num, _ in group if num != royal_num and ek != entity_key]
            if other_numbers:
                results.append(Tier1Result(
                    id=s["id"],
                    text=text,
                    entity_type=entity_type,
                    entity_key=entity_key,
                    mention_count=mention_count,
                    decision="SEPARATE",
                    reason=f"Royal number {royal_num} differs from {other_numbers[:3]}",
                    base_name=base_name,
                    royal_number=royal_num,
                    contexts=contexts
                ))
                processed_keys.add(entity_key)
                continue

        # Rule 3: Exact match 병합
        norm_key = (entity_type, normalize_text(text))
        matches = exact_index.get(norm_key, [])
        other_matches = [m for m in matches if m["entity_key"] != entity_key]

        if other_matches:
            # 가장 높은 mention_count 항목을 primary로
            all_matches = [s] + other_matches
            primary = max(all_matches, key=lambda x: x.get("mention_count", 1))

            if primary["entity_key"] != entity_key:
                # 현재 항목을 primary에 병합
                results.append(Tier1Result(
                    id=s["id"],
                    text=text,
                    entity_type=entity_type,
                    entity_key=entity_key,
                    mention_count=mention_count,
                    decision="MERGE_EXACT",
                    reason=f"Exact match, merged to higher mention count ({primary['mention_count']})",
                    merged_with=primary["entity_key"],
                    contexts=contexts
                ))
                processed_keys.add(entity_key)
                continue

        # Rule 4: 나머지는 Tier 2로
        results.append(Tier1Result(
            id=s["id"],
            text=text,
            entity_type=entity_type,
            entity_key=entity_key,
            mention_count=mention_count,
            decision="PASS_TO_TIER2",
            reason="Needs embedding-based analysis",
            base_name=base_name,
            royal_number=royal_num,
            contexts=contexts
        ))
        processed_keys.add(entity_key)

        if (i + 1) % 500 == 0:
            print(f"  Processed {i+1}/{len(samples)}...")

    return results


def main():
    print("=" * 60)
    print("       PHASE 2 PILOT - TIER 1 RULE-BASED FILTERING")
    print("=" * 60)

    # 샘플 로드
    samples_file = PILOT_DIR / "pilot_samples_3000.jsonl"

    if not samples_file.exists():
        print(f"ERROR: Sample file not found: {samples_file}")
        print("Run phase2_pilot_extract.py first!")
        return

    samples = []
    with open(samples_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))

    print(f"Loaded {len(samples)} samples")
    print("-" * 60)

    start_time = datetime.now()

    # Tier 1 처리
    results = process_tier1(samples)

    # 결과 저장
    output_file = PILOT_DIR / "tier1_results.jsonl"
    with open(output_file, 'w', encoding='utf-8') as f:
        for r in results:
            f.write(json.dumps(asdict(r), ensure_ascii=False) + '\n')

    # Tier 2로 전달될 항목 저장 (contexts 포함)
    tier2_items = [r for r in results if r.decision == "PASS_TO_TIER2"]
    tier2_file = PILOT_DIR / "tier2_input.jsonl"

    with open(tier2_file, 'w', encoding='utf-8') as f:
        for r in tier2_items:
            item = {
                "id": r.id,
                "text": r.text,
                "entity_type": r.entity_type,
                "entity_key": r.entity_key,
                "mention_count": r.mention_count,
                "contexts": r.contexts,
                "base_name": r.base_name,
                "royal_number": r.royal_number
            }
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

    # 통계
    elapsed = (datetime.now() - start_time).total_seconds()

    decisions = {}
    for r in results:
        decisions[r.decision] = decisions.get(r.decision, 0) + 1

    print("\n" + "=" * 60)
    print("       TIER 1 RESULTS")
    print("=" * 60)

    total = len(results)
    for decision in ["FILTER_OUT", "MERGE_EXACT", "SEPARATE", "PASS_TO_TIER2"]:
        count = decisions.get(decision, 0)
        pct = count / total * 100 if total > 0 else 0
        print(f"  {decision:15s}: {count:5d} ({pct:5.1f}%)")

    print("-" * 60)
    print(f"  Total processed: {total}")
    print(f"  Time elapsed: {elapsed:.1f}s")

    # 효율 분석
    filtered_count = decisions.get("FILTER_OUT", 0) + decisions.get("MERGE_EXACT", 0)
    tier2_count = decisions.get("PASS_TO_TIER2", 0) + decisions.get("SEPARATE", 0)
    reduction = filtered_count / total * 100 if total > 0 else 0

    print(f"\n  Tier 1 reduction: {reduction:.1f}%")
    print(f"  Items to Tier 2: {tier2_count}")

    print(f"\nSaved to:")
    print(f"  Results: {output_file}")
    print(f"  Tier 2 input: {tier2_file}")

    # 샘플 미리보기
    print("\n" + "-" * 60)
    print("Sample FILTER_OUT items:")
    filter_out = [r for r in results if r.decision == "FILTER_OUT"][:5]
    for r in filter_out:
        print(f"  [{r.entity_type}] '{r.text}' - {r.reason}")

    print("\nSample SEPARATE items (Royal numbers):")
    separate = [r for r in results if r.decision == "SEPARATE"][:5]
    for r in separate:
        print(f"  [{r.entity_type}] '{r.text}' - base: {r.base_name}, num: {r.royal_number}")


if __name__ == "__main__":
    main()
