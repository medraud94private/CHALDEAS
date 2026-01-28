"""
Fetch historical persons from Wikidata (Reverse Approach)

Instead of matching our DB to Wikidata, fetch curated historical figures
from Wikidata and match them to our DB.

Usage:
    python poc/scripts/fetch_wikidata_persons.py --category philosophers --limit 500
    python poc/scripts/fetch_wikidata_persons.py --category rulers --year-before 1800
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import argparse
import time
import requests
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, List

# Wikidata SPARQL endpoint
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"

# Category definitions (occupation QIDs)
CATEGORIES = {
    "philosophers": "Q4964182",      # philosopher
    "rulers": "Q116",                 # monarch
    "military": "Q47064",             # military personnel
    "artists": "Q483501",             # artist
    "religious": "Q2259532",          # religious figure
    "scientists": "Q901",             # scientist
    "writers": "Q36180",              # writer
    "politicians": "Q82955",          # politician
    "explorers": "Q11900058",         # explorer
}


@dataclass
class WikidataPerson:
    qid: str
    name: str
    name_ko: Optional[str]
    description: Optional[str]
    description_ko: Optional[str]
    birth_year: Optional[int]
    death_year: Optional[int]
    birth_place: Optional[str]
    death_place: Optional[str]
    occupation: Optional[str]
    image_url: Optional[str]
    wikipedia_url: Optional[str]
    sitelinks: int = 0


def parse_year(date_str: Optional[str]) -> Optional[int]:
    """Parse year from Wikidata date string."""
    if not date_str:
        return None
    try:
        # Format: "1234-01-01T00:00:00Z" or "-0500-01-01T00:00:00Z"
        if date_str.startswith("-"):
            # BCE date
            year_str = date_str[1:].split("-")[0]
            return -int(year_str)
        else:
            return int(date_str.split("-")[0])
    except:
        return None


def fetch_persons_by_category(
    category: str,
    year_before: int = 1900,
    limit: int = 1000,
    offset: int = 0
) -> List[WikidataPerson]:
    """Fetch historical persons from Wikidata by category."""

    occupation_qid = CATEGORIES.get(category)
    if not occupation_qid:
        print(f"Unknown category: {category}")
        print(f"Available: {list(CATEGORIES.keys())}")
        return []

    # Simplified query for better performance
    query = f"""
    SELECT ?person ?personLabel ?personDescription ?birth ?death ?image
    WHERE {{
      ?person wdt:P31 wd:Q5 .                    # instance of human
      ?person wdt:P106 wd:{occupation_qid} .    # occupation
      ?person wdt:P569 ?birth .                  # must have birth date

      OPTIONAL {{ ?person wdt:P570 ?death . }}
      OPTIONAL {{ ?person wdt:P18 ?image . }}

      # Filter: born before specified year (historical figures)
      FILTER (YEAR(?birth) < {year_before})

      SERVICE wikibase:label {{
        bd:serviceParam wikibase:language "en,ko" .
      }}
    }}
    LIMIT {limit}
    OFFSET {offset}
    """

    headers = {
        "User-Agent": "CHALDEAS/1.0 (Historical Knowledge System)",
        "Accept": "application/json"
    }

    try:
        response = requests.get(
            WIKIDATA_SPARQL,
            params={"query": query, "format": "json"},
            headers=headers,
            timeout=60
        )
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Error fetching from Wikidata: {e}")
        return []

    persons = []
    for result in data.get("results", {}).get("bindings", []):
        qid = result.get("person", {}).get("value", "").split("/")[-1]

        person = WikidataPerson(
            qid=qid,
            name=result.get("personLabel", {}).get("value"),
            name_ko=None,  # Would need separate query with ko filter
            description=result.get("personDescription", {}).get("value"),
            description_ko=None,
            birth_year=parse_year(result.get("birth", {}).get("value")),
            death_year=parse_year(result.get("death", {}).get("value")),
            birth_place=None,  # Simplified query doesn't include
            death_place=None,
            occupation=category,  # Use category as occupation
            image_url=result.get("image", {}).get("value"),
            wikipedia_url=None,
            sitelinks=0
        )
        persons.append(person)

    return persons


def main():
    parser = argparse.ArgumentParser(description="Fetch historical persons from Wikidata")
    parser.add_argument("--category", type=str, required=True,
                       help=f"Category: {list(CATEGORIES.keys())}")
    parser.add_argument("--year-before", type=int, default=1900,
                       help="Only include persons born before this year")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    print(f"Fetching {args.category} born before {args.year_before}...")
    print(f"Limit: {args.limit}, Offset: {args.offset}")

    persons = fetch_persons_by_category(
        category=args.category,
        year_before=args.year_before,
        limit=args.limit,
        offset=args.offset
    )

    print(f"\nFetched {len(persons)} persons")

    if persons:
        # Show samples
        print("\nTop 10 by sitelinks:")
        for p in persons[:10]:
            birth = p.birth_year or "?"
            death = p.death_year or "?"
            print(f"  {p.qid}: {p.name} ({birth}-{death}) - {p.sitelinks} sitelinks")

        # Stats
        with_birth = sum(1 for p in persons if p.birth_year)
        with_death = sum(1 for p in persons if p.death_year)
        with_ko = sum(1 for p in persons if p.name_ko)
        with_image = sum(1 for p in persons if p.image_url)

        print(f"\nStats:")
        print(f"  With birth year: {with_birth} ({100*with_birth/len(persons):.1f}%)")
        print(f"  With death year: {with_death} ({100*with_death/len(persons):.1f}%)")
        print(f"  With Korean name: {with_ko} ({100*with_ko/len(persons):.1f}%)")
        print(f"  With image: {with_image} ({100*with_image/len(persons):.1f}%)")

    # Save to file
    output_path = args.output or f"poc/data/wikidata_{args.category}.json"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_data = {
        "category": args.category,
        "year_before": args.year_before,
        "count": len(persons),
        "persons": [asdict(p) for p in persons]
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\nSaved to {output_path}")


if __name__ == "__main__":
    main()
