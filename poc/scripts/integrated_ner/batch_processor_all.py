"""
Integrated NER Pipeline - All Sources Batch Processor
British Library 외 Gutenberg 등 모든 소스 처리
"""
import json
import sys
import io
import os
import asyncio
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)

# Import from main processor
sys.path.insert(0, str(Path(__file__).parent))
from batch_processor import (
    load_env, create_batch_request, upload_file, submit_batch,
    check_batch_status, download_results, build_entity_index,
    get_json_schema, OPENAI_URL, MAX_REQUESTS_PER_BATCH
)

load_env()

RAW_DIR = Path("C:/Projects/Chaldeas/data/raw")
OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "integrated_ner_full"


def load_gutenberg_document(doc_path: Path) -> str:
    """Gutenberg 문서 로드 (txt 또는 json)"""
    try:
        if doc_path.suffix == '.txt':
            with open(doc_path, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
        elif doc_path.suffix == '.json':
            with open(doc_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data.get('text', data.get('content', str(data)))
                elif isinstance(data, list):
                    return " ".join(str(item) for item in data)
                return str(data)
    except Exception as e:
        return ""
    return ""


def load_generic_document(doc_path: Path) -> str:
    """일반 문서 로드"""
    try:
        if doc_path.suffix == '.json':
            with open(doc_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    # 다양한 필드 시도
                    for key in ['text', 'content', 'body', 'description', 'extract']:
                        if key in data and data[key]:
                            return str(data[key])
                    return json.dumps(data, ensure_ascii=False)
                elif isinstance(data, list):
                    # British Library 형식
                    if data and isinstance(data[0], list) and len(data[0]) > 1:
                        return " ".join(item[1] if len(item) > 1 else "" for item in data)
                    return " ".join(str(item) for item in data)
                return str(data)
        elif doc_path.suffix in ['.txt', '.html', '.xml']:
            with open(doc_path, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
    except Exception as e:
        return ""
    return ""


def collect_all_sources() -> Dict[str, List[Path]]:
    """모든 소스에서 문서 수집"""
    sources = {}

    for source_dir in sorted(RAW_DIR.iterdir()):
        if not source_dir.is_dir():
            continue

        source_name = source_dir.name
        docs = []

        # 각 소스별 파일 패턴
        if source_name == 'british_library':
            # 이미 처리됨, 스킵
            continue
        elif source_name == 'gutenberg':
            for ext in ['*.txt', '*.json']:
                docs.extend(source_dir.rglob(ext))
        else:
            for ext in ['*.json', '*.txt', '*.html', '*.xml']:
                docs.extend(source_dir.rglob(ext))

        if docs:
            sources[source_name] = docs

    return sources


async def prepare_batch_files_for_source(
    source_name: str,
    doc_paths: List[Path],
    batch_size: int = MAX_REQUESTS_PER_BATCH
) -> List[Path]:
    """특정 소스의 배치 파일 준비"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    batch_files = []

    print(f"\n[{source_name}] Preparing {len(doc_paths)} documents...", flush=True)

    current_batch = []
    batch_num = 0
    skip_count = 0
    error_count = 0

    for i, doc_path in enumerate(doc_paths):
        try:
            text = load_generic_document(doc_path)
            if len(text) < 50:
                skip_count += 1
                continue

            # 문서 ID: 소스명_파일명
            doc_id = f"{source_name}_{doc_path.stem}"
            request = create_batch_request(doc_id, text)
            current_batch.append(request)

            if len(current_batch) >= batch_size:
                batch_file = OUTPUT_DIR / f"batch_{source_name}_{batch_num}.jsonl"
                with open(batch_file, 'w', encoding='utf-8') as f:
                    for req in current_batch:
                        f.write(json.dumps(req, ensure_ascii=False) + '\n')
                batch_files.append(batch_file)
                print(f"  Created {batch_file.name} ({len(current_batch)} requests)", flush=True)
                current_batch = []
                batch_num += 1

        except Exception as e:
            error_count += 1
            if error_count <= 5:
                print(f"  Error: {doc_path.name}: {e}", flush=True)

        if (i + 1) % 1000 == 0:
            print(f"  Processed {i+1}/{len(doc_paths)}...", flush=True)

    # 마지막 배치
    if current_batch:
        batch_file = OUTPUT_DIR / f"batch_{source_name}_{batch_num}.jsonl"
        with open(batch_file, 'w', encoding='utf-8') as f:
            for req in current_batch:
                f.write(json.dumps(req, ensure_ascii=False) + '\n')
        batch_files.append(batch_file)
        print(f"  Created {batch_file.name} ({len(current_batch)} requests)", flush=True)

    print(f"  [{source_name}] Done: {len(batch_files)} files, {skip_count} skipped, {error_count} errors", flush=True)
    return batch_files


async def run_remaining_sources():
    """British Library 외 나머지 소스 처리"""
    import httpx

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")

    print("=" * 60)
    print("   INTEGRATED NER - REMAINING SOURCES")
    print("=" * 60)

    start_time = datetime.now()

    # 1. 모든 소스 수집
    print("\n[Step 1] Collecting remaining sources...")
    sources = collect_all_sources()

    total_docs = sum(len(docs) for docs in sources.values())
    print(f"  Found {len(sources)} sources, {total_docs} documents total")

    for name, docs in sorted(sources.items(), key=lambda x: -len(x[1])):
        print(f"    {name}: {len(docs)}")

    # 2. 각 소스별 배치 파일 준비
    print("\n[Step 2] Preparing batch files...")
    all_batch_files = []

    for source_name, doc_paths in sources.items():
        batch_files = await prepare_batch_files_for_source(source_name, doc_paths)
        all_batch_files.extend(batch_files)

    print(f"\n  Total batch files: {len(all_batch_files)}")

    if not all_batch_files:
        print("  No batch files to process.")
        return

    # 3. 배치 제출
    print("\n[Step 3] Submitting batches...")
    batch_ids = []

    async with httpx.AsyncClient(timeout=300.0) as client:
        for batch_file in all_batch_files:
            print(f"  Uploading {batch_file.name}...", flush=True)
            file_id = await upload_file(client, batch_file, api_key)

            print(f"  Submitting batch...", flush=True)
            batch_id = await submit_batch(client, file_id, api_key)
            print(f"    Batch ID: {batch_id}", flush=True)
            batch_ids.append(batch_id)

        # 상태 저장
        status_file = OUTPUT_DIR / "batch_status_remaining.json"
        with open(status_file, 'w') as f:
            json.dump({
                "batch_ids": batch_ids,
                "start_time": start_time.isoformat(),
                "sources": {name: len(docs) for name, docs in sources.items()}
            }, f, indent=2)

        print(f"\n  Saved status to {status_file}")

        # 4. 완료 대기
        print("\n[Step 4] Waiting for completion...")

        all_complete = False
        while not all_complete:
            all_complete = True
            total_completed = 0
            total_failed = 0

            for batch_id in batch_ids:
                status = await check_batch_status(client, batch_id, api_key)
                batch_status = status.get("status", "unknown")
                completed = status.get("request_counts", {}).get("completed", 0)
                failed = status.get("request_counts", {}).get("failed", 0)

                total_completed += completed
                total_failed += failed

                if batch_status not in ["completed", "failed", "expired", "cancelled"]:
                    all_complete = False

            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"\r  Status: {total_completed} completed, {total_failed} failed, {elapsed/60:.1f}min elapsed", end="", flush=True)

            if not all_complete:
                await asyncio.sleep(60)

        print("\n\n  All batches complete!")

        # 5. 결과 다운로드
        print("\n[Step 5] Downloading results...")
        all_results = []

        for batch_id in batch_ids:
            status = await check_batch_status(client, batch_id, api_key)
            output_file_id = status.get("output_file_id")

            if output_file_id:
                content = await download_results(client, output_file_id, api_key)
                for line in content.strip().split('\n'):
                    if line:
                        all_results.append(json.loads(line))

        # 결과 저장
        results_file = OUTPUT_DIR / f"extraction_remaining_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
        with open(results_file, 'w', encoding='utf-8') as f:
            for r in all_results:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')

        print(f"  Saved {len(all_results)} results to {results_file}")

    elapsed_total = (datetime.now() - start_time).total_seconds()
    print(f"\n{'=' * 60}")
    print(f"  COMPLETE! Total time: {elapsed_total/60:.1f} minutes")
    print(f"{'=' * 60}")


def main():
    asyncio.run(run_remaining_sources())


if __name__ == "__main__":
    main()
