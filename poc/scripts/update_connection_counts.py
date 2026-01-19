#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Update connection_count for all entities.

Adds and populates connection_count column to track how many relationships
each entity has. Used for filtering out orphan entities from default views.

Usage:
    python update_connection_counts.py
"""

import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import psycopg2


def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='chaldeas',
        user='chaldeas',
        password='chaldeas_dev',
        port=5432
    )


def add_columns_if_not_exist(cur):
    """Add connection_count column to entity tables if not exists."""
    tables = ['persons', 'events', 'locations']

    for table in tables:
        cur.execute(f"""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = '{table}' AND column_name = 'connection_count'
        """)
        if not cur.fetchone():
            print(f"Adding connection_count to {table}...")
            cur.execute(f"ALTER TABLE {table} ADD COLUMN connection_count INTEGER DEFAULT 0")
        else:
            print(f"{table}.connection_count already exists")


def update_person_counts(cur):
    """Update connection counts for persons."""
    print("\nUpdating persons connection_count...")

    cur.execute("""
        UPDATE persons p
        SET connection_count = COALESCE(counts.cnt, 0)
        FROM (
            SELECT person_id, SUM(cnt) as cnt FROM (
                -- person_relationships (as person_id)
                SELECT person_id, COUNT(*) as cnt FROM person_relationships GROUP BY person_id
                UNION ALL
                -- person_relationships (as related_person_id)
                SELECT related_person_id as person_id, COUNT(*) as cnt FROM person_relationships GROUP BY related_person_id
                UNION ALL
                -- event_persons
                SELECT person_id, COUNT(*) as cnt FROM event_persons GROUP BY person_id
                UNION ALL
                -- person_locations
                SELECT person_id, COUNT(*) as cnt FROM person_locations GROUP BY person_id
            ) sub
            GROUP BY person_id
        ) counts
        WHERE p.id = counts.person_id
    """)

    updated = cur.rowcount
    print(f"  Updated {updated:,} persons")

    # Check distribution
    cur.execute("SELECT connection_count, COUNT(*) FROM persons GROUP BY connection_count ORDER BY connection_count")
    dist = cur.fetchall()

    connected = sum(cnt for cc, cnt in dist if cc and cc > 0)
    orphans = sum(cnt for cc, cnt in dist if cc is None or cc == 0)

    print(f"  Connected: {connected:,}")
    print(f"  Orphans: {orphans:,}")


def update_event_counts(cur):
    """Update connection counts for events."""
    print("\nUpdating events connection_count...")

    cur.execute("""
        UPDATE events e
        SET connection_count = COALESCE(counts.cnt, 0)
        FROM (
            SELECT event_id, SUM(cnt) as cnt FROM (
                -- event_persons
                SELECT event_id, COUNT(*) as cnt FROM event_persons GROUP BY event_id
                UNION ALL
                -- event_locations
                SELECT event_id, COUNT(*) as cnt FROM event_locations GROUP BY event_id
                UNION ALL
                -- event_relationships (as from_event_id)
                SELECT from_event_id as event_id, COUNT(*) as cnt FROM event_relationships GROUP BY from_event_id
                UNION ALL
                -- event_relationships (as to_event_id)
                SELECT to_event_id as event_id, COUNT(*) as cnt FROM event_relationships GROUP BY to_event_id
            ) sub
            GROUP BY event_id
        ) counts
        WHERE e.id = counts.event_id
    """)

    updated = cur.rowcount
    print(f"  Updated {updated:,} events")

    cur.execute("SELECT COUNT(*) FROM events WHERE connection_count > 0")
    connected = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM events WHERE connection_count = 0 OR connection_count IS NULL")
    orphans = cur.fetchone()[0]

    print(f"  Connected: {connected:,}")
    print(f"  Orphans: {orphans:,}")


def update_location_counts(cur):
    """Update connection counts for locations."""
    print("\nUpdating locations connection_count...")

    cur.execute("""
        UPDATE locations l
        SET connection_count = COALESCE(counts.cnt, 0)
        FROM (
            SELECT location_id, SUM(cnt) as cnt FROM (
                -- event_locations
                SELECT location_id, COUNT(*) as cnt FROM event_locations GROUP BY location_id
                UNION ALL
                -- person_locations
                SELECT location_id, COUNT(*) as cnt FROM person_locations GROUP BY location_id
                UNION ALL
                -- location_relationships (as location_id)
                SELECT location_id, COUNT(*) as cnt FROM location_relationships GROUP BY location_id
                UNION ALL
                -- location_relationships (as related_location_id)
                SELECT related_location_id as location_id, COUNT(*) as cnt FROM location_relationships GROUP BY related_location_id
            ) sub
            GROUP BY location_id
        ) counts
        WHERE l.id = counts.location_id
    """)

    updated = cur.rowcount
    print(f"  Updated {updated:,} locations")

    cur.execute("SELECT COUNT(*) FROM locations WHERE connection_count > 0")
    connected = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM locations WHERE connection_count = 0 OR connection_count IS NULL")
    orphans = cur.fetchone()[0]

    print(f"  Connected: {connected:,}")
    print(f"  Orphans: {orphans:,}")


def create_index(cur):
    """Create index on connection_count for efficient filtering."""
    print("\nCreating indexes...")

    for table in ['persons', 'events', 'locations']:
        idx_name = f"idx_{table}_connection_count"
        cur.execute(f"""
            SELECT indexname FROM pg_indexes
            WHERE tablename = '{table}' AND indexname = '{idx_name}'
        """)
        if not cur.fetchone():
            cur.execute(f"CREATE INDEX {idx_name} ON {table}(connection_count)")
            print(f"  Created {idx_name}")
        else:
            print(f"  {idx_name} already exists")


def main():
    print("=" * 60)
    print("Update Connection Counts")
    print("=" * 60)

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        add_columns_if_not_exist(cur)
        conn.commit()

        update_person_counts(cur)
        conn.commit()

        update_event_counts(cur)
        conn.commit()

        update_location_counts(cur)
        conn.commit()

        create_index(cur)
        conn.commit()

        print("\n" + "=" * 60)
        print("Done!")
        print("=" * 60)

    finally:
        conn.close()


if __name__ == '__main__':
    main()
