#!/usr/bin/env python3
"""
CHALDEAS Data Quality Analysis

Analyzes aggregated NER data for:
- Confidence distribution
- Era/temporal distribution
- Duplicate candidates
- Top entities by mention count
"""
import json
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict
import sys

DATA_PATH = Path(__file__).parent.parent / "data/integrated_ner_full/aggregated"
OUTPUT_PATH = Path(__file__).parent.parent.parent / "docs/logs/analysis"


def load_data(entity_type: str) -> list:
    """Load aggregated entity data."""
    filepath = DATA_PATH / f"{entity_type}.json"
    if not filepath.exists():
        print(f"  File not found: {filepath}")
        return []
    with open(filepath, encoding='utf-8') as f:
        return json.load(f)


def analyze_confidence(entities: list, entity_type: str) -> dict:
    """Analyze confidence distribution."""
    dist = {"high": 0, "medium": 0, "low": 0, "very_low": 0}
    total = len(entities)

    for e in entities:
        conf = e.get("confidence", 0.5)
        if conf >= 0.9:
            dist["high"] += 1
        elif conf >= 0.7:
            dist["medium"] += 1
        elif conf >= 0.4:
            dist["low"] += 1
        else:
            dist["very_low"] += 1

    return {
        "entity_type": entity_type,
        "total": total,
        "distribution": dist,
        "percentages": {k: f"{v/total*100:.1f}%" if total > 0 else "0%" for k, v in dist.items()}
    }


def analyze_era_distribution(persons: list) -> dict:
    """Analyze era distribution for persons."""
    era_counts = Counter()
    for p in persons:
        era = p.get("era") or "Unknown"
        era_counts[era] += 1

    # Top 20 eras
    top_eras = era_counts.most_common(20)
    return {
        "total_eras": len(era_counts),
        "top_20": [{"era": era, "count": count} for era, count in top_eras]
    }


def analyze_top_entities(entities: list, entity_type: str, limit: int = 50) -> list:
    """Get top entities by mention count."""
    sorted_entities = sorted(
        entities,
        key=lambda x: x.get("mention_count", 1),
        reverse=True
    )[:limit]

    return [
        {
            "name": e["name"],
            "mention_count": e.get("mention_count", 1),
            "confidence": e.get("confidence", 0.5),
            "era": e.get("era") if entity_type == "persons" else None
        }
        for e in sorted_entities
    ]


def analyze_temporal_coverage(entities: list, entity_type: str) -> dict:
    """Analyze temporal coverage (years with data)."""
    years = []

    for e in entities:
        if entity_type == "persons":
            if e.get("birth_year"):
                years.append(e["birth_year"])
            if e.get("death_year"):
                years.append(e["death_year"])
        elif entity_type == "events":
            if e.get("year"):
                years.append(e["year"])
        elif entity_type in ("polities", "periods"):
            if e.get("start_year"):
                years.append(e["start_year"])
            if e.get("end_year"):
                years.append(e["end_year"])

    if not years:
        return {"has_temporal_data": False}

    # Group by century
    century_counts = Counter()
    bce_count = 0
    ce_count = 0

    for y in years:
        if y < 0:
            bce_count += 1
            century = f"{abs(y)//100 + 1} BCE"
        else:
            ce_count += 1
            century = f"{y//100 + 1} CE"
        century_counts[century] += 1

    return {
        "has_temporal_data": True,
        "total_year_references": len(years),
        "min_year": min(years),
        "max_year": max(years),
        "bce_count": bce_count,
        "ce_count": ce_count,
        "bce_ratio": f"{bce_count/len(years)*100:.1f}%",
        "top_centuries": [
            {"century": c, "count": n}
            for c, n in century_counts.most_common(10)
        ]
    }


def find_duplicate_candidates(entities: list, entity_type: str) -> list:
    """Find potential duplicate entities by name similarity."""
    from difflib import SequenceMatcher

    # Group by first 3 characters of lowercase name
    groups = defaultdict(list)
    for i, e in enumerate(entities):
        name = e.get("name", "").lower()
        if len(name) >= 3:
            key = name[:3]
            groups[key].append((i, e))

    duplicates = []
    checked = set()

    for key, items in groups.items():
        if len(items) < 2:
            continue

        for i, (idx1, e1) in enumerate(items):
            for idx2, e2 in items[i+1:]:
                pair_key = (min(idx1, idx2), max(idx1, idx2))
                if pair_key in checked:
                    continue

                name1 = e1.get("name", "").lower()
                name2 = e2.get("name", "").lower()

                # Skip if same name (exact duplicates already merged)
                if name1 == name2:
                    continue

                ratio = SequenceMatcher(None, name1, name2).ratio()
                if ratio >= 0.85:  # 85% similar
                    duplicates.append({
                        "name1": e1["name"],
                        "name2": e2["name"],
                        "similarity": f"{ratio*100:.1f}%",
                        "confidence1": e1.get("confidence", 0.5),
                        "confidence2": e2.get("confidence", 0.5)
                    })
                    checked.add(pair_key)

                if len(duplicates) >= 100:  # Limit for performance
                    break
            if len(duplicates) >= 100:
                break
        if len(duplicates) >= 100:
            break

    return duplicates[:50]  # Return top 50


def main():
    """Run all analyses."""
    print("=" * 60)
    print("CHALDEAS Data Quality Analysis")
    print("=" * 60)
    print(f"Data path: {DATA_PATH}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()

    if not DATA_PATH.exists():
        print(f"ERROR: Data path not found: {DATA_PATH}")
        print("Run aggregate_ner_results.py first.")
        sys.exit(1)

    report = {
        "timestamp": datetime.now().isoformat(),
        "data_path": str(DATA_PATH),
        "analyses": {}
    }

    # 1. Load and count all entities
    print("[1/6] Loading data...")
    entity_types = ["persons", "locations", "events", "polities", "periods"]
    all_data = {}

    for et in entity_types:
        data = load_data(et)
        all_data[et] = data
        print(f"  {et}: {len(data):,} entities")

    total = sum(len(d) for d in all_data.values())
    print(f"  TOTAL: {total:,} entities")
    report["total_entities"] = total

    # 2. Confidence analysis
    print("\n[2/6] Analyzing confidence distribution...")
    confidence_report = {}
    for et, data in all_data.items():
        if data:
            conf = analyze_confidence(data, et)
            confidence_report[et] = conf
            print(f"  {et}: High={conf['percentages']['high']}, Medium={conf['percentages']['medium']}, Low={conf['percentages']['low']}")
    report["analyses"]["confidence"] = confidence_report

    # 3. Era distribution (persons)
    print("\n[3/6] Analyzing era distribution (persons)...")
    era_report = analyze_era_distribution(all_data["persons"])
    print(f"  Total distinct eras: {era_report['total_eras']}")
    print("  Top 5 eras:")
    for e in era_report["top_20"][:5]:
        print(f"    - {e['era']}: {e['count']:,}")
    report["analyses"]["era_distribution"] = era_report

    # 4. Top entities
    print("\n[4/6] Finding top entities by mention count...")
    top_report = {}
    for et in ["persons", "locations"]:
        if all_data[et]:
            top = analyze_top_entities(all_data[et], et, 20)
            top_report[et] = top
            print(f"  Top 5 {et}:")
            for e in top[:5]:
                print(f"    - {e['name']}: {e['mention_count']:,} mentions")
    report["analyses"]["top_entities"] = top_report

    # 5. Temporal coverage
    print("\n[5/6] Analyzing temporal coverage...")
    temporal_report = {}
    for et in ["persons", "events", "polities"]:
        if all_data[et]:
            temp = analyze_temporal_coverage(all_data[et], et)
            temporal_report[et] = temp
            if temp.get("has_temporal_data"):
                print(f"  {et}: {temp['min_year']} to {temp['max_year']}, BCE ratio: {temp['bce_ratio']}")
    report["analyses"]["temporal_coverage"] = temporal_report

    # 6. Duplicate candidates
    print("\n[6/6] Finding duplicate candidates...")
    duplicates_report = {}
    for et in ["persons", "locations"]:
        if all_data[et]:
            dups = find_duplicate_candidates(all_data[et], et)
            duplicates_report[et] = dups
            print(f"  {et}: {len(dups)} potential duplicates found")
            if dups:
                # Safe print for non-ASCII characters
                try:
                    print(f"    Example: '{dups[0]['name1']}' ~ '{dups[0]['name2']}' ({dups[0]['similarity']})")
                except UnicodeEncodeError:
                    print(f"    Example: (contains non-ASCII characters) ({dups[0]['similarity']})")
    report["analyses"]["duplicate_candidates"] = duplicates_report

    # Save report
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = OUTPUT_PATH / f"data_quality_{timestamp}.json"

    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(f"Report saved: {report_file}")
    print("=" * 60)

    # Print summary
    print("\n## SUMMARY ##")
    print(f"Total entities: {total:,}")
    print(f"High confidence (≥0.9): {sum(c['distribution']['high'] for c in confidence_report.values()):,}")
    print(f"BCE data points: {sum(t.get('bce_count', 0) for t in temporal_report.values()):,}")
    print(f"Potential duplicates: {sum(len(d) for d in duplicates_report.values())}")


if __name__ == "__main__":
    main()
