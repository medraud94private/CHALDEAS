"""
Migrate checkpoint from V3 (mentions in entities) to V4 (mentions in separate JSONL)

This script:
1. Reads existing phase1_checkpoint.json (with embedded mentions)
2. Extracts all mentions to mentions.jsonl (append-only format)
3. Creates new lightweight checkpoint (entities without mentions)

Usage:
    python migrate_checkpoint_v4.py
"""
import json
import sys
import io
from pathlib import Path
from datetime import datetime

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass

DATA_DIR = Path(__file__).parent.parent / "data"


def migrate():
    checkpoint_file = DATA_DIR / "phase1_checkpoint.json"
    mentions_file = DATA_DIR / "mentions.jsonl"
    new_checkpoint_file = DATA_DIR / "phase1_checkpoint_v4.json"

    if not checkpoint_file.exists():
        print(f"ERROR: Checkpoint file not found: {checkpoint_file}")
        return False

    print(f"Loading checkpoint: {checkpoint_file}")
    print(f"File size: {checkpoint_file.stat().st_size / 1024 / 1024:.1f} MB")

    # Load existing checkpoint
    with open(checkpoint_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    entities = data.get("registry", {}).get("entities", [])
    processed_files = data.get("processed_files", [])

    print(f"Entities: {len(entities):,}")
    print(f"Processed files: {len(processed_files):,}")

    # Extract mentions and create lightweight entities
    total_mentions = 0
    lightweight_entities = []

    print(f"\nExtracting mentions to: {mentions_file}")

    with open(mentions_file, 'w', encoding='utf-8') as mf:
        for i, entity in enumerate(entities):
            entity_key = entity.get("key", "")
            mentions = entity.get("mentions", [])

            # Write each mention as a separate JSONL line
            for mention in mentions:
                mention_record = {
                    "entity_key": entity_key,
                    "source_path": mention.get("source_path", ""),
                    "start": mention.get("start", 0),
                    "end": mention.get("end", 0),
                    "chunk_start": mention.get("chunk_start", 0),
                    "chunk_end": mention.get("chunk_end", 0)
                }
                mf.write(json.dumps(mention_record, ensure_ascii=False) + '\n')
                total_mentions += 1

            # Create lightweight entity (without mentions)
            lightweight_entity = {
                "key": entity_key,
                "text": entity.get("text", ""),
                "normalized": entity.get("normalized", ""),
                "entity_type": entity.get("entity_type", ""),
                "sample_text": entity.get("sample_text", ""),
                "mention_count": entity.get("mention_count", len(mentions)),
                "first_seen": entity.get("first_seen", "")
            }
            lightweight_entities.append(lightweight_entity)

            if (i + 1) % 100000 == 0:
                print(f"  Processed {i + 1:,} entities, {total_mentions:,} mentions...")

    print(f"Total mentions extracted: {total_mentions:,}")
    print(f"Mentions file size: {mentions_file.stat().st_size / 1024 / 1024:.1f} MB")

    # Create new lightweight checkpoint
    new_data = {
        "version": 4,
        "migrated_from": 3,
        "migrated_at": datetime.now().isoformat(),
        "timestamp": data.get("timestamp", datetime.now().isoformat()),
        "processed_files_count": len(processed_files),
        "processed_files": processed_files,
        "exported_entities": data.get("exported_entities", []),
        "registry": {
            "entities": lightweight_entities,
            "next_id": data.get("registry", {}).get("next_id", 1),
            "unique_count": len(lightweight_entities),
            "total_mentions": total_mentions
        }
    }

    print(f"\nSaving new checkpoint: {new_checkpoint_file}")
    with open(new_checkpoint_file, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)

    print(f"New checkpoint size: {new_checkpoint_file.stat().st_size / 1024 / 1024:.1f} MB")

    # Summary
    print("\n" + "=" * 60)
    print("Migration Complete!")
    print("=" * 60)
    print(f"Old checkpoint: {checkpoint_file.stat().st_size / 1024 / 1024:.1f} MB")
    print(f"New checkpoint: {new_checkpoint_file.stat().st_size / 1024 / 1024:.1f} MB")
    print(f"Mentions file:  {mentions_file.stat().st_size / 1024 / 1024:.1f} MB")
    print()
    print("Next steps:")
    print("  1. Verify the migration looks correct")
    print("  2. Rename files:")
    print(f"     mv {checkpoint_file} {checkpoint_file}.bak")
    print(f"     mv {new_checkpoint_file} {checkpoint_file}")
    print("  3. Restart Phase 1 with updated checkpoint.py")

    return True


if __name__ == "__main__":
    migrate()
