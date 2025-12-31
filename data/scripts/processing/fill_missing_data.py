#!/usr/bin/env python3
"""Fill missing dates and locations using GPT-5-nano."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import os
import re
from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import RealDictCursor
from openai import OpenAI

client = OpenAI()

def get_db():
    return psycopg2.connect('postgresql://chaldeas:chaldeas_dev@localhost:5432/chaldeas')

def extract_info(title, desc):
    prompt = f'''Give ONE year number and ONE location for this historical topic.
Negative for BCE. Just numbers and place name.

Title: {title}
Text: {desc[:600]}

Format exactly like:
YEAR: -490
LOCATION: Greece'''

    try:
        resp = client.chat.completions.create(
            model='gpt-5-nano',
            messages=[{'role': 'user', 'content': prompt}]
        )
        text = resp.choices[0].message.content.strip()

        year = 0
        location = None

        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('YEAR:'):
                try:
                    num = re.search(r'-?\d+', line)
                    if num:
                        year = int(num.group())
                except:
                    pass
            if line.startswith('LOCATION:'):
                location = line.replace('LOCATION:', '').strip()

        return year, location
    except Exception as e:
        print(f'  Error: {e}', flush=True)
        return 0, None

def find_loc_id(conn, name):
    if not name:
        return None
    cur = conn.cursor()
    cur.execute("SELECT id FROM locations WHERE LOWER(name) LIKE %s LIMIT 1", (f'%{name.lower()}%',))
    r = cur.fetchone()
    return r[0] if r else None

def main():
    print('=' * 50, flush=True)
    print('Fill Missing Data', flush=True)
    print('=' * 50, flush=True)

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    print('DB connected', flush=True)

    cur.execute('''
        SELECT id, title, description FROM events
        WHERE date_start = 0 AND description IS NOT NULL
        LIMIT 200
    ''')
    events = cur.fetchall()
    print(f'Events: {len(events)}', flush=True)

    for i, e in enumerate(events):
        year, loc = extract_info(e['title'], e['description'] or '')

        if year != 0:
            loc_id = find_loc_id(conn, loc) if loc else None

            if loc_id:
                cur.execute('UPDATE events SET date_start=%s, primary_location_id=%s WHERE id=%s',
                           (year, loc_id, e['id']))
            else:
                cur.execute('UPDATE events SET date_start=%s WHERE id=%s', (year, e['id']))

            conn.commit()
            print(f'[{i+1}] {e["title"][:40]} -> {year}, {loc}', flush=True)

    print('Done!', flush=True)
    conn.close()

if __name__ == '__main__':
    main()
