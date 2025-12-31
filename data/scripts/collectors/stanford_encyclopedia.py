"""
Stanford Encyclopedia of Philosophy Collector

Website: https://plato.stanford.edu/
Type: Academic philosophy encyclopedia

Contains:
- Ancient philosophy (Socrates, Plato, Aristotle, Stoics, etc.)
- Medieval philosophy (Augustine, Aquinas, etc.)
- Modern philosophy (Descartes, Kant, Hegel, etc.)
- Ethics, metaphysics, logic, epistemology
- Philosophy of science, mind, religion

License: Open access, free for academic use
Note: High-quality peer-reviewed articles
"""
import httpx
import asyncio
from pathlib import Path
import json
from typing import Optional, List
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re


class StanfordEncyclopediaCollector:
    """
    Collector for Stanford Encyclopedia of Philosophy.
    """

    BASE_URL = "https://plato.stanford.edu"
    CONTENTS_URL = "https://plato.stanford.edu/contents.html"

    # Key historical philosophy topics (prioritized for FGO/historical relevance)
    PRIORITY_TOPICS = [
        # Ancient Philosophy
        "socrates", "plato", "aristotle", "presocratics", "stoicism",
        "epicurus", "pythagoras", "heraclitus", "parmenides", "zeno-elea",
        "democritus", "sophists", "cynics", "skepticism-ancient",
        "neoplatonism", "plotinus", "marcus-aurelius",

        # Medieval Philosophy
        "augustine", "aquinas", "anselm", "abelard", "boethius",
        "maimonides", "averroes", "avicenna", "al-farabi", "al-kindi",
        "duns-scotus", "ockham", "medieval-philosophy",

        # Renaissance & Early Modern
        "machiavelli", "erasmus", "montaigne", "bacon-francis",
        "hobbes", "descartes", "spinoza", "leibniz", "locke", "hume",
        "rousseau", "kant", "berkeley",

        # Key Concepts
        "free-will", "determinism", "ethics-virtue", "natural-law-ethics",
        "justice", "political-obligation", "war", "cosmological-argument",
        "teleological-arguments", "problem-of-evil", "immortality",
        "personal-identity", "time", "causation-metaphysics",

        # Religion & Mythology
        "religion-morality", "divine-command", "afterlife",
        "reincarnation", "prophecy", "miracles", "mysticism",
    ]

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=True,
            headers={
                "User-Agent": "CHALDEAS/0.1 (Historical Knowledge System; Educational Research)"
            }
        )
        self.entries = []

    async def get_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a page."""
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            print(f"  Error: {e}")
            return None

    async def collect_table_of_contents(self) -> List[dict]:
        """Collect all entries from the table of contents."""
        print("  Fetching table of contents...")

        soup = await self.get_page(self.CONTENTS_URL)
        if not soup:
            return []

        entries = []

        # Find all entry links - SEP uses relative links like "entries/abduction/"
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            text = link.get_text(strip=True)

            # SEP entries start with "entries/"
            if href.startswith("entries/") and text and len(text) > 2:
                # Build full URL
                full_url = urljoin(self.BASE_URL + "/", href)

                # Get the slug for priority matching
                slug = href.replace("entries/", "").rstrip("/")

                entries.append({
                    "title": text,
                    "url": full_url,
                    "slug": slug,
                    "source": "stanford_encyclopedia",
                })

        print(f"  Found {len(entries)} entries in table of contents")
        await asyncio.sleep(0.5)
        return entries

    async def collect_entry_content(self, entry: dict) -> dict:
        """Collect full text of an entry."""
        soup = await self.get_page(entry["url"])
        if not soup:
            return entry

        content = ""

        # Remove navigation and unnecessary elements
        for nav in soup.find_all(["script", "style", "nav", "header", "footer"]):
            nav.decompose()

        # Try to find main content
        main = (
            soup.find("div", id="main-text") or
            soup.find("div", id="aueditable") or
            soup.find("article") or
            soup.find("main") or
            soup.find("body")
        )

        if main:
            content = main.get_text(separator="\n", strip=True)
            content = re.sub(r'\n{3,}', '\n\n', content)

        # Try to extract preamble/abstract
        preamble = soup.find("div", id="preamble")
        if preamble:
            entry["abstract"] = preamble.get_text(strip=True)[:1000]

        entry["content"] = content[:80000]  # SEP articles can be long
        entry["content_length"] = len(content)

        return entry

    async def collect_all(self):
        """Collect all Stanford Encyclopedia of Philosophy entries."""
        print("\n" + "=" * 60)
        print("Collecting from Stanford Encyclopedia of Philosophy")
        print("=" * 60)

        # Get all entries from table of contents
        all_entries = await self.collect_table_of_contents()
        print(f"Found {len(all_entries)} total entries")

        # Remove duplicates
        seen_urls = set()
        unique_entries = []
        for entry in all_entries:
            if entry["url"] not in seen_urls:
                seen_urls.add(entry["url"])
                unique_entries.append(entry)

        print(f"Unique entries: {len(unique_entries)}")

        # Save index
        index_file = self.output_dir / "sep_index.json"
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(unique_entries, f, indent=2, ensure_ascii=False)

        # Prioritize entries matching our topics
        priority_entries = []
        other_entries = []

        for entry in unique_entries:
            slug = entry.get("slug", "").lower()
            is_priority = any(topic in slug for topic in self.PRIORITY_TOPICS)
            if is_priority:
                priority_entries.append(entry)
            else:
                other_entries.append(entry)

        print(f"Priority entries (historical/philosophical): {len(priority_entries)}")

        # Collect detailed content
        # First priority entries, then fill with others
        entries_to_collect = priority_entries[:150] + other_entries[:50]
        entries_to_collect = entries_to_collect[:200]

        print(f"\nCollecting content for {len(entries_to_collect)} key entries...")
        detailed_entries = []

        for i, entry in enumerate(entries_to_collect):
            safe_title = entry['title'][:40].encode('ascii', 'replace').decode('ascii')
            print(f"  [{i+1}/{len(entries_to_collect)}] {safe_title}...")

            detailed = await self.collect_entry_content(entry)
            detailed_entries.append(detailed)
            await asyncio.sleep(0.8)

        # Save detailed entries
        detailed_file = self.output_dir / "sep_entries.json"
        with open(detailed_file, "w", encoding="utf-8") as f:
            json.dump(detailed_entries, f, indent=2, ensure_ascii=False)

        # Save metadata
        metadata = {
            "source": "stanford_encyclopedia",
            "url": self.BASE_URL,
            "description": "Stanford Encyclopedia of Philosophy - Peer-reviewed philosophy articles",
            "total_entries": len(unique_entries),
            "priority_collected": len([e for e in detailed_entries if e.get("slug", "") in [t for t in self.PRIORITY_TOPICS]]),
            "detailed_collected": len(detailed_entries),
            "priority_topics": self.PRIORITY_TOPICS,
            "license": "Open access academic use",
        }

        metadata_file = self.output_dir / "sep_metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        print("\nStanford Encyclopedia collection complete!")

    async def close(self):
        await self.client.aclose()


async def main():
    output_dir = Path("data/raw/stanford_encyclopedia")
    collector = StanfordEncyclopediaCollector(output_dir)
    try:
        await collector.collect_all()
    finally:
        await collector.close()


if __name__ == "__main__":
    asyncio.run(main())
