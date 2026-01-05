"""
Integrated NER Pipeline - Pilot Test
100개 문서로 새 파이프라인 테스트
"""
import json
import sys
import io
import os
import asyncio
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from schema import DocumentExtraction
from extractor import IntegratedNERExtractor, ExtractionResult


DATA_DIR = Path("C:/Projects/Chaldeas/data/raw/british_library/extracted/json")
OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "integrated_ner_pilot"


@dataclass
class PilotStats:
    total_docs: int = 0
    success_count: int = 0
    failed_count: int = 0
    total_persons: int = 0
    total_locations: int = 0
    total_polities: int = 0
    total_periods: int = 0
    total_events: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    model_usage: Dict[str, int] = None
    elapsed_seconds: float = 0.0

    def __post_init__(self):
        if self.model_usage is None:
            self.model_usage = {}


def load_document(doc_path: Path) -> str:
    """British Library 문서 로드"""
    with open(doc_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if isinstance(data, list):
        return " ".join(item[1] if len(item) > 1 else "" for item in data)
    return str(data)


async def run_pilot(num_docs: int = 100, parallel: int = 5):
    """파일럿 테스트 실행"""

    print("=" * 60)
    print("       INTEGRATED NER PIPELINE - PILOT TEST")
    print("=" * 60)
    print(f"Documents to process: {num_docs}")
    print(f"Parallel requests: {parallel}")
    print("-" * 60)

    # 출력 디렉토리 생성
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 문서 목록 수집
    doc_paths = []
    for subdir in sorted(DATA_DIR.iterdir()):
        if subdir.is_dir():
            for doc_path in subdir.glob("*_text.json"):
                doc_paths.append(doc_path)
                if len(doc_paths) >= num_docs:
                    break
        if len(doc_paths) >= num_docs:
            break

    print(f"Found {len(doc_paths)} documents")

    # 통계
    stats = PilotStats(total_docs=len(doc_paths))
    all_results = []
    start_time = datetime.now()

    # 추출기 생성
    extractor = IntegratedNERExtractor()

    # 세마포어로 동시 요청 제한
    semaphore = asyncio.Semaphore(parallel)

    async def process_one(doc_path: Path, idx: int) -> Dict:
        async with semaphore:
            try:
                text = load_document(doc_path)

                if len(text) < 50:
                    return {"doc": doc_path.name, "error": "Too short", "success": False}

                result = await extractor.extract(text)

                if result.success:
                    ext = result.extraction
                    # Handle both Pydantic model and dict
                    if hasattr(ext, 'model_dump'):
                        ext_dict = ext.model_dump()
                    else:
                        ext_dict = ext  # Already a dict

                    return {
                        "doc": doc_path.name,
                        "success": True,
                        "model": result.model_used,
                        "tokens": result.tokens_used,
                        "cost": result.cost,
                        "persons": len(ext_dict.get("persons", [])),
                        "locations": len(ext_dict.get("locations", [])),
                        "polities": len(ext_dict.get("polities", [])),
                        "periods": len(ext_dict.get("periods", [])),
                        "events": len(ext_dict.get("events", [])),
                        "extraction": ext_dict
                    }
                else:
                    return {
                        "doc": doc_path.name,
                        "success": False,
                        "error": result.error
                    }
            except Exception as e:
                return {
                    "doc": doc_path.name,
                    "success": False,
                    "error": str(e)
                }

    # 배치 처리
    print("\nProcessing documents...")
    tasks = [process_one(doc_path, i) for i, doc_path in enumerate(doc_paths)]

    for i, coro in enumerate(asyncio.as_completed(tasks)):
        result = await coro

        if result["success"]:
            stats.success_count += 1
            stats.total_persons += result.get("persons", 0)
            stats.total_locations += result.get("locations", 0)
            stats.total_polities += result.get("polities", 0)
            stats.total_periods += result.get("periods", 0)
            stats.total_events += result.get("events", 0)
            stats.total_tokens += result.get("tokens", 0)
            stats.total_cost += result.get("cost", 0)

            model = result.get("model", "unknown")
            stats.model_usage[model] = stats.model_usage.get(model, 0) + 1
        else:
            stats.failed_count += 1

        all_results.append(result)

        if (i + 1) % 10 == 0:
            print(f"  Processed {i + 1}/{len(doc_paths)} - "
                  f"Success: {stats.success_count}, Failed: {stats.failed_count}")

    stats.elapsed_seconds = (datetime.now() - start_time).total_seconds()

    # 결과 저장
    results_file = OUTPUT_DIR / f"pilot_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump({
            "stats": asdict(stats),
            "results": all_results
        }, f, ensure_ascii=False, indent=2)

    # 통계 출력
    print("\n" + "=" * 60)
    print("       PILOT TEST RESULTS")
    print("=" * 60)

    print(f"\n[Processing]")
    print(f"  Total documents:  {stats.total_docs}")
    print(f"  Success:          {stats.success_count} ({stats.success_count/stats.total_docs*100:.1f}%)")
    print(f"  Failed:           {stats.failed_count}")
    print(f"  Time:             {stats.elapsed_seconds:.1f}s")
    print(f"  Speed:            {stats.total_docs / stats.elapsed_seconds:.1f} docs/s")

    print(f"\n[Extraction Counts]")
    print(f"  Persons:          {stats.total_persons}")
    print(f"  Locations:        {stats.total_locations}")
    print(f"  Polities:         {stats.total_polities}")
    print(f"  Periods:          {stats.total_periods}")
    print(f"  Events:           {stats.total_events}")
    total_entities = stats.total_persons + stats.total_locations + stats.total_polities + stats.total_periods + stats.total_events
    print(f"  TOTAL:            {total_entities}")
    if stats.success_count > 0:
        print(f"  Avg per doc:      {total_entities / stats.success_count:.1f}")

    print(f"\n[Cost]")
    print(f"  Total tokens:     {stats.total_tokens:,}")
    print(f"  Total cost:       ${stats.total_cost:.4f}")
    if stats.success_count > 0:
        print(f"  Avg cost/doc:     ${stats.total_cost / stats.success_count:.6f}")

    print(f"\n[Model Usage]")
    for model, count in sorted(stats.model_usage.items()):
        print(f"  {model}: {count} ({count/stats.success_count*100:.1f}%)")

    # 전체 스케일 예측
    print(f"\n[Full Scale Projection (116,000 docs)]")
    if stats.success_count > 0:
        scale = 116000 / stats.success_count
        projected_cost = stats.total_cost * scale
        projected_entities = total_entities * scale
        print(f"  Estimated cost:   ${projected_cost:.2f}")
        print(f"  Estimated entities: {projected_entities:,.0f}")

    print(f"\nResults saved to: {results_file}")

    # 샘플 결과 출력
    print("\n" + "-" * 60)
    print("Sample extractions:")

    for result in all_results[:3]:
        if result.get("success") and result.get("extraction"):
            print(f"\n  [{result['doc']}]")
            ext = result["extraction"]

            if ext.get("persons"):
                print(f"    Persons: ", end="")
                names = [p["name"] for p in ext["persons"][:3]]
                print(", ".join(names))

            if ext.get("polities"):
                print(f"    Polities: ", end="")
                names = [p["name"] for p in ext["polities"][:2]]
                print(", ".join(names))

            if ext.get("events"):
                print(f"    Events: ", end="")
                names = [e["name"] for e in ext["events"][:2]]
                print(", ".join(names))


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--num", type=int, default=100, help="Number of documents")
    parser.add_argument("--parallel", type=int, default=5, help="Parallel requests")
    args = parser.parse_args()

    asyncio.run(run_pilot(args.num, args.parallel))


if __name__ == "__main__":
    main()
