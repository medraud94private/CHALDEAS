"""
Archivist PoC - Entity Matching and Disambiguation
Uses Qwen3:8B to decide: CREATE_NEW / LINK_EXISTING / PENDING
"""
import json
import re
import httpx
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum

from app.config import settings


class Decision(str, Enum):
    CREATE_NEW = "CREATE_NEW"
    LINK_EXISTING = "LINK_EXISTING"
    PENDING = "PENDING"


@dataclass
class EntityRecord:
    """An entity stored in the registry."""
    id: int
    text: str
    normalized: str
    entity_type: str  # person, location, event
    context_snippet: str  # 첫 발견 문맥
    attributes: Dict[str, Any] = field(default_factory=dict)
    # 시대 정보 (있으면)
    year_start: Optional[int] = None
    year_end: Optional[int] = None
    # 별칭들
    aliases: List[str] = field(default_factory=list)
    # 출처
    sources: List[str] = field(default_factory=list)


@dataclass
class MatchCandidate:
    """A potential match from the registry."""
    entity: EntityRecord
    name_similarity: float
    context_similarity: float
    time_overlap: bool
    ordinal_conflict: bool  # 세대 구분 충돌


@dataclass
class ArchivistDecision:
    """A decision made by the Archivist."""
    decision: Decision
    confidence: float
    reasoning: str
    linked_entity_id: Optional[int] = None
    # 메타데이터
    new_entity_text: str = ""
    new_entity_type: str = ""
    candidates_checked: int = 0
    processing_time_ms: float = 0


@dataclass
class ArchivistStats:
    """Statistics for Archivist performance."""
    total_decisions: int = 0
    create_new_count: int = 0
    link_existing_count: int = 0
    pending_count: int = 0
    ordinal_conflicts_caught: int = 0
    avg_confidence: float = 0.0
    avg_candidates_per_decision: float = 0.0


class EntityRegistry:
    """In-memory entity registry for PoC."""

    def __init__(self):
        self.entities: Dict[int, EntityRecord] = {}
        self.next_id = 1
        # 빠른 검색을 위한 인덱스
        self._name_index: Dict[str, List[int]] = {}  # normalized_name -> [entity_ids]
        self._type_index: Dict[str, List[int]] = {}  # type -> [entity_ids]

    def add(self, entity: EntityRecord) -> EntityRecord:
        """Add entity to registry."""
        entity.id = self.next_id
        self.next_id += 1
        self.entities[entity.id] = entity

        # Update indexes
        norm_name = entity.normalized.lower()
        if norm_name not in self._name_index:
            self._name_index[norm_name] = []
        self._name_index[norm_name].append(entity.id)

        if entity.entity_type not in self._type_index:
            self._type_index[entity.entity_type] = []
        self._type_index[entity.entity_type].append(entity.id)

        return entity

    def find_candidates(
        self,
        text: str,
        entity_type: str,
        max_candidates: int = 10
    ) -> List[EntityRecord]:
        """Find potential matching entities."""
        candidates = []
        text_lower = text.lower()
        text_base = self._extract_base_name(text_lower)

        # 1. 정확히 일치하는 이름
        if text_lower in self._name_index:
            for eid in self._name_index[text_lower]:
                candidates.append(self.entities[eid])

        # 2. 베이스 이름이 일치하는 경우 (Louis XIV -> Louis)
        for norm_name, eids in self._name_index.items():
            if norm_name == text_lower:
                continue
            if text_base in norm_name or norm_name in text_base:
                for eid in eids:
                    if self.entities[eid] not in candidates:
                        candidates.append(self.entities[eid])

        # 3. 같은 타입의 유사한 이름
        if entity_type in self._type_index:
            for eid in self._type_index[entity_type]:
                entity = self.entities[eid]
                if entity not in candidates:
                    similarity = self._name_similarity(text_lower, entity.normalized.lower())
                    if similarity > 0.5:
                        candidates.append(entity)

        return candidates[:max_candidates]

    def _extract_base_name(self, name: str) -> str:
        """Extract base name without ordinals."""
        # Remove Roman numerals and ordinals
        patterns = [
            r'\s+(i{1,3}|iv|v|vi{0,3}|ix|x{0,3})$',  # Roman numerals
            r'\s+\d+(st|nd|rd|th)?$',  # Arabic ordinals
            r'\s+the\s+(great|elder|younger)$',  # Titles
        ]
        result = name
        for pattern in patterns:
            result = re.sub(pattern, '', result, flags=re.IGNORECASE)
        return result.strip()

    def _name_similarity(self, name1: str, name2: str) -> float:
        """Simple name similarity (Jaccard on characters)."""
        set1 = set(name1.replace(" ", ""))
        set2 = set(name2.replace(" ", ""))
        if not set1 or not set2:
            return 0.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0

    def get_stats(self) -> Dict[str, int]:
        """Get registry statistics."""
        type_counts = {}
        for entity in self.entities.values():
            t = entity.entity_type
            type_counts[t] = type_counts.get(t, 0) + 1
        return {
            "total": len(self.entities),
            "by_type": type_counts
        }


class Archivist:
    """
    The Archivist: Gatekeeper of the Storage.
    Uses Qwen to make intelligent entity matching decisions.
    Supports fast_mode for rule-based matching without LLM.
    """

    ORDINAL_PATTERN = re.compile(
        r'(I{1,3}|IV|V?I{0,3}|IX|X{0,3}|[0-9]+)$|(\d+세)$|(\d+世)$',
        re.IGNORECASE
    )

    def __init__(self, registry: EntityRegistry = None, fast_mode: bool = False):
        self.registry = registry or EntityRegistry()
        self.decisions: List[ArchivistDecision] = []
        self.pending_queue: List[Dict] = []
        self._stats = ArchivistStats()
        self.fast_mode = fast_mode  # Skip LLM, use rule-based matching

    async def process_entity(
        self,
        text: str,
        entity_type: str,
        context: str,
        source: str = "unknown"
    ) -> Tuple[ArchivistDecision, Optional[EntityRecord]]:
        """
        Process an extracted entity.
        Returns (decision, entity_record or None).
        """
        start_time = datetime.now()

        # 1. Find candidates
        candidates = self.registry.find_candidates(text, entity_type)

        # 2. Check for ordinal conflicts
        ordinal = self._extract_ordinal(text)
        filtered_candidates = []
        for c in candidates:
            c_ordinal = self._extract_ordinal(c.text)
            if ordinal and c_ordinal and ordinal != c_ordinal:
                # Ordinal conflict - cannot be the same entity
                self._stats.ordinal_conflicts_caught += 1
                continue
            filtered_candidates.append(c)

        # 3. If no candidates, create new
        if not filtered_candidates:
            decision = ArchivistDecision(
                decision=Decision.CREATE_NEW,
                confidence=0.95,
                reasoning="기존 엔티티 중 일치하는 후보 없음",
                new_entity_text=text,
                new_entity_type=entity_type,
                candidates_checked=len(candidates)
            )
            entity = self._create_entity(text, entity_type, context, source)
            self._record_decision(decision, start_time)
            return decision, entity

        # 4. Make decision (fast mode: rules only, normal: use Qwen)
        if self.fast_mode:
            decision = self._fast_decide(text, entity_type, filtered_candidates)
        else:
            decision = await self._ask_qwen(text, entity_type, context, filtered_candidates)
        decision.candidates_checked = len(candidates)

        # 5. Execute decision
        entity = None
        if decision.decision == Decision.CREATE_NEW:
            entity = self._create_entity(text, entity_type, context, source)
        elif decision.decision == Decision.LINK_EXISTING:
            if decision.linked_entity_id:
                entity = self.registry.entities.get(decision.linked_entity_id)
                if entity:
                    # Add as alias
                    if text not in entity.aliases and text.lower() != entity.normalized.lower():
                        entity.aliases.append(text)
                    if source not in entity.sources:
                        entity.sources.append(source)
        else:  # PENDING
            self.pending_queue.append({
                "text": text,
                "entity_type": entity_type,
                "context": context,
                "candidates": [asdict(c) for c in filtered_candidates],
                "decision": asdict(decision)
            })

        self._record_decision(decision, start_time)
        return decision, entity

    def _fast_decide(
        self,
        text: str,
        entity_type: str,
        candidates: List[EntityRecord]
    ) -> ArchivistDecision:
        """Fast rule-based decision without LLM.

        Rules:
        1. Exact name match (case-insensitive) -> LINK_EXISTING
        2. Single candidate with high similarity (>0.8) -> LINK_EXISTING
        3. Multiple similar candidates -> PENDING
        4. Low similarity candidates -> CREATE_NEW
        """
        text_lower = text.lower().strip()

        # Rule 1: Exact match
        for c in candidates:
            if c.normalized.lower().strip() == text_lower:
                return ArchivistDecision(
                    decision=Decision.LINK_EXISTING,
                    confidence=0.95,
                    reasoning="Exact name match",
                    linked_entity_id=c.id,
                    new_entity_text=text,
                    new_entity_type=entity_type
                )
            # Also check aliases
            for alias in c.aliases:
                if alias.lower().strip() == text_lower:
                    return ArchivistDecision(
                        decision=Decision.LINK_EXISTING,
                        confidence=0.90,
                        reasoning="Alias match",
                        linked_entity_id=c.id,
                        new_entity_text=text,
                        new_entity_type=entity_type
                    )

        # Rule 2: Calculate similarity scores
        scored = []
        for c in candidates:
            sim = self.registry._name_similarity(text_lower, c.normalized.lower())
            scored.append((c, sim))

        scored.sort(key=lambda x: x[1], reverse=True)

        if scored:
            best_candidate, best_sim = scored[0]

            # High similarity single match
            if best_sim > 0.85:
                # Check if there's a close second
                if len(scored) > 1 and scored[1][1] > 0.8:
                    # Multiple high-similarity candidates - needs review
                    return ArchivistDecision(
                        decision=Decision.PENDING,
                        confidence=0.5,
                        reasoning=f"Multiple similar candidates (top: {best_sim:.2f}, {scored[1][1]:.2f})",
                        new_entity_text=text,
                        new_entity_type=entity_type
                    )
                return ArchivistDecision(
                    decision=Decision.LINK_EXISTING,
                    confidence=best_sim,
                    reasoning=f"High similarity match ({best_sim:.2f})",
                    linked_entity_id=best_candidate.id,
                    new_entity_text=text,
                    new_entity_type=entity_type
                )

            # Medium similarity - could go either way
            if best_sim > 0.6:
                return ArchivistDecision(
                    decision=Decision.PENDING,
                    confidence=0.4,
                    reasoning=f"Ambiguous similarity ({best_sim:.2f})",
                    new_entity_text=text,
                    new_entity_type=entity_type
                )

        # Low similarity - create new
        return ArchivistDecision(
            decision=Decision.CREATE_NEW,
            confidence=0.75,
            reasoning="No high-similarity candidates",
            new_entity_text=text,
            new_entity_type=entity_type
        )

    async def _ask_qwen(
        self,
        text: str,
        entity_type: str,
        context: str,
        candidates: List[EntityRecord]
    ) -> ArchivistDecision:
        """Ask Qwen to make a matching decision with retry."""

        # Simplified candidate info
        cand_list = [f"ID:{c.id} \"{c.normalized}\"" for c in candidates[:5]]

        # SHORT prompt for fast response
        prompt = f"""Entity: "{text}" ({entity_type})
Candidates: {', '.join(cand_list)}

Same entity? Reply JSON: {{"decision":"LINK_EXISTING","id":N}} or {{"decision":"CREATE_NEW"}}"""

        # Retry up to 3 times with exponential backoff
        import asyncio
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=90.0) as client:
                    # Use /api/chat with think:false to disable Qwen3 thinking mode
                    response = await client.post(
                        f"{settings.ollama_base_url}/api/chat",
                        json={
                            "model": settings.ollama_model,
                            "messages": [{"role": "user", "content": prompt}],
                            "stream": False,
                            "think": False,  # Critical: disable Qwen3 thinking mode
                            "options": {"temperature": 0.1, "num_predict": 100}
                        }
                    )

                    if response.status_code == 200:
                        result = response.json()
                        # /api/chat returns message.content instead of response
                        response_text = result.get("message", {}).get("content", "")

                        # Extract JSON
                        json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
                        if json_match:
                            data = json.loads(json_match.group())
                            decision_str = data.get("decision", "PENDING")
                            linked_id = data.get("id") or data.get("linked_entity_id")
                            return ArchivistDecision(
                                decision=Decision(decision_str),
                                confidence=0.8,
                                reasoning=f"Qwen decision (attempt {attempt+1})",
                                linked_entity_id=linked_id,
                                new_entity_text=text,
                                new_entity_type=entity_type
                            )
                    elif response.status_code >= 500:
                        # Server error, retry after delay
                        await asyncio.sleep(2 ** attempt)
                        continue
            except httpx.ConnectError:
                # Connection failed, retry with delay
                await asyncio.sleep(2 ** attempt)
                continue
            except httpx.TimeoutException:
                # Timeout, retry with delay
                await asyncio.sleep(2 ** attempt)
                continue
            except Exception as e:
                if attempt < 2:
                    await asyncio.sleep(1)
                    continue

        # Fallback: if only one candidate with high name match, link it
        if len(candidates) == 1:
            return ArchivistDecision(
                decision=Decision.PENDING,
                confidence=0.5,
                reasoning="LLM 호출 실패, 수동 검토 필요",
                new_entity_text=text,
                new_entity_type=entity_type
            )

        return ArchivistDecision(
            decision=Decision.PENDING,
            confidence=0.3,
            reasoning="LLM 호출 실패, 후보 다수로 수동 검토 필요",
            new_entity_text=text,
            new_entity_type=entity_type
        )

    def _extract_ordinal(self, text: str) -> Optional[str]:
        """Extract ordinal from name (I, II, XIV, etc.)"""
        match = self.ORDINAL_PATTERN.search(text.strip())
        if match:
            ordinal = match.group(1) or match.group(2) or match.group(3)
            return ordinal.upper() if ordinal else None
        return None

    def _create_entity(
        self,
        text: str,
        entity_type: str,
        context: str,
        source: str
    ) -> EntityRecord:
        """Create a new entity in the registry."""
        entity = EntityRecord(
            id=0,  # Will be set by registry
            text=text,
            normalized=text,  # Could be enhanced
            entity_type=entity_type,
            context_snippet=context[:500],
            sources=[source]
        )
        return self.registry.add(entity)

    def _record_decision(self, decision: ArchivistDecision, start_time: datetime):
        """Record decision for statistics."""
        elapsed = (datetime.now() - start_time).total_seconds() * 1000
        decision.processing_time_ms = elapsed
        self.decisions.append(decision)

        # Update stats
        self._stats.total_decisions += 1
        if decision.decision == Decision.CREATE_NEW:
            self._stats.create_new_count += 1
        elif decision.decision == Decision.LINK_EXISTING:
            self._stats.link_existing_count += 1
        else:
            self._stats.pending_count += 1

        # Running average confidence
        n = self._stats.total_decisions
        self._stats.avg_confidence = (
            (self._stats.avg_confidence * (n - 1) + decision.confidence) / n
        )
        self._stats.avg_candidates_per_decision = (
            (self._stats.avg_candidates_per_decision * (n - 1) + decision.candidates_checked) / n
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get Archivist statistics."""
        return {
            "decisions": asdict(self._stats),
            "registry": self.registry.get_stats(),
            "pending_queue_size": len(self.pending_queue)
        }

    def get_report(self) -> str:
        """Generate a human-readable report."""
        stats = self.get_stats()
        d = stats["decisions"]
        r = stats["registry"]

        report = f"""
========================================
        ARCHIVIST PoC REPORT
========================================

[ Decision Statistics ]
  Total Decisions: {d['total_decisions']}
  - CREATE_NEW:    {d['create_new_count']} ({d['create_new_count']/max(d['total_decisions'],1)*100:.1f}%)
  - LINK_EXISTING: {d['link_existing_count']} ({d['link_existing_count']/max(d['total_decisions'],1)*100:.1f}%)
  - PENDING:       {d['pending_count']} ({d['pending_count']/max(d['total_decisions'],1)*100:.1f}%)

  Ordinal Conflicts Caught: {d['ordinal_conflicts_caught']}
  Average Confidence: {d['avg_confidence']:.2f}
  Avg Candidates/Decision: {d['avg_candidates_per_decision']:.2f}

[ Registry Statistics ]
  Total Entities: {r['total']}
  By Type: {r['by_type']}

[ Pending Queue ]
  Items Awaiting Review: {stats['pending_queue_size']}

========================================
"""
        return report
