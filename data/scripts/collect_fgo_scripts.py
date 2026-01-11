"""
FGO 스토리 스크립트 수집 스크립트
Atlas Academy API에서 메인 스토리 및 이벤트 스크립트를 수집합니다.

사용법:
    python data/scripts/collect_fgo_scripts.py [--region NA|JP] [--type main|event|all]
"""

import json
import sys
import time
import re
import argparse
from pathlib import Path
from typing import Optional, List, Dict
import urllib.request
import urllib.error

# Windows 콘솔 인코딩 문제 해결
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# 설정
BASE_URL = "https://api.atlasacademy.io"
STATIC_URL = "https://static.atlasacademy.io"
OUTPUT_DIR = Path("data/raw/atlas_academy/scripts")
RATE_LIMIT_DELAY = 0.2

# Singularity/Lostbelt 정보
MAIN_STORIES = {
    "singularities": [
        {"id": "fuyuki", "name": "Fuyuki", "name_ko": "후유키", "year": 2004, "warId": 100},
        {"id": "orleans", "name": "Orleans", "name_ko": "오를레앙", "year": 1431, "warId": 101},
        {"id": "septem", "name": "Septem", "name_ko": "세프템", "year": 60, "warId": 102},
        {"id": "okeanos", "name": "Okeanos", "name_ko": "오케아노스", "year": 1573, "warId": 103},
        {"id": "london", "name": "London", "name_ko": "런던", "year": 1888, "warId": 104},
        {"id": "america", "name": "E Pluribus Unum", "name_ko": "이 플루리버스 우넘", "year": 1783, "warId": 105},
        {"id": "camelot", "name": "Camelot", "name_ko": "캐멀롯", "year": 1273, "warId": 106},
        {"id": "babylonia", "name": "Babylonia", "name_ko": "바빌로니아", "year": -2655, "warId": 107},
        {"id": "solomon", "name": "Solomon", "name_ko": "솔로몬", "year": 2016, "warId": 108},
    ],
    "lostbelts": [
        {"id": "lb1", "name": "Anastasia", "name_ko": "아나스타시아", "year": 1570, "warId": 301},
        {"id": "lb2", "name": "Gotterdammerung", "name_ko": "괴팅겐", "year": -1000, "warId": 302},
        {"id": "lb3", "name": "SIN", "name_ko": "시황", "year": -210, "warId": 303},
        {"id": "lb4", "name": "Yuga Kshetra", "name_ko": "유가", "year": 11900, "warId": 304},
        {"id": "lb5", "name": "Atlantis", "name_ko": "아틀란티스", "year": -12000, "warId": 305},
        {"id": "lb5.5", "name": "Olympus", "name_ko": "올림포스", "year": -12000, "warId": 306},
        {"id": "lb6", "name": "Avalon", "name_ko": "아발론", "year": 500, "warId": 308},
        {"id": "lb7", "name": "Nahui Mictlan", "name_ko": "나우이 믹틀란", "year": -2655, "warId": 311},
    ]
}


def fetch_json(url: str) -> Optional[dict]:
    """URL에서 JSON 데이터를 가져옵니다."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "CHALDEAS/1.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print(f"  HTTP Error {e.code}: {url}")
        return None
    except Exception as e:
        print(f"  Error: {e}")
        return None


def fetch_text(url: str) -> Optional[str]:
    """URL에서 텍스트 데이터를 가져옵니다."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "CHALDEAS/1.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.read().decode("utf-8")
    except Exception:
        return None


def parse_script(script_text: str) -> Dict:
    """스크립트 텍스트를 파싱하여 대사를 추출합니다."""
    lines = script_text.split("\n")
    dialogues = []
    current_speaker = None

    for line in lines:
        line = line.strip()

        # 화자 변경
        if line.startswith("＠") or line.startswith("@"):
            current_speaker = line[1:].strip()
            continue

        # 연출 명령어 스킵
        if line.startswith("[") or line.startswith("＄") or not line:
            continue

        # 대사 추가
        if current_speaker and line:
            # 태그 제거
            clean_line = re.sub(r'\[.*?\]', '', line).strip()
            if clean_line:
                dialogues.append({
                    "speaker": current_speaker,
                    "text": clean_line
                })

    return {
        "raw": script_text,
        "dialogues": dialogues,
        "dialogue_count": len(dialogues)
    }


def get_war_info(region: str, war_id: int) -> Optional[dict]:
    """War(스토리 챕터) 정보를 가져옵니다."""
    url = f"{BASE_URL}/nice/{region}/war/{war_id}"
    return fetch_json(url)


def get_quest_scripts(region: str, quest_id: int) -> List[str]:
    """퀘스트의 스크립트 URL들을 가져옵니다."""
    url = f"{BASE_URL}/nice/{region}/quest/{quest_id}"
    quest_data = fetch_json(url)

    if not quest_data:
        return []

    scripts = []
    # phaseScripts에서 스크립트 URL 추출
    for phase_script in quest_data.get("phaseScripts", []):
        for script in phase_script.get("scripts", []):
            script_url = script.get("script")
            if script_url:
                scripts.append(script_url)

    return scripts


def collect_war_scripts(region: str, war_info: dict) -> Dict:
    """War(스토리 챕터)의 모든 스크립트를 수집합니다."""
    war_id = war_info["warId"]
    war_name = war_info["name"]

    print(f"\n{'='*50}")
    print(f"Collecting: {war_name} (War ID: {war_id})")
    print(f"{'='*50}")

    war_data = get_war_info(region, war_id)
    if not war_data:
        print(f"  War not found!")
        return None

    result = {
        "id": war_info["id"],
        "name": war_name,
        "name_ko": war_info["name_ko"],
        "year": war_info["year"],
        "warId": war_id,
        "spots": [],
        "total_scripts": 0,
        "total_dialogues": 0
    }

    # 각 스팟(지역) 순회
    for spot in war_data.get("spots", []):
        spot_name = spot.get("name", "Unknown")
        spot_result = {
            "name": spot_name,
            "quests": []
        }

        print(f"\n  Spot: {spot_name}")

        # 각 퀘스트 순회
        for quest in spot.get("quests", []):
            quest_id = quest.get("id")
            quest_name = quest.get("name", "Unknown")

            # 메인 스토리 퀘스트만 (type이 main인 것)
            if quest.get("type") != "main":
                continue

            print(f"    Quest: {quest_name}...", end=" ")

            quest_result = {
                "id": quest_id,
                "name": quest_name,
                "scripts": []
            }

            # 퀘스트의 스크립트 수집
            script_urls = get_quest_scripts(region, quest_id)

            for script_url in script_urls:
                script_text = fetch_text(script_url)
                if script_text:
                    parsed = parse_script(script_text)
                    quest_result["scripts"].append({
                        "url": script_url,
                        "dialogues": parsed["dialogues"],
                        "dialogue_count": parsed["dialogue_count"]
                    })
                    result["total_scripts"] += 1
                    result["total_dialogues"] += parsed["dialogue_count"]

                time.sleep(RATE_LIMIT_DELAY)

            if quest_result["scripts"]:
                spot_result["quests"].append(quest_result)
                print(f"{len(quest_result['scripts'])} scripts")
            else:
                print("no scripts")

            time.sleep(RATE_LIMIT_DELAY)

        if spot_result["quests"]:
            result["spots"].append(spot_result)

    return result


def collect_main_story(region: str = "NA", story_type: str = "all"):
    """메인 스토리 스크립트를 수집합니다."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    stories_to_collect = []

    if story_type in ("all", "singularity"):
        stories_to_collect.extend(MAIN_STORIES["singularities"])

    if story_type in ("all", "lostbelt"):
        stories_to_collect.extend(MAIN_STORIES["lostbelts"])

    all_results = []

    for story in stories_to_collect:
        result = collect_war_scripts(region, story)
        if result:
            all_results.append(result)

            # 개별 파일로도 저장
            story_file = OUTPUT_DIR / f"{story['id']}_{region.lower()}.json"
            with open(story_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"  Saved: {story_file}")

    # 전체 결과 저장
    output_file = OUTPUT_DIR / f"main_story_{region.lower()}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    # 요약 출력
    print(f"\n{'='*50}")
    print("Collection Summary")
    print(f"{'='*50}")
    total_scripts = sum(r["total_scripts"] for r in all_results)
    total_dialogues = sum(r["total_dialogues"] for r in all_results)
    print(f"Stories collected: {len(all_results)}")
    print(f"Total scripts: {total_scripts}")
    print(f"Total dialogues: {total_dialogues}")
    print(f"Output: {output_file}")


def collect_singularity_info(region: str = "NA"):
    """Singularity/Lostbelt 기본 정보만 수집합니다 (스크립트 없이)."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = {
        "singularities": [],
        "lostbelts": []
    }

    print("Collecting Singularity/Lostbelt info...")

    for category in ["singularities", "lostbelts"]:
        for story in MAIN_STORIES[category]:
            war_data = get_war_info(region, story["warId"])

            if war_data:
                info = {
                    "id": story["id"],
                    "name": story["name"],
                    "name_ko": story["name_ko"],
                    "longName": war_data.get("longName"),
                    "year": story["year"],
                    "warId": story["warId"],
                    "banner": war_data.get("banner"),
                    "spots": [{"name": s.get("name"), "questCount": len(s.get("quests", []))}
                              for s in war_data.get("spots", [])],
                }
                results[category].append(info)
                print(f"  {story['name']}: OK")
            else:
                print(f"  {story['name']}: Not found")

            time.sleep(RATE_LIMIT_DELAY)

    # 저장
    output_file = OUTPUT_DIR / f"story_info_{region.lower()}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nSaved: {output_file}")
    return results


def main():
    parser = argparse.ArgumentParser(description="Collect FGO story scripts from Atlas Academy")
    parser.add_argument("--region", default="NA", choices=["NA", "JP"],
                        help="Game region (default: NA)")
    parser.add_argument("--type", default="info", choices=["info", "singularity", "lostbelt", "all"],
                        help="What to collect: info (metadata only), singularity, lostbelt, or all")

    args = parser.parse_args()

    print("=" * 50)
    print("FGO Script Collector")
    print(f"Region: {args.region}")
    print(f"Type: {args.type}")
    print("=" * 50)

    if args.type == "info":
        collect_singularity_info(region=args.region)
    else:
        collect_main_story(region=args.region, story_type=args.type)


if __name__ == "__main__":
    main()
