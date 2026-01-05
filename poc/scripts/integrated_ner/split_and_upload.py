"""
Split large batch files and upload them.
Splits into 10,000-request chunks for faster uploads.
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
CHUNK_SIZE = 10000  # Requests per chunk


def split_batch_files():
    """Split large batch files into smaller chunks."""
    print("\n[Splitting batch files into 10,000-request chunks]", flush=True)

    chunk_dir = OUTPUT_DIR / "chunks"
    chunk_dir.mkdir(exist_ok=True)

    # Check if already split
    existing_chunks = list(chunk_dir.glob("chunk_*.jsonl"))
    if existing_chunks:
        print(f"  Found {len(existing_chunks)} existing chunks", flush=True)
        return sorted(existing_chunks)

    batch_files = sorted(OUTPUT_DIR.glob("batch_requests_*.jsonl"))
    all_chunks = []

    for batch_file in batch_files:
        print(f"  Splitting {batch_file.name}...", flush=True)

        chunk_num = len(all_chunks)
        current_chunk = []
        lines_read = 0

        with open(batch_file, 'r', encoding='utf-8') as f:
            for line in f:
                current_chunk.append(line)
                lines_read += 1

                if len(current_chunk) >= CHUNK_SIZE:
                    chunk_file = chunk_dir / f"chunk_{chunk_num:03d}.jsonl"
                    with open(chunk_file, 'w', encoding='utf-8') as cf:
                        cf.writelines(current_chunk)
                    all_chunks.append(chunk_file)
                    size_mb = chunk_file.stat().st_size / (1024 * 1024)
                    print(f"    Created {chunk_file.name} ({len(current_chunk)} requests, {size_mb:.1f} MB)", flush=True)
                    current_chunk = []
                    chunk_num += 1

        # Last chunk
        if current_chunk:
            chunk_file = chunk_dir / f"chunk_{chunk_num:03d}.jsonl"
            with open(chunk_file, 'w', encoding='utf-8') as cf:
                cf.writelines(current_chunk)
            all_chunks.append(chunk_file)
            size_mb = chunk_file.stat().st_size / (1024 * 1024)
            print(f"    Created {chunk_file.name} ({len(current_chunk)} requests, {size_mb:.1f} MB)", flush=True)

    print(f"\n  Total: {len(all_chunks)} chunk files", flush=True)
    return all_chunks


async def upload_file(client, file_path: Path, api_key: str, max_retries: int = 3):
    """Upload a chunk file."""
    import httpx

    for attempt in range(max_retries):
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (file_path.name, f, 'application/jsonl')}
                data = {'purpose': 'batch'}

                response = await client.post(
                    f"{OPENAI_URL}/files",
                    headers={"Authorization": f"Bearer {api_key}"},
                    files=files,
                    data=data
                )

                if response.status_code == 200:
                    return response.json()["id"]
                elif response.status_code == 429:
                    retry_after = int(response.headers.get("retry-after", 60))
                    print(f"      Rate limited. Waiting {retry_after}s...", flush=True)
                    await asyncio.sleep(retry_after)
                else:
                    print(f"      Error {response.status_code}: {response.text[:200]}", flush=True)
                    if attempt < max_retries - 1:
                        await asyncio.sleep(10)

        except httpx.ReadTimeout:
            print(f"      Timeout on attempt {attempt + 1}. Retrying...", flush=True)
            if attempt < max_retries - 1:
                await asyncio.sleep(30)
        except Exception as e:
            print(f"      Error: {e}", flush=True)
            if attempt < max_retries - 1:
                await asyncio.sleep(10)

    return None


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
        print(f"      Batch submit failed: {response.text[:200]}", flush=True)
        return None

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
    print("   SPLIT AND UPLOAD BATCH FILES", flush=True)
    print("=" * 60, flush=True)

    start_time = datetime.now()

    # Split files
    chunk_files = split_batch_files()

    # Load existing progress
    status_file = OUTPUT_DIR / "upload_status.json"
    progress = {"uploaded": {}, "batches": {}, "completed": []}
    if status_file.exists():
        with open(status_file, 'r') as f:
            progress = json.load(f)
        print(f"\nResuming from previous progress:", flush=True)
        print(f"  Uploaded: {len(progress['uploaded'])} chunks", flush=True)
        print(f"  Batches: {len(progress['batches'])} submitted", flush=True)

    # Upload and submit
    print(f"\n[Step 1] Uploading and submitting chunks...", flush=True)

    # Extended timeout for uploads (~90MB files)
    timeout = httpx.Timeout(300.0, connect=30.0)  # 5 minutes per chunk

    async with httpx.AsyncClient(timeout=timeout) as client:
        for chunk_file in chunk_files:
            chunk_name = chunk_file.name

            # Skip if already has batch
            if chunk_name in progress['batches']:
                print(f"  {chunk_name}: Already submitted (batch: {progress['batches'][chunk_name]})", flush=True)
                continue

            # Upload if not done
            if chunk_name not in progress['uploaded']:
                size_mb = chunk_file.stat().st_size / (1024 * 1024)
                print(f"  {chunk_name} ({size_mb:.1f} MB): Uploading...", flush=True)

                file_id = await upload_file(client, chunk_file, api_key)
                if not file_id:
                    print(f"    Failed to upload {chunk_name}", flush=True)
                    continue

                progress['uploaded'][chunk_name] = file_id
                print(f"    Uploaded: {file_id}", flush=True)

                # Save progress
                with open(status_file, 'w') as f:
                    json.dump(progress, f, indent=2)
            else:
                file_id = progress['uploaded'][chunk_name]
                print(f"  {chunk_name}: Already uploaded ({file_id})", flush=True)

            # Submit batch
            print(f"    Submitting batch...", flush=True)
            batch_id = await submit_batch(client, file_id, api_key)
            if not batch_id:
                print(f"    Failed to submit batch", flush=True)
                continue

            progress['batches'][chunk_name] = batch_id
            print(f"    Batch ID: {batch_id}", flush=True)

            # Save progress
            with open(status_file, 'w') as f:
                json.dump(progress, f, indent=2)

            # Small delay between submissions
            await asyncio.sleep(1)

        # Wait for completion
        print(f"\n[Step 2] Waiting for all batches to complete...", flush=True)
        print(f"  Total batches: {len(progress['batches'])}", flush=True)
        print(f"  Checking every 60 seconds...", flush=True)

        all_complete = False
        while not all_complete:
            all_complete = True
            completed_count = 0
            in_progress_count = 0
            total_completed_requests = 0
            total_failed_requests = 0

            for chunk_name, batch_id in progress['batches'].items():
                if chunk_name in progress['completed']:
                    completed_count += 1
                    continue

                status = await check_batch_status(client, batch_id, api_key)
                batch_status = status.get("status", "unknown")
                counts = status.get("request_counts", {})

                if batch_status in ["completed", "failed", "expired", "cancelled"]:
                    progress['completed'].append(chunk_name)
                    completed_count += 1
                    total_completed_requests += counts.get("completed", 0)
                    total_failed_requests += counts.get("failed", 0)
                else:
                    all_complete = False
                    in_progress_count += 1
                    total_completed_requests += counts.get("completed", 0)

            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"\r  [{elapsed/60:.1f}min] Completed: {completed_count}/{len(progress['batches'])}, "
                  f"In progress: {in_progress_count}, "
                  f"Requests: {total_completed_requests:,} done, {total_failed_requests:,} failed          ",
                  end="", flush=True)

            # Save progress
            with open(status_file, 'w') as f:
                json.dump(progress, f, indent=2)

            if not all_complete:
                await asyncio.sleep(60)

        print(f"\n\n  All batches complete!", flush=True)

        # Download results
        print(f"\n[Step 3] Downloading results...", flush=True)
        all_results = []
        total_entities = {"persons": 0, "locations": 0, "polities": 0, "periods": 0, "events": 0}
        failed_count = 0
        invalid_count = 0

        for chunk_name, batch_id in progress['batches'].items():
            status = await check_batch_status(client, batch_id, api_key)
            output_file_id = status.get("output_file_id")

            if output_file_id:
                print(f"  Downloading {chunk_name}...", flush=True)
                content = await download_results(client, output_file_id, api_key)

                for line in content.strip().split('\n'):
                    if line:
                        try:
                            result = json.loads(line)
                            all_results.append(result)

                            # Check for errors
                            if result.get("error"):
                                failed_count += 1
                                continue

                            # Count entities
                            response_body = result.get("response", {}).get("body", {})
                            if response_body.get("choices"):
                                content_str = response_body["choices"][0]["message"]["content"]
                                try:
                                    extraction = json.loads(content_str)
                                    for key in total_entities:
                                        total_entities[key] += len(extraction.get(key, []))
                                except:
                                    invalid_count += 1
                        except:
                            pass

        # Save results
        results_file = OUTPUT_DIR / f"extraction_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
        with open(results_file, 'w', encoding='utf-8') as f:
            for r in all_results:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')

        print(f"\n  Saved {len(all_results)} results to {results_file.name}", flush=True)
        print(f"\n  Results summary:", flush=True)
        print(f"    Total requests: {len(all_results):,}", flush=True)
        print(f"    API errors: {failed_count:,}", flush=True)
        print(f"    Invalid JSON: {invalid_count:,}", flush=True)

        print(f"\n  Entity counts:", flush=True)
        for key, count in total_entities.items():
            print(f"    {key}: {count:,}", flush=True)

        total_entities_sum = sum(total_entities.values())
        print(f"\n  TOTAL ENTITIES: {total_entities_sum:,}", flush=True)

        elapsed_total = (datetime.now() - start_time).total_seconds()
        print(f"\n{'=' * 60}", flush=True)
        print(f"  COMPLETE! Total time: {elapsed_total/60:.1f} minutes", flush=True)
        print(f"{'=' * 60}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
