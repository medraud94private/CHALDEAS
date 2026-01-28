"""
Kiwix-first Reconciliation - Kiwix 우선, Wikidata API 폴백

기존 wikidata_reconcile.py 체크포인트에서 이어서 작업
1차: Kiwix Wikipedia 로컬 매칭 (빠름)
2차: 실패 시 Wikidata Reconciliation API (느림)

Usage:
    python kiwix_reconcile.py --resume              # 체크포인트에서 이어서
    python kiwix_reconcile.py --limit 1000          # 처음부터 1000개
    python kiwix_reconcile.py --kiwix-only          # Kiwix만 사용 (API 폴백 없음)
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import time
import argparse
import re
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, asdict

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

import requests
from libzim.reader import Archive
from html.parser import HTMLParser

# ============ Config ============

ZIM_DIR = Path(__file__).parent.parent.parent / "data" / "kiwix"
WIKIPEDIA_ZIM = ZIM_DIR / "wikipedia_en_nopic.zim"

# 체크포인트 (기존 wikidata_reconcile.py와 공유)
INDEX_FILE = Path(__file__).parent.parent / "data" / "reconcile_index.json"
RESULTS_JSONL = Path(__file__).parent.parent / "data" / "reconcile_results.jsonl"

# Wikidata API (폴백용)
RECONCILE_API = "https://wikidata.reconci.link/en/api"

# Lazy loading
_wikipedia_archive = None


def get_wikipedia() -> Archive:
    global _wikipedia_archive
    if _wikipedia_archive is None:
        _wikipedia_archive = Archive(str(WIKIPEDIA_ZIM))
    return _wikipedia_archive


# ============ HTML Parser ============

class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.skip_tags = {'script', 'style', 'nav', 'header', 'footer', 'aside', 'sup'}
        self.current_skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self.current_skip += 1

    def handle_endtag(self, tag):
        if tag in self.skip_tags and self.current_skip > 0:
            self.current_skip -= 1

    def handle_data(self, data):
        if self.current_skip == 0:
            self.text_parts.append(data)

    def get_text(self):
        return ''.join(self.text_parts).strip()


def html_to_text(html: str) -> str:
    parser = HTMLTextExtractor()
    parser.feed(html)
    return parser.get_text()


# ============ Kiwix Matching ============

def get_wikipedia_article(title: str) -> Optional[str]:
    """Wikipedia 문서 HTML 가져오기"""
    zim = get_wikipedia()

    paths_to_try = [
        f"A/{title}",
        f"A/{title.replace(' ', '_')}",
        title,
        title.replace(' ', '_'),
    ]

    for path in paths_to_try:
        try:
            entry = zim.get_entry_by_path(path)
            if entry.is_redirect:
                entry = entry.get_redirect_entry()
            item = entry.get_item()
            return bytes(item.content).decode('utf-8')
        except (KeyError, RuntimeError):
            continue

    return None


def extract_qid_from_html(html: str) -> Optional[str]:
    """HTML에서 Wikidata QID 추출"""
    match = re.search(r'wikidata\.org/wiki/(Q\d+)', html)
    return match.group(1) if match else None


def extract_years_from_html(html: str) -> Tuple[Optional[int], Optional[int]]:
    """HTML에서 생몰년 추출"""
    text = html_to_text(html)[:500]

    patterns = [
        r'\((\d{1,4})\s*[–-]\s*(\d{1,4})\)',  # (1769–1821)
        r'\(c\.\s*(\d{1,4})\s*[–-]\s*(\d{1,4})\)',  # (c. 1412 – 1431)
        r'\((\d{1,4})\s*BC\s*[–-]\s*(\d{1,4})\s*BC\)',  # BCE
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            birth = int(match.group(1))
            death = int(match.group(2)) if match.group(2) else None
            if 'BC' in pattern:
                birth = -birth
                death = -death if death else None
            return birth, death

    return None, None


def match_with_kiwix(name: str, birth_year: Optional[int] = None, death_year: Optional[int] = None) -> Dict:
    """Kiwix Wikipedia로 매칭 시도"""
    html = get_wikipedia_article(name)

    if not html:
        return {"source": "kiwix", "status": "not_found"}

    qid = extract_qid_from_html(html)
    if not qid:
        return {"source": "kiwix", "status": "no_qid"}

    wiki_birth, wiki_death = extract_years_from_html(html)

    # 생몰년 검증
    lifespan_match = True
    if birth_year and wiki_birth:
        if abs(birth_year - wiki_birth) > 5:
            lifespan_match = False
    if death_year and wiki_death:
        if abs(death_year - wiki_death) > 5:
            lifespan_match = False

    return {
        "source": "kiwix",
        "status": "matched" if lifespan_match else "uncertain",
        "qid": qid,
        "wiki_birth": wiki_birth,
        "wiki_death": wiki_death,
        "lifespan_match": lifespan_match,
    }


# ============ Wikidata API Fallback ============

def match_with_wikidata_api(name: str, birth_year: Optional[int] = None) -> Dict:
    """Wikidata Reconciliation API로 매칭 (폴백)"""
    try:
        query = {"q0": {"query": name, "type": "Q5"}}  # Q5 = human

        if birth_year:
            # 생년 힌트 추가
            query["q0"]["properties"] = [
                {"pid": "P569", "v": str(birth_year)}  # P569 = date of birth
            ]

        response = requests.post(
            RECONCILE_API,
            data={"queries": json.dumps(query)},
            timeout=30
        )

        if response.status_code != 200:
            return {"source": "wikidata_api", "status": "api_error", "error": response.status_code}

        data = response.json()
        results = data.get("q0", {}).get("result", [])

        if not results:
            return {"source": "wikidata_api", "status": "no_match"}

        best = results[0]
        return {
            "source": "wikidata_api",
            "status": "matched" if best.get("score", 0) > 80 else "uncertain",
            "qid": best.get("id"),
            "score": best.get("score"),
            "name_match": best.get("name"),
        }

    except Exception as e:
        return {"source": "wikidata_api", "status": "error", "error": str(e)}


# ============ Hybrid Matching ============

def hybrid_match(person: Dict, use_api_fallback: bool = True) -> Dict:
    """하이브리드 매칭: Kiwix 우선, API 폴백"""
    name = person.get("name", "")
    birth_year = person.get("birth_year")
    death_year = person.get("death_year")

    # 1차: Kiwix 시도
    result = match_with_kiwix(name, birth_year, death_year)

    # Kiwix에서 찾음
    if result["status"] == "matched":
        return result

    # 2차: API 폴백 (옵션)
    if use_api_fallback and result["status"] in ("not_found", "no_qid"):
        time.sleep(0.5)  # API rate limit
        api_result = match_with_wikidata_api(name, birth_year)
        api_result["kiwix_tried"] = True
        return api_result

    return result


# ============ Checkpoint Management ============

def load_checkpoint() -> Tuple[int, Dict]:
    """체크포인트 로드 (기존 형식 호환)"""
    if INDEX_FILE.exists():
        with open(INDEX_FILE, 'r', encoding='utf-8') as f:
            index = json.load(f)
            # 기존 형식(last_offset) 또는 새 형식(last_id) 지원
            last = index.get("last_offset", index.get("last_id", 0))
            return last, index.get("stats", {})
    return 0, {}


def save_checkpoint(last_offset: int, stats: Dict):
    """체크포인트 저장 (기존 형식 유지)"""
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump({"last_offset": last_offset, "stats": stats}, f)


def append_result(result: Dict):
    """결과 추가 (JSONL)"""
    RESULTS_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_JSONL, 'a', encoding='utf-8') as f:
        f.write(json.dumps(result, ensure_ascii=False) + '\n')


# ============ Main Processing ============

def process_persons(limit: int = 1000, resume: bool = True, kiwix_only: bool = False):
    """persons 테이블 처리"""
    from app.db.session import SessionLocal
    from app.models import Person

    db = SessionLocal()

    try:
        # 체크포인트 로드
        offset, stats = load_checkpoint() if resume else (0, {})

        if not stats or "kiwix_matched" not in stats:
            # 기존 stats 형식 변환 또는 새로 시작
            old_matched = stats.get("matched", 0)
            stats = {
                "kiwix_matched": 0,
                "api_matched": old_matched,
                "uncertain": stats.get("uncertain", 0),
                "not_found": stats.get("no_match", 0),
                "total": stats.get("total", 0)
            }

        print(f"Starting from offset: {offset}")
        print(f"Current stats: {stats}")
        print(f"Mode: {'Kiwix only' if kiwix_only else 'Kiwix + API fallback'}")
        print("-" * 60)

        # 처리할 persons 가져오기 (offset 방식)
        persons = db.query(Person).order_by(Person.id).offset(offset).limit(limit).all()

        if not persons:
            print("No more persons to process!")
            return

        for i, person in enumerate(persons):
            person_data = {
                "id": person.id,
                "name": person.name,
                "birth_year": person.birth_year,
                "death_year": person.death_year,
                "existing_qid": person.wikidata_id,
            }

            # 하이브리드 매칭
            result = hybrid_match(person_data, use_api_fallback=not kiwix_only)
            result["person_id"] = person.id
            result["person_name"] = person.name

            # 통계 업데이트
            stats["total"] += 1
            if result["status"] == "matched":
                if result["source"] == "kiwix":
                    stats["kiwix_matched"] += 1
                else:
                    stats["api_matched"] += 1
            elif result["status"] == "uncertain":
                stats["uncertain"] += 1
            else:
                stats["not_found"] += 1

            # 결과 저장
            append_result(result)

            # 진행 상황 출력
            status_icon = "✓" if result["status"] == "matched" else "?" if result["status"] == "uncertain" else "✗"
            qid_str = result.get("qid", "-")
            print(f"[{offset + i + 1}] {status_icon} {person.name} → {qid_str} ({result['source']})")

            # 체크포인트 저장 (100개마다)
            if (i + 1) % 100 == 0:
                save_checkpoint(offset + i + 1, stats)
                print(f"  [Checkpoint saved at offset {offset + i + 1}]")

        # 최종 체크포인트 저장
        save_checkpoint(offset + len(persons), stats)

        print("-" * 60)
        print(f"Completed! Processed {len(persons)} persons")
        print(f"Stats: {json.dumps(stats, indent=2)}")

    finally:
        db.close()


def show_stats():
    """현재 통계 표시"""
    last_id, stats = load_checkpoint()
    print(f"Last processed ID: {last_id}")
    print(f"Stats: {json.dumps(stats, indent=2)}")

    if RESULTS_JSONL.exists():
        with open(RESULTS_JSONL, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        print(f"Total results in JSONL: {len(lines)}")


# ============ CLI ============

def main():
    parser = argparse.ArgumentParser(description="Kiwix-first Reconciliation")
    parser.add_argument("--limit", type=int, default=1000, help="Number of persons to process")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--kiwix-only", action="store_true", help="Use Kiwix only, no API fallback")
    parser.add_argument("--stats", action="store_true", help="Show current stats")

    args = parser.parse_args()

    if args.stats:
        show_stats()
        return

    process_persons(
        limit=args.limit,
        resume=args.resume,
        kiwix_only=args.kiwix_only
    )


if __name__ == "__main__":
    main()
