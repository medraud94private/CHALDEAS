"""
Entity Matcher Service

책에서 추출된 엔티티를 DB와 매칭하는 5단계 파이프라인:
1. Exact Match - 이름 정확히 일치
2. Alias Match - entity_aliases 테이블에서 검색
3. Wikidata QID - Wikidata 검색 → 기존 QID와 매칭
4. Embedding Similarity - 임베딩 유사도 검색
5. LLM Verification - 최종 검증

Usage:
    from entity_matcher import EntityMatcher

    matcher = EntityMatcher()
    result = matcher.match('person', 'Napoleon Bonaparte')
    # MatchResult(matched=True, entity_id=26, confidence=0.98, method='wikidata')
"""

import os
import sys
import json
import httpx
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path

import psycopg2

# Load .env if not already loaded
def _load_env():
    if os.environ.get('OPENAI_API_KEY'):
        return
    # Try multiple .env locations
    for env_path in [
        Path(__file__).parent.parent.parent / '.env',  # repo root
        Path(__file__).parent.parent.parent / 'backend' / '.env',
        Path.cwd() / '.env',
    ]:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        key, _, value = line.strip().partition('=')
                        key = key.strip()
                        value = value.strip('"').strip("'").strip()
                        if key and value and key not in os.environ:
                            os.environ[key] = value
            break

_load_env()
from psycopg2.extras import RealDictCursor

# OpenAI for embeddings
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# DB 설정
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'dbname': 'chaldeas',
    'user': 'chaldeas',
    'password': 'chaldeas_dev'
}

# Wikidata API
WIKIDATA_API = "https://www.wikidata.org/w/api.php"

# Ollama 설정 (LLM 검증용)
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "gemma2:9b"


@dataclass
class MatchResult:
    """매칭 결과"""
    matched: bool
    entity_id: Optional[int]
    confidence: float
    method: str  # 'exact', 'alias', 'wikidata', 'embedding', 'llm', 'new'
    merged: bool = False  # QID 중복 병합 발생 여부
    details: Optional[Dict] = None


@dataclass
class MatchCandidate:
    """매칭 후보"""
    entity_id: int
    name: str
    similarity: float
    wikidata_id: Optional[str] = None


class EntityMatcher:
    """
    엔티티 매칭 서비스

    5단계 파이프라인으로 추출된 엔티티를 기존 DB와 매칭.
    매칭 실패 시 새 엔티티 생성.
    """

    def __init__(self, auto_create: bool = False):
        """
        Args:
            auto_create: True면 매칭 실패 시 자동으로 새 엔티티 생성
        """
        self.auto_create = auto_create
        self._conn = None

    @property
    def conn(self):
        """Lazy DB connection"""
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(**DB_CONFIG)
        return self._conn

    def close(self):
        """DB 연결 종료"""
        if self._conn and not self._conn.closed:
            self._conn.close()

    # ─── 메인 매칭 메서드 ─────────────────────────────────────

    def match(self, entity_type: str, name: str, context: str = None) -> MatchResult:
        """
        5단계 매칭 파이프라인 실행

        Args:
            entity_type: 'person', 'location', 'event'
            name: 엔티티 이름
            context: 문맥 (LLM 검증용)

        Returns:
            MatchResult
        """
        table = self._get_table(entity_type)

        # 1. Exact match
        entity = self._exact_match(table, name)
        if entity:
            return MatchResult(True, entity['id'], 1.0, 'exact')

        # 2. Alias match
        entity = self._alias_match(entity_type, name)
        if entity:
            return MatchResult(True, entity['id'], 0.95, 'alias')

        # 3. Wikidata QID
        qid = self._search_wikidata(name, entity_type)
        if qid:
            entities = self._find_by_qid(table, qid)
            if entities:
                if len(entities) > 1:
                    # QID 중복 발견 → 자동 병합
                    primary = self._merge_duplicates(entity_type, entities)
                    self._save_alias(entity_type, primary['id'], name, 'merged')
                    return MatchResult(True, primary['id'], 0.98, 'wikidata', merged=True)
                else:
                    self._save_alias(entity_type, entities[0]['id'], name, 'wikidata')
                    return MatchResult(True, entities[0]['id'], 0.98, 'wikidata')

        # 4. Embedding similarity
        candidates = self._embedding_search(entity_type, name)
        if candidates:
            # 높은 유사도면 바로 매칭
            if candidates[0].similarity >= 0.95:
                self._save_alias(entity_type, candidates[0].entity_id, name, 'learned')
                return MatchResult(True, candidates[0].entity_id, candidates[0].similarity, 'embedding')

            # 5. LLM verification (0.85-0.95 구간)
            best = self._llm_verify(entity_type, name, context, candidates)
            if best and best.similarity >= 0.9:
                self._save_alias(entity_type, best.entity_id, name, 'learned')
                return MatchResult(True, best.entity_id, best.similarity, 'llm')

        # No match
        if self.auto_create:
            new_entity = self._create_entity(entity_type, name, qid)
            return MatchResult(True, new_entity['id'], 1.0, 'new')

        return MatchResult(False, None, 0.0, 'none', details={'wikidata_qid': qid})

    def match_person(self, name: str, context: str = None) -> MatchResult:
        return self.match('person', name, context)

    def match_location(self, name: str, context: str = None) -> MatchResult:
        return self.match('location', name, context)

    def match_event(self, name: str, context: str = None) -> MatchResult:
        return self.match('event', name, context)

    # ─── Stage 1: Exact Match ─────────────────────────────────

    def _exact_match(self, table: str, name: str) -> Optional[Dict]:
        """이름 정확히 일치"""
        cur = self.conn.cursor(cursor_factory=RealDictCursor)
        name_col = 'title' if table == 'events' else 'name'
        cur.execute(f"""
            SELECT id, {name_col} as name, wikidata_id
            FROM {table}
            WHERE LOWER({name_col}) = LOWER(%s)
            LIMIT 1
        """, (name,))
        return cur.fetchone()

    # ─── Stage 2: Alias Match ─────────────────────────────────

    def _alias_match(self, entity_type: str, name: str) -> Optional[Dict]:
        """entity_aliases 테이블에서 검색"""
        cur = self.conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT entity_id
            FROM entity_aliases
            WHERE entity_type = %s AND LOWER(alias) = LOWER(%s)
            LIMIT 1
        """, (entity_type, name))
        result = cur.fetchone()

        if result:
            table = self._get_table(entity_type)
            cur.execute(f"SELECT id, name, wikidata_id FROM {table} WHERE id = %s",
                       (result['entity_id'],))
            return cur.fetchone()
        return None

    # ─── Stage 3: Wikidata QID ────────────────────────────────

    def _search_wikidata(self, name: str, entity_type: str) -> Optional[str]:
        """Wikidata에서 이름 검색 → QID 반환"""
        try:
            params = {
                "action": "wbsearchentities",
                "search": name,
                "language": "en",
                "format": "json",
                "limit": 5,
                "type": "item"
            }
            headers = {
                "User-Agent": "CHALDEAS/1.0 (https://chaldeas.site; contact@chaldeas.site)"
            }

            resp = httpx.get(WIKIDATA_API, params=params, headers=headers, timeout=10)
            data = resp.json()

            if data.get("search"):
                # 첫 번째 결과 반환 (향후: entity_type으로 필터링 가능)
                return data["search"][0]["id"]
        except Exception as e:
            print(f"Wikidata search error: {e}")

        return None

    def _find_by_qid(self, table: str, qid: str) -> List[Dict]:
        """DB에서 QID로 엔티티 찾기"""
        cur = self.conn.cursor(cursor_factory=RealDictCursor)
        name_col = 'title' if table == 'events' else 'name'
        cur.execute(f"""
            SELECT id, {name_col} as name, wikidata_id
            FROM {table}
            WHERE wikidata_id = %s
        """, (qid,))
        return cur.fetchall()

    # ─── Stage 4: Embedding Similarity ────────────────────────

    def _embedding_search(self, entity_type: str, name: str,
                          limit: int = 5, min_sim: float = 0.85) -> List[MatchCandidate]:
        """임베딩 유사도로 후보 검색"""
        if not OPENAI_AVAILABLE:
            return []

        try:
            # 이름 임베딩 생성
            query_embedding = self._get_embedding(name)
            if not query_embedding:
                return []

            table = self._get_table(entity_type)
            cur = self.conn.cursor(cursor_factory=RealDictCursor)

            # pgvector 유사도 검색 (cosine similarity)
            name_col = 'title' if table == 'events' else 'name'
            cur.execute(f"""
                SELECT id, {name_col} as name, wikidata_id,
                       1 - (embedding <=> %s::vector) as similarity
                FROM {table}
                WHERE embedding IS NOT NULL
                AND 1 - (embedding <=> %s::vector) > %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """, (query_embedding, query_embedding, min_sim, query_embedding, limit))

            candidates = []
            for row in cur.fetchall():
                candidates.append(MatchCandidate(
                    entity_id=row['id'],
                    name=row['name'],
                    similarity=row['similarity'],
                    wikidata_id=row.get('wikidata_id')
                ))

            return candidates

        except Exception as e:
            print(f"Embedding search error: {e}")
            return []

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """OpenAI 임베딩 생성"""
        if not OPENAI_AVAILABLE:
            return None

        try:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                return None

            client = OpenAI(api_key=api_key)
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            return response.data[0].embedding

        except Exception as e:
            print(f"Embedding error: {e}")
            return None

    # ─── Stage 5: LLM Verification ────────────────────────────

    def _llm_verify(self, entity_type: str, name: str, context: str,
                    candidates: List[MatchCandidate]) -> Optional[MatchCandidate]:
        """LLM으로 매칭 검증"""
        if not candidates:
            return None

        # 후보 목록 생성 (최대 10개)
        candidate_info = []
        for i, c in enumerate(candidates[:10]):
            candidate_info.append(f"{i+1}. {c.name} (similarity: {c.similarity:.2f})")

        prompt = f"""You are matching historical entity names.

Extracted name: "{name}"
Entity type: {entity_type}
{f'Context: "{context[:200]}..."' if context else ''}

Candidates from database:
{chr(10).join(candidate_info)}

Question: Is the extracted name referring to any of these candidates?

Respond in JSON format:
{{"match_index": 1, "confidence": 0.95, "reason": "brief explanation"}}

If no match, respond:
{{"match_index": null, "confidence": 0.0, "reason": "no match found"}}
"""

        # OpenAI 먼저 시도 (Ollama는 책 추출 중)
        result = self._call_openai(prompt)
        if not result:
            # Ollama 폴백
            result = self._call_ollama(prompt)

        if result and result.get('match_index'):
            idx = result['match_index'] - 1
            if 0 <= idx < len(candidates):
                candidates[idx].similarity = result.get('confidence', 0.9)
                return candidates[idx]

        return None

    def _call_ollama(self, prompt: str) -> Optional[Dict]:
        """Ollama API 호출 (gemma2:9b)"""
        try:
            resp = httpx.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "format": "json",
                    "stream": False
                },
                timeout=60
            )

            if resp.status_code == 200:
                data = resp.json()
                response_text = data.get('response', '')
                return json.loads(response_text)

        except Exception as e:
            print(f"Ollama error: {e}")

        return None

    def _call_openai(self, prompt: str) -> Optional[Dict]:
        """OpenAI API 호출 (폴백)"""
        if not OPENAI_AVAILABLE:
            return None

        try:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                return None

            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-5.1-chat-latest",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_completion_tokens=200
            )

            return json.loads(response.choices[0].message.content)

        except Exception as e:
            print(f"OpenAI error: {e}")

        return None

    # ─── 중복 병합 ────────────────────────────────────────────

    def _merge_duplicates(self, entity_type: str, entities: List[Dict]) -> Dict:
        """
        QID 중복 엔티티 병합
        - 첫 번째를 primary로 선택
        - 나머지 이름을 alias로 저장
        - 관계 이전 후 삭제
        """
        primary = self._select_primary(entities)
        table = self._get_table(entity_type)
        cur = self.conn.cursor()

        for entity in entities:
            if entity['id'] != primary['id']:
                # Alias 저장
                self._save_alias(entity_type, primary['id'], entity['name'], 'merged')

                # 관계 이전 (entity_type별로 다름)
                self._transfer_relationships(entity_type, entity['id'], primary['id'])

                # 삭제
                cur.execute(f"DELETE FROM {table} WHERE id = %s", (entity['id'],))

        self.conn.commit()
        print(f"Merged {len(entities)} duplicates → {primary['name']} (id={primary['id']})")
        return primary

    def _select_primary(self, entities: List[Dict]) -> Dict:
        """대표 엔티티 선정 (가장 일반적인 영어명)"""
        def score(e):
            name = e['name']
            s = 0
            if name.isascii():
                s += 10
            if name.replace(' ', '').isalnum():
                s += 5
            if 10 <= len(name) <= 30:
                s += 5
            if ' the ' in name.lower() or ' of ' in name.lower():
                s += 3
            return s

        return max(entities, key=score)

    def _transfer_relationships(self, entity_type: str, from_id: int, to_id: int):
        """관계 이전 (TODO: 각 테이블별 구현)"""
        cur = self.conn.cursor()

        if entity_type == 'person':
            # person_sources
            cur.execute("""
                UPDATE person_sources SET person_id = %s
                WHERE person_id = %s
                AND NOT EXISTS (SELECT 1 FROM person_sources WHERE person_id = %s AND source_id = person_sources.source_id)
            """, (to_id, from_id, to_id))
            cur.execute("DELETE FROM person_sources WHERE person_id = %s", (from_id,))

            # event_persons
            cur.execute("""
                UPDATE event_persons SET person_id = %s
                WHERE person_id = %s
                AND NOT EXISTS (SELECT 1 FROM event_persons WHERE person_id = %s AND event_id = event_persons.event_id)
            """, (to_id, from_id, to_id))
            cur.execute("DELETE FROM event_persons WHERE person_id = %s", (from_id,))

            # person_relationships (중복 제거 후 이전)
            cur.execute("""
                DELETE FROM person_relationships
                WHERE person_id = %s
                AND EXISTS (SELECT 1 FROM person_relationships pr2
                            WHERE pr2.person_id = %s AND pr2.related_person_id = person_relationships.related_person_id)
            """, (from_id, to_id))
            cur.execute("""
                UPDATE person_relationships SET person_id = %s WHERE person_id = %s
            """, (to_id, from_id))
            cur.execute("""
                DELETE FROM person_relationships
                WHERE related_person_id = %s
                AND EXISTS (SELECT 1 FROM person_relationships pr2
                            WHERE pr2.related_person_id = %s AND pr2.person_id = person_relationships.person_id)
            """, (from_id, to_id))
            cur.execute("""
                UPDATE person_relationships SET related_person_id = %s WHERE related_person_id = %s
            """, (to_id, from_id))

        elif entity_type == 'location':
            # location_sources
            cur.execute("""
                UPDATE location_sources SET location_id = %s
                WHERE location_id = %s
                AND NOT EXISTS (SELECT 1 FROM location_sources WHERE location_id = %s AND source_id = location_sources.source_id)
            """, (to_id, from_id, to_id))
            cur.execute("DELETE FROM location_sources WHERE location_id = %s", (from_id,))

            # event_locations
            cur.execute("""
                UPDATE event_locations SET location_id = %s
                WHERE location_id = %s
                AND NOT EXISTS (SELECT 1 FROM event_locations WHERE location_id = %s AND event_id = event_locations.event_id)
            """, (to_id, from_id, to_id))
            cur.execute("DELETE FROM event_locations WHERE location_id = %s", (from_id,))

        elif entity_type == 'event':
            # event_sources
            cur.execute("""
                UPDATE event_sources SET event_id = %s
                WHERE event_id = %s
                AND NOT EXISTS (SELECT 1 FROM event_sources WHERE event_id = %s AND source_id = event_sources.source_id)
            """, (to_id, from_id, to_id))
            cur.execute("DELETE FROM event_sources WHERE event_id = %s", (from_id,))

    # ─── Alias 저장 ───────────────────────────────────────────

    def _save_alias(self, entity_type: str, entity_id: int, alias: str, alias_type: str):
        """Alias 저장 (중복 무시)"""
        cur = self.conn.cursor()
        try:
            cur.execute("""
                INSERT INTO entity_aliases (entity_type, entity_id, alias, alias_type, created_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (entity_type, entity_id, alias) DO NOTHING
            """, (entity_type, entity_id, alias, alias_type, datetime.utcnow()))
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            print(f"Error saving alias: {e}")

    # ─── 새 엔티티 생성 ───────────────────────────────────────

    def _create_entity(self, entity_type: str, name: str, qid: str = None) -> Dict:
        """새 엔티티 생성"""
        table = self._get_table(entity_type)
        cur = self.conn.cursor(cursor_factory=RealDictCursor)

        if entity_type == 'person':
            cur.execute("""
                INSERT INTO persons (name, wikidata_id, created_at)
                VALUES (%s, %s, %s)
                RETURNING id, name, wikidata_id
            """, (name, qid, datetime.utcnow()))
        elif entity_type == 'location':
            cur.execute("""
                INSERT INTO locations (name, wikidata_id, created_at)
                VALUES (%s, %s, %s)
                RETURNING id, name, wikidata_id
            """, (name, qid, datetime.utcnow()))
        elif entity_type == 'event':
            cur.execute("""
                INSERT INTO events (name, wikidata_id, created_at)
                VALUES (%s, %s, %s)
                RETURNING id, name, wikidata_id
            """, (name, qid, datetime.utcnow()))

        self.conn.commit()
        return cur.fetchone()

    # ─── 유틸리티 ─────────────────────────────────────────────

    def _get_table(self, entity_type: str) -> str:
        """entity_type → 테이블명"""
        return {
            'person': 'persons',
            'location': 'locations',
            'event': 'events'
        }.get(entity_type, 'persons')


# ─── 테스트 ───────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    matcher = EntityMatcher()

    # 테스트
    tests = [
        ('person', 'Napoleon'),
        ('person', 'Alexander the Great'),
        ('person', 'Napoléon Bonaparte'),  # alias 테스트
        ('location', 'Paris'),
        ('location', 'Constantinople'),
    ]

    print("=== EntityMatcher 테스트 ===\n")
    for entity_type, name in tests:
        result = matcher.match(entity_type, name)
        print(f"{entity_type}: \"{name}\"")
        print(f"  → matched={result.matched}, id={result.entity_id}, "
              f"conf={result.confidence}, method={result.method}")
        if result.details:
            print(f"  → details: {result.details}")
        print()

    matcher.close()
