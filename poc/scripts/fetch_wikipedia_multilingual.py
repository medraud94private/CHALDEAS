"""
Fetch multilingual Wikipedia descriptions for persons, events, and locations.

Uses Wikidata IDs to get descriptions in ko, ja, en from Wikipedia.
Updates the database with:
- biography_ko, biography_ja for persons
- description_ko, description_ja for events
- description_ko, description_ja for locations
- source tracking fields (biography_source, description_source, etc.)

Usage:
    python poc/scripts/fetch_wikipedia_multilingual.py --entity-type persons --limit 100
    python poc/scripts/fetch_wikipedia_multilingual.py --entity-type events --limit 100
    python poc/scripts/fetch_wikipedia_multilingual.py --entity-type locations --limit 100
"""

import argparse
import time
import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
import sys

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://chaldeas:chaldeas_dev@localhost:5432/chaldeas')

# Wikidata API endpoints
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIPEDIA_API_TEMPLATE = "https://{lang}.wikipedia.org/w/api.php"

LANGUAGES = ['en', 'ko', 'ja']

# Rate limiting - Wikidata recommends max 50 req/sec, we use 1 req/sec to be safe
REQUEST_DELAY = 1.0  # seconds between requests

# User-Agent header (required by Wikimedia APIs)
HEADERS = {
    'User-Agent': 'CHALDEAS/0.7 (https://www.chaldeas.site; chaldeas.site@gmail.com)'
}


def get_wikidata_sitelinks(wikidata_id: str) -> dict:
    """
    Get Wikipedia sitelinks for a Wikidata entity.
    Returns dict like {'enwiki': 'Article_Title', 'kowiki': '기사_제목', 'jawiki': '記事のタイトル'}
    """
    params = {
        'action': 'wbgetentities',
        'ids': wikidata_id,
        'props': 'sitelinks',
        'format': 'json'
    }

    try:
        response = requests.get(WIKIDATA_API, params=params, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()

        entity = data.get('entities', {}).get(wikidata_id, {})
        sitelinks = entity.get('sitelinks', {})

        result = {}
        for lang in LANGUAGES:
            wiki_key = f"{lang}wiki"
            if wiki_key in sitelinks:
                result[wiki_key] = sitelinks[wiki_key].get('title', '')

        return result
    except Exception as e:
        print(f"  Error fetching sitelinks for {wikidata_id}: {e}")
        return {}


def get_wikipedia_extract(lang: str, title: str) -> tuple[str, str]:
    """
    Get Wikipedia extract (description) for an article.
    Returns (extract_text, full_url).
    """
    api_url = WIKIPEDIA_API_TEMPLATE.format(lang=lang)

    params = {
        'action': 'query',
        'titles': title,
        'prop': 'extracts|info',
        'exintro': True,
        'explaintext': True,
        'exsectionformat': 'plain',
        'inprop': 'url',
        'format': 'json'
    }

    try:
        response = requests.get(api_url, params=params, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()

        pages = data.get('query', {}).get('pages', {})
        for page_id, page in pages.items():
            if page_id == '-1':
                continue
            extract = page.get('extract', '')
            url = page.get('fullurl', f"https://{lang}.wikipedia.org/wiki/{title}")
            return extract, url

        return '', ''
    except Exception as e:
        print(f"  Error fetching Wikipedia extract for {lang}:{title}: {e}")
        return '', ''


def fetch_multilingual_descriptions(wikidata_id: str) -> dict:
    """
    Fetch descriptions in all target languages for a Wikidata entity.
    Returns dict with keys like 'en', 'ko', 'ja' containing (description, url) tuples.
    """
    result = {}

    # Get sitelinks from Wikidata
    sitelinks = get_wikidata_sitelinks(wikidata_id)

    if not sitelinks:
        return result

    # Fetch extract from each available Wikipedia
    for lang in LANGUAGES:
        wiki_key = f"{lang}wiki"
        if wiki_key in sitelinks:
            title = sitelinks[wiki_key]
            extract, url = get_wikipedia_extract(lang, title)
            if extract:
                result[lang] = {
                    'text': extract[:5000],  # Limit to 5000 chars
                    'url': url,
                    'source': f'wikipedia_{lang}'
                }
            time.sleep(REQUEST_DELAY)

    return result


def update_persons(session, limit: int = 100, offset: int = 0):
    """Update persons with multilingual biographies."""
    print(f"\n=== Updating Persons (limit={limit}, offset={offset}) ===\n")

    # Get persons with wikidata_id but missing translations
    query = text("""
        SELECT id, name, wikidata_id
        FROM persons
        WHERE wikidata_id IS NOT NULL
          AND wikidata_id != ''
          AND (biography_ja IS NULL OR biography_ko IS NULL)
        ORDER BY connection_count DESC NULLS LAST, id
        LIMIT :limit OFFSET :offset
    """)

    result = session.execute(query, {'limit': limit, 'offset': offset})
    persons = result.fetchall()

    print(f"Found {len(persons)} persons to update")

    updated = 0
    for person in persons:
        person_id, name, wikidata_id = person
        print(f"\n[{person_id}] {name} ({wikidata_id})")

        descriptions = fetch_multilingual_descriptions(wikidata_id)

        if not descriptions:
            print("  No descriptions found")
            continue

        # Build update query
        updates = []
        params = {'id': person_id}

        for lang, data in descriptions.items():
            if lang == 'ko':
                updates.append("biography_ko = :bio_ko")
                params['bio_ko'] = data['text']
            elif lang == 'ja':
                updates.append("biography_ja = :bio_ja")
                params['bio_ja'] = data['text']
            elif lang == 'en':
                # Update English biography only if empty
                updates.append("biography = COALESCE(biography, :bio_en)")
                params['bio_en'] = data['text']

        # Set source info from first available
        first_lang = list(descriptions.keys())[0]
        first_data = descriptions[first_lang]
        updates.append("biography_source = :source")
        updates.append("biography_source_url = :source_url")
        params['source'] = first_data['source']
        params['source_url'] = first_data['url']

        if updates:
            update_query = text(f"""
                UPDATE persons
                SET {', '.join(updates)}
                WHERE id = :id
            """)
            session.execute(update_query, params)
            session.commit()
            updated += 1
            print(f"  Updated with {list(descriptions.keys())} descriptions")

    print(f"\n=== Updated {updated} persons ===")
    return updated


def update_events(session, limit: int = 100, offset: int = 0):
    """Update events with multilingual descriptions."""
    print(f"\n=== Updating Events (limit={limit}, offset={offset}) ===\n")

    query = text("""
        SELECT id, title, wikidata_id
        FROM events
        WHERE wikidata_id IS NOT NULL
          AND wikidata_id != ''
          AND (description_ja IS NULL OR description_ko IS NULL)
        ORDER BY connection_count DESC NULLS LAST, id
        LIMIT :limit OFFSET :offset
    """)

    result = session.execute(query, {'limit': limit, 'offset': offset})
    events = result.fetchall()

    print(f"Found {len(events)} events to update")

    updated = 0
    for event in events:
        event_id, title, wikidata_id = event
        print(f"\n[{event_id}] {title} ({wikidata_id})")

        descriptions = fetch_multilingual_descriptions(wikidata_id)

        if not descriptions:
            print("  No descriptions found")
            continue

        updates = []
        params = {'id': event_id}

        for lang, data in descriptions.items():
            if lang == 'ko':
                updates.append("description_ko = :desc_ko")
                params['desc_ko'] = data['text']
            elif lang == 'ja':
                updates.append("description_ja = :desc_ja")
                params['desc_ja'] = data['text']
            elif lang == 'en':
                updates.append("description = COALESCE(description, :desc_en)")
                params['desc_en'] = data['text']

        first_lang = list(descriptions.keys())[0]
        first_data = descriptions[first_lang]
        updates.append("description_source = :source")
        updates.append("description_source_url = :source_url")
        params['source'] = first_data['source']
        params['source_url'] = first_data['url']

        if updates:
            update_query = text(f"""
                UPDATE events
                SET {', '.join(updates)}
                WHERE id = :id
            """)
            session.execute(update_query, params)
            session.commit()
            updated += 1
            print(f"  Updated with {list(descriptions.keys())} descriptions")

    print(f"\n=== Updated {updated} events ===")
    return updated


def update_locations(session, limit: int = 100, offset: int = 0):
    """Update locations with multilingual descriptions."""
    print(f"\n=== Updating Locations (limit={limit}, offset={offset}) ===\n")

    query = text("""
        SELECT id, name, wikidata_id
        FROM locations
        WHERE wikidata_id IS NOT NULL
          AND wikidata_id != ''
          AND (description_ja IS NULL OR description_ko IS NULL)
        ORDER BY connection_count DESC NULLS LAST, id
        LIMIT :limit OFFSET :offset
    """)

    result = session.execute(query, {'limit': limit, 'offset': offset})
    locations = result.fetchall()

    print(f"Found {len(locations)} locations to update")

    updated = 0
    for location in locations:
        loc_id, name, wikidata_id = location
        print(f"\n[{loc_id}] {name} ({wikidata_id})")

        descriptions = fetch_multilingual_descriptions(wikidata_id)

        if not descriptions:
            print("  No descriptions found")
            continue

        updates = []
        params = {'id': loc_id}

        for lang, data in descriptions.items():
            if lang == 'ko':
                updates.append("description_ko = :desc_ko")
                params['desc_ko'] = data['text']
            elif lang == 'ja':
                updates.append("description_ja = :desc_ja")
                params['desc_ja'] = data['text']
            elif lang == 'en':
                updates.append("description = COALESCE(description, :desc_en)")
                params['desc_en'] = data['text']

        first_lang = list(descriptions.keys())[0]
        first_data = descriptions[first_lang]
        updates.append("description_source = :source")
        updates.append("description_source_url = :source_url")
        params['source'] = first_data['source']
        params['source_url'] = first_data['url']

        if updates:
            update_query = text(f"""
                UPDATE locations
                SET {', '.join(updates)}
                WHERE id = :id
            """)
            session.execute(update_query, params)
            session.commit()
            updated += 1
            print(f"  Updated with {list(descriptions.keys())} descriptions")

    print(f"\n=== Updated {updated} locations ===")
    return updated


def mark_existing_sources(session, entity_type: str):
    """Mark existing Wikipedia data with source information."""
    print(f"\n=== Marking existing sources for {entity_type} ===\n")

    if entity_type == 'persons':
        query = text("""
            UPDATE persons
            SET biography_source = 'wikipedia_en',
                biography_source_url = wikipedia_url
            WHERE biography IS NOT NULL
              AND biography != ''
              AND wikipedia_url IS NOT NULL
              AND biography_source IS NULL
        """)
    elif entity_type == 'events':
        query = text("""
            UPDATE events
            SET description_source = 'wikipedia_en',
                description_source_url = wikipedia_url
            WHERE description IS NOT NULL
              AND description != ''
              AND wikipedia_url IS NOT NULL
              AND description_source IS NULL
        """)
    elif entity_type == 'locations':
        query = text("""
            UPDATE locations
            SET description_source = 'wikipedia_en',
                description_source_url = wikipedia_url
            WHERE description IS NOT NULL
              AND description != ''
              AND wikipedia_url IS NOT NULL
              AND description_source IS NULL
        """)
    else:
        print(f"Unknown entity type: {entity_type}")
        return 0

    result = session.execute(query)
    session.commit()
    count = result.rowcount
    print(f"Marked {count} existing records with Wikipedia source")
    return count


def main():
    parser = argparse.ArgumentParser(description='Fetch multilingual Wikipedia descriptions')
    parser.add_argument('--entity-type', choices=['persons', 'events', 'locations', 'all'],
                        default='all', help='Entity type to update')
    parser.add_argument('--limit', type=int, default=100, help='Number of entities to process')
    parser.add_argument('--offset', type=int, default=0, help='Offset for pagination')
    parser.add_argument('--mark-existing', action='store_true',
                        help='Mark existing Wikipedia data with source info')

    args = parser.parse_args()

    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        if args.mark_existing:
            if args.entity_type == 'all':
                for et in ['persons', 'events', 'locations']:
                    mark_existing_sources(session, et)
            else:
                mark_existing_sources(session, args.entity_type)
            return

        if args.entity_type == 'all':
            update_persons(session, args.limit, args.offset)
            update_events(session, args.limit, args.offset)
            update_locations(session, args.limit, args.offset)
        elif args.entity_type == 'persons':
            update_persons(session, args.limit, args.offset)
        elif args.entity_type == 'events':
            update_events(session, args.limit, args.offset)
        elif args.entity_type == 'locations':
            update_locations(session, args.limit, args.offset)

    finally:
        session.close()


if __name__ == '__main__':
    main()
