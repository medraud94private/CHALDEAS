"""
Yale Avalon Project Collector

Website: https://avalon.law.yale.edu/
Type: Primary source documents in law, history, and diplomacy

Contains:
- Magna Carta to present day documents
- Nuremberg Trials transcripts
- US founding documents
- International treaties

License: Public domain / educational use
"""
import httpx
import asyncio
from pathlib import Path
import json
from typing import Optional, List
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re


class AvalonCollector:
    """
    Collector for Yale Avalon Project historical documents.
    """

    BASE_URL = "https://avalon.law.yale.edu"

    # Major collections by century
    COLLECTIONS = {
        "ancient": "/subject_menus/ancient.asp",
        "medieval": "/subject_menus/medmenu.asp",
        "15th_century": "/subject_menus/15th.asp",
        "16th_century": "/subject_menus/16th.asp",
        "17th_century": "/subject_menus/17th.asp",
        "18th_century": "/subject_menus/18th.asp",
        "19th_century": "/subject_menus/19th.asp",
        "20th_century": "/subject_menus/20th.asp",
        "21st_century": "/subject_menus/21st.asp",
    }

    # Key document collections
    KEY_COLLECTIONS = {
        "american_founding": "/subject_menus/constpap.asp",
        "federalist_papers": "/subject_menus/fed.asp",
        "nuremberg_trials": "/subject_menus/imt.asp",
        "treaties": "/subject_menus/major.asp",
        "diplomacy": "/subject_menus/diplomacy.asp",
    }

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
        self.documents = []

    async def get_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a page."""
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            print(f"  Error: {e}")
            return None

    async def collect_collection_index(self, name: str, path: str) -> List[dict]:
        """Collect document list from a collection page."""
        url = urljoin(self.BASE_URL, path)
        print(f"  Fetching {name}...")

        soup = await self.get_page(url)
        if not soup:
            return []

        docs = []
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            text = link.get_text(strip=True)

            # Filter for document pages
            if text and len(text) > 5 and href.endswith(".asp"):
                if not any(x in href for x in ["menu", "subject", "default"]):
                    full_url = urljoin(url, href)
                    docs.append({
                        "title": text,
                        "url": full_url,
                        "collection": name,
                        "source": "avalon",
                    })

        await asyncio.sleep(0.5)
        return docs

    async def collect_document_content(self, doc: dict) -> dict:
        """Collect full text of a document."""
        soup = await self.get_page(doc["url"])
        if not soup:
            return doc

        # Extract main content
        content = ""

        # Remove navigation elements
        for nav in soup.find_all(["script", "style", "nav"]):
            nav.decompose()

        # Get body text
        body = soup.find("body")
        if body:
            content = body.get_text(separator="\n", strip=True)
            # Clean up excessive whitespace
            content = re.sub(r'\n{3,}', '\n\n', content)

        doc["content"] = content[:50000]  # Limit size
        doc["content_length"] = len(content)

        return doc

    async def collect_all(self):
        """Collect all Avalon Project documents."""
        print("\n" + "=" * 60)
        print("Collecting from Yale Avalon Project")
        print("=" * 60)

        all_docs = []

        # Collect from century collections
        print("\nCollecting by century...")
        for name, path in self.COLLECTIONS.items():
            docs = await self.collect_collection_index(name, path)
            all_docs.extend(docs)
            print(f"    {name}: {len(docs)} documents")

        # Collect from key collections
        print("\nCollecting key collections...")
        for name, path in self.KEY_COLLECTIONS.items():
            docs = await self.collect_collection_index(name, path)
            all_docs.extend(docs)
            print(f"    {name}: {len(docs)} documents")

        # Remove duplicates
        seen_urls = set()
        unique_docs = []
        for doc in all_docs:
            if doc["url"] not in seen_urls:
                seen_urls.add(doc["url"])
                unique_docs.append(doc)

        print(f"\nTotal unique documents: {len(unique_docs)}")

        # Save index
        index_file = self.output_dir / "avalon_index.json"
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(unique_docs, f, indent=2, ensure_ascii=False)

        # Collect content for subset (be respectful)
        print(f"\nCollecting content for up to 100 key documents...")
        detailed_docs = []

        for i, doc in enumerate(unique_docs[:100]):
            safe_title = doc['title'][:40].encode('ascii', 'replace').decode('ascii')
            print(f"  [{i+1}/100] {safe_title}...")

            detailed = await self.collect_document_content(doc)
            detailed_docs.append(detailed)
            await asyncio.sleep(1)

        # Save detailed documents
        detailed_file = self.output_dir / "avalon_documents.json"
        with open(detailed_file, "w", encoding="utf-8") as f:
            json.dump(detailed_docs, f, indent=2, ensure_ascii=False)

        # Save metadata
        metadata = {
            "source": "avalon",
            "url": self.BASE_URL,
            "description": "Yale Avalon Project - Documents in Law, History and Diplomacy",
            "total_documents": len(unique_docs),
            "detailed_collected": len(detailed_docs),
            "collections": list(self.COLLECTIONS.keys()) + list(self.KEY_COLLECTIONS.keys()),
            "license": "Public domain / educational use",
        }

        metadata_file = self.output_dir / "avalon_metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        print("\nAvalon Project collection complete!")

    async def close(self):
        await self.client.aclose()


async def main():
    output_dir = Path("data/raw/avalon")
    collector = AvalonCollector(output_dir)
    try:
        await collector.collect_all()
    finally:
        await collector.close()


if __name__ == "__main__":
    asyncio.run(main())
