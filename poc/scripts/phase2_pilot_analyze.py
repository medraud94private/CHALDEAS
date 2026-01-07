"""
Phase 2 Pilot - Step 5: Analysis and Cost Calculation
각 단계별 통계, 비용 계산, 효율 측정
"""
import json
import sys
import io
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
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

# 비용 상수 (2026년 1월 기준 추정)
COSTS = {
    "text-embedding-3-small": 0.00002 / 1000,  # $/token
    "gpt-5-nano": {
        "input": 0.0001 / 1000,   # $/token (추정)
        "output": 0.0002 / 1000,  # $/token (추정)
        "batch_discount": 0.5    # 50% 할인
    }
}


@dataclass
class PilotStats:
    # 샘플
    total_samples: int = 0
    person_samples: int = 0
    location_samples: int = 0
    samples_with_context: int = 0

    # Tier 1
    tier1_filter_out: int = 0
    tier1_merge_exact: int = 0
    tier1_separate: int = 0
    tier1_pass_to_tier2: int = 0

    # Tier 2
    tier2_total_clusters: int = 0
    tier2_singleton_clusters: int = 0
    tier2_multi_clusters: int = 0
    tier2_cluster_members: int = 0
    tier2_pass_to_tier3: int = 0

    # Tier 3
    tier3_valid: int = 0
    tier3_invalid: int = 0
    tier3_ambiguous: int = 0
    tier3_error: int = 0
    tier3_batch_count: int = 0
    tier3_realtime_count: int = 0
    tier3_batch_avg_latency: float = 0.0
    tier3_realtime_avg_latency: float = 0.0

    # 비용
    embedding_tokens: int = 0
    embedding_cost: float = 0.0
    llm_input_tokens: int = 0
    llm_output_tokens: int = 0
    llm_batch_cost: float = 0.0
    llm_realtime_cost: float = 0.0
    total_cost: float = 0.0


def load_jsonl(filepath: Path) -> List[Dict]:
    """JSONL 파일 로드"""
    results = []
    if filepath.exists():
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    results.append(json.loads(line))
    return results


def analyze_pilot() -> PilotStats:
    """파일럿 결과 분석"""
    stats = PilotStats()

    # 1. 샘플 분석
    samples = load_jsonl(PILOT_DIR / "pilot_samples_3000.jsonl")
    stats.total_samples = len(samples)
    stats.person_samples = sum(1 for s in samples if s.get("entity_type") == "person")
    stats.location_samples = sum(1 for s in samples if s.get("entity_type") == "location")
    stats.samples_with_context = sum(1 for s in samples if s.get("contexts"))

    # 2. Tier 1 분석
    tier1_results = load_jsonl(PILOT_DIR / "tier1_results.jsonl")
    for r in tier1_results:
        decision = r.get("decision", "")
        if decision == "FILTER_OUT":
            stats.tier1_filter_out += 1
        elif decision == "MERGE_EXACT":
            stats.tier1_merge_exact += 1
        elif decision == "SEPARATE":
            stats.tier1_separate += 1
        elif decision == "PASS_TO_TIER2":
            stats.tier1_pass_to_tier2 += 1

    # 3. Tier 2 분석
    tier2_results = load_jsonl(PILOT_DIR / "tier2_results.jsonl")
    cluster_ids = set()
    singleton_clusters = set()

    for r in tier2_results:
        decision = r.get("decision", "")
        cluster_id = r.get("cluster_id", -1)
        cluster_ids.add(cluster_id)

        if decision == "CLUSTER_MEMBER":
            stats.tier2_cluster_members += 1
        elif decision == "PASS_TO_TIER3":
            stats.tier2_pass_to_tier3 += 1
            singleton_clusters.add(cluster_id)

    stats.tier2_total_clusters = len(cluster_ids)
    stats.tier2_singleton_clusters = len(singleton_clusters)
    stats.tier2_multi_clusters = stats.tier2_total_clusters - stats.tier2_singleton_clusters

    # 임베딩 비용 계산 (50 tokens/item 가정)
    stats.embedding_tokens = stats.tier1_pass_to_tier2 * 50
    stats.embedding_cost = stats.embedding_tokens * COSTS["text-embedding-3-small"]

    # 4. Tier 3 분석
    tier3_results = load_jsonl(PILOT_DIR / "tier3_results.jsonl")
    batch_latencies = []
    realtime_latencies = []

    for r in tier3_results:
        decision = r.get("decision", "")
        api_mode = r.get("api_mode", "")
        latency = r.get("latency_ms", 0)

        if decision == "VALID":
            stats.tier3_valid += 1
        elif decision == "INVALID":
            stats.tier3_invalid += 1
        elif decision == "AMBIGUOUS":
            stats.tier3_ambiguous += 1
        elif decision == "ERROR":
            stats.tier3_error += 1

        if api_mode == "batch":
            stats.tier3_batch_count += 1
            batch_latencies.append(latency)
        elif api_mode == "realtime":
            stats.tier3_realtime_count += 1
            realtime_latencies.append(latency)

    if batch_latencies:
        stats.tier3_batch_avg_latency = sum(batch_latencies) / len(batch_latencies)
    if realtime_latencies:
        stats.tier3_realtime_avg_latency = sum(realtime_latencies) / len(realtime_latencies)

    # LLM 비용 계산 (200 input + 50 output tokens/item 가정)
    input_per_item = 200
    output_per_item = 50

    batch_input = stats.tier3_batch_count * input_per_item
    batch_output = stats.tier3_batch_count * output_per_item
    stats.llm_batch_cost = (
        batch_input * COSTS["gpt-5-nano"]["input"] +
        batch_output * COSTS["gpt-5-nano"]["output"]
    ) * COSTS["gpt-5-nano"]["batch_discount"]

    realtime_input = stats.tier3_realtime_count * input_per_item
    realtime_output = stats.tier3_realtime_count * output_per_item
    stats.llm_realtime_cost = (
        realtime_input * COSTS["gpt-5-nano"]["input"] +
        realtime_output * COSTS["gpt-5-nano"]["output"]
    )

    stats.llm_input_tokens = batch_input + realtime_input
    stats.llm_output_tokens = batch_output + realtime_output

    # 총 비용
    stats.total_cost = stats.embedding_cost + stats.llm_batch_cost + stats.llm_realtime_cost

    return stats


def print_report(stats: PilotStats):
    """보고서 출력"""
    print("=" * 70)
    print("           PHASE 2 PILOT TEST REPORT")
    print("=" * 70)

    # 1. 샘플 개요
    print(f"\n[1. Sample Overview]")
    print(f"  Total samples:     {stats.total_samples:,}")
    print(f"  Persons:           {stats.person_samples:,} ({stats.person_samples/stats.total_samples*100:.1f}%)")
    print(f"  Locations:         {stats.location_samples:,} ({stats.location_samples/stats.total_samples*100:.1f}%)")
    print(f"  With context:      {stats.samples_with_context:,} ({stats.samples_with_context/stats.total_samples*100:.1f}%)")

    # 2. Tier 1 결과
    print(f"\n[2. Tier 1: Rule-based Filtering]")
    tier1_total = stats.tier1_filter_out + stats.tier1_merge_exact + stats.tier1_separate + stats.tier1_pass_to_tier2
    if tier1_total > 0:
        print(f"  FILTER_OUT:        {stats.tier1_filter_out:>5} ({stats.tier1_filter_out/tier1_total*100:>5.1f}%)")
        print(f"  MERGE_EXACT:       {stats.tier1_merge_exact:>5} ({stats.tier1_merge_exact/tier1_total*100:>5.1f}%)")
        print(f"  SEPARATE:          {stats.tier1_separate:>5} ({stats.tier1_separate/tier1_total*100:>5.1f}%)")
        print(f"  PASS_TO_TIER2:     {stats.tier1_pass_to_tier2:>5} ({stats.tier1_pass_to_tier2/tier1_total*100:>5.1f}%)")

        tier1_reduction = (stats.tier1_filter_out + stats.tier1_merge_exact) / tier1_total * 100
        print(f"  --")
        print(f"  Tier 1 Reduction:  {tier1_reduction:.1f}%")
    else:
        print(f"  (No Tier 1 results found)")

    # 3. Tier 2 결과
    print(f"\n[3. Tier 2: Embedding Clustering]")
    tier2_input = stats.tier1_pass_to_tier2 + stats.tier1_separate
    tier2_total = stats.tier2_cluster_members + stats.tier2_pass_to_tier3 + stats.tier2_multi_clusters  # representatives
    if tier2_input > 0:
        print(f"  Input items:       {tier2_input:>5}")
        print(f"  Total clusters:    {stats.tier2_total_clusters:>5}")
        print(f"  Multi-member:      {stats.tier2_multi_clusters:>5}")
        print(f"  Singletons:        {stats.tier2_singleton_clusters:>5}")
        print(f"  PASS_TO_TIER3:     {stats.tier2_pass_to_tier3:>5}")

        if stats.tier2_cluster_members > 0:
            tier2_reduction = stats.tier2_cluster_members / tier2_input * 100
            print(f"  --")
            print(f"  Tier 2 Reduction:  {tier2_reduction:.1f}% (merged into representatives)")
    else:
        print(f"  (No Tier 2 results found)")

    # 4. Tier 3 결과
    print(f"\n[4. Tier 3: LLM Verification]")
    tier3_total = stats.tier3_valid + stats.tier3_invalid + stats.tier3_ambiguous + stats.tier3_error
    if tier3_total > 0:
        print(f"  Input items:       {tier3_total:>5}")
        print(f"  VALID:             {stats.tier3_valid:>5} ({stats.tier3_valid/tier3_total*100:>5.1f}%)")
        print(f"  INVALID:           {stats.tier3_invalid:>5} ({stats.tier3_invalid/tier3_total*100:>5.1f}%)")
        print(f"  AMBIGUOUS:         {stats.tier3_ambiguous:>5} ({stats.tier3_ambiguous/tier3_total*100:>5.1f}%)")
        print(f"  ERROR:             {stats.tier3_error:>5} ({stats.tier3_error/tier3_total*100:>5.1f}%)")
    else:
        print(f"  (No Tier 3 results found)")

    # 5. API 비교
    print(f"\n[5. API Comparison]")
    print(f"  {'Mode':<12} {'Count':>8} {'Avg Latency':>15}")
    print(f"  {'-'*12} {'-'*8} {'-'*15}")
    print(f"  {'Batch':<12} {stats.tier3_batch_count:>8} {stats.tier3_batch_avg_latency:>12.0f} ms")
    print(f"  {'Realtime':<12} {stats.tier3_realtime_count:>8} {stats.tier3_realtime_avg_latency:>12.0f} ms")

    # 6. 비용 분석
    print(f"\n[6. Cost Analysis]")
    print(f"  Embedding ({stats.embedding_tokens:,} tokens):  ${stats.embedding_cost:.6f}")
    print(f"  LLM Batch ({stats.tier3_batch_count} items):       ${stats.llm_batch_cost:.6f}")
    print(f"  LLM Realtime ({stats.tier3_realtime_count} items):    ${stats.llm_realtime_cost:.6f}")
    print(f"  {'-'*42}")
    print(f"  TOTAL:                          ${stats.total_cost:.6f}")

    # 7. 전체 스케일 예측
    print(f"\n[7. Full-Scale Projection (2M entities)]")
    if stats.total_samples > 0:
        scale_factor = 2_000_000 / stats.total_samples

        # Tier 1 효과 적용
        tier1_pass_rate = (stats.tier1_pass_to_tier2 + stats.tier1_separate) / stats.total_samples
        tier2_input_projected = int(2_000_000 * tier1_pass_rate)

        # Tier 2 효과 적용
        tier2_pass_rate = stats.tier2_pass_to_tier3 / max(stats.tier1_pass_to_tier2, 1) if stats.tier1_pass_to_tier2 > 0 else 1.0
        tier3_input_projected = int(tier2_input_projected * tier2_pass_rate)

        # 비용 예측
        embedding_cost_projected = tier2_input_projected * 50 * COSTS["text-embedding-3-small"]
        llm_cost_projected_batch = tier3_input_projected * 250 * COSTS["gpt-5-nano"]["input"] * COSTS["gpt-5-nano"]["batch_discount"]
        llm_cost_projected_realtime = tier3_input_projected * 250 * COSTS["gpt-5-nano"]["input"]

        total_batch = embedding_cost_projected + llm_cost_projected_batch
        total_realtime = embedding_cost_projected + llm_cost_projected_realtime

        print(f"  Tier 1 pass rate:  {tier1_pass_rate*100:.1f}%")
        print(f"  Tier 2 pass rate:  {tier2_pass_rate*100:.1f}%")
        print(f"  --")
        print(f"  Tier 2 input:      {tier2_input_projected:,} entities")
        print(f"  Tier 3 input:      {tier3_input_projected:,} entities")
        print(f"  --")
        print(f"  Cost (batch-only): ${total_batch:.2f}")
        print(f"  Cost (realtime):   ${total_realtime:.2f}")

    # 8. 효율 요약
    print(f"\n[8. Efficiency Summary]")
    if stats.total_samples > 0:
        tier1_filtered = stats.tier1_filter_out + stats.tier1_merge_exact
        tier2_merged = stats.tier2_cluster_members
        total_reduced = tier1_filtered + tier2_merged

        print(f"  Items filtered by Tier 1:  {tier1_filtered:>5} ({tier1_filtered/stats.total_samples*100:.1f}%)")
        print(f"  Items merged by Tier 2:    {tier2_merged:>5} ({tier2_merged/stats.total_samples*100:.1f}%)")
        print(f"  --")
        print(f"  Total reduction:           {total_reduced:>5} ({total_reduced/stats.total_samples*100:.1f}%)")
        print(f"  Items needing LLM:         {stats.tier2_pass_to_tier3:>5} ({stats.tier2_pass_to_tier3/stats.total_samples*100:.1f}%)")

    print("\n" + "=" * 70)


def main():
    print("Analyzing pilot results...\n")

    stats = analyze_pilot()
    print_report(stats)

    # JSON으로도 저장
    output_file = PILOT_DIR / "pilot_analysis.json"
    analysis_data = {
        "timestamp": datetime.now().isoformat(),
        "samples": {
            "total": stats.total_samples,
            "persons": stats.person_samples,
            "locations": stats.location_samples,
            "with_context": stats.samples_with_context
        },
        "tier1": {
            "filter_out": stats.tier1_filter_out,
            "merge_exact": stats.tier1_merge_exact,
            "separate": stats.tier1_separate,
            "pass_to_tier2": stats.tier1_pass_to_tier2
        },
        "tier2": {
            "total_clusters": stats.tier2_total_clusters,
            "singleton_clusters": stats.tier2_singleton_clusters,
            "multi_clusters": stats.tier2_multi_clusters,
            "cluster_members": stats.tier2_cluster_members,
            "pass_to_tier3": stats.tier2_pass_to_tier3
        },
        "tier3": {
            "valid": stats.tier3_valid,
            "invalid": stats.tier3_invalid,
            "ambiguous": stats.tier3_ambiguous,
            "error": stats.tier3_error,
            "batch_count": stats.tier3_batch_count,
            "realtime_count": stats.tier3_realtime_count,
            "batch_avg_latency_ms": stats.tier3_batch_avg_latency,
            "realtime_avg_latency_ms": stats.tier3_realtime_avg_latency
        },
        "cost": {
            "embedding_tokens": stats.embedding_tokens,
            "embedding_cost": stats.embedding_cost,
            "llm_batch_cost": stats.llm_batch_cost,
            "llm_realtime_cost": stats.llm_realtime_cost,
            "total_cost": stats.total_cost
        }
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(analysis_data, f, ensure_ascii=False, indent=2)

    print(f"\nAnalysis saved to: {output_file}")


if __name__ == "__main__":
    main()
