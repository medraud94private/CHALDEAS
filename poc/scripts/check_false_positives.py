import sys
import psycopg2

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

conn = psycopg2.connect(
    host='localhost', dbname='chaldeas', user='chaldeas',
    password='chaldeas_dev', port=5432
)
cur = conn.cursor()

print("=== Top 20 Persons by Relationship Count ===")
cur.execute("""
    SELECT p.name, COUNT(*) as cnt
    FROM person_relationships pr
    JOIN persons p ON pr.person_id = p.id
    GROUP BY p.id, p.name
    ORDER BY cnt DESC
    LIMIT 20
""")
for name, cnt in cur.fetchall():
    print(f"  {name}: {cnt:,}")

print("\n=== Suspicious Names (likely false positives) ===")
suspicious = ['Commons', 'Other', 'University', 'College', 'School', 'Church', 'Museum']
for s in suspicious:
    cur.execute("SELECT id, name FROM persons WHERE name ILIKE %s", (f"%{s}%",))
    results = cur.fetchall()
    if results:
        print(f"'{s}' matches: {len(results)}")
        for pid, name in results[:3]:
            print(f"    {pid}: {name}")
