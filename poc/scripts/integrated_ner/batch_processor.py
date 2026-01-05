"""
Integrated NER Pipeline - Full Scale Batch Processor
116,000개 문서를 OpenAI Batch API로 처리
"""
import json
import sys
import io
import os
import asyncio
import httpx
import time
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from collections import defaultdict

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)

# Load .env
def load_env():
    env_path = Path(__file__).parent.parent.parent.parent / ".env"
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

load_env()

# Paths
DATA_DIR = Path("C:/Projects/Chaldeas/data/raw/british_library/extracted/json")
OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "integrated_ner_full"
OPENAI_URL = "https://api.openai.com/v1"

# Batch API limits
MAX_REQUESTS_PER_BATCH = 50000


def get_json_schema():
    """OpenAI Structured Output JSON Schema"""
    return {
        "type": "object",
        "properties": {
            "persons": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "role": {"type": ["string", "null"]},
                        "birth_year": {"type": ["integer", "null"]},
                        "death_year": {"type": ["integer", "null"]},
                        "era": {"type": ["string", "null"]},
                        "confidence": {"type": "number"}
                    },
                    "required": ["name", "role", "birth_year", "death_year", "era", "confidence"],
                    "additionalProperties": False
                }
            },
            "locations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "location_type": {"type": ["string", "null"]},
                        "modern_name": {"type": ["string", "null"]},
                        "confidence": {"type": "number"}
                    },
                    "required": ["name", "location_type", "modern_name", "confidence"],
                    "additionalProperties": False
                }
            },
            "polities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "polity_type": {"type": ["string", "null"]},
                        "start_year": {"type": ["integer", "null"]},
                        "end_year": {"type": ["integer", "null"]},
                        "confidence": {"type": "number"}
                    },
                    "required": ["name", "polity_type", "start_year", "end_year", "confidence"],
                    "additionalProperties": False
                }
            },
            "periods": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "start_year": {"type": ["integer", "null"]},
                        "end_year": {"type": ["integer", "null"]},
                        "region": {"type": ["string", "null"]},
                        "confidence": {"type": "number"}
                    },
                    "required": ["name", "start_year", "end_year", "region", "confidence"],
                    "additionalProperties": False
                }
            },
            "events": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "year": {"type": ["integer", "null"]},
                        "persons_involved": {"type": "array", "items": {"type": "string"}},
                        "locations_involved": {"type": "array", "items": {"type": "string"}},
                        "confidence": {"type": "number"}
                    },
                    "required": ["name", "year", "persons_involved", "locations_involved", "confidence"],
                    "additionalProperties": False
                }
            }
        },
        "required": ["persons", "locations", "polities", "periods", "events"],
        "additionalProperties": False
    }


EXTRACTION_PROMPT = """Extract historical entities from this document.

RULES:
- Persons: Clear names only. Skip titles alone, abbreviations, partial names.
- Locations: Cities, regions, countries, landmarks.
- Polities: Empires, kingdoms, dynasties.
- Periods: Named eras (Renaissance, Victorian Era).
- Events: Battles, treaties, revolutions.
- Use negative years for BCE (-490 = 490 BCE).
- Confidence: 1.0=explicit, 0.5=inferred, 0.3=uncertain.

TEXT:
{text}"""


def load_document(doc_path: Path) -> str:
    """British Library 문서 로드"""
    with open(doc_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if isinstance(data, list):
        return " ".join(item[1] if len(item) > 1 else "" for item in data)
    return str(data)


def collect_all_documents() -> List[Path]:
    """모든 문서 경로 수집"""
    doc_paths = []
    for subdir in sorted(DATA_DIR.iterdir()):
        if subdir.is_dir():
            for doc_path in subdir.glob("*_text.json"):
                doc_paths.append(doc_path)
    return doc_paths


def create_batch_request(doc_id: str, text: str) -> dict:
    """단일 배치 요청 생성"""
    return {
        "custom_id": doc_id,
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": "gpt-5-nano",
            "messages": [
                {"role": "system", "content": "Extract historical entities. Return valid JSON."},
                {"role": "user", "content": EXTRACTION_PROMPT.format(text=text[:6000])}
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "extraction",
                    "strict": True,
                    "schema": get_json_schema()
                }
            },
            "max_completion_tokens": 3000
        }
    }


async def prepare_batch_files(doc_paths: List[Path], batch_size: int = MAX_REQUESTS_PER_BATCH) -> List[Path]:
    """배치 파일 준비 (대용량 최적화)"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    batch_files = []

    print(f"Preparing batch files for {len(doc_paths)} documents...", flush=True)

    current_batch = []
    batch_num = 0
    skip_count = 0
    error_count = 0

    for i, doc_path in enumerate(doc_paths):
        try:
            text = load_document(doc_path)
            if len(text) < 50:
                skip_count += 1
                continue

            doc_id = doc_path.stem
            request = create_batch_request(doc_id, text)
            current_batch.append(request)

            if len(current_batch) >= batch_size:
                batch_file = OUTPUT_DIR / f"batch_requests_{batch_num}.jsonl"
                with open(batch_file, 'w', encoding='utf-8') as f:
                    for req in current_batch:
                        f.write(json.dumps(req, ensure_ascii=False) + '\n')
                batch_files.append(batch_file)
                print(f"  Created {batch_file.name} ({len(current_batch)} requests)", flush=True)
                current_batch = []
                batch_num += 1

        except Exception as e:
            error_count += 1
            if error_count <= 10:  # 처음 10개만 출력
                print(f"  Error loading {doc_path.name}: {e}", flush=True)

        # 진행 상황 더 자주 출력
        if (i + 1) % 1000 == 0:
            print(f"  Processed {i + 1}/{len(doc_paths)} (batch {batch_num}, skipped {skip_count}, errors {error_count})...", flush=True)

    # 마지막 배치
    if current_batch:
        batch_file = OUTPUT_DIR / f"batch_requests_{batch_num}.jsonl"
        with open(batch_file, 'w', encoding='utf-8') as f:
            for req in current_batch:
                f.write(json.dumps(req, ensure_ascii=False) + '\n')
        batch_files.append(batch_file)
        print(f"  Created {batch_file.name} ({len(current_batch)} requests)", flush=True)

    print(f"  Total: {len(batch_files)} batch files, {skip_count} skipped, {error_count} errors", flush=True)
    return batch_files


async def upload_file(client: httpx.AsyncClient, file_path: Path, api_key: str, max_retries: int = 5) -> str:
    """파일 업로드 (rate limit 대응)"""
    for attempt in range(max_retries):
        with open(file_path, 'rb') as f:
            response = await client.post(
                f"{OPENAI_URL}/files",
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": (file_path.name, f, "application/jsonl")},
                data={"purpose": "batch"}
            )

        if response.status_code == 200:
            return response.json()["id"]

        if response.status_code == 429:  # Rate limit
            retry_after = int(response.headers.get("retry-after", 60))
            print(f"    Rate limited. Waiting {retry_after}s...")
            await asyncio.sleep(retry_after)
            continue

        if response.status_code >= 500:  # Server error
            wait_time = 30 * (attempt + 1)
            print(f"    Server error. Waiting {wait_time}s...")
            await asyncio.sleep(wait_time)
            continue

        raise Exception(f"Upload failed: {response.status_code} - {response.text}")

    raise Exception(f"Upload failed after {max_retries} retries")


async def submit_batch(client: httpx.AsyncClient, file_id: str, api_key: str, max_retries: int = 5) -> str:
    """배치 제출 (rate limit 대응)"""
    for attempt in range(max_retries):
        response = await client.post(
            f"{OPENAI_URL}/batches",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "input_file_id": file_id,
                "endpoint": "/v1/chat/completions",
                "completion_window": "24h"
            }
        )

        if response.status_code == 200:
            return response.json()["id"]

        if response.status_code == 429:  # Rate limit
            retry_after = int(response.headers.get("retry-after", 60))
            print(f"    Rate limited. Waiting {retry_after}s...")
            await asyncio.sleep(retry_after)
            continue

        if response.status_code >= 500:
            wait_time = 30 * (attempt + 1)
            print(f"    Server error. Waiting {wait_time}s...")
            await asyncio.sleep(wait_time)
            continue

        raise Exception(f"Batch submit failed: {response.status_code} - {response.text}")

    raise Exception(f"Batch submit failed after {max_retries} retries")


async def check_batch_status(client: httpx.AsyncClient, batch_id: str, api_key: str) -> dict:
    """배치 상태 확인"""
    response = await client.get(
        f"{OPENAI_URL}/batches/{batch_id}",
        headers={"Authorization": f"Bearer {api_key}"}
    )
    return response.json()


async def download_results(client: httpx.AsyncClient, file_id: str, api_key: str) -> str:
    """결과 파일 다운로드"""
    response = await client.get(
        f"{OPENAI_URL}/files/{file_id}/content",
        headers={"Authorization": f"Bearer {api_key}"}
    )
    return response.text


async def run_full_pipeline():
    """전체 파이프라인 실행"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")

    print("=" * 60)
    print("   INTEGRATED NER - FULL SCALE BATCH PROCESSING")
    print("=" * 60)

    start_time = datetime.now()

    # 1. 문서 수집
    print("\n[Step 1] Collecting documents...")
    doc_paths = collect_all_documents()
    print(f"  Found {len(doc_paths)} documents")

    # 2. 배치 파일 준비
    print("\n[Step 2] Preparing batch files...")
    batch_files = await prepare_batch_files(doc_paths)
    print(f"  Created {len(batch_files)} batch files")

    # 3. 배치 제출
    print("\n[Step 3] Submitting batches...")
    batch_ids = []

    async with httpx.AsyncClient(timeout=300.0) as client:
        for batch_file in batch_files:
            print(f"  Uploading {batch_file.name}...")
            file_id = await upload_file(client, batch_file, api_key)
            print(f"    File ID: {file_id}")

            print(f"  Submitting batch...")
            batch_id = await submit_batch(client, file_id, api_key)
            print(f"    Batch ID: {batch_id}")
            batch_ids.append(batch_id)

        # 상태 저장
        status_file = OUTPUT_DIR / "batch_status.json"
        with open(status_file, 'w') as f:
            json.dump({
                "batch_ids": batch_ids,
                "start_time": start_time.isoformat(),
                "total_docs": len(doc_paths)
            }, f, indent=2)

        print(f"\n  Batch IDs saved to {status_file}")

        # 4. 완료 대기
        print("\n[Step 4] Waiting for completion...")
        print("  (This may take 2-6 hours. You can check status with --status)")

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
                total = status.get("request_counts", {}).get("total", 0)

                total_completed += completed
                total_failed += failed

                if batch_status not in ["completed", "failed", "expired", "cancelled"]:
                    all_complete = False

            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"\r  Status: {total_completed}/{len(doc_paths)} completed, "
                  f"{total_failed} failed, {elapsed/60:.1f}min elapsed", end="")

            if not all_complete:
                await asyncio.sleep(60)  # 1분마다 체크

        print("\n\n  All batches complete!")

        # 5. 결과 다운로드
        print("\n[Step 5] Downloading results...")
        all_results = []

        for batch_id in batch_ids:
            status = await check_batch_status(client, batch_id, api_key)
            output_file_id = status.get("output_file_id")

            if output_file_id:
                print(f"  Downloading results for {batch_id}...")
                content = await download_results(client, output_file_id, api_key)

                for line in content.strip().split('\n'):
                    if line:
                        result = json.loads(line)
                        all_results.append(result)

        # 결과 저장
        results_file = OUTPUT_DIR / f"extraction_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
        with open(results_file, 'w', encoding='utf-8') as f:
            for r in all_results:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')

        print(f"  Saved {len(all_results)} results to {results_file}")

    # 6. 역인덱스 생성
    print("\n[Step 6] Building entity index...")
    await build_entity_index(results_file)

    elapsed_total = (datetime.now() - start_time).total_seconds()
    print(f"\n{'=' * 60}")
    print(f"  COMPLETE! Total time: {elapsed_total/3600:.1f} hours")
    print(f"{'=' * 60}")


async def build_entity_index(results_file: Path):
    """엔티티 → 문서 역인덱스 생성 (실패작 분리 저장)"""
    entity_index = defaultdict(lambda: {
        "type": None,
        "info": {},
        "docs": [],
        "count": 0
    })

    success_count = 0
    error_count = 0

    # 실패작 저장용
    failed_results = []
    invalid_structure = []

    with open(results_file, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue

            result = json.loads(line)
            doc_id = result.get("custom_id", "unknown")

            # 응답 파싱
            response = result.get("response", {})
            if response.get("status_code") != 200:
                error_count += 1
                failed_results.append({
                    "doc_id": doc_id,
                    "error": "API error",
                    "status_code": response.get("status_code"),
                    "raw": result
                })
                continue

            body = response.get("body", {})
            content = body.get("choices", [{}])[0].get("message", {}).get("content", "{}")

            try:
                extraction = json.loads(content)

                # 구조 검증
                required_keys = ["persons", "locations", "polities", "periods", "events"]
                if not all(key in extraction for key in required_keys):
                    invalid_structure.append({
                        "doc_id": doc_id,
                        "error": "Missing required keys",
                        "keys_found": list(extraction.keys()),
                        "raw": result
                    })
                    error_count += 1
                    continue

                # 각 배열이 리스트인지 확인
                if not all(isinstance(extraction[key], list) for key in required_keys):
                    invalid_structure.append({
                        "doc_id": doc_id,
                        "error": "Values are not arrays",
                        "raw": result
                    })
                    error_count += 1
                    continue

                success_count += 1

                # 각 엔티티 타입별로 인덱싱
                for person in extraction.get("persons", []):
                    key = f"person:{person['name'].lower()}"
                    entity_index[key]["type"] = "person"
                    entity_index[key]["info"] = person
                    entity_index[key]["docs"].append(doc_id)
                    entity_index[key]["count"] += 1

                for location in extraction.get("locations", []):
                    key = f"location:{location['name'].lower()}"
                    entity_index[key]["type"] = "location"
                    entity_index[key]["info"] = location
                    entity_index[key]["docs"].append(doc_id)
                    entity_index[key]["count"] += 1

                for polity in extraction.get("polities", []):
                    key = f"polity:{polity['name'].lower()}"
                    entity_index[key]["type"] = "polity"
                    entity_index[key]["info"] = polity
                    entity_index[key]["docs"].append(doc_id)
                    entity_index[key]["count"] += 1

                for period in extraction.get("periods", []):
                    key = f"period:{period['name'].lower()}"
                    entity_index[key]["type"] = "period"
                    entity_index[key]["info"] = period
                    entity_index[key]["docs"].append(doc_id)
                    entity_index[key]["count"] += 1

                for event in extraction.get("events", []):
                    key = f"event:{event['name'].lower()}"
                    entity_index[key]["type"] = "event"
                    entity_index[key]["info"] = event
                    entity_index[key]["docs"].append(doc_id)
                    entity_index[key]["count"] += 1

            except json.JSONDecodeError as e:
                error_count += 1
                invalid_structure.append({
                    "doc_id": doc_id,
                    "error": f"JSON decode error: {e}",
                    "raw": result
                })

    # 인덱스 저장
    index_file = OUTPUT_DIR / "entity_index.json"
    with open(index_file, 'w', encoding='utf-8') as f:
        json.dump(dict(entity_index), f, ensure_ascii=False, indent=2)

    # 실패작 저장 (나중에 재작업용)
    if failed_results:
        failed_file = OUTPUT_DIR / "failed_api_errors.jsonl"
        with open(failed_file, 'w', encoding='utf-8') as f:
            for item in failed_results:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')
        print(f"  API errors saved to {failed_file} ({len(failed_results)} items)")

    if invalid_structure:
        invalid_file = OUTPUT_DIR / "failed_invalid_structure.jsonl"
        with open(invalid_file, 'w', encoding='utf-8') as f:
            for item in invalid_structure:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')
        print(f"  Invalid structures saved to {invalid_file} ({len(invalid_structure)} items)")

    # 재작업 대상 doc_id 목록 저장
    retry_doc_ids = [item["doc_id"] for item in failed_results + invalid_structure]
    if retry_doc_ids:
        retry_file = OUTPUT_DIR / "retry_doc_ids.txt"
        with open(retry_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(retry_doc_ids))
        print(f"  Retry list saved to {retry_file} ({len(retry_doc_ids)} docs)")

    # 통계
    print(f"\n  Success: {success_count}, Errors: {error_count}")
    print(f"  Unique entities: {len(entity_index)}")

    # 타입별 통계
    type_counts = defaultdict(int)
    for key, info in entity_index.items():
        type_counts[info["type"]] += 1

    print(f"  By type:")
    for etype, count in sorted(type_counts.items()):
        print(f"    {etype}: {count}")

    # 가장 많이 등장하는 엔티티
    top_entities = sorted(entity_index.items(), key=lambda x: -x[1]["count"])[:20]

    print(f"\n  Top entities:")
    for key, info in top_entities[:10]:
        print(f"    {key}: {info['count']} documents")

    print(f"\n  Index saved to {index_file}")


async def check_status():
    """배치 상태 확인"""
    api_key = os.getenv("OPENAI_API_KEY")
    status_file = OUTPUT_DIR / "batch_status.json"

    if not status_file.exists():
        print("No batch status found. Run without --status first.")
        return

    with open(status_file, 'r') as f:
        status_data = json.load(f)

    batch_ids = status_data["batch_ids"]
    start_time = datetime.fromisoformat(status_data["start_time"])

    print("=" * 60)
    print("   BATCH STATUS CHECK")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=60.0) as client:
        for batch_id in batch_ids:
            status = await check_batch_status(client, batch_id, api_key)

            print(f"\nBatch: {batch_id}")
            print(f"  Status: {status.get('status')}")
            print(f"  Completed: {status.get('request_counts', {}).get('completed', 0)}")
            print(f"  Failed: {status.get('request_counts', {}).get('failed', 0)}")
            print(f"  Total: {status.get('request_counts', {}).get('total', 0)}")

    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\nElapsed: {elapsed/60:.1f} minutes")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", action="store_true", help="Check batch status")
    parser.add_argument("--index-only", type=str, help="Build index from results file")
    args = parser.parse_args()

    if args.status:
        asyncio.run(check_status())
    elif args.index_only:
        asyncio.run(build_entity_index(Path(args.index_only)))
    else:
        asyncio.run(run_full_pipeline())


if __name__ == "__main__":
    main()
