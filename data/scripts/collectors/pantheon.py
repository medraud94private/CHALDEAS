"""
Pantheon Dataset Collector

Source: MIT Media Lab Pantheon Project
Paper: https://www.nature.com/articles/sdata201575
Data: https://pantheon.world/

Contains:
- 11,341 globally famous historical figures
- Birth/death dates and locations
- Occupations and domains
- Wikipedia-based popularity metrics

License: Open data (CC BY 4.0)
"""
import httpx
import asyncio
from pathlib import Path
import json
import csv
from io import StringIO
from typing import Optional


class PantheonCollector:
    """
    Collector for MIT Pantheon historical figures dataset.

    Pantheon contains verified biographical data for 11,341
    individuals who have transcended linguistic and geographic boundaries.
    """

    # Pantheon data exports (Google Cloud Storage)
    # 2025 version with ~70,000+ persons
    CSV_URL_2025 = "https://storage.googleapis.com/pantheon-public-data/person_2025_update.csv.bz2"
    # Legacy 1.0 with 11,341 verified biographies
    TSV_URL_LEGACY = "https://storage.googleapis.com/pantheon-public-data/legacy_pantheon.tsv.bz2"

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.AsyncClient(
            timeout=120.0,
            follow_redirects=True,
            headers={
                "User-Agent": "CHALDEAS/0.1 (Historical Knowledge System; Educational Research)"
            }
        )

    async def download_dataset(self) -> Optional[list]:
        """Download the Pantheon dataset."""
        import bz2

        print("Downloading Pantheon 2025 dataset (bz2 compressed)...")

        try:
            response = await self.client.get(self.CSV_URL_2025)
            response.raise_for_status()

            # Decompress bz2
            decompressed = bz2.decompress(response.content)
            text = decompressed.decode('utf-8')

            reader = csv.DictReader(StringIO(text))
            data = list(reader)
            print(f"Downloaded {len(data)} persons from Pantheon 2025")
            return data

        except Exception as e:
            print(f"Error with 2025 dataset: {e}")
            print("Trying legacy 1.0 dataset...")

            try:
                response = await self.client.get(self.TSV_URL_LEGACY)
                response.raise_for_status()

                decompressed = bz2.decompress(response.content)
                text = decompressed.decode('utf-8')

                reader = csv.DictReader(StringIO(text), delimiter='\t')
                data = list(reader)
                print(f"Downloaded {len(data)} persons from Pantheon 1.0")
                return data

            except Exception as e2:
                print(f"Error downloading legacy data: {e2}")
                return None

    async def collect_via_api(self) -> list:
        """Collect data via Pantheon API with pagination."""
        print("Collecting via Pantheon API...")

        all_persons = []
        offset = 0
        limit = 500

        while True:
            try:
                response = await self.client.get(
                    self.DATA_URL,
                    params={"limit": limit, "offset": offset}
                )

                if response.status_code != 200:
                    break

                data = response.json()
                if not data or len(data) == 0:
                    break

                all_persons.extend(data)
                print(f"  Fetched {len(all_persons)} persons...")

                if len(data) < limit:
                    break

                offset += limit
                await asyncio.sleep(0.5)

            except Exception as e:
                print(f"  Error at offset {offset}: {e}")
                break

        return all_persons

    def extract_fgo_relevant(self, persons: list) -> list:
        """Extract persons relevant to FGO (historical/mythological figures)."""
        if not persons:
            return []

        # Check first person to understand field names
        sample = persons[0]
        print(f"  Sample fields: {list(sample.keys())[:10]}")

        fgo_relevant = []

        for person in persons:
            # Try various field name formats
            name = (person.get("name") or person.get("en_page_title") or
                    person.get("full_name") or "")
            birth_year = (person.get("birthyear") or person.get("birth_year") or
                         person.get("byear") or "2000")
            death_year = (person.get("deathyear") or person.get("death_year") or
                         person.get("dyear"))
            occupation = (person.get("occupation") or person.get("occ3") or
                         person.get("domain") or "")
            country = (person.get("countryName") or person.get("bplace_country") or
                      person.get("country_name") or person.get("countryCode") or "")
            gender = person.get("gender") or person.get("sex") or ""
            hpi = person.get("HPI") or person.get("hpi") or person.get("historical_popularity_index")

            # Convert birth_year to int
            try:
                birth_year = int(float(str(birth_year)))
            except:
                birth_year = 2000

            # Include pre-1950 figures (FGO focuses on historical figures)
            if birth_year < 1950 and name:
                fgo_relevant.append({
                    "name": name,
                    "birth_year": birth_year,
                    "death_year": death_year,
                    "country": country,
                    "occupation": occupation,
                    "gender": gender,
                    "hpi": hpi,
                    "source": "pantheon",
                })

        return fgo_relevant

    async def collect_all(self):
        """Collect all Pantheon data."""
        print("\n" + "=" * 60)
        print("Collecting from Pantheon (MIT)")
        print("=" * 60)

        # Try to get data
        persons = await self.download_dataset()

        if not persons:
            persons = await self.collect_via_api()

        if not persons:
            print("Could not retrieve Pantheon data")
            return

        # Save raw data
        raw_file = self.output_dir / "pantheon_raw.json"
        with open(raw_file, "w", encoding="utf-8") as f:
            json.dump(persons, f, indent=2, ensure_ascii=False)
        print(f"Saved {len(persons)} persons to raw file")

        # Extract FGO-relevant
        fgo_relevant = self.extract_fgo_relevant(persons)

        relevant_file = self.output_dir / "pantheon_historical.json"
        with open(relevant_file, "w", encoding="utf-8") as f:
            json.dump(fgo_relevant, f, indent=2, ensure_ascii=False)
        print(f"Extracted {len(fgo_relevant)} historical figures")

        # Save metadata
        metadata = {
            "source": "pantheon",
            "url": "https://pantheon.world/",
            "description": "MIT Pantheon dataset - globally famous historical figures",
            "total_persons": len(persons),
            "historical_figures": len(fgo_relevant),
            "license": "CC BY 4.0",
        }

        metadata_file = self.output_dir / "pantheon_metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        print("\nPantheon collection complete!")

    async def close(self):
        await self.client.aclose()


async def main():
    """Main entry point."""
    output_dir = Path("data/raw/pantheon")
    collector = PantheonCollector(output_dir)

    try:
        await collector.collect_all()
    finally:
        await collector.close()


if __name__ == "__main__":
    asyncio.run(main())
