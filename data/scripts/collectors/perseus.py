"""
Perseus Digital Library Collector

Website: https://www.perseus.tufts.edu/
API: CTS (Canonical Text Services)

Data includes:
- Greek and Latin classical texts
- Historical figures metadata
- Geographical data

License: CC BY-SA (usable with attribution)
"""
import httpx
import asyncio
from pathlib import Path
from typing import Optional
import json
from xml.etree import ElementTree as ET
import re


class PerseusCollector:
    """
    Collector for Perseus Digital Library.

    Uses the CTS (Canonical Text Services) protocol via Perseids.
    """

    BASE_URL = "https://cts.perseids.org/api/cts"
    CAPABILITY_URL = f"{BASE_URL}?request=GetCapabilities"

    # Namespaces used in CTS XML responses
    NAMESPACES = {
        "ti": "http://chs.harvard.edu/xmlns/cts",
        "dc": "http://purl.org/dc/elements/1.1/",
    }

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=True,
            headers={"User-Agent": "CHALDEAS/0.1 (Historical Knowledge System)"}
        )
        self.works_metadata = []

    async def get_catalog(self) -> dict:
        """Get the catalog of available texts and parse it."""
        print("Fetching Perseus CTS catalog...")

        response = await self.client.get(self.CAPABILITY_URL)
        response.raise_for_status()

        # Parse XML
        root = ET.fromstring(response.text)

        catalog = {
            "textgroups": [],
            "works": [],
        }

        # Find all textgroups (authors/collections)
        for tg in root.findall(".//ti:textgroup", self.NAMESPACES):
            urn = tg.get("urn", "")

            # Get group name
            groupname = tg.find("ti:groupname", self.NAMESPACES)
            name = groupname.text if groupname is not None else ""

            catalog["textgroups"].append({
                "urn": urn,
                "name": name,
            })

            # Find works in this textgroup
            for work in tg.findall(".//ti:work", self.NAMESPACES):
                work_urn = work.get("urn", "")

                # Get work title
                title_elem = work.find("ti:title", self.NAMESPACES)
                title = title_elem.text if title_elem is not None else ""

                # Determine language from URN
                language = "greek" if "greekLit" in work_urn else "latin"

                # Find available editions
                editions = []
                for edition in work.findall(".//ti:edition", self.NAMESPACES):
                    ed_urn = edition.get("urn", "")
                    ed_label = edition.find("ti:label", self.NAMESPACES)
                    ed_label = ed_label.text if ed_label is not None else ""

                    editions.append({
                        "urn": ed_urn,
                        "label": ed_label,
                    })

                catalog["works"].append({
                    "urn": work_urn,
                    "title": title,
                    "author": name,
                    "textgroup": urn,
                    "language": language,
                    "editions": editions,
                })

        print(f"Found {len(catalog['textgroups'])} authors, {len(catalog['works'])} works")
        return catalog

    async def get_valid_refs(self, urn: str) -> list[str]:
        """Get valid reference points for a text."""
        url = f"{self.BASE_URL}?request=GetValidReff&urn={urn}"
        try:
            response = await self.client.get(url)
            response.raise_for_status()

            root = ET.fromstring(response.text)
            refs = []

            for ref in root.findall(".//ti:urn", self.NAMESPACES):
                if ref.text:
                    refs.append(ref.text)

            return refs

        except Exception as e:
            print(f"  Error getting refs for {urn}: {e}")
            return []

    async def get_text(self, urn: str) -> Optional[str]:
        """
        Get a text passage by its URN.

        Example URN: urn:cts:greekLit:tlg0012.tlg001.perseus-grc2:1.1
        (Homer's Iliad, Book 1, Line 1 in Greek)
        """
        url = f"{self.BASE_URL}?request=GetPassage&urn={urn}"
        try:
            response = await self.client.get(url)
            response.raise_for_status()

            root = ET.fromstring(response.text)

            # Find the passage content
            passage = root.find(".//ti:passage", self.NAMESPACES)
            if passage is not None:
                # Get all text content
                return self._extract_text(passage)

            return None

        except Exception as e:
            print(f"Error fetching {urn}: {e}")
            return None

    def _extract_text(self, element) -> str:
        """Extract text content from XML element."""
        text_parts = []

        def walk(el):
            if el.text:
                text_parts.append(el.text)
            for child in el:
                walk(child)
                if child.tail:
                    text_parts.append(child.tail)

        walk(element)
        return " ".join(text_parts)

    async def collect_all(self, limit: Optional[int] = None):
        """
        Collect all available texts metadata.

        Args:
            limit: Max number of works to process (None = all)
        """
        print("\n" + "=" * 60)
        print("Collecting from Perseus Digital Library")
        print("=" * 60)

        # Get and save catalog
        catalog = await self.get_catalog()

        catalog_path = self.output_dir / "perseus_catalog.json"
        with open(catalog_path, "w", encoding="utf-8") as f:
            json.dump(catalog, f, indent=2, ensure_ascii=False)
        print(f"Catalog saved to {catalog_path}")

        # Process works and collect metadata
        works_to_process = catalog["works"]
        if limit:
            works_to_process = works_to_process[:limit]

        print(f"\nProcessing {len(works_to_process)} works...")

        for i, work in enumerate(works_to_process):
            if i % 20 == 0:
                print(f"  Processing {i+1}/{len(works_to_process)}...")

            # Get reference count for first edition if available
            ref_count = 0
            if work.get("editions"):
                refs = await self.get_valid_refs(work["editions"][0]["urn"])
                ref_count = len(refs)

            self.works_metadata.append({
                "urn": work["urn"],
                "title": work["title"],
                "author": work["author"],
                "language": work["language"],
                "edition_count": len(work.get("editions", [])),
                "ref_count": ref_count,
                "source": "perseus",
            })

            await asyncio.sleep(0.3)  # Rate limiting

        # Save works metadata
        works_path = self.output_dir / "perseus_works.json"
        with open(works_path, "w", encoding="utf-8") as f:
            json.dump(self.works_metadata, f, indent=2, ensure_ascii=False)

        print(f"\nSaved {len(self.works_metadata)} works to {works_path}")

        # Print summary
        greek = sum(1 for w in self.works_metadata if w["language"] == "greek")
        latin = sum(1 for w in self.works_metadata if w["language"] == "latin")
        print(f"\nSummary:")
        print(f"  Greek works: {greek}")
        print(f"  Latin works: {latin}")

    async def close(self):
        await self.client.aclose()


# Key Perseus URNs for important texts
IMPORTANT_TEXTS = [
    # Greek Literature
    ("urn:cts:greekLit:tlg0012.tlg001", "Homer - Iliad"),
    ("urn:cts:greekLit:tlg0012.tlg002", "Homer - Odyssey"),
    ("urn:cts:greekLit:tlg0016.tlg001", "Herodotus - Histories"),
    ("urn:cts:greekLit:tlg0003.tlg001", "Thucydides - History"),
    ("urn:cts:greekLit:tlg0059.tlg030", "Plato - Republic"),
    ("urn:cts:greekLit:tlg0059.tlg002", "Plato - Apology"),
    ("urn:cts:greekLit:tlg0086.tlg035", "Aristotle - Nicomachean Ethics"),

    # Latin Literature
    ("urn:cts:latinLit:phi0448.phi001", "Caesar - Gallic War"),
    ("urn:cts:latinLit:phi0690.phi003", "Virgil - Aeneid"),
    ("urn:cts:latinLit:phi0978.phi001", "Tacitus - Annals"),
    ("urn:cts:latinLit:phi0474.phi005", "Cicero - De Officiis"),
]


async def main():
    """Main entry point for Perseus collection."""
    output_dir = Path("data/raw/perseus")
    collector = PerseusCollector(output_dir)

    try:
        await collector.collect_all()
    finally:
        await collector.close()


if __name__ == "__main__":
    asyncio.run(main())
