"""
FGO 마테리얼/프로필 수집 스크립트
Atlas Academy API에서 서번트 프로필(마테리얼) 데이터를 수집합니다.

사용법:
    python data/scripts/collect_fgo_materials.py [--region NA|JP] [--limit N]
"""

import json
import sys
import time
import argparse
from pathlib import Path
from typing import Optional
import urllib.request
import urllib.error

# Windows 콘솔 인코딩 문제 해결
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# 설정
BASE_URL = "https://api.atlasacademy.io"
OUTPUT_DIR = Path("data/raw/atlas_academy/materials")
RATE_LIMIT_DELAY = 0.3  # API 요청 간 딜레이 (초)


def fetch_json(url: str) -> Optional[dict]:
    """URL에서 JSON 데이터를 가져옵니다."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "CHALDEAS/1.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"  HTTP Error {e.code}: {url}")
        return None
    except Exception as e:
        print(f"  Error fetching {url}: {e}")
        return None


def get_servant_list(region: str) -> list:
    """서번트 목록을 가져옵니다."""
    url = f"{BASE_URL}/export/{region}/basic_servant.json"
    print(f"Fetching servant list from {url}...")
    data = fetch_json(url)
    if data:
        # 일반 서번트만 필터링 (type: normal, heroine)
        servants = [s for s in data if s.get("type") in ("normal", "heroine")]
        print(f"  Found {len(servants)} servants")
        return servants
    return []


def get_servant_lore(region: str, servant_id: int) -> Optional[dict]:
    """서번트의 상세 정보(마테리얼 포함)를 가져옵니다."""
    url = f"{BASE_URL}/nice/{region}/servant/{servant_id}?lore=true"
    return fetch_json(url)


def extract_profile(servant_data: dict) -> dict:
    """서번트 데이터에서 프로필 정보를 추출합니다."""
    profile = servant_data.get("profile", {})

    # 기본 정보
    result = {
        "id": servant_data.get("id"),
        "collectionNo": servant_data.get("collectionNo"),
        "name": servant_data.get("name"),
        "originalName": servant_data.get("originalName"),
        "className": servant_data.get("className"),
        "rarity": servant_data.get("rarity"),
        "gender": servant_data.get("gender"),
        "attribute": servant_data.get("attribute"),

        # 프로필 정보
        "cv": profile.get("cv"),
        "illustrator": profile.get("illustrator"),
        "stats": profile.get("stats"),

        # 마테리얼 텍스트 (절친도별)
        "comments": [],

        # 코스튬 정보
        "costumes": {},

        # 특성
        "traits": [t.get("name") for t in servant_data.get("traits", [])],
    }

    # 마테리얼 코멘트 추출
    for comment in profile.get("comments", []):
        result["comments"].append({
            "id": comment.get("id"),
            "condType": comment.get("condType"),
            "condValues": comment.get("condValues"),
            "comment": comment.get("comment"),
        })

    # 코스튬 정보 추출
    for costume_id, costume in profile.get("costume", {}).items():
        result["costumes"][costume_id] = {
            "name": costume.get("name"),
            "shortName": costume.get("shortName"),
            "detail": costume.get("detail"),
        }

    # 이미지 URL
    extra_assets = servant_data.get("extraAssets", {})
    faces = extra_assets.get("faces", {}).get("ascension", {})
    if faces:
        result["faceUrl"] = faces.get("1") or faces.get("2") or list(faces.values())[0]

    return result


def collect_materials(region: str = "NA", limit: Optional[int] = None):
    """전체 서번트의 마테리얼을 수집합니다."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 서번트 목록 가져오기
    servants = get_servant_list(region)
    if not servants:
        print("No servants found!")
        return

    if limit:
        servants = servants[:limit]
        print(f"Limiting to {limit} servants")

    # 결과 저장용
    all_profiles = []
    failed = []

    print(f"\nCollecting profiles for {len(servants)} servants...")

    for i, servant in enumerate(servants):
        servant_id = servant.get("id")
        servant_name = servant.get("name")

        print(f"[{i+1}/{len(servants)}] {servant_name} (ID: {servant_id})...", end=" ")

        # 상세 정보 가져오기
        data = get_servant_lore(region, servant_id)

        if data:
            profile = extract_profile(data)
            all_profiles.append(profile)
            print("OK")
        else:
            failed.append({"id": servant_id, "name": servant_name})
            print("FAILED")

        # Rate limiting
        time.sleep(RATE_LIMIT_DELAY)

    # 결과 저장
    output_file = OUTPUT_DIR / f"servant_profiles_{region.lower()}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_profiles, f, ensure_ascii=False, indent=2)

    print(f"\n=== Collection Complete ===")
    print(f"Success: {len(all_profiles)}")
    print(f"Failed: {len(failed)}")
    print(f"Output: {output_file}")

    if failed:
        failed_file = OUTPUT_DIR / f"failed_{region.lower()}.json"
        with open(failed_file, "w", encoding="utf-8") as f:
            json.dump(failed, f, ensure_ascii=False, indent=2)
        print(f"Failed list: {failed_file}")

    return all_profiles


def main():
    parser = argparse.ArgumentParser(description="Collect FGO servant materials from Atlas Academy")
    parser.add_argument("--region", default="NA", choices=["NA", "JP", "KR", "CN", "TW"],
                        help="Game region (default: NA)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit number of servants to collect (for testing)")

    args = parser.parse_args()

    print("=" * 50)
    print("FGO Material Collector")
    print(f"Region: {args.region}")
    print("=" * 50)

    collect_materials(region=args.region, limit=args.limit)


if __name__ == "__main__":
    main()
