"""
Import source documents and text mentions from batch NER data.

This script:
1. Adds 'content' column to sources table (for full text)
2. Imports source documents from batch input files
3. Links entities to sources via text_mentions table
"""

import os
import sys
import json
import re
from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Database connection
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://chaldeas:chaldeas_dev@localhost:5432/chaldeas"
)

# Data paths
BATCH_DATA_DIR = Path("C:/Projects/Chaldeas/poc/data/integrated_ner_full")

def get_archive_type(custom_id: str) -> str:
    """Extract archive type from custom_id."""
    if custom_id.startswith("gutenberg_"):
        return "gutenberg"
    elif custom_id.startswith("british_library_"):
        return "british_library"
    elif custom_id.startswith("perseus_"):
        return "perseus"
    elif custom_id.startswith("archive_"):
        return "internet_archive"
    else:
        return "unknown"

def extract_text_from_message(message_content: str) -> str:
    """Extract the actual document text from the prompt."""
    # Find the TEXT: marker and extract everything after it
    match = re.search(r'TEXT:\s*\n(.+)', message_content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return message_content

def parse_document_title(text: str, custom_id: str) -> tuple[str, str | None, int | None]:
    """Try to extract title, author, and year from text."""
    title = custom_id  # fallback
    author = None
    year = None

    # Try to find Project Gutenberg metadata
    title_match = re.search(r'Title:\s*(.+?)(?:\n|$)', text)
    if title_match:
        title = title_match.group(1).strip()

    author_match = re.search(r'Author:\s*(.+?)(?:\n|$)', text)
    if author_match:
        author = author_match.group(1).strip()

    # Try to find release date/year
    year_match = re.search(r'(?:Release date|Published).*?(\d{4})', text)
    if year_match:
        year = int(year_match.group(1))

    return title, author, year


def main():
    print("=" * 60)
    print("CHALDEAS Source Documents & Mentions Import")
    print("=" * 60)
    print(f"Database: {DATABASE_URL.split('@')[1]}")
    print(f"Started: {datetime.now().isoformat()}")
    print()

    # Create engine and session
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Step 1: Add content column if not exists
        print("[1/4] Checking/adding content column to sources table...")
        try:
            session.execute(text("""
                ALTER TABLE sources ADD COLUMN IF NOT EXISTS content TEXT
            """))
            session.commit()
            print("  -> content column ready")
        except Exception as e:
            session.rollback()
            print(f"  -> Column may already exist: {e}")

        # Step 2: Find all batch files
        input_files = sorted(BATCH_DATA_DIR.glob("minimal_batch_*[0-9].jsonl"))
        output_files = sorted(BATCH_DATA_DIR.glob("minimal_batch_*_output.jsonl"))

        print(f"\n[2/4] Found {len(input_files)} input files, {len(output_files)} output files")

        # Step 3: Import sources from input files
        print("\n[3/4] Importing source documents...")
        source_id_map = {}  # custom_id -> source_id
        total_sources = 0

        for input_file in input_files:
            file_name = input_file.name
            print(f"\n  Processing {file_name}...")

            with open(input_file, 'r', encoding='utf-8') as f:
                batch_count = 0
                for line_num, line in enumerate(f, 1):
                    try:
                        data = json.loads(line)
                        custom_id = data.get('custom_id', '')

                        # Skip if already processed
                        if custom_id in source_id_map:
                            continue

                        # Extract text from message
                        messages = data.get('body', {}).get('messages', [])
                        user_message = next((m for m in messages if m.get('role') == 'user'), None)
                        if not user_message:
                            continue

                        full_text = extract_text_from_message(user_message.get('content', ''))
                        archive_type = get_archive_type(custom_id)
                        title, author, year = parse_document_title(full_text, custom_id)

                        # Insert source
                        result = session.execute(text("""
                            INSERT INTO sources (
                                name, type, document_id, archive_type,
                                title, author, original_year, content,
                                created_at, updated_at
                            ) VALUES (
                                :name, 'document', :document_id, :archive_type,
                                :title, :author, :year, :content,
                                NOW(), NOW()
                            )
                            ON CONFLICT DO NOTHING
                            RETURNING id
                        """), {
                            "name": custom_id,
                            "document_id": custom_id,
                            "archive_type": archive_type,
                            "title": title[:500] if title else custom_id,
                            "author": author[:255] if author else None,
                            "year": year,
                            "content": full_text
                        })

                        row = result.fetchone()
                        if row:
                            source_id_map[custom_id] = row[0]
                            batch_count += 1
                            total_sources += 1

                        if batch_count % 500 == 0:
                            session.commit()
                            print(f"    {batch_count} sources from this file...")

                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        session.rollback()
                        print(f"    Error at line {line_num}: {e}")
                        continue

                session.commit()
                print(f"    -> {batch_count} sources imported from {file_name}")

        print(f"\n  Total sources imported: {total_sources}")

        # Load existing source IDs for documents we didn't just insert
        print("\n  Loading existing source IDs...")
        result = session.execute(text("SELECT document_id, id FROM sources WHERE document_id IS NOT NULL"))
        for row in result:
            if row[0] not in source_id_map:
                source_id_map[row[0]] = row[1]
        print(f"  -> {len(source_id_map)} total source mappings")

        # Step 4: Import text_mentions from output files
        print("\n[4/4] Importing text mentions (entity-source links)...")

        # Build entity name -> id maps for each entity type
        print("  Building entity lookup maps...")
        entity_maps = {}

        for entity_type, table_name, name_col in [
            ('person', 'persons', 'name'),
            ('location', 'locations', 'name'),
            ('event', 'events', 'title'),
            ('polity', 'polities', 'name'),
            ('period', 'periods', 'name'),
        ]:
            result = session.execute(text(f"SELECT {name_col}, id FROM {table_name}"))
            entity_maps[entity_type] = {row[0].lower(): row[1] for row in result if row[0]}
            print(f"    {entity_type}: {len(entity_maps[entity_type])} entries")

        total_mentions = 0

        for output_file in output_files:
            file_name = output_file.name
            print(f"\n  Processing {file_name}...")

            with open(output_file, 'r', encoding='utf-8') as f:
                batch_count = 0

                for line_num, line in enumerate(f, 1):
                    try:
                        data = json.loads(line)
                        custom_id = data.get('custom_id', '')
                        source_id = source_id_map.get(custom_id)

                        if not source_id:
                            continue

                        # Get extraction result
                        response = data.get('response', {})
                        if response.get('status_code') != 200:
                            continue

                        body = response.get('body', {})
                        choices = body.get('choices', [])
                        if not choices:
                            continue

                        content = choices[0].get('message', {}).get('content', '')
                        try:
                            entities = json.loads(content)
                        except json.JSONDecodeError:
                            continue

                        extraction_model = body.get('model', 'gpt-5-nano')
                        request_id = response.get('request_id', '')

                        # Process each entity type
                        mentions_to_insert = []

                        for entity_type, key in [
                            ('person', 'persons'),
                            ('location', 'locations'),
                            ('event', 'events'),
                            ('polity', 'polities'),
                            ('period', 'periods'),
                        ]:
                            items = entities.get(key, [])
                            entity_map = entity_maps.get(entity_type, {})

                            for item in items:
                                name = item.get('name') or item.get('title', '')
                                if not name:
                                    continue

                                entity_id = entity_map.get(name.lower())
                                if not entity_id:
                                    continue

                                confidence = item.get('confidence', 1.0)

                                mentions_to_insert.append({
                                    "entity_type": entity_type,
                                    "entity_id": entity_id,
                                    "source_id": source_id,
                                    "mention_text": name[:500],
                                    "confidence": confidence,
                                    "extraction_model": extraction_model,
                                    "request_id": request_id,
                                })

                        # Batch insert mentions
                        if mentions_to_insert:
                            for mention in mentions_to_insert:
                                session.execute(text("""
                                    INSERT INTO text_mentions (
                                        entity_type, entity_id, source_id,
                                        mention_text, confidence,
                                        extraction_model, request_id, extracted_at
                                    ) VALUES (
                                        :entity_type, :entity_id, :source_id,
                                        :mention_text, :confidence,
                                        :extraction_model, :request_id, NOW()
                                    )
                                    ON CONFLICT DO NOTHING
                                """), mention)

                            batch_count += len(mentions_to_insert)
                            total_mentions += len(mentions_to_insert)

                        if line_num % 500 == 0:
                            session.commit()
                            print(f"    {line_num} documents processed, {batch_count} mentions...")

                    except Exception as e:
                        session.rollback()
                        if line_num % 1000 == 0:
                            print(f"    Error at line {line_num}: {e}")
                        continue

                session.commit()
                print(f"    -> {batch_count} mentions from {file_name}")

        print(f"\n  Total mentions imported: {total_mentions}")

        # Final stats
        print("\n" + "=" * 60)
        print("IMPORT COMPLETE")

        # Get final counts
        sources_count = session.execute(text("SELECT COUNT(*) FROM sources")).scalar()
        mentions_count = session.execute(text("SELECT COUNT(*) FROM text_mentions")).scalar()

        # Get DB size
        db_size = session.execute(text("""
            SELECT pg_size_pretty(pg_database_size('chaldeas'))
        """)).scalar()

        print(f"Sources: {sources_count:,}")
        print(f"Text Mentions: {mentions_count:,}")
        print(f"Database Size: {db_size}")
        print(f"Finished: {datetime.now().isoformat()}")
        print("=" * 60)

    except Exception as e:
        session.rollback()
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
