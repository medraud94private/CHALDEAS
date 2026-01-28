"""
Wikipedia 추출 데이터 보강 - 빈 필드 채우기

기존 JSONL (path 있음) → ZIM에서 content/links/qid 추출 → enriched JSONL

Usage:
    python enrich_wikipedia_extract.py --type persons --workers 16
    python enrich_wikipedia_extract.py --type all --workers 16
    python enrich_wikipedia_extract.py --resume
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import re
import argparse
import multiprocessing as mp
from pathlib import Path
from typing import Optional, List, Dict, Any
from html.parser import HTMLParser
from datetime import datetime
from functools import partial

from libzim.reader import Archive

# ============ Config ============

ZIM_PATH = Path(__file__).parent.parent.parent / "data" / "kiwix" / "wikipedia_en_nopic.zim"
INPUT_DIR = Path(__file__).parent.parent / "data" / "wikipedia_extract"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "wikipedia_enriched"
CHECKPOINT_FILE = OUTPUT_DIR / "enrich_checkpoint.json"

WIKIPEDIA_BASE_URL = "https://en.wikipedia.org/wiki/"


# ============ HTML Parsers ============

class FullTextExtractor(HTMLParser):
    """전체 본문 추출 (깨끗한 텍스트)"""
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.skip_tags = {'script', 'style', 'nav', 'header', 'footer', 'aside', 'sup', 'sub', 'table'}
        self.current_skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self.current_skip += 1

    def handle_endtag(self, tag):
        if tag in self.skip_tags and self.current_skip > 0:
            self.current_skip -= 1
        if tag in ('p', 'div', 'br', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'tr'):
            self.text_parts.append('\n')

    def handle_data(self, data):
        if self.current_skip == 0:
            self.text_parts.append(data)

    def get_text(self) -> str:
        text = ''.join(self.text_parts)
        text = re.sub(r'\n\s*\n+', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        text = re.sub(r'\n +', '\n', text)
        return text.strip()


class LinkExtractor(HTMLParser):
    """내부 링크 추출"""
    def __init__(self):
        super().__init__()
        self.links = set()
        self.in_content = False
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        if tag == 'div' and attrs_dict.get('id') == 'mw-content-text':
            self.in_content = True

        if tag in ('nav', 'aside') or 'navbox' in attrs_dict.get('class', ''):
            self.skip_depth += 1
            return

        if self.in_content and self.skip_depth == 0 and tag == 'a':
            href = attrs_dict.get('href', '')
            if not href:
                return
            if href.startswith(('http', 'https', '#', '_', 'mailto:')):
                return
            skip_prefixes = ('Special:', 'File:', 'Help:', 'Category:', 'Template:',
                           'Wikipedia:', 'Talk:', 'Portal:', 'User:', 'Module:', 'MediaWiki:')
            if any(href.startswith(p) or ('/' + p) in href for p in skip_prefixes):
                return
            link = href.replace('/wiki/', '').replace('./', '')
            link = link.split('#')[0]
            link = link.replace('_', ' ')
            if link and ':' not in link:
                self.links.add(link)

    def handle_endtag(self, tag):
        if tag in ('nav', 'aside') and self.skip_depth > 0:
            self.skip_depth -= 1


def extract_full_text(html: str) -> str:
    """HTML에서 전체 본문 추출"""
    parser = FullTextExtractor()
    try:
        parser.feed(html)
    except:
        pass
    return parser.get_text()


def extract_links(html: str) -> List[str]:
    """HTML에서 내부 링크 추출"""
    parser = LinkExtractor()
    try:
        parser.feed(html)
    except:
        pass
    return list(parser.links)


def extract_qid(html: str) -> Optional[str]:
    """HTML에서 Wikidata QID 추출"""
    match = re.search(r'wikidata\.org/wiki/(Q\d+)', html)
    return match.group(1) if match else None


def extract_summary(html: str) -> str:
    """첫 문단 추출 (깨끗하게)"""
    text = extract_full_text(html[:15000])
    paragraphs = text.split('\n\n')
    for p in paragraphs:
        p = p.strip()
        if len(p) > 50:
            return p[:1000]
    return text[:1000] if text else ""


# ============ Worker Function ============

def process_record(record: Dict[str, Any], zim_path: str) -> Dict[str, Any]:
    """단일 레코드 보강"""
    try:
        zim = Archive(zim_path)
        path = record.get('path')

        if not path:
            record['_error'] = 'no_path'
            return record

        # ZIM에서 문서 찾기
        try:
            entry = zim.get_entry_by_path(path)
            if entry.is_redirect:
                entry = entry.get_redirect_entry()
            item = entry.get_item()
            html = bytes(item.content).decode('utf-8', errors='ignore')
        except Exception as e:
            record['_error'] = f'zim_error: {str(e)[:50]}'
            return record

        # 필드 채우기
        record['content'] = extract_full_text(html)
        record['links'] = extract_links(html)
        record['wikipedia_url'] = WIKIPEDIA_BASE_URL + path.replace(' ', '_')

        # qid 없으면 다시 시도
        if not record.get('qid'):
            record['qid'] = extract_qid(html)

        # summary 정리
        record['summary'] = extract_summary(html)

        record['_enriched'] = True

    except Exception as e:
        record['_error'] = str(e)[:100]

    return record


def process_batch(records: List[Dict], zim_path: str) -> List[Dict]:
    """배치 처리 (워커당 ZIM 한 번만 열기)"""
    zim = Archive(zim_path)
    results = []

    for record in records:
        try:
            path = record.get('path')
            if not path:
                record['_error'] = 'no_path'
                results.append(record)
                continue

            # ZIM에서 문서 찾기
            try:
                entry = zim.get_entry_by_path(path)
                if entry.is_redirect:
                    entry = entry.get_redirect_entry()
                item = entry.get_item()
                html = bytes(item.content).decode('utf-8', errors='ignore')
            except Exception as e:
                record['_error'] = f'zim_error: {str(e)[:50]}'
                results.append(record)
                continue

            # 필드 채우기
            record['content'] = extract_full_text(html)
            record['links'] = extract_links(html)
            record['wikipedia_url'] = WIKIPEDIA_BASE_URL + path.replace(' ', '_')

            if not record.get('qid'):
                record['qid'] = extract_qid(html)

            record['summary'] = extract_summary(html)
            record['_enriched'] = True

        except Exception as e:
            record['_error'] = str(e)[:100]

        results.append(record)

    return results


# ============ Main ============

def load_checkpoint() -> Dict:
    """체크포인트 로드"""
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'persons': 0, 'events': 0, 'locations': 0}


def save_checkpoint(progress: Dict):
    """체크포인트 저장"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, indent=2)


def enrich_file(entity_type: str, num_workers: int = 16, resume: bool = True):
    """파일 보강"""
    input_file = INPUT_DIR / f"{entity_type}.jsonl"
    output_file = OUTPUT_DIR / f"{entity_type}.jsonl"

    if not input_file.exists():
        print(f"Input file not found: {input_file}")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 레코드 로드
    print(f"Loading {entity_type}...", flush=True)
    records = []
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                records.append(json.loads(line.strip()))
            except:
                pass

    total = len(records)
    print(f"Loaded {total:,} records", flush=True)

    # 체크포인트
    checkpoint = load_checkpoint() if resume else {'persons': 0, 'events': 0, 'locations': 0}
    start_idx = checkpoint.get(entity_type, 0)

    if start_idx >= total:
        print(f"Already completed: {entity_type}")
        return

    print(f"Starting from: {start_idx:,}", flush=True)
    print(f"Workers: {num_workers}", flush=True)
    print("-" * 60, flush=True)

    # 출력 파일 (append 모드)
    mode = 'a' if start_idx > 0 else 'w'
    out_f = open(output_file, mode, encoding='utf-8')

    start_time = datetime.now()
    batch_size = 500
    processed = start_idx
    enriched = 0
    errors = 0

    zim_path = str(ZIM_PATH)

    try:
        # 배치 단위로 처리
        for batch_start in range(start_idx, total, batch_size * num_workers):
            batch_end = min(batch_start + batch_size * num_workers, total)
            batch_records = records[batch_start:batch_end]

            # 워커별로 배치 나누기
            worker_batches = []
            per_worker = len(batch_records) // num_workers + 1
            for i in range(0, len(batch_records), per_worker):
                worker_batches.append(batch_records[i:i+per_worker])

            # 병렬 처리
            with mp.Pool(num_workers) as pool:
                process_func = partial(process_batch, zim_path=zim_path)
                results_nested = pool.map(process_func, worker_batches)

            # 결과 저장
            for batch_results in results_nested:
                for record in batch_results:
                    out_f.write(json.dumps(record, ensure_ascii=False) + '\n')
                    processed += 1
                    if record.get('_enriched'):
                        enriched += 1
                    if record.get('_error'):
                        errors += 1

            out_f.flush()

            # 진행상황
            elapsed = (datetime.now() - start_time).total_seconds()
            rate = (processed - start_idx) / elapsed if elapsed > 0 else 0
            eta = (total - processed) / rate / 60 if rate > 0 else 0
            pct = processed / total * 100

            print(f"[{processed:,}/{total:,} ({pct:.1f}%)] "
                  f"enriched:{enriched:,} errors:{errors:,} "
                  f"({rate:.0f}/s, ETA:{eta:.0f}min)", flush=True)

            # 체크포인트 저장
            checkpoint[entity_type] = processed
            save_checkpoint(checkpoint)

    finally:
        out_f.close()

    elapsed = (datetime.now() - start_time).total_seconds() / 60
    print("-" * 60, flush=True)
    print(f"Completed {entity_type} in {elapsed:.1f} minutes", flush=True)
    print(f"Total: {processed:,}, Enriched: {enriched:,}, Errors: {errors:,}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Enrich Wikipedia extraction data")
    parser.add_argument("--type", choices=['persons', 'events', 'locations', 'all'], default='all')
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--resume", action="store_true", default=True)
    parser.add_argument("--no-resume", action="store_true")

    args = parser.parse_args()

    resume = not args.no_resume

    if args.type == 'all':
        for entity_type in ['persons', 'events', 'locations']:
            enrich_file(entity_type, args.workers, resume)
    else:
        enrich_file(args.type, args.workers, resume)


if __name__ == "__main__":
    mp.freeze_support()  # Windows 지원
    main()
