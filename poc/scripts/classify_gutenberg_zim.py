"""
Classify Gutenberg ZIM contents for FGO/History relevance.

Usage:
    python poc/scripts/classify_gutenberg_zim.py

Output:
    - poc/data/gutenberg_catalog.json (전체 목록)
    - poc/data/gutenberg_useful.json (FGO/역사 관련)
    - poc/data/gutenberg_excluded.json (제외)
"""

import json
import os
import re
from pathlib import Path

# libzim 설치 필요: pip install libzim
try:
    from libzim.reader import Archive
    HAS_LIBZIM = True
except ImportError:
    HAS_LIBZIM = False
    print("Warning: libzim not installed. Run: pip install libzim")

# 프로젝트 루트 기준 절대 경로
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ZIM_PATH = str(PROJECT_ROOT / "data" / "kiwix" / "gutenberg_en_all.zim")
OUTPUT_DIR = str(PROJECT_ROOT / "poc" / "data" / "gutenberg_classify")

# FGO/역사 관련 키워드
USEFUL_KEYWORDS = {
    # 신화/전설
    'mythology', 'myth', 'legend', 'folklore', 'fairy tale', 'fable',
    'gods', 'heroes', 'epic', 'saga',

    # 지역별 신화
    'greek', 'roman', 'norse', 'celtic', 'irish', 'egyptian',
    'indian', 'hindu', 'buddhist', 'persian', 'arabian', 'babylonian',
    'mesopotamian', 'japanese', 'chinese', 'aztec', 'mayan',

    # 역사
    'history', 'historical', 'biography', 'ancient', 'medieval',
    'renaissance', 'war', 'battle', 'empire', 'kingdom', 'dynasty',

    # 고전문학
    'iliad', 'odyssey', 'aeneid', 'metamorphoses', 'divine comedy',
    'paradise lost', 'beowulf', 'nibelungen', 'arthurian', 'camelot',
    'round table', 'holy grail', 'charlemagne', 'roland',

    # 철학/종교
    'philosophy', 'philosopher', 'plato', 'aristotle', 'socrates',
    'religion', 'bible', 'scripture', 'sacred',

    # 문학 고전 (FGO 서번트 관련)
    'shakespeare', 'hamlet', 'macbeth', 'othello',
    'frankenstein', 'dracula', 'sherlock', 'holmes', 'moriarty',
    'monte cristo', 'phantom', 'opera', 'don quixote',
    'jekyll', 'hyde', 'faust', 'dante', 'inferno',

    # 특정 인물
    'alexander', 'caesar', 'cleopatra', 'napoleon', 'nero',
    'leonidas', 'spartacus', 'hannibal', 'attila',
    'joan of arc', 'jeanne', 'king arthur', 'merlin',
    'gilgamesh', 'achilles', 'hercules', 'heracles',
    'odysseus', 'ulysses', 'jason', 'argonaut',
    'sigurd', 'siegfried', 'brynhild', 'brunhild',
    'cu chulainn', 'cuchulain', 'fionn', 'finn',
    'rama', 'arjuna', 'karna', 'mahabharata', 'ramayana',
}

# 제외 키워드
EXCLUDE_KEYWORDS = {
    # 기술/과학
    'manual', 'handbook', 'guide to', 'how to',
    'engineering', 'chemistry', 'physics', 'mathematics',
    'electricity', 'machinery', 'manufacturing',

    # 실용서
    'cookbook', 'recipe', 'gardening', 'farming',
    'agriculture', 'veterinary', 'medical', 'surgery',
    'accounting', 'bookkeeping', 'business',

    # 법률
    'law', 'legal', 'court', 'statute', 'regulation',

    # 기타
    'catalog', 'catalogue', 'index', 'dictionary',
    'grammar', 'textbook', 'lesson', 'exercise',
}

# LCC 분류별 유용도
LCC_USEFUL = {
    'B': 'useful',      # 철학, 종교, 신화
    'D': 'useful',      # 세계사
    'PA': 'useful',     # 고전문학
    'PQ': 'useful',     # 로망스 문학
    'PR': 'useful',     # 영문학
    'PN': 'useful',     # 문학 일반
    'PT': 'useful',     # 독일문학
    'G': 'partial',     # 지리/인류학 (민속학 포함)
    'C': 'partial',     # 역사 보조학
    'E': 'partial',     # 미국사
    'N': 'partial',     # 미술
    'PZ': 'partial',    # 아동문학/동화
    'U': 'partial',     # 군사학
}


def classify_book(title: str, author: str = "", subject: str = "", lcc: str = "") -> dict:
    """Classify a single book."""
    title_lower = title.lower()
    author_lower = author.lower() if author else ""
    subject_lower = subject.lower() if subject else ""
    combined = f"{title_lower} {author_lower} {subject_lower}"

    result = {
        'title': title,
        'author': author,
        'subject': subject,
        'lcc': lcc,
        'classification': 'unknown',
        'relevance_score': 0,
        'matched_keywords': [],
        'exclude_keywords': [],
    }

    # 제외 키워드 체크
    for kw in EXCLUDE_KEYWORDS:
        if kw in combined:
            result['exclude_keywords'].append(kw)

    # 유용 키워드 체크
    for kw in USEFUL_KEYWORDS:
        if kw in combined:
            result['matched_keywords'].append(kw)
            result['relevance_score'] += 1

    # LCC 분류 체크
    if lcc:
        for lcc_code, usefulness in LCC_USEFUL.items():
            if lcc.startswith(lcc_code):
                if usefulness == 'useful':
                    result['relevance_score'] += 3
                elif usefulness == 'partial':
                    result['relevance_score'] += 1
                break

    # 최종 분류
    if result['exclude_keywords'] and result['relevance_score'] < 2:
        result['classification'] = 'excluded'
    elif result['relevance_score'] >= 2:
        result['classification'] = 'useful'
    elif result['relevance_score'] == 1:
        result['classification'] = 'maybe'
    else:
        result['classification'] = 'excluded'

    return result


def extract_metadata_from_zim(zim_path: str, limit: int = None) -> list:
    """Extract book metadata from ZIM file."""
    if not HAS_LIBZIM:
        print("libzim not available. Cannot read ZIM file.")
        return []

    print(f"Opening ZIM: {zim_path}")
    zim = Archive(zim_path)

    books = []
    count = 0

    print(f"Total entries: {zim.entry_count}")

    for entry in zim.iterarticles():
        if limit and count >= limit:
            break

        try:
            title = entry.title
            path = entry.path

            # 메인 문서만 (인덱스, 이미지 등 제외)
            if not path.startswith('A/'):
                continue

            # 메타데이터 추출 시도
            content = ""
            try:
                item = entry.get_item()
                content = item.content.decode('utf-8', errors='ignore')[:2000]
            except:
                pass

            # 저자/주제 추출 (HTML에서)
            author = ""
            subject = ""
            lcc = ""

            # Author 추출
            author_match = re.search(r'<meta name="author" content="([^"]+)"', content)
            if author_match:
                author = author_match.group(1)

            # Subject 추출
            subject_match = re.search(r'<meta name="subject" content="([^"]+)"', content)
            if subject_match:
                subject = subject_match.group(1)

            # LCC 추출
            lcc_match = re.search(r'LCC:\s*([A-Z]{1,2})', content)
            if lcc_match:
                lcc = lcc_match.group(1)

            books.append({
                'title': title,
                'path': path,
                'author': author,
                'subject': subject,
                'lcc': lcc,
            })

            count += 1
            if count % 1000 == 0:
                print(f"  Processed {count} entries...")

        except Exception as e:
            continue

    print(f"Extracted {len(books)} books")
    return books


def classify_all_books(books: list) -> dict:
    """Classify all books."""
    results = {
        'useful': [],
        'maybe': [],
        'excluded': [],
        'stats': {
            'total': 0,
            'useful': 0,
            'maybe': 0,
            'excluded': 0,
        }
    }

    for book in books:
        classified = classify_book(
            title=book.get('title', ''),
            author=book.get('author', ''),
            subject=book.get('subject', ''),
            lcc=book.get('lcc', '')
        )

        # 원본 정보 추가
        classified['path'] = book.get('path', '')

        classification = classified['classification']
        results[classification].append(classified)
        results['stats']['total'] += 1
        results['stats'][classification] += 1

    return results


def save_results(results: dict, output_dir: str):
    """Save classification results."""
    os.makedirs(output_dir, exist_ok=True)

    # 전체 카탈로그
    with open(f"{output_dir}/gutenberg_catalog.json", 'w', encoding='utf-8') as f:
        json.dump({
            'stats': results['stats'],
            'useful_count': len(results['useful']),
            'maybe_count': len(results['maybe']),
            'excluded_count': len(results['excluded']),
        }, f, indent=2, ensure_ascii=False)

    # 유용한 책 목록
    with open(f"{output_dir}/gutenberg_useful.json", 'w', encoding='utf-8') as f:
        json.dump(results['useful'], f, indent=2, ensure_ascii=False)

    # Maybe 목록
    with open(f"{output_dir}/gutenberg_maybe.json", 'w', encoding='utf-8') as f:
        json.dump(results['maybe'], f, indent=2, ensure_ascii=False)

    # 제외 목록 (샘플만)
    with open(f"{output_dir}/gutenberg_excluded_sample.json", 'w', encoding='utf-8') as f:
        json.dump(results['excluded'][:1000], f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to {output_dir}/")
    print(f"  - gutenberg_catalog.json (통계)")
    print(f"  - gutenberg_useful.json ({len(results['useful'])} books)")
    print(f"  - gutenberg_maybe.json ({len(results['maybe'])} books)")
    print(f"  - gutenberg_excluded_sample.json (샘플 1000)")


def main():
    print("=" * 60)
    print("Gutenberg ZIM Classification for FGO/History")
    print("=" * 60)

    # ZIM 파일 체크
    if not os.path.exists(ZIM_PATH):
        print(f"ZIM file not found: {ZIM_PATH}")
        print("Waiting for download to complete...")
        return

    # 파일 크기 체크
    size_gb = os.path.getsize(ZIM_PATH) / (1024**3)
    print(f"ZIM file size: {size_gb:.1f} GB")

    if size_gb < 200:
        print("Download may be incomplete. Expected ~206GB.")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            return

    # 메타데이터 추출
    print("\n[1/3] Extracting metadata from ZIM...")
    books = extract_metadata_from_zim(ZIM_PATH)

    if not books:
        print("No books extracted. Check libzim installation.")
        return

    # 분류
    print("\n[2/3] Classifying books...")
    results = classify_all_books(books)

    # 저장
    print("\n[3/3] Saving results...")
    save_results(results, OUTPUT_DIR)

    # 통계 출력
    print("\n" + "=" * 60)
    print("CLASSIFICATION SUMMARY")
    print("=" * 60)
    print(f"Total books:  {results['stats']['total']:,}")
    print(f"Useful:       {results['stats']['useful']:,} ({100*results['stats']['useful']/results['stats']['total']:.1f}%)")
    print(f"Maybe:        {results['stats']['maybe']:,} ({100*results['stats']['maybe']/results['stats']['total']:.1f}%)")
    print(f"Excluded:     {results['stats']['excluded']:,} ({100*results['stats']['excluded']/results['stats']['total']:.1f}%)")

    # 상위 유용 책 샘플
    print("\n[TOP 10 USEFUL BOOKS]")
    top_useful = sorted(results['useful'], key=lambda x: x['relevance_score'], reverse=True)[:10]
    for book in top_useful:
        print(f"  - {book['title'][:60]} (score: {book['relevance_score']})")


if __name__ == "__main__":
    main()
