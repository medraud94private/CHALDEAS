"""
Phase 2 Pilot - Step 3: Tier 2 Embedding Clustering
text-embedding-3-small을 사용한 의미 기반 클러스터링
- 같은 entity_type끼리만 비교
- 코사인 유사도 threshold 기반 클러스터링
- 싱글톤 클러스터는 Tier 3로 전달
"""
import json
import sys
import io
import os
import asyncio
import httpx
import numpy as np
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional, Tuple, Set
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

# OpenAI API 설정
OPENAI_URL = "https://api.openai.com/v1"
EMBEDDING_MODEL = "text-embedding-3-small"

# 클러스터링 설정
SIMILARITY_THRESHOLD = 0.85  # 같은 엔티티로 판단하는 임계값
BATCH_SIZE = 100  # 한 번에 임베딩할 개수


@dataclass
class EmbeddingItem:
    entity_key: str
    text: str
    entity_type: str
    mention_count: int
    embedding: List[float] = field(default_factory=list)
    contexts: List[Dict] = field(default_factory=list)


@dataclass
class Cluster:
    cluster_id: int
    representative_key: str
    representative_text: str
    entity_type: str
    members: List[str]  # entity_keys
    member_texts: List[str]
    avg_similarity: float


@dataclass
class Tier2Result:
    id: int
    entity_key: str
    text: str
    entity_type: str
    mention_count: int
    cluster_id: int
    is_representative: bool
    decision: str  # CLUSTER_MEMBER, CLUSTER_REPRESENTATIVE, PASS_TO_TIER3
    reason: str
    similarity_to_representative: float = 0.0
    contexts: List[Dict] = field(default_factory=list)


class EmbeddingClient:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Batch embedding 호출"""
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{OPENAI_URL}/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": EMBEDDING_MODEL,
                    "input": texts
                }
            )

            if response.status_code != 200:
                raise Exception(f"Embedding error: {response.status_code} - {response.text[:200]}")

            data = response.json()
            # 순서 보장을 위해 index로 정렬
            embeddings = sorted(data["data"], key=lambda x: x["index"])
            return [e["embedding"] for e in embeddings]


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """코사인 유사도 계산"""
    a_arr = np.array(a)
    b_arr = np.array(b)
    dot = np.dot(a_arr, b_arr)
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def build_embedding_text(item: Dict) -> str:
    """임베딩용 텍스트 생성 (entity + context)"""
    text = item["text"]
    entity_type = item["entity_type"]

    # Context 추가 (있으면)
    ctx_parts = []
    for ctx in item.get("contexts", [])[:2]:
        ctx_text = ctx.get("context_text", "")
        if ctx_text:
            # 너무 긴 context는 자르기
            ctx_parts.append(ctx_text[:100])

    ctx_str = " | ".join(ctx_parts) if ctx_parts else ""

    if ctx_str:
        return f"{text} ({entity_type}) | Context: {ctx_str}"
    else:
        return f"{text} ({entity_type})"


def cluster_by_similarity(
    items: List[EmbeddingItem],
    threshold: float = SIMILARITY_THRESHOLD
) -> List[Cluster]:
    """
    임계값 기반 클러스터링 (행렬 곱 최적화)
    같은 entity_type끼리만 비교
    mention_count가 높은 항목을 대표로 선정
    """
    clusters = []

    # entity_type별로 분리
    by_type: Dict[str, List[EmbeddingItem]] = {}
    for item in items:
        if item.entity_type not in by_type:
            by_type[item.entity_type] = []
        by_type[item.entity_type].append(item)

    for entity_type, type_items in by_type.items():
        print(f"  Clustering {entity_type}: {len(type_items)} items...")

        # mention_count 내림차순 정렬 (대표 선정용)
        type_items.sort(key=lambda x: -x.mention_count)

        if not type_items:
            continue

        # 임베딩 행렬 구성 및 정규화
        embeddings = np.array([item.embedding for item in type_items])
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1  # 0으로 나누기 방지
        embeddings_normalized = embeddings / norms

        # 한번의 행렬 곱으로 모든 유사도 계산 (핵심 최적화!)
        similarity_matrix = embeddings_normalized @ embeddings_normalized.T

        # Union-Find로 클러스터링
        n = len(type_items)
        parent = list(range(n))

        def find(x):
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                # mention_count가 높은 쪽을 대표로
                if type_items[px].mention_count >= type_items[py].mention_count:
                    parent[py] = px
                else:
                    parent[px] = py

        # threshold 이상인 쌍 찾기 (벡터화)
        above_threshold = similarity_matrix >= threshold
        np.fill_diagonal(above_threshold, False)  # 자기 자신 제외

        # Union 수행
        for i in range(n):
            for j in range(i + 1, n):
                if above_threshold[i, j]:
                    union(i, j)

        # 클러스터 그룹화
        cluster_groups: Dict[int, List[int]] = {}
        for i in range(n):
            root = find(i)
            if root not in cluster_groups:
                cluster_groups[root] = []
            cluster_groups[root].append(i)

        # Cluster 객체 생성
        for root, members in cluster_groups.items():
            rep_item = type_items[root]
            member_keys = [type_items[i].entity_key for i in members]
            member_texts = [type_items[i].text for i in members]

            # 대표와의 평균 유사도
            if len(members) > 1:
                sims = [similarity_matrix[root, i] for i in members if i != root]
                avg_sim = float(np.mean(sims))
            else:
                avg_sim = 1.0

            clusters.append(Cluster(
                cluster_id=len(clusters),
                representative_key=rep_item.entity_key,
                representative_text=rep_item.text,
                entity_type=entity_type,
                members=member_keys,
                member_texts=member_texts,
                avg_similarity=avg_sim
            ))

    return clusters


async def process_tier2(samples: List[Dict]) -> Tuple[List[Tier2Result], List[Dict]]:
    """Tier 2 처리"""

    client = EmbeddingClient()

    # 1. 임베딩 텍스트 준비
    print(f"Preparing embedding texts for {len(samples)} items...")
    embedding_texts = [build_embedding_text(s) for s in samples]

    # 2. Batch로 임베딩 생성
    print(f"Generating embeddings (batch size: {BATCH_SIZE})...")
    all_embeddings = []

    for i in range(0, len(embedding_texts), BATCH_SIZE):
        batch = embedding_texts[i:i+BATCH_SIZE]
        batch_embeddings = await client.get_embeddings(batch)
        all_embeddings.extend(batch_embeddings)
        print(f"  Processed {min(i+BATCH_SIZE, len(embedding_texts))}/{len(embedding_texts)}")

    # 3. EmbeddingItem 생성
    items = []
    for s, emb in zip(samples, all_embeddings):
        items.append(EmbeddingItem(
            entity_key=s["entity_key"],
            text=s["text"],
            entity_type=s["entity_type"],
            mention_count=s.get("mention_count", 1),
            embedding=emb,
            contexts=s.get("contexts", [])
        ))

    # 4. 클러스터링
    print(f"Clustering with threshold {SIMILARITY_THRESHOLD}...")
    clusters = cluster_by_similarity(items, SIMILARITY_THRESHOLD)

    # 5. 결과 생성
    results = []
    tier3_items = []

    # entity_key로 빠른 조회
    item_map = {i.entity_key: i for i in items}
    sample_map = {s["entity_key"]: s for s in samples}

    for cluster in clusters:
        rep_item = item_map[cluster.representative_key]

        for member_key in cluster.members:
            member_item = item_map[member_key]
            sample = sample_map[member_key]
            is_rep = (member_key == cluster.representative_key)

            # 대표와의 유사도 계산
            if is_rep:
                sim = 1.0
            else:
                sim = cosine_similarity(member_item.embedding, rep_item.embedding)

            # 싱글톤 클러스터는 Tier 3로
            if len(cluster.members) == 1:
                results.append(Tier2Result(
                    id=sample["id"],
                    entity_key=member_key,
                    text=member_item.text,
                    entity_type=member_item.entity_type,
                    mention_count=member_item.mention_count,
                    cluster_id=cluster.cluster_id,
                    is_representative=True,
                    decision="PASS_TO_TIER3",
                    reason="Singleton cluster - needs LLM verification",
                    similarity_to_representative=1.0,
                    contexts=member_item.contexts
                ))
                tier3_items.append(sample)
            else:
                decision = "CLUSTER_REPRESENTATIVE" if is_rep else "CLUSTER_MEMBER"
                reason = f"Clustered (size: {len(cluster.members)}, avg_sim: {cluster.avg_similarity:.3f})"

                results.append(Tier2Result(
                    id=sample["id"],
                    entity_key=member_key,
                    text=member_item.text,
                    entity_type=member_item.entity_type,
                    mention_count=member_item.mention_count,
                    cluster_id=cluster.cluster_id,
                    is_representative=is_rep,
                    decision=decision,
                    reason=reason,
                    similarity_to_representative=sim,
                    contexts=member_item.contexts
                ))

    return results, tier3_items, clusters


async def main_async():
    print("=" * 60)
    print("       PHASE 2 PILOT - TIER 2 EMBEDDING CLUSTERING")
    print("=" * 60)

    # Tier 2 입력 로드
    input_file = PILOT_DIR / "tier2_input.jsonl"

    if not input_file.exists():
        print(f"ERROR: Input file not found: {input_file}")
        print("Run phase2_pilot_tier1.py first!")
        return

    samples = []
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))

    print(f"Loaded {len(samples)} Tier 2 items")
    print(f"Embedding model: {EMBEDDING_MODEL}")
    print(f"Similarity threshold: {SIMILARITY_THRESHOLD}")
    print("-" * 60)

    start_time = datetime.now()

    # 처리
    results, tier3_items, clusters = await process_tier2(samples)

    # 결과 저장
    output_file = PILOT_DIR / "tier2_results.jsonl"
    with open(output_file, 'w', encoding='utf-8') as f:
        for r in results:
            f.write(json.dumps(asdict(r), ensure_ascii=False) + '\n')

    # Tier 3 입력 저장
    tier3_file = PILOT_DIR / "tier3_input.jsonl"
    with open(tier3_file, 'w', encoding='utf-8') as f:
        for item in tier3_items:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

    # 클러스터 정보 저장
    clusters_file = PILOT_DIR / "tier2_clusters.json"
    clusters_data = [asdict(c) for c in clusters]
    with open(clusters_file, 'w', encoding='utf-8') as f:
        json.dump(clusters_data, f, ensure_ascii=False, indent=2)

    # 통계
    elapsed = (datetime.now() - start_time).total_seconds()

    decisions = {}
    for r in results:
        decisions[r.decision] = decisions.get(r.decision, 0) + 1

    # 클러스터 크기 분포
    cluster_sizes = [len(c.members) for c in clusters]
    singleton_count = sum(1 for s in cluster_sizes if s == 1)
    multi_count = len(cluster_sizes) - singleton_count

    print("\n" + "=" * 60)
    print("       TIER 2 RESULTS")
    print("=" * 60)

    total = len(results)
    for decision in ["CLUSTER_REPRESENTATIVE", "CLUSTER_MEMBER", "PASS_TO_TIER3"]:
        count = decisions.get(decision, 0)
        pct = count / total * 100 if total > 0 else 0
        print(f"  {decision:22s}: {count:5d} ({pct:5.1f}%)")

    print("-" * 60)
    print(f"  Total items: {total}")
    print(f"  Total clusters: {len(clusters)}")
    print(f"  Singleton clusters: {singleton_count} ({singleton_count/len(clusters)*100:.1f}%)")
    print(f"  Multi-member clusters: {multi_count}")
    print(f"  Items to Tier 3: {len(tier3_items)}")
    print(f"  Time elapsed: {elapsed:.1f}s")

    # 효율 분석
    clustered_count = decisions.get("CLUSTER_MEMBER", 0)
    reduction = clustered_count / total * 100 if total > 0 else 0

    print(f"\n  Tier 2 reduction: {reduction:.1f}% (merged into representatives)")

    # 임베딩 비용 추정
    total_tokens = len(samples) * 50  # 대략적인 추정
    embedding_cost = total_tokens * 0.00002 / 1000
    print(f"  Estimated embedding cost: ${embedding_cost:.4f}")

    print(f"\nSaved to:")
    print(f"  Results: {output_file}")
    print(f"  Clusters: {clusters_file}")
    print(f"  Tier 3 input: {tier3_file}")

    # 샘플 클러스터 미리보기
    print("\n" + "-" * 60)
    print("Sample multi-member clusters:")
    multi_clusters = [c for c in clusters if len(c.members) > 1][:3]
    for c in multi_clusters:
        print(f"\n  Cluster {c.cluster_id} ({c.entity_type}, size: {len(c.members)}):")
        print(f"    Representative: {c.representative_text}")
        print(f"    Members: {', '.join(c.member_texts[:5])}")
        if len(c.member_texts) > 5:
            print(f"    ... and {len(c.member_texts) - 5} more")


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
