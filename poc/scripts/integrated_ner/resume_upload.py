"""
Resume batch upload after timeout failure.
Uses longer timeout for large file uploads.
"""
import json
import sys
import io
import os
import asyncio
from pathlib import Path
from datetime import datetime

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

OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "integrated_ner_full"
OPENAI_URL = "https://api.openai.com/v1"


async def upload_file_chunked(file_path: Path, api_key: str, max_retries: int = 3):
    """Upload file with extended timeout and retry logic."""
    import httpx

    file_size = file_path.stat().st_size
    # Calculate timeout: 1 minute per 50MB, minimum 5 minutes
    timeout_minutes = max(5, int(file_size / (50 * 1024 * 1024)) + 2)
    timeout = httpx.Timeout(timeout_minutes * 60.0, connect=30.0)

    print(f"  File size: {file_size / (1024*1024):.1f} MB", flush=True)
    print(f"  Timeout: {timeout_minutes} minutes", flush=True)

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                with open(file_path, 'rb') as f:
                    files = {'file': (file_path.name, f, 'application/jsonl')}
                    data = {'purpose': 'batch'}

                    print(f"  Uploading (attempt {attempt + 1}/{max_retries})...", flush=True)

                    response = await client.post(
                        f"{OPENAI_URL}/files",
                        headers={"Authorization": f"Bearer {api_key}"},
                        files=files,
                        data=data
                    )

                    if response.status_code == 200:
                        result = response.json()
                        return result["id"]
                    elif response.status_code == 429:
                        retry_after = int(response.headers.get("retry-after", 60))
                        print(f"  Rate limited. Waiting {retry_after}s...", flush=True)
                        await asyncio.sleep(retry_after)
                    else:
                        print(f"  Error {response.status_code}: {response.text[:200]}", flush=True)
                        if attempt < max_retries - 1:
                            await asyncio.sleep(10)

        except httpx.ReadTimeout:
            print(f"  Timeout on attempt {attempt + 1}. Retrying...", flush=True)
            if attempt < max_retries - 1:
                await asyncio.sleep(30)
        except Exception as e:
            print(f"  Error: {e}", flush=True)
            if attempt < max_retries - 1:
                await asyncio.sleep(10)

    raise Exception(f"Failed to upload {file_path.name} after {max_retries} attempts")


async def submit_batch(client, file_id: str, api_key: str) -> str:
    """Submit batch job."""
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

    if response.status_code != 200:
        raise Exception(f"Batch submit failed: {response.status_code} - {response.text}")

    return response.json()["id"]


async def check_batch_status(client, batch_id: str, api_key: str) -> dict:
    """Check batch status."""
    response = await client.get(
        f"{OPENAI_URL}/batches/{batch_id}",
        headers={"Authorization": f"Bearer {api_key}"}
    )
    return response.json()


async def download_results(client, file_id: str, api_key: str) -> str:
    """Download results file."""
    response = await client.get(
        f"{OPENAI_URL}/files/{file_id}/content",
        headers={"Authorization": f"Bearer {api_key}"}
    )
    return response.text


async def main():
    import httpx

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")

    print("=" * 60, flush=True)
    print("   RESUME BATCH UPLOAD", flush=True)
    print("=" * 60, flush=True)

    start_time = datetime.now()

    # Find existing batch files
    batch_files = sorted(OUTPUT_DIR.glob("batch_requests_*.jsonl"))
    print(f"\nFound {len(batch_files)} batch files:", flush=True)
    for bf in batch_files:
        size_mb = bf.stat().st_size / (1024 * 1024)
        print(f"  {bf.name}: {size_mb:.1f} MB", flush=True)

    # Check if there's existing status
    status_file = OUTPUT_DIR / "batch_status.json"
    existing_status = {}
    if status_file.exists():
        with open(status_file, 'r') as f:
            existing_status = json.load(f)
        print(f"\nFound existing status: {len(existing_status.get('batch_ids', []))} batches", flush=True)

    # Upload and submit
    batch_ids = existing_status.get('batch_ids', [])
    file_ids = existing_status.get('file_ids', [])

    print(f"\n[Step 1] Uploading batch files...", flush=True)

    for i, batch_file in enumerate(batch_files):
        # Skip if already uploaded
        if i < len(file_ids):
            print(f"\n  {batch_file.name}: Already uploaded (file_id: {file_ids[i]})", flush=True)
            continue

        print(f"\n  Uploading {batch_file.name}...", flush=True)
        file_id = await upload_file_chunked(batch_file, api_key)
        file_ids.append(file_id)
        print(f"  File ID: {file_id}", flush=True)

        # Save progress
        with open(status_file, 'w') as f:
            json.dump({
                "file_ids": file_ids,
                "batch_ids": batch_ids,
                "start_time": start_time.isoformat()
            }, f, indent=2)

    print(f"\n[Step 2] Submitting batches...", flush=True)

    async with httpx.AsyncClient(timeout=60.0) as client:
        for i, file_id in enumerate(file_ids):
            # Skip if already submitted
            if i < len(batch_ids):
                print(f"  Batch {i}: Already submitted (batch_id: {batch_ids[i]})", flush=True)
                continue

            print(f"  Submitting batch {i}...", flush=True)
            batch_id = await submit_batch(client, file_id, api_key)
            batch_ids.append(batch_id)
            print(f"  Batch ID: {batch_id}", flush=True)

            # Save progress
            with open(status_file, 'w') as f:
                json.dump({
                    "file_ids": file_ids,
                    "batch_ids": batch_ids,
                    "start_time": start_time.isoformat()
                }, f, indent=2)

        print(f"\n[Step 3] Waiting for completion...", flush=True)
        print(f"  This may take 10-30 minutes. Checking every 60 seconds.", flush=True)

        all_complete = False
        while not all_complete:
            all_complete = True
            status_summary = []

            for batch_id in batch_ids:
                status = await check_batch_status(client, batch_id, api_key)
                batch_status = status.get("status", "unknown")
                counts = status.get("request_counts", {})
                completed = counts.get("completed", 0)
                failed = counts.get("failed", 0)
                total = counts.get("total", 0)

                status_summary.append(f"{batch_status}:{completed}/{total}")

                if batch_status not in ["completed", "failed", "expired", "cancelled"]:
                    all_complete = False

            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"\r  [{elapsed/60:.1f}min] Status: {', '.join(status_summary)}          ", end="", flush=True)

            if not all_complete:
                await asyncio.sleep(60)

        print(f"\n\n  All batches complete!", flush=True)

        # Download results
        print(f"\n[Step 4] Downloading results...", flush=True)
        all_results = []
        total_entities = {"persons": 0, "locations": 0, "polities": 0, "periods": 0, "events": 0}

        for batch_id in batch_ids:
            status = await check_batch_status(client, batch_id, api_key)
            output_file_id = status.get("output_file_id")

            if output_file_id:
                print(f"  Downloading from batch {batch_id}...", flush=True)
                content = await download_results(client, output_file_id, api_key)

                for line in content.strip().split('\n'):
                    if line:
                        try:
                            result = json.loads(line)
                            all_results.append(result)

                            # Count entities
                            if result.get("response", {}).get("body", {}).get("choices"):
                                content_str = result["response"]["body"]["choices"][0]["message"]["content"]
                                extraction = json.loads(content_str)
                                for key in total_entities:
                                    total_entities[key] += len(extraction.get(key, []))
                        except:
                            pass

        # Save results
        results_file = OUTPUT_DIR / f"extraction_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
        with open(results_file, 'w', encoding='utf-8') as f:
            for r in all_results:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')

        print(f"\n  Saved {len(all_results)} results to {results_file.name}", flush=True)
        print(f"\n  Entity counts:", flush=True)
        for key, count in total_entities.items():
            print(f"    {key}: {count:,}", flush=True)

        elapsed_total = (datetime.now() - start_time).total_seconds()
        print(f"\n{'=' * 60}", flush=True)
        print(f"  COMPLETE! Total time: {elapsed_total/60:.1f} minutes", flush=True)
        print(f"{'=' * 60}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
