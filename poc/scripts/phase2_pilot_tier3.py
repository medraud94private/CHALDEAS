"""
Phase 2 Pilot - Step 4: Tier 3 LLM Verification
배치 API와 실시간 API를 사용한 엔티티 유효성 검증
- 배치 API: 50% 저렴, 10-30분 대기
- 실시간 API: 즉시 결과, 비용 2배
- 500개씩 분할하여 비교 테스트
"""
import json
import sys
import io
import os
import asyncio
import httpx
import time
import re
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import argparse

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass

DATA_DIR = Path(__file__).parent.parent / "data"
PILOT_DIR = DATA_DIR / "pilot"

# OpenAI API 설정
OPENAI_URL = "https://api.openai.com/v1"
MODEL = "gpt-5-nano"

# 처리 설정
PARALLEL_CALLS = 20  # 실시간 API 병렬 호출 수
BATCH_POLL_INTERVAL = 30  # 배치 상태 확인 간격 (초)


@dataclass
class Tier3Result:
    id: int
    entity_key: str
    text: str
    entity_type: str
    mention_count: int
    decision: str  # VALID, INVALID, AMBIGUOUS, ERROR
    confidence: float
    reason: str
    api_mode: str  # "batch" or "realtime"
    latency_ms: float = 0
    contexts: List[Dict] = field(default_factory=list)


class LLMClient:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        self.batch_file_id = None
        self.batch_id = None

    def build_prompt(self, item: Dict) -> str:
        """프롬프트 생성 (context 포함)"""
        text = item["text"]
        entity_type = item["entity_type"]
        mention_count = item.get("mention_count", 1)

        # Context 추출
        ctx_samples = []
        for ctx in item.get("contexts", [])[:3]:
            ctx_text = ctx.get("context_text", "")
            if ctx_text:
                ctx_samples.append(f'  - "{ctx_text[:80]}"')

        ctx_text = "\n".join(ctx_samples) if ctx_samples else "  (no context available)"

        prompt = f"""Entity: "{text}"
Type: {entity_type}
Mentions: {mention_count} times

Context examples:
{ctx_text}

Task: Determine if this is a valid historical entity (person, location, or event).

Rules:
1. Names like "SON", "LIMITED", "WORKS", "STREET" alone are NOT valid entities
2. Partial names without enough context are NOT valid (e.g., "J." or "Smith" alone)
3. Company suffixes (& Co., Ltd., Sons) indicate organization, not person
4. Material names (Oak, Brass, Iron) are NOT locations
5. Generic terms (January, Monday, Street) are NOT valid entities

Respond with ONE of:
- VALID: This is a legitimate {entity_type} that can be identified
- INVALID: Not a valid entity - explain briefly why
- AMBIGUOUS: Cannot determine without more context

Your response (VALID/INVALID/AMBIGUOUS + brief reason):"""

        return prompt

    def _parse_response(self, item: Dict, content: str, api_mode: str, latency: float) -> Tier3Result:
        """LLM 응답 파싱"""
        content_upper = content.upper()

        # VALID 판정
        if "VALID" in content_upper and "INVALID" not in content_upper:
            decision = "VALID"
            confidence = 0.85
            # 이유 추출 (첫 줄 또는 VALID 뒤)
            reason_match = re.search(r'VALID[:\s]*(.+?)(?:\n|$)', content, re.IGNORECASE)
            reason = reason_match.group(1).strip() if reason_match else "LLM validated as legitimate entity"

        # INVALID 판정
        elif "INVALID" in content_upper:
            decision = "INVALID"
            confidence = 0.80
            reason_match = re.search(r'INVALID[:\s]*(.+?)(?:\n|$)', content, re.IGNORECASE)
            reason = reason_match.group(1).strip() if reason_match else "LLM marked as invalid"

        # AMBIGUOUS 판정
        elif "AMBIGUOUS" in content_upper:
            decision = "AMBIGUOUS"
            confidence = 0.50
            reason_match = re.search(r'AMBIGUOUS[:\s]*(.+?)(?:\n|$)', content, re.IGNORECASE)
            reason = reason_match.group(1).strip() if reason_match else "LLM marked as ambiguous"

        # 파싱 실패
        else:
            decision = "AMBIGUOUS"
            confidence = 0.40
            reason = f"Could not parse: {content[:100]}"

        return Tier3Result(
            id=item.get("id", 0),
            entity_key=item.get("entity_key", ""),
            text=item.get("text", ""),
            entity_type=item.get("entity_type", ""),
            mention_count=item.get("mention_count", 1),
            decision=decision,
            confidence=confidence,
            reason=reason[:200],  # 이유 길이 제한
            api_mode=api_mode,
            latency_ms=latency,
            contexts=item.get("contexts", [])
        )

    # ========== 실시간 API ==========
    async def call_realtime_single(self, item: Dict) -> Tier3Result:
        """단일 실시간 API 호출"""
        start = time.time()
        prompt = self.build_prompt(item)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{OPENAI_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_completion_tokens": 100
                    }
                )

                latency = (time.time() - start) * 1000

                if response.status_code != 200:
                    return Tier3Result(
                        id=item.get("id", 0),
                        entity_key=item.get("entity_key", ""),
                        text=item.get("text", ""),
                        entity_type=item.get("entity_type", ""),
                        mention_count=item.get("mention_count", 1),
                        decision="ERROR",
                        confidence=0.0,
                        reason=f"API error: {response.status_code}",
                        api_mode="realtime",
                        latency_ms=latency,
                        contexts=item.get("contexts", [])
                    )

                content = response.json()["choices"][0]["message"]["content"].strip()
                return self._parse_response(item, content, "realtime", latency)

        except Exception as e:
            latency = (time.time() - start) * 1000
            return Tier3Result(
                id=item.get("id", 0),
                entity_key=item.get("entity_key", ""),
                text=item.get("text", ""),
                entity_type=item.get("entity_type", ""),
                mention_count=item.get("mention_count", 1),
                decision="ERROR",
                confidence=0.0,
                reason=str(e)[:100],
                api_mode="realtime",
                latency_ms=latency,
                contexts=item.get("contexts", [])
            )

    async def process_realtime(self, items: List[Dict], parallel: int = PARALLEL_CALLS) -> List[Tier3Result]:
        """실시간 API 병렬 처리"""
        results = []
        total = len(items)

        for i in range(0, total, parallel):
            chunk = items[i:i+parallel]
            tasks = [self.call_realtime_single(item) for item in chunk]
            chunk_results = await asyncio.gather(*tasks, return_exceptions=True)

            for r in chunk_results:
                if isinstance(r, Exception):
                    results.append(Tier3Result(
                        id=0,
                        entity_key="",
                        text="",
                        entity_type="",
                        mention_count=0,
                        decision="ERROR",
                        confidence=0.0,
                        reason=str(r)[:100],
                        api_mode="realtime",
                        latency_ms=0,
                        contexts=[]
                    ))
                else:
                    results.append(r)

            print(f"  Realtime: {min(i+parallel, total)}/{total}")

        return results

    # ========== 배치 API ==========
    async def prepare_batch_file(self, items: List[Dict]) -> str:
        """배치 요청 파일 생성 및 업로드"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        batch_file = PILOT_DIR / f"batch_requests_{timestamp}.jsonl"

        # 요청 파일 생성
        with open(batch_file, 'w', encoding='utf-8') as f:
            for item in items:
                prompt = self.build_prompt(item)
                request = {
                    "custom_id": item["entity_key"],
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_completion_tokens": 100
                    }
                }
                f.write(json.dumps(request, ensure_ascii=False) + "\n")

        print(f"  Batch file created: {batch_file}")

        # 파일 업로드
        async with httpx.AsyncClient(timeout=120.0) as client:
            with open(batch_file, 'rb') as f:
                response = await client.post(
                    f"{OPENAI_URL}/files",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    files={"file": (batch_file.name, f, "application/jsonl")},
                    data={"purpose": "batch"}
                )

            if response.status_code != 200:
                raise Exception(f"File upload failed: {response.status_code} - {response.text[:200]}")

            self.batch_file_id = response.json()["id"]
            print(f"  File uploaded: {self.batch_file_id}")

            return self.batch_file_id

    async def submit_batch(self) -> str:
        """배치 제출"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{OPENAI_URL}/batches",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "input_file_id": self.batch_file_id,
                    "endpoint": "/v1/chat/completions",
                    "completion_window": "24h"
                }
            )

            if response.status_code != 200:
                raise Exception(f"Batch creation failed: {response.status_code} - {response.text[:200]}")

            self.batch_id = response.json()["id"]
            print(f"  Batch submitted: {self.batch_id}")

            return self.batch_id

    async def wait_for_batch(self, poll_interval: int = BATCH_POLL_INTERVAL, max_wait: int = 7200) -> str:
        """배치 완료 대기"""
        start = time.time()

        while time.time() - start < max_wait:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{OPENAI_URL}/batches/{self.batch_id}",
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )

                if response.status_code != 200:
                    raise Exception(f"Status check failed: {response.status_code}")

                batch_info = response.json()
                status = batch_info["status"]
                completed = batch_info.get("request_counts", {}).get("completed", 0)
                total = batch_info.get("request_counts", {}).get("total", 0)

                elapsed = int(time.time() - start)
                print(f"  Batch status: {status} ({completed}/{total}) - {elapsed}s elapsed")

                if status == "completed":
                    return batch_info["output_file_id"]
                elif status in ["failed", "expired", "cancelled"]:
                    raise Exception(f"Batch failed with status: {status}")

            await asyncio.sleep(poll_interval)

        raise Exception(f"Batch timeout after {max_wait}s")

    async def download_batch_results(self, output_file_id: str) -> List[Dict]:
        """배치 결과 다운로드"""
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(
                f"{OPENAI_URL}/files/{output_file_id}/content",
                headers={"Authorization": f"Bearer {self.api_key}"}
            )

            if response.status_code != 200:
                raise Exception(f"Download failed: {response.status_code}")

            results = []
            for line in response.text.strip().split('\n'):
                if line:
                    results.append(json.loads(line))

            return results

    async def process_batch(self, items: List[Dict]) -> List[Tier3Result]:
        """배치 API 전체 처리"""
        start_time = time.time()

        print("  Preparing batch file...")
        await self.prepare_batch_file(items)

        print("  Submitting batch...")
        await self.submit_batch()

        print("  Waiting for completion...")
        output_file_id = await self.wait_for_batch()

        print("  Downloading results...")
        raw_results = await self.download_batch_results(output_file_id)

        total_time = time.time() - start_time
        avg_latency = (total_time * 1000) / len(items) if items else 0

        # 결과 파싱
        item_map = {i["entity_key"]: i for i in items}
        results = []

        for r in raw_results:
            entity_key = r["custom_id"]
            item = item_map.get(entity_key, {"entity_key": entity_key})

            content = ""
            if "response" in r and "body" in r["response"]:
                choices = r["response"]["body"].get("choices", [])
                if choices:
                    content = choices[0]["message"]["content"].strip()

            if content:
                result = self._parse_response(item, content, "batch", avg_latency)
            else:
                result = Tier3Result(
                    id=item.get("id", 0),
                    entity_key=entity_key,
                    text=item.get("text", ""),
                    entity_type=item.get("entity_type", ""),
                    mention_count=item.get("mention_count", 1),
                    decision="ERROR",
                    confidence=0.0,
                    reason="Empty response from batch",
                    api_mode="batch",
                    latency_ms=avg_latency,
                    contexts=item.get("contexts", [])
                )

            results.append(result)

        return results


async def main_async(mode: str = "both", batch_count: int = 500, realtime_count: int = 500):
    print("=" * 60)
    print("       PHASE 2 PILOT - TIER 3 LLM VERIFICATION")
    print("=" * 60)

    # Tier 3 입력 로드
    input_file = PILOT_DIR / "tier3_input.jsonl"

    if not input_file.exists():
        print(f"ERROR: Input file not found: {input_file}")
        print("Run phase2_pilot_tier2.py first!")
        return

    samples = []
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))

    print(f"Loaded {len(samples)} Tier 3 items")
    print(f"Mode: {mode}")
    print(f"Model: {MODEL}")
    print("-" * 60)

    client = LLMClient()
    all_results = []
    start_time = datetime.now()

    # 모드에 따라 처리
    if mode in ["batch", "both"]:
        batch_items = samples[:batch_count]
        if batch_items:
            print(f"\n=== Batch API Test ({len(batch_items)} items) ===")
            batch_start = time.time()
            batch_results = await client.process_batch(batch_items)
            batch_time = time.time() - batch_start
            all_results.extend(batch_results)
            print(f"  Total time: {batch_time:.1f}s")
            print(f"  Avg per item: {batch_time/len(batch_items)*1000:.0f}ms")

    if mode in ["realtime", "both"]:
        if mode == "both":
            realtime_items = samples[batch_count:batch_count+realtime_count]
        else:
            realtime_items = samples[:realtime_count]

        if realtime_items:
            print(f"\n=== Realtime API Test ({len(realtime_items)} items) ===")
            realtime_start = time.time()
            realtime_results = await client.process_realtime(realtime_items, parallel=PARALLEL_CALLS)
            realtime_time = time.time() - realtime_start
            all_results.extend(realtime_results)
            print(f"  Total time: {realtime_time:.1f}s")
            print(f"  Avg per item: {realtime_time/len(realtime_items)*1000:.0f}ms")

    # 결과 저장
    output_file = PILOT_DIR / "tier3_results.jsonl"
    with open(output_file, 'w', encoding='utf-8') as f:
        for r in all_results:
            f.write(json.dumps(asdict(r), ensure_ascii=False) + '\n')

    # 통계
    elapsed = (datetime.now() - start_time).total_seconds()

    print("\n" + "=" * 60)
    print("       TIER 3 RESULTS")
    print("=" * 60)

    # 모드별 통계
    for api_mode in ["batch", "realtime"]:
        mode_results = [r for r in all_results if r.api_mode == api_mode]
        if not mode_results:
            continue

        print(f"\n{api_mode.upper()} API:")

        decisions = {}
        for r in mode_results:
            decisions[r.decision] = decisions.get(r.decision, 0) + 1

        for decision in ["VALID", "INVALID", "AMBIGUOUS", "ERROR"]:
            count = decisions.get(decision, 0)
            pct = count / len(mode_results) * 100 if mode_results else 0
            print(f"  {decision:12s}: {count:5d} ({pct:5.1f}%)")

        avg_latency = sum(r.latency_ms for r in mode_results) / len(mode_results)
        print(f"  Avg latency: {avg_latency:.0f}ms")

    print("-" * 60)
    print(f"Total processed: {len(all_results)}")
    print(f"Total time: {elapsed:.1f}s")

    # 비용 추정
    total_tokens = len(all_results) * 250  # 대략적인 추정
    batch_cost = sum(1 for r in all_results if r.api_mode == "batch") * 250 * 0.001 / 1000 * 0.5
    realtime_cost = sum(1 for r in all_results if r.api_mode == "realtime") * 250 * 0.001 / 1000
    total_cost = batch_cost + realtime_cost

    print(f"\nEstimated cost:")
    print(f"  Batch: ${batch_cost:.4f}")
    print(f"  Realtime: ${realtime_cost:.4f}")
    print(f"  Total: ${total_cost:.4f}")

    print(f"\nSaved to: {output_file}")

    # 샘플 결과 미리보기
    print("\n" + "-" * 60)
    print("Sample VALID items:")
    valid_items = [r for r in all_results if r.decision == "VALID"][:3]
    for r in valid_items:
        print(f"  [{r.entity_type}] '{r.text}' - {r.reason[:50]}")

    print("\nSample INVALID items:")
    invalid_items = [r for r in all_results if r.decision == "INVALID"][:3]
    for r in invalid_items:
        print(f"  [{r.entity_type}] '{r.text}' - {r.reason[:50]}")


def main():
    parser = argparse.ArgumentParser(description="Phase 2 Pilot - Tier 3 LLM Verification")
    parser.add_argument("--mode", type=str, default="both", choices=["batch", "realtime", "both"],
                        help="API mode to use")
    parser.add_argument("--batch-count", type=int, default=500,
                        help="Number of items for batch API")
    parser.add_argument("--realtime-count", type=int, default=500,
                        help="Number of items for realtime API")
    args = parser.parse_args()

    asyncio.run(main_async(
        mode=args.mode,
        batch_count=args.batch_count,
        realtime_count=args.realtime_count
    ))


if __name__ == "__main__":
    main()
