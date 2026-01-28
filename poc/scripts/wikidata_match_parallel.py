"""
Parallel Wikidata Entity Matching

Architecture:
- N workers for Wikidata fetch + fuzzy + embedding matching
- Separate LLM worker that batch processes uncertain matches
- Main thread coordinates and collects results
- Checkpoint saving for resumability

Usage:
    python poc/scripts/wikidata_match_parallel.py --workers 4 --limit 1000
    python poc/scripts/wikidata_match_parallel.py --workers 8 --limit 10000 --skip-llm
    python poc/scripts/wikidata_match_parallel.py --resume  # Resume from checkpoint
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import time
import argparse
import threading
from queue import Queue, Empty
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

import requests
from rapidfuzz import fuzz
from rapidfuzz.distance import JaroWinkler

# Globals
WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"
OLLAMA_URL = "http://localhost:11434/api/generate"
LLM_MODEL = "gemma2:9b-instruct-q4_0"

# Thread-safe print
print_lock = threading.Lock()

def safe_print(*args, **kwargs):
    with print_lock:
        print(*args, **kwargs)
        sys.stdout.flush()


@dataclass
class MatchTask:
    """Task for matching a person"""
    person_id: int
    person_name: str
    description: str = ""
    lifespan: str = ""
    birth_year: Optional[int] = None
    death_year: Optional[int] = None


@dataclass
class MatchResult:
    """Result of matching"""
    person_id: int
    person_name: str
    wikidata_qid: Optional[str] = None
    match_type: str = "none"
    confidence: float = 0.0
    aliases: List[str] = field(default_factory=list)
    needs_llm: bool = False
    llm_context: Optional[Dict] = None


@dataclass
class LLMTask:
    """Task for LLM verification"""
    result: MatchResult
    candidate_name: str
    candidate_desc: str
    candidate_qid: str
    fuzzy_score: float


class GlobalRateLimiter:
    """Thread-safe global rate limiter shared across all workers"""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self.last_call = 0
        self.call_lock = threading.Lock()
        self.delay = 0.3  # default

    def set_delay(self, delay: float):
        self.delay = delay

    def wait(self):
        with self.call_lock:
            now = time.time()
            wait = self.delay - (now - self.last_call)
            if wait > 0:
                time.sleep(wait)
            self.last_call = time.time()


# Global rate limiter instance
_rate_limiter = GlobalRateLimiter()


class WikidataFetcher:
    """Handles Wikidata API calls with rate limiting and fallback"""

    SEARCH_API = "https://www.wikidata.org/w/api.php"
    SPARQL_API = "https://query.wikidata.org/sparql"

    def __init__(self, delay: float = 0.3):
        self.delay = delay
        self.base_delay = delay
        _rate_limiter.set_delay(delay)

        # Fallback state
        self.primary_blocked = False
        self.sparql_blocked = False
        self.primary_block_time = 0
        self.sparql_block_time = 0
        self.block_duration = 300  # 5 minutes wait before retry
        self.consecutive_429s = 0
        self._state_lock = threading.Lock()

    def _rate_limit(self):
        _rate_limiter.wait()

    def _mark_blocked(self, endpoint: str):
        """Mark an endpoint as blocked"""
        with self._state_lock:
            if endpoint == "primary":
                self.primary_blocked = True
                self.primary_block_time = time.time()
            else:
                self.sparql_blocked = True
                self.sparql_block_time = time.time()

            self.consecutive_429s += 1

            # Increase delay exponentially when hitting rate limits
            new_delay = min(self.base_delay * (2 ** self.consecutive_429s), 10.0)
            _rate_limiter.set_delay(new_delay)
            safe_print(f"  [RATE LIMIT] {endpoint} blocked, delay increased to {new_delay:.1f}s")

    def _check_unblock(self):
        """Check if blocked endpoints should be unblocked"""
        with self._state_lock:
            now = time.time()
            if self.primary_blocked and (now - self.primary_block_time) > self.block_duration:
                self.primary_blocked = False
                safe_print("  [UNBLOCK] Primary API unblocked, retrying...")
            if self.sparql_blocked and (now - self.sparql_block_time) > self.block_duration:
                self.sparql_blocked = False
                safe_print("  [UNBLOCK] SPARQL API unblocked, retrying...")

    def _reset_consecutive_429s(self):
        """Reset consecutive 429 counter on successful request"""
        with self._state_lock:
            if self.consecutive_429s > 0:
                self.consecutive_429s = 0
                _rate_limiter.set_delay(self.base_delay)

    def search(self, name: str, limit: int = 10) -> List[Dict]:
        """
        Search Wikidata with automatic fallback between endpoints.

        Strategy:
        1. Try primary API (wbsearchentities)
        2. If 429, switch to SPARQL
        3. If SPARQL 429, wait and retry primary
        """
        self._check_unblock()

        # Determine which endpoint to use
        with self._state_lock:
            use_sparql = self.primary_blocked and not self.sparql_blocked
            both_blocked = self.primary_blocked and self.sparql_blocked

        if both_blocked:
            # Both endpoints blocked, wait
            wait_time = self.block_duration - (time.time() - min(self.primary_block_time, self.sparql_block_time))
            if wait_time > 0:
                safe_print(f"  [WAITING] Both endpoints blocked, waiting {wait_time:.0f}s...")
                time.sleep(min(wait_time, 60))  # Wait max 60s at a time
                self._check_unblock()

        if use_sparql:
            result = self._search_sparql(name, limit)
            if result is not None:  # None means 429
                return result
            # SPARQL also blocked, fall through to primary

        # Try primary API
        result = self._search_primary(name, limit)
        if result is not None:
            return result

        # Primary blocked, try SPARQL
        if not self.sparql_blocked:
            result = self._search_sparql(name, limit)
            if result is not None:
                return result

        return []

    def _search_primary(self, name: str, limit: int = 10) -> Optional[List[Dict]]:
        """
        Search using wbsearchentities API.
        Returns None on 429 (rate limit), [] on no results.
        """
        self._rate_limit()

        try:
            resp = requests.get(
                self.SEARCH_API,
                params={
                    "action": "wbsearchentities",
                    "search": name,
                    "language": "en",
                    "type": "item",
                    "limit": limit,
                    "format": "json"
                },
                headers={"User-Agent": "CHALDEAS/1.0 (historical data project)"},
                timeout=30
            )

            if resp.status_code == 429:
                self._mark_blocked("primary")
                return None  # Signal to try fallback

            if resp.status_code != 200:
                return []

            self._reset_consecutive_429s()
            data = resp.json()
            search_results = data.get("search", [])

            if not search_results:
                return []

            # Get details for candidates (filter humans only)
            qids = [r["id"] for r in search_results]
            return self._get_entity_details(qids)

        except Exception as e:
            safe_print(f"  [WARN] Primary API error: {e}")
            return []

    def _search_sparql(self, name: str, limit: int = 10) -> Optional[List[Dict]]:
        """
        Search using SPARQL endpoint.
        Returns None on 429 (rate limit), [] on no results.
        """
        self._rate_limit()

        # Escape quotes in name
        escaped_name = name.replace('"', '\\"').replace("'", "\\'")

        query = f'''
        SELECT ?item ?itemLabel ?itemDescription
               (GROUP_CONCAT(DISTINCT ?alias; SEPARATOR="|") AS ?aliases)
               ?birth ?death
        WHERE {{
          ?item rdfs:label "{escaped_name}"@en.
          ?item wdt:P31 wd:Q5.  # human
          OPTIONAL {{ ?item wdt:P569 ?birth. }}
          OPTIONAL {{ ?item wdt:P570 ?death. }}
          OPTIONAL {{ ?item skos:altLabel ?alias. FILTER(LANG(?alias) = "en") }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        GROUP BY ?item ?itemLabel ?itemDescription ?birth ?death
        LIMIT {limit}
        '''

        try:
            resp = requests.get(
                self.SPARQL_API,
                params={"query": query, "format": "json"},
                headers={"User-Agent": "CHALDEAS/1.0 (historical data project)"},
                timeout=30
            )

            if resp.status_code == 429:
                self._mark_blocked("sparql")
                return None  # Signal to try fallback

            if resp.status_code != 200:
                return []

            self._reset_consecutive_429s()
            data = resp.json()
            results = data.get("results", {}).get("bindings", [])

            # Format to match primary API output
            formatted = []
            for r in results:
                formatted.append({
                    "item": r.get("item", {}),
                    "itemLabel": r.get("itemLabel", {}),
                    "itemDescription": r.get("itemDescription", {}),
                    "aliases": r.get("aliases", {}),
                    "birth": r.get("birth", {}),
                    "death": r.get("death", {}),
                })

            return formatted

        except Exception as e:
            safe_print(f"  [WARN] SPARQL API error: {e}")
            return []

    def _get_entity_details(self, qids: List[str]) -> List[Dict]:
        """Fetch entity details using wbgetentities API"""
        if not qids:
            return []

        self._rate_limit()

        try:
            resp = requests.get(
                self.SEARCH_API,
                params={
                    "action": "wbgetentities",
                    "ids": "|".join(qids),
                    "props": "labels|descriptions|aliases|claims",
                    "languages": "en",
                    "format": "json"
                },
                headers={"User-Agent": "CHALDEAS/1.0 (historical data project)"},
                timeout=30
            )

            if resp.status_code == 429:
                self._mark_blocked("primary")
                return []

            if resp.status_code != 200:
                return []

            self._reset_consecutive_429s()

            data = resp.json()
            entities = data.get("entities", {})

            results = []
            for qid, entity in entities.items():
                if "missing" in entity:
                    continue

                # Check if human (P31 = Q5)
                claims = entity.get("claims", {})
                instance_of = claims.get("P31", [])
                is_human = any(
                    c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id") == "Q5"
                    for c in instance_of
                )
                if not is_human:
                    continue

                # Extract label
                label = entity.get("labels", {}).get("en", {}).get("value", "")

                # Extract description
                desc = entity.get("descriptions", {}).get("en", {}).get("value", "")

                # Extract aliases
                alias_list = entity.get("aliases", {}).get("en", [])
                aliases = [a.get("value", "") for a in alias_list]

                # Extract birth date (P569)
                birth = None
                birth_claims = claims.get("P569", [])
                if birth_claims:
                    birth_val = birth_claims[0].get("mainsnak", {}).get("datavalue", {}).get("value", {})
                    birth = birth_val.get("time", "")

                # Extract death date (P570)
                death = None
                death_claims = claims.get("P570", [])
                if death_claims:
                    death_val = death_claims[0].get("mainsnak", {}).get("datavalue", {}).get("value", {})
                    death = death_val.get("time", "")

                # Format like SPARQL result for compatibility
                results.append({
                    "item": {"value": f"http://www.wikidata.org/entity/{qid}"},
                    "itemLabel": {"value": label},
                    "itemDescription": {"value": desc},
                    "aliases": {"value": "|".join(aliases)},
                    "birth": {"value": birth} if birth else {},
                    "death": {"value": death} if death else {},
                })

            return results

        except Exception as e:
            safe_print(f"  [WARN] Entity fetch error: {e}")
            return []

    def search_fuzzy(self, name: str, limit: int = 10) -> List[Dict]:
        """Alias for search - now both use search API"""
        # Try with simplified name (remove parentheses content)
        search_name = name.split("(")[0].strip()
        if len(search_name) < 3:
            search_name = name
        return self.search(search_name, limit)


# === Lifespan comparison helpers ===

def extract_year_from_wikidata(date_str: str) -> Optional[int]:
    """
    Extract year from Wikidata date format.
    Examples:
      "+1643-01-04T00:00:00Z" -> 1643
      "-0044-03-15T00:00:00Z" -> -44 (44 BCE)
      "+1879-03-14T00:00:00Z" -> 1879
    """
    if not date_str:
        return None
    try:
        # Handle BCE dates (negative years)
        if date_str.startswith("-"):
            # "-0044-03-15T00:00:00Z" -> -44
            year_str = date_str[1:5]  # "0044"
            return -int(year_str)
        elif date_str.startswith("+"):
            # "+1643-01-04T00:00:00Z" -> 1643
            year_str = date_str[1:5]  # "1643"
            return int(year_str)
        else:
            # "1643-01-04T00:00:00Z" -> 1643 (no prefix)
            return int(date_str[:4])
    except (ValueError, IndexError):
        return None


def calculate_lifespan_score(
    person_birth: Optional[int],
    person_death: Optional[int],
    wiki_birth: Optional[int],
    wiki_death: Optional[int],
    tolerance: int = 3
) -> tuple[float, str]:
    """
    Calculate lifespan match score between our person and Wikidata candidate.

    Returns:
        (score, reason)
        - score: 0.0 to 1.0
        - reason: explanation string

    Logic:
        - Both birth & death match: 1.0 (definite match)
        - One matches, other missing: 0.8 (likely match)
        - One matches, other mismatch: 0.3 (possible different person)
        - Both mismatch: 0.0 (different person)
        - No data to compare: 0.5 (neutral)
    """
    # No data on our side
    if person_birth is None and person_death is None:
        return 0.5, "no_person_dates"

    # No data on wiki side
    if wiki_birth is None and wiki_death is None:
        return 0.5, "no_wiki_dates"

    birth_match = None  # None = no data, True = match, False = mismatch
    death_match = None

    # Check birth
    if person_birth is not None and wiki_birth is not None:
        birth_match = abs(person_birth - wiki_birth) <= tolerance

    # Check death
    if person_death is not None and wiki_death is not None:
        death_match = abs(person_death - wiki_death) <= tolerance

    # Scoring logic
    if birth_match is True and death_match is True:
        return 1.0, "both_match"
    elif birth_match is True and death_match is None:
        return 0.8, "birth_match_only"
    elif birth_match is None and death_match is True:
        return 0.8, "death_match_only"
    elif birth_match is True and death_match is False:
        return 0.3, "birth_match_death_mismatch"
    elif birth_match is False and death_match is True:
        return 0.3, "birth_mismatch_death_match"
    elif birth_match is False and death_match is False:
        return 0.0, "both_mismatch"
    elif birth_match is False and death_match is None:
        return 0.2, "birth_mismatch"
    elif birth_match is None and death_match is False:
        return 0.2, "death_mismatch"
    else:
        return 0.5, "partial_data"


class MatchingWorker:
    """Worker that does Wikidata fetch + fuzzy + embedding matching"""

    def __init__(self, fetcher: WikidataFetcher, embedder=None):
        self.fetcher = fetcher
        self.embedder = embedder

    def fuzzy_match(self, name1: str, name2: str) -> Dict[str, float]:
        n1 = name1.lower().strip()
        n2 = name2.lower().strip()
        return {
            "ratio": fuzz.ratio(n1, n2) / 100,
            "token_set": fuzz.token_set_ratio(n1, n2) / 100,
            "jaro_winkler": JaroWinkler.similarity(n1, n2),
        }

    def _parse_candidate(self, c: Dict, task: MatchTask) -> Dict:
        """Parse Wikidata candidate and calculate scores"""
        qid = c.get("item", {}).get("value", "").split("/")[-1]
        label = c.get("itemLabel", {}).get("value", "")
        desc = c.get("itemDescription", {}).get("value", "")
        aliases_str = c.get("aliases", {}).get("value", "")
        aliases = [a.strip() for a in aliases_str.split("|") if a.strip()]

        # Extract birth/death from Wikidata
        wiki_birth = extract_year_from_wikidata(c.get("birth", {}).get("value", ""))
        wiki_death = extract_year_from_wikidata(c.get("death", {}).get("value", ""))

        # Calculate lifespan score
        lifespan_score, lifespan_reason = calculate_lifespan_score(
            task.birth_year, task.death_year,
            wiki_birth, wiki_death
        )

        # Calculate name match type
        name_match_type = "none"
        name_score = 0.0

        if label.lower() == task.person_name.lower():
            name_match_type = "exact"
            name_score = 1.0
        else:
            for alias in aliases:
                if alias.lower() == task.person_name.lower():
                    name_match_type = "alias"
                    name_score = 0.95
                    break

            if name_match_type == "none":
                fuzzy_scores = self.fuzzy_match(task.person_name, label)
                name_score = max(fuzzy_scores.values())
                if name_score >= 0.6:
                    name_match_type = "fuzzy"

        return {
            "qid": qid,
            "label": label,
            "desc": desc,
            "aliases": aliases,
            "wiki_birth": wiki_birth,
            "wiki_death": wiki_death,
            "name_match_type": name_match_type,
            "name_score": name_score,
            "lifespan_score": lifespan_score,
            "lifespan_reason": lifespan_reason,
        }

    def _calculate_final_confidence(self, name_score: float, name_type: str,
                                     lifespan_score: float, lifespan_reason: str) -> tuple[float, str]:
        """
        Calculate final confidence combining name and lifespan scores.

        Strategy:
        - If lifespan clearly mismatches (score=0), reject even exact name match
        - If lifespan matches well, boost confidence
        - If no lifespan data, rely on name match only
        """
        # Lifespan is definitive mismatch -> reject
        if lifespan_score == 0.0:
            return 0.0, f"{name_type}_but_lifespan_mismatch"

        # Lifespan is partial mismatch -> lower confidence significantly
        if lifespan_score <= 0.3:
            final = name_score * 0.4  # Heavy penalty
            return final, f"{name_type}_lifespan_suspicious"

        # Lifespan is neutral (no data) -> rely on name only
        if lifespan_reason in ("no_person_dates", "no_wiki_dates", "partial_data"):
            return name_score, f"{name_type}_no_lifespan_data"

        # Lifespan matches well -> boost or confirm
        if lifespan_score >= 0.8:
            # Boost fuzzy matches, confirm exact/alias
            if name_type == "exact":
                return 1.0, "exact_lifespan_confirmed"
            elif name_type == "alias":
                return 0.98, "alias_lifespan_confirmed"
            else:
                # Fuzzy + good lifespan = boost
                boosted = min(name_score + 0.15, 0.95)
                return boosted, "fuzzy_lifespan_boosted"

        # Lifespan is moderate match
        return name_score * 0.9, f"{name_type}_lifespan_partial"

    def process(self, task: MatchTask) -> tuple[MatchResult, Optional[LLMTask]]:
        """Process a single person, return result and optional LLM task"""
        result = MatchResult(
            person_id=task.person_id,
            person_name=task.person_name
        )

        # 1. Exact search
        candidates = self.fetcher.search(task.person_name)

        # 2. If no results, try fuzzy search
        if not candidates:
            candidates = self.fetcher.search_fuzzy(task.person_name)

        if not candidates:
            return result, None

        # 3. Parse all candidates and score them
        parsed_candidates = [self._parse_candidate(c, task) for c in candidates]

        # 4. Find best candidate considering both name AND lifespan
        best_candidate = None
        best_final_score = 0.0
        best_match_type = "none"
        best_reason = ""

        for pc in parsed_candidates:
            if pc["name_match_type"] == "none":
                continue

            final_score, reason = self._calculate_final_confidence(
                pc["name_score"],
                pc["name_match_type"],
                pc["lifespan_score"],
                pc["lifespan_reason"]
            )

            # Track best
            if final_score > best_final_score:
                best_final_score = final_score
                best_candidate = pc
                best_match_type = pc["name_match_type"]
                best_reason = reason

        # 5. No viable candidate
        if not best_candidate or best_final_score < 0.1:
            return result, None

        # 6. Decide based on final score
        if best_final_score >= 0.95:
            # High confidence - auto match
            result.wikidata_qid = best_candidate["qid"]
            result.match_type = best_reason
            result.confidence = best_final_score
            result.aliases = best_candidate["aliases"]
            return result, None

        elif best_final_score >= 0.6:
            # Medium confidence - needs LLM verification
            result.needs_llm = True
            llm_task = LLMTask(
                result=result,
                candidate_name=best_candidate["label"],
                candidate_desc=best_candidate["desc"],
                candidate_qid=best_candidate["qid"],
                fuzzy_score=best_final_score
            )
            result.aliases = best_candidate["aliases"]
            # Store lifespan info for LLM context
            result.llm_context = {
                "lifespan_score": best_candidate["lifespan_score"],
                "lifespan_reason": best_candidate["lifespan_reason"],
                "wiki_birth": best_candidate["wiki_birth"],
                "wiki_death": best_candidate["wiki_death"],
                "person_birth": task.birth_year,
                "person_death": task.death_year,
            }
            return result, llm_task

        elif best_final_score >= 0.3:
            # Low confidence - mark as uncertain, skip LLM
            result.match_type = f"low_confidence_{best_reason}"
            result.confidence = best_final_score
            result.llm_context = {
                "candidate_qid": best_candidate["qid"],
                "candidate_name": best_candidate["label"],
                "lifespan_reason": best_candidate["lifespan_reason"],
            }
            return result, None

        return result, None


class LLMVerifier:
    """Separate LLM worker that processes accumulated uncertain matches"""

    def __init__(self, batch_size: int = 10, timeout: float = 30.0):
        self.queue: Queue[LLMTask] = Queue()
        self.results: Queue[MatchResult] = Queue()
        self.batch_size = batch_size
        self.timeout = timeout
        self.running = True
        self.processed = 0
        self.verified = 0

    def add_task(self, task: LLMTask):
        self.queue.put(task)

    def verify_single(self, task: LLMTask) -> MatchResult:
        """Verify a single match with LLM"""
        result = task.result

        prompt = f"""You are verifying if two names refer to the same historical person.

Source name: {result.person_name}
Candidate name: {task.candidate_name}
Candidate description: {task.candidate_desc}
Fuzzy similarity: {task.fuzzy_score:.2f}

Are these the same person? Consider:
- Name variations (translations, titles, nicknames)
- Historical context
- Time period consistency

Reply with ONLY "YES" or "NO" followed by confidence 0-100.
Example: "YES 85" or "NO 90"
"""

        try:
            resp = requests.post(
                OLLAMA_URL,
                json={
                    "model": LLM_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1}
                },
                timeout=120
            )

            if resp.status_code == 200:
                answer = resp.json().get("response", "").strip().upper()

                if answer.startswith("YES"):
                    try:
                        conf = int(answer.split()[1]) / 100
                    except:
                        conf = 0.8

                    result.wikidata_qid = task.candidate_qid
                    result.match_type = "llm_verified"
                    result.confidence = conf
                    self.verified += 1
                else:
                    result.match_type = "llm_rejected"
                    result.confidence = 0.0

        except Exception as e:
            safe_print(f"  [LLM ERROR] {e}")
            result.match_type = "llm_error"

        self.processed += 1
        return result

    def run(self):
        """Main LLM worker loop"""
        safe_print("[LLM Worker] Started")

        while self.running or not self.queue.empty():
            batch = []

            # Collect batch
            try:
                # Wait for first item
                task = self.queue.get(timeout=self.timeout)
                batch.append(task)

                # Try to get more items (non-blocking)
                while len(batch) < self.batch_size:
                    try:
                        task = self.queue.get_nowait()
                        batch.append(task)
                    except Empty:
                        break

            except Empty:
                # Timeout - check if we should stop
                continue

            if batch:
                safe_print(f"[LLM Worker] Processing batch of {len(batch)}...")
                for task in batch:
                    result = self.verify_single(task)
                    self.results.put(result)
                    status = "MATCH" if result.wikidata_qid else "NO MATCH"
                    safe_print(f"  [LLM] {result.person_name} -> {status}")

        safe_print(f"[LLM Worker] Done. Processed: {self.processed}, Verified: {self.verified}")

    def stop(self):
        self.running = False


def load_persons(limit: int, offset: int = 0):
    """Load persons from DB"""
    from app.db.session import SessionLocal
    from app.models.person import Person

    db = SessionLocal()
    try:
        # Get unmatched persons
        query = db.query(Person).filter(
            Person.wikidata_id.is_(None)
        ).order_by(Person.id).offset(offset).limit(limit)

        persons = []
        for p in query:
            # Build lifespan string for display
            lifespan = ""
            if p.birth_year or p.death_year:
                b = str(p.birth_year) if p.birth_year else "?"
                d = str(p.death_year) if p.death_year else "?"
                lifespan = f"{b}-{d}"

            persons.append(MatchTask(
                person_id=p.id,
                person_name=p.name,
                description=p.biography or "",
                lifespan=lifespan,
                birth_year=p.birth_year,  # None if empty
                death_year=p.death_year,  # None if empty
            ))

        return persons
    finally:
        db.close()


def load_checkpoint():
    """Load checkpoint if exists"""
    checkpoint_path = Path(__file__).parent.parent / "data" / "wikidata_checkpoint.json"
    if checkpoint_path.exists():
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_checkpoint(results: List[MatchResult], stats: dict, offset: int, llm_pending: List[dict] = None):
    """Save checkpoint for resumability"""
    checkpoint_path = Path(__file__).parent.parent / "data" / "wikidata_checkpoint.json"
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "last_offset": offset,
        "stats": stats,
        "llm_pending": llm_pending or [],
        "results": [
            {
                "person_id": r.person_id,
                "person_name": r.person_name,
                "wikidata_qid": r.wikidata_qid,
                "match_type": r.match_type,
                "confidence": r.confidence,
                "aliases": r.aliases
            }
            for r in results
        ]
    }

    with open(checkpoint_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    safe_print(f"  [Checkpoint saved: {len(results)} results, offset {offset}]")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4, help="Number of fetch workers")
    parser.add_argument("--limit", type=int, default=1000, help="Number of persons to process")
    parser.add_argument("--offset", type=int, default=0, help="Offset in DB")
    parser.add_argument("--llm-batch", type=int, default=10, help="LLM batch size")
    parser.add_argument("--delay", type=float, default=0.2, help="API rate limit delay (seconds)")
    parser.add_argument("--skip-llm", action="store_true", help="Skip LLM verification (fast mode)")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--checkpoint-interval", type=int, default=100, help="Save checkpoint every N results")
    args = parser.parse_args()

    # Handle resume
    checkpoint = None
    if args.resume:
        checkpoint = load_checkpoint()
        if checkpoint:
            args.offset = checkpoint["last_offset"]
            safe_print(f"Resuming from checkpoint: offset {args.offset}")
        else:
            safe_print("No checkpoint found, starting fresh")

    safe_print(f"=== Parallel Wikidata Matching ===")
    safe_print(f"Workers: {args.workers}, Limit: {args.limit}, Delay: {args.delay}s")
    safe_print(f"Skip LLM: {args.skip_llm}, Offset: {args.offset}")

    # Load persons
    safe_print("Loading persons from DB...")
    tasks = load_persons(args.limit, args.offset)
    safe_print(f"Loaded {len(tasks)} persons")

    if not tasks:
        safe_print("No persons to process")
        return

    # Initialize
    fetcher = WikidataFetcher(delay=args.delay)
    worker = MatchingWorker(fetcher)

    # LLM verifier (only if not skipping)
    llm_verifier = None
    llm_thread = None
    if not args.skip_llm:
        llm_verifier = LLMVerifier(batch_size=args.llm_batch)
        llm_thread = threading.Thread(target=llm_verifier.run, daemon=True)
        llm_thread.start()

    # Results collection
    results = []
    llm_pending_tasks = []  # Track pending LLM tasks for checkpoint
    stats = {
        "total": len(tasks),
        "exact": 0,
        "exact_lifespan_confirmed": 0,
        "alias": 0,
        "alias_lifespan_confirmed": 0,
        "fuzzy": 0,
        "fuzzy_lifespan_boosted": 0,
        "lifespan_rejected": 0,
        "low_confidence": 0,
        "llm_verified": 0,
        "llm_rejected": 0,
        "llm_skipped": 0,
        "no_match": 0,
        "errors": 0
    }

    def categorize_match_type(match_type: str) -> str:
        """Categorize detailed match type into stats bucket"""
        if match_type == "none" or not match_type:
            return "no_match"
        if "lifespan_mismatch" in match_type:
            return "lifespan_rejected"
        if match_type.startswith("low_confidence"):
            return "low_confidence"
        if "exact_lifespan_confirmed" in match_type:
            return "exact_lifespan_confirmed"
        if "alias_lifespan_confirmed" in match_type:
            return "alias_lifespan_confirmed"
        if "fuzzy_lifespan_boosted" in match_type:
            return "fuzzy_lifespan_boosted"
        if match_type.startswith("exact") or "exact" in match_type:
            return "exact"
        if match_type.startswith("alias") or "alias" in match_type:
            return "alias"
        if match_type.startswith("fuzzy") or "fuzzy" in match_type:
            return "fuzzy"
        return match_type  # Use as-is if not recognized

    start_time = time.time()
    pending_llm = 0

    # Process with thread pool
    safe_print(f"\nProcessing with {args.workers} workers...")

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(worker.process, task): task for task in tasks}

        completed = 0
        for future in as_completed(futures):
            completed += 1
            task = futures[future]

            try:
                result, llm_task = future.result()

                if llm_task:
                    if args.skip_llm:
                        # Skip LLM - mark as skipped but save candidate info
                        result.match_type = "llm_skipped"
                        result.llm_context = {
                            "candidate_name": llm_task.candidate_name,
                            "candidate_desc": llm_task.candidate_desc,
                            "candidate_qid": llm_task.candidate_qid,
                            "fuzzy_score": llm_task.fuzzy_score
                        }
                        results.append(result)
                        stats["llm_skipped"] += 1
                        safe_print(f"[{completed}/{len(tasks)}] {task.person_name} -> LLM skipped (score: {llm_task.fuzzy_score:.2f})")
                    else:
                        # Send to LLM queue
                        llm_verifier.add_task(llm_task)
                        llm_pending_tasks.append({
                            "person_id": result.person_id,
                            "person_name": result.person_name,
                            "candidate_qid": llm_task.candidate_qid,
                            "candidate_name": llm_task.candidate_name,
                            "fuzzy_score": llm_task.fuzzy_score
                        })
                        pending_llm += 1
                        safe_print(f"[{completed}/{len(tasks)}] {task.person_name} -> LLM queue (pending: {pending_llm})")
                else:
                    # Direct result
                    results.append(result)
                    stat_key = categorize_match_type(result.match_type)
                    if stat_key in stats:
                        stats[stat_key] += 1
                    else:
                        stats["no_match"] += 1  # Fallback

                    # Build status with lifespan info
                    if result.wikidata_qid:
                        status = f"{result.match_type} ({result.confidence:.2f})"
                    elif result.match_type and "lifespan" in result.match_type:
                        status = f"REJECTED: {result.match_type}"
                    else:
                        status = "no match"

                    lifespan_info = f" [{task.lifespan}]" if task.lifespan else ""
                    safe_print(f"[{completed}/{len(tasks)}] {task.person_name}{lifespan_info} -> {status}")

            except Exception as e:
                safe_print(f"[{completed}/{len(tasks)}] {task.person_name} -> ERROR: {e}")
                stats["errors"] += 1
                results.append(MatchResult(
                    person_id=task.person_id,
                    person_name=task.person_name,
                    match_type="error"
                ))

            # Periodic checkpoint save
            if completed % args.checkpoint_interval == 0:
                save_checkpoint(results, stats, args.offset + completed, llm_pending_tasks)

    # Handle LLM completion
    if llm_verifier and not args.skip_llm:
        safe_print(f"\nWaiting for LLM worker to finish ({pending_llm} tasks)...")
        llm_verifier.stop()
        llm_thread.join(timeout=300)  # 5 min max

        # Collect LLM results
        while not llm_verifier.results.empty():
            result = llm_verifier.results.get()
            results.append(result)
            if result.wikidata_qid:
                stats["llm_verified"] += 1
            else:
                stats["llm_rejected"] += 1

    elapsed = time.time() - start_time

    # Summary
    safe_print(f"\n=== Results ===")
    safe_print(f"Time: {elapsed:.1f}s ({elapsed/len(tasks):.2f}s per person)")
    safe_print(f"Total: {stats['total']}")

    # Count matched (high confidence)
    matched_count = (
        stats['exact'] + stats['exact_lifespan_confirmed'] +
        stats['alias'] + stats['alias_lifespan_confirmed'] +
        stats['fuzzy'] + stats['fuzzy_lifespan_boosted'] +
        stats['llm_verified']
    )
    safe_print(f"\nMatched (high confidence): {matched_count}")
    safe_print(f"  - Exact: {stats['exact']}")
    safe_print(f"  - Exact + Lifespan confirmed: {stats['exact_lifespan_confirmed']}")
    safe_print(f"  - Alias: {stats['alias']}")
    safe_print(f"  - Alias + Lifespan confirmed: {stats['alias_lifespan_confirmed']}")
    safe_print(f"  - Fuzzy: {stats['fuzzy']}")
    safe_print(f"  - Fuzzy + Lifespan boosted: {stats['fuzzy_lifespan_boosted']}")
    safe_print(f"  - LLM verified: {stats['llm_verified']}")

    safe_print(f"\nRejected/Uncertain:")
    safe_print(f"  - Lifespan mismatch (동명이인): {stats['lifespan_rejected']}")
    safe_print(f"  - Low confidence: {stats['low_confidence']}")
    safe_print(f"  - LLM rejected: {stats['llm_rejected']}")
    if stats['llm_skipped'] > 0:
        safe_print(f"  - LLM skipped: {stats['llm_skipped']} (run without --skip-llm)")

    safe_print(f"\nNo match: {stats['no_match']}")
    safe_print(f"Errors: {stats['errors']}")

    # Save final results
    output_path = Path(__file__).parent.parent / "data" / "wikidata_parallel_results.json"
    output_data = {
        "stats": stats,
        "last_offset": args.offset + len(tasks),
        "elapsed_seconds": elapsed,
        "skip_llm": args.skip_llm,
        "results": [
            {
                "person_id": r.person_id,
                "person_name": r.person_name,
                "wikidata_qid": r.wikidata_qid,
                "match_type": r.match_type,
                "confidence": r.confidence,
                "aliases": r.aliases,
                "llm_context": getattr(r, 'llm_context', None)
            }
            for r in results
        ]
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    safe_print(f"\nResults saved to: {output_path}")

    # Final checkpoint
    save_checkpoint(results, stats, args.offset + len(tasks))


if __name__ == "__main__":
    main()
