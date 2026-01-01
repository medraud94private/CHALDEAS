# Location Resolution Strategy

## Overview

CHALDEAS needs accurate geographic coordinates for all historical events, persons, and places. Since many historical records lack precise coordinates, we implement a multi-source resolution system.

## Resolution Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Location Resolution Pipeline                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   Input: "Marathon" (from historical text)                          │
│                    │                                                 │
│                    ▼                                                 │
│   ┌────────────────────────────────────────┐                        │
│   │ 1. Pleiades Gazetteer (Confidence: 95%)│                        │
│   │    - 34,000+ ancient world places       │                        │
│   │    - Multiple name attestations         │                        │
│   │    - Time period information            │                        │
│   └────────────────────────────────────────┘                        │
│                    │ Not found?                                      │
│                    ▼                                                 │
│   ┌────────────────────────────────────────┐                        │
│   │ 2. Wikidata SPARQL (Confidence: 90%)   │                        │
│   │    - Millions of entities               │                        │
│   │    - P625 coordinate property           │                        │
│   │    - Multi-language labels              │                        │
│   └────────────────────────────────────────┘                        │
│                    │ Not found?                                      │
│                    ▼                                                 │
│   ┌────────────────────────────────────────┐                        │
│   │ 3. World Historical Gazetteer (85%)    │                        │
│   │    - Historical place names             │                        │
│   │    - Temporal scoping                   │                        │
│   └────────────────────────────────────────┘                        │
│                    │ Not found?                                      │
│                    ▼                                                 │
│   ┌────────────────────────────────────────┐                        │
│   │ 4. Ancient Region Mapping (60%)        │                        │
│   │    - "Attica" → Greece (37.9, 23.7)    │                        │
│   │    - "Persia" → Iran (32.0, 53.0)      │                        │
│   └────────────────────────────────────────┘                        │
│                    │ Not found?                                      │
│                    ▼                                                 │
│   ┌────────────────────────────────────────┐                        │
│   │ 5. Country Centroid Fallback (30%)     │                        │
│   │    - Use country center as last resort  │                        │
│   └────────────────────────────────────────┘                        │
│                                                                      │
│   Output: ResolvedLocation {                                        │
│     name: "Marathon",                                               │
│     latitude: 38.1536,                                              │
│     longitude: 23.9633,                                             │
│     source: "pleiades",                                             │
│     confidence: 0.95,                                               │
│     pleiades_id: "580037"                                           │
│   }                                                                 │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Sources

### 1. Pleiades Gazetteer (Primary)
- **URL**: https://pleiades.stoa.org/
- **Coverage**: Ancient Mediterranean, Near East, Egypt
- **Data**: 34,000+ places with coordinates
- **License**: CC BY 3.0
- **Why**: Most authoritative for ancient world geography

### 2. Wikidata (Secondary)
- **URL**: https://www.wikidata.org/
- **Coverage**: Global, all time periods
- **Data**: Millions of geographic entities
- **License**: CC0
- **Why**: Comprehensive backup, modern place links

### 3. World Historical Gazetteer
- **URL**: https://whgazetteer.org/
- **Coverage**: Global historical places
- **Data**: Temporal place data
- **License**: CC BY
- **Why**: Time-scoped place names

### 4. GeoHack Reference
- **URL**: https://geohack.toolforge.org/
- **Use Case**: Manual verification, multiple map sources
- **Integration**: Link generation for user verification

## Confidence Levels

| Source | Confidence | Use Case |
|--------|------------|----------|
| Pleiades (exact match) | 0.95 | Ancient world places |
| Wikidata (P625) | 0.90 | General locations |
| WHG | 0.85 | Historical places |
| Ancient Region | 0.60 | Regional approximation |
| Country Centroid | 0.30 | Last resort fallback |

## Implementation

### GeoResolver Class

```python
class GeoResolver:
    async def resolve(self, location_name: str, context: dict = None) -> ResolvedLocation:
        # 1. Try Pleiades first (best for ancient places)
        result = self._resolve_pleiades(name_lower)
        if result:
            return result

        # 2. Try Wikidata
        result = await self._resolve_wikidata(location_name)
        if result:
            return result

        # 3. Try World Historical Gazetteer
        result = await self._resolve_whg(location_name)
        if result:
            return result

        # 4. Try ancient region mappings
        result = self._resolve_ancient_region(name_lower)
        if result:
            return result

        # 5. Fallback to country centroid
        if context and context.get("country"):
            return self._resolve_country_centroid(context["country"])

        return None
```

### Context-Aware Resolution

```python
# Context helps disambiguate
await resolver.resolve("Thebes", context={"period": "ancient_greek"})
# → Thebes, Greece (38.32, 23.32)

await resolver.resolve("Thebes", context={"period": "ancient_egyptian"})
# → Thebes, Egypt (25.70, 32.65)
```

## Data Enrichment Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Data Enrichment Pipeline                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   Raw Data (from collectors)                                        │
│   {                                                                 │
│     "name": "Battle of Marathon",                                   │
│     "date": "-490",                                                 │
│     "location": "Marathon"     ← No coordinates                     │
│   }                                                                 │
│                    │                                                 │
│                    ▼                                                 │
│   GeoResolver.resolve("Marathon")                                   │
│                    │                                                 │
│                    ▼                                                 │
│   Enriched Data                                                     │
│   {                                                                 │
│     "name": "Battle of Marathon",                                   │
│     "date": "-490",                                                 │
│     "location": "Marathon",                                         │
│     "coordinates": {           ← Added                              │
│       "latitude": 38.1536,                                          │
│       "longitude": 23.9633                                          │
│     },                                                              │
│     "location_source": "pleiades",                                  │
│     "location_confidence": 0.95,                                    │
│     "pleiades_id": "580037"                                         │
│   }                                                                 │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Edge Cases

### 1. Multiple Matches
- Use time period context to disambiguate
- Prefer Pleiades for ancient, Wikidata for modern

### 2. Name Variations
- Build name variant index from Pleiades
- Support transliteration (Greek, Latin, Arabic)

### 3. No Coordinates Found
- Flag for manual review
- Use region centroid with low confidence
- Generate GeoHack link for research

### 4. Moving Locations
- Some locations changed over time (rivers, coastlines)
- Store multiple temporal coordinates if available

## Quality Metrics

Track resolution quality:
- Total locations processed
- Resolution success rate per source
- Average confidence score
- Manual review queue size

## Future Improvements

1. **Machine Learning**: Train model on successful resolutions
2. **User Feedback**: Allow corrections, improve over time
3. **Historical Maps**: Overlay historical maps for verification
4. **Temporal Awareness**: Adjust coordinates for historical geography
