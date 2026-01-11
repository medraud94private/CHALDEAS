#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Person Story 생성 POC (Phase 3-4 테스트)

DB에서 인물 관련 데이터를 수집하고,
로컬 LLM(gemma2)으로 Person Story(역사의 고리)를 생성합니다.

사용법:
    python generate_person_story.py --person "Alexander the Great"
    python generate_person_story.py --person-id 22
"""

import sys
import json
import argparse
import requests
from pathlib import Path
from datetime import datetime
from decimal import Decimal


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'backend'))

import psycopg2
from dotenv import load_dotenv
load_dotenv()


OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "gpt-5.1-chat-latest"  # OpenAI (기본)
LOCAL_MODEL = "gemma2:9b-instruct-q4_0"  # 로컬 옵션


def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='chaldeas',
        user='chaldeas',
        password='chaldeas_dev',
        port=5432
    )


def fetch_person_data(person_id: int = None, person_name: str = None) -> dict:
    """DB에서 인물 관련 모든 데이터 수집"""
    conn = get_db_connection()
    cur = conn.cursor()

    # 1. 인물 기본 정보
    if person_id:
        cur.execute('''
            SELECT id, name, name_ko, birth_year, death_year, role, certainty, biography
            FROM persons WHERE id = %s
        ''', (person_id,))
    else:
        cur.execute('''
            SELECT id, name, name_ko, birth_year, death_year, role, certainty, biography
            FROM persons WHERE LOWER(name) LIKE %s
            ORDER BY mention_count DESC NULLS LAST
            LIMIT 1
        ''', (f'%{person_name.lower()}%',))

    person = cur.fetchone()
    if not person:
        conn.close()
        return None

    person_data = {
        'id': person[0],
        'name': person[1],
        'name_ko': person[2],
        'birth_year': person[3],
        'death_year': person[4],
        'role': person[5],
        'certainty': person[6],
        'description': person[7],
        'events': {
            'direct_period': [],    # 직접 언급 + 시대 맞음 (핵심)
            'direct_other': [],     # 직접 언급 + 시대 안맞음 (후대 기록/아티클)
            'context_only': [],     # 언급 없지만 시대/공간 맞음 (동시대 배경)
        },
        'locations': [],
        'related_persons': [],
    }

    # 검색 키워드 추출
    name_parts = person_data['name'].lower().split()
    search_name = name_parts[0] if name_parts else ''  # "Alexander the Great" -> "alexander"

    # 생애 기간 정의
    birth = person_data['birth_year'] or -500
    death = person_data['death_year'] or 0
    period_start = birth - 20
    period_end = death + 30  # 사후 영향 포함

    # === Category 1: 직접 언급 + 시대 맞음 (핵심 이벤트) ===
    cur.execute('''
        SELECT e.id, e.title, e.date_start, e.date_end,
               l.name as location_name, l.latitude, l.longitude,
               e.description
        FROM events e
        LEFT JOIN locations l ON e.primary_location_id = l.id
        WHERE (LOWER(e.title) LIKE %s OR LOWER(e.description) LIKE %s)
          AND e.date_start BETWEEN %s AND %s
        ORDER BY e.date_start
        LIMIT 50
    ''', (f'%{search_name}%', f'%{search_name}%', period_start, period_end))

    direct_period_ids = set()
    for row in cur.fetchall():
        direct_period_ids.add(row[0])
        person_data['events']['direct_period'].append({
            'id': row[0],
            'title': row[1],
            'date_start': row[2],
            'date_end': row[3],
            'location_name': row[4],
            'latitude': row[5],
            'longitude': row[6],
            'description': (row[7] or '')[:200],
        })

    # === Category 2: 직접 언급 + 시대 안맞음 (후대 기록/아티클) ===
    cur.execute('''
        SELECT e.id, e.title, e.date_start, e.date_end,
               l.name as location_name, l.latitude, l.longitude,
               e.description
        FROM events e
        LEFT JOIN locations l ON e.primary_location_id = l.id
        WHERE (LOWER(e.title) LIKE %s OR LOWER(e.description) LIKE %s)
          AND (e.date_start < %s OR e.date_start > %s)
        ORDER BY e.date_start
        LIMIT 30
    ''', (f'%{search_name}%', f'%{search_name}%', period_start, period_end))

    for row in cur.fetchall():
        if row[0] not in direct_period_ids:
            person_data['events']['direct_other'].append({
                'id': row[0],
                'title': row[1],
                'date_start': row[2],
                'date_end': row[3],
                'location_name': row[4],
                'latitude': row[5],
                'longitude': row[6],
                'description': (row[7] or '')[:200],
            })

    # === Category 3: 언급 없지만 시대/공간 맞음 (동시대 배경) ===
    # 마케도니아/페르시아 관련 키워드 + 시대 맞음
    context_keywords = ['macedon', 'persia', 'darius', 'philip', 'ptolem', 'seleuc', 'hellenist']
    all_direct_ids = direct_period_ids | {e['id'] for e in person_data['events']['direct_other']}

    for keyword in context_keywords:
        cur.execute('''
            SELECT e.id, e.title, e.date_start, e.date_end,
                   l.name as location_name, l.latitude, l.longitude,
                   e.description
            FROM events e
            LEFT JOIN locations l ON e.primary_location_id = l.id
            WHERE (LOWER(e.title) LIKE %s OR LOWER(e.description) LIKE %s)
              AND e.date_start BETWEEN %s AND %s
              AND NOT (LOWER(e.description) LIKE %s)
            ORDER BY e.date_start
            LIMIT 20
        ''', (f'%{keyword}%', f'%{keyword}%', period_start, period_end, f'%{search_name}%'))

        for row in cur.fetchall():
            if row[0] not in all_direct_ids:
                all_direct_ids.add(row[0])
                person_data['events']['context_only'].append({
                    'id': row[0],
                    'title': row[1],
                    'date_start': row[2],
                    'date_end': row[3],
                    'location_name': row[4],
                    'latitude': row[5],
                    'longitude': row[6],
                    'description': (row[7] or '')[:200],
                })

    # 각 카테고리 정렬
    for cat in person_data['events']:
        person_data['events'][cat].sort(key=lambda x: x['date_start'] or 0)

    conn.close()
    return person_data


def generate_person_story(person_data: dict, model: str = DEFAULT_MODEL, use_local: bool = False) -> dict:
    """LLM으로 Person Story 생성"""
    import os
    from openai import OpenAI

    events = person_data['events']

    # 최우선 이벤트 (직접 언급 + 시대 맞음)
    primary_events_text = ""
    for e in events['direct_period'][:20]:
        year_str = f"{abs(e['date_start'])} {'BCE' if e['date_start'] < 0 else 'CE'}" if e['date_start'] else "Unknown"
        loc_str = f" at {e['location_name']}" if e['location_name'] else ""
        primary_events_text += f"- [{e['id']}] {e['title']} ({year_str}){loc_str}\n"

    # 참조 이벤트 (동시대 맥락)
    context_events_text = ""
    for e in events['context_only'][:10]:
        year_str = f"{abs(e['date_start'])} {'BCE' if e['date_start'] < 0 else 'CE'}" if e['date_start'] else "Unknown"
        context_events_text += f"- [{e['id']}] {e['title']} ({year_str})\n"

    prompt = f"""You are a historian creating a "Person Story" - a narrative chain of key life events for a historical figure.

## Person Information
- Name: {person_data['name']}
- Birth: {abs(person_data['birth_year']) if person_data['birth_year'] else 'Unknown'} {'BCE' if person_data['birth_year'] and person_data['birth_year'] < 0 else 'CE'}
- Death: {abs(person_data['death_year']) if person_data['death_year'] else 'Unknown'} {'BCE' if person_data['death_year'] and person_data['death_year'] < 0 else 'CE'}
- Role: {person_data['role'] or 'Unknown'}

## PRIMARY EVENTS (directly involving this person)
{primary_events_text}

## CONTEXT EVENTS (same era, related figures/places)
{context_events_text}

## Your Task
Create a Person Story with these elements:

1. **Summary**: 2-3 sentence overview of this person's historical significance
2. **Life Phases**: Divide their life into 3-5 distinct phases
3. **Key Events**: Select 5-10 most important events from the list above, explain why each matters
4. **Connections**: Note any related historical figures or places
5. **Legacy**: Their lasting impact on history

Respond in JSON format:
{{
  "summary": "...",
  "life_phases": [
    {{"name": "Early Life", "years": "356-336 BCE", "description": "..."}},
    ...
  ],
  "key_events": [
    {{"event_id": 123, "title": "...", "year": -334, "significance": "..."}},
    ...
  ],
  "connections": [
    {{"name": "...", "relationship": "...", "significance": "..."}},
    ...
  ],
  "legacy": "..."
}}
"""

    total_events = len(events['direct_period']) + len(events['context_only'])
    print(f"\n[LLM] Generating Person Story with {model}...")
    print(f"[LLM] Events provided: {total_events} (primary: {len(events['direct_period'])}, context: {len(events['context_only'])})")

    try:
        if use_local:
            # Ollama (로컬)
            resp = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 2000,
                    }
                },
                timeout=300
            )

            if resp.status_code != 200:
                return {"error": f"Ollama error: {resp.status_code}"}

            content = resp.json().get('response', '')
        else:
            # OpenAI
            client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a historian. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=2000
            )
            content = response.choices[0].message.content

            # 토큰 사용량 출력
            usage = response.usage
            print(f"[LLM] Tokens: {usage.prompt_tokens} in, {usage.completion_tokens} out")

        # JSON 추출
        import re
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                story = json.loads(json_match.group())
                story['_meta'] = {
                    'model': model,
                    'primary_events': len(events['direct_period']),
                    'context_events': len(events['context_only']),
                    'generated_at': datetime.now().isoformat(),
                }
                return story
            except json.JSONDecodeError as e:
                return {"error": f"JSON parse error: {e}", "raw": content[:500]}
        else:
            return {"error": "No JSON found", "raw": content[:500]}

    except Exception as e:
        return {"error": str(e)}


def main():
    parser = argparse.ArgumentParser(description='Person Story 생성')
    parser.add_argument('--person', type=str, help='인물 이름')
    parser.add_argument('--person-id', type=int, help='인물 ID')
    parser.add_argument('--model', type=str, default=DEFAULT_MODEL, help='LLM 모델')
    parser.add_argument('--local', action='store_true', help='로컬 LLM 사용 (Ollama)')
    parser.add_argument('--output', type=str, help='출력 파일')

    args = parser.parse_args()

    if not args.person and not args.person_id:
        parser.print_help()
        return

    # 1. DB에서 데이터 수집
    print("=" * 60)
    print("PERSON STORY GENERATOR (Phase 3-4 POC)")
    print("=" * 60)

    print("\n[1] Fetching person data from DB...")
    person_data = fetch_person_data(args.person_id, args.person)

    if not person_data:
        print(f"[ERROR] Person not found: {args.person or args.person_id}")
        return

    print(f"  - Name: {person_data['name']}")
    print(f"  - Life: {person_data['birth_year']} ~ {person_data['death_year']}")

    events = person_data['events']
    total = len(events['direct_period']) + len(events['direct_other']) + len(events['context_only'])
    print(f"  - Events found: {total}")
    print(f"    - direct_period (최우선): {len(events['direct_period'])}")
    print(f"    - direct_other (참조-후대): {len(events['direct_other'])}")
    print(f"    - context_only (참조-동시대): {len(events['context_only'])}")

    # 이벤트 미리보기
    print("\n[2] Events preview:")
    print("  === 최우선 (직접 언급 + 시대 맞음) ===")
    for e in events['direct_period'][:8]:
        print(f"  [{e['id']}] {e['title'][:45]} ({e['date_start']})")
    if len(events['direct_period']) > 8:
        print(f"  ... and {len(events['direct_period']) - 8} more")

    print("\n  === 참조-후대 (직접 언급 + 시대 안맞음) ===")
    for e in events['direct_other'][:5]:
        print(f"  [{e['id']}] {e['title'][:45]} ({e['date_start']})")

    print("\n  === 참조-동시대 (언급 없지만 맥락) ===")
    for e in events['context_only'][:5]:
        print(f"  [{e['id']}] {e['title'][:45]} ({e['date_start']})")

    # 2. LLM으로 스토리 생성
    print("\n[3] Generating Person Story...")
    model = LOCAL_MODEL if args.local else args.model
    story = generate_person_story(person_data, model, use_local=args.local)

    if 'error' in story:
        print(f"\n[ERROR] {story['error']}")
        if 'raw' in story:
            print(f"[RAW] {story['raw']}")
        return

    # 3. 결과 출력
    print("\n" + "=" * 60)
    print("GENERATED PERSON STORY")
    print("=" * 60)

    print(f"\n## Summary\n{story.get('summary', 'N/A')}")

    print("\n## Life Phases")
    for phase in story.get('life_phases', []):
        print(f"  - {phase.get('name')} ({phase.get('years')}): {phase.get('description', '')[:100]}")

    print("\n## Key Events")
    for evt in story.get('key_events', []):
        print(f"  - [{evt.get('event_id')}] {evt.get('title')} ({evt.get('year')})")
        print(f"    → {evt.get('significance', '')[:100]}")

    print("\n## Connections")
    for conn in story.get('connections', []):
        print(f"  - {conn.get('name')} ({conn.get('relationship')})")

    print(f"\n## Legacy\n{story.get('legacy', 'N/A')}")

    # 4. 파일 저장
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path(__file__).parent.parent / 'data' / 'stories' / f"{person_data['name'].replace(' ', '_').lower()}_story.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    full_result = {
        'person': person_data,
        'story': story,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(full_result, f, ensure_ascii=False, indent=2, cls=DecimalEncoder)

    print(f"\n[SAVED] {output_path}")


if __name__ == '__main__':
    main()
