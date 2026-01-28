"""Download all FGO/History/Mythology related books from Project Gutenberg"""
import requests
import os
import time

# 책 목록: (Gutenberg ID, 파일명, 카테고리)
BOOKS = [
    # Tier 1: 최우선
    (1251, "le_morte_darthur", "arthurian"),
    (6130, "iliad_homer", "greek"),
    (228, "aeneid_virgil", "roman"),

    # Tier 2: 높은 우선순위
    (1152, "volsunga_saga", "norse"),
    (830, "argonautica", "greek"),
    (16464, "cattle_raid_cooley", "celtic"),
    (7321, "nibelungenlied", "germanic"),
    (24869, "ramayana", "indian"),
    (14726, "poetic_edda", "norse"),
    (18947, "prose_edda", "norse"),

    # Tier 3: 개별 서번트
    (84, "frankenstein", "literary"),
    (1184, "count_of_monte_cristo", "literary"),
    (1661, "sherlock_holmes_complete", "literary"),
    (43, "dr_jekyll_mr_hyde", "literary"),
    (16328, "beowulf", "germanic"),
    (996, "don_quixote", "literary"),
    (175, "phantom_of_opera", "literary"),
    (3747, "orlando_furioso", "carolingian"),
    (391, "song_of_roland", "carolingian"),

    # Tier 4: 역사 전기
    (1351, "joan_of_arc_twain", "history"),
    (3567, "napoleon_biography", "history"),
    (1301, "french_revolution_carlyle", "history"),
    (25759, "lives_of_artists_vasari", "history"),
    (17007, "book_of_five_rings", "japanese"),
    (24439, "geronimo_story", "history"),

    # Tier 5: 신화/종교
    (26073, "metamorphoses_ovid", "roman"),
    (7145, "book_of_dead_egyptian", "egyptian"),
    (17321, "babylonian_legends", "mesopotamian"),
    (1597, "andersen_fairy_tales", "literary"),
    (2591, "grimm_fairy_tales", "literary"),

    # 추가: 그리스/로마
    (1727, "odyssey_homer", "greek"),  # 이미 있을 수 있음
    (2131, "herodotus_histories", "greek"),  # 이미 있을 수 있음
    (674, "plutarch_lives", "greek"),  # 이미 있을 수 있음
    (4928, "bulfinch_mythology", "mythology"),  # 이미 있을 수 있음

    # 추가: 켈트/아일랜드
    (14465, "gods_and_fighting_men", "celtic"),
    (2892, "irish_fairy_tales", "celtic"),

    # 추가: 아서왕
    (610, "idylls_of_the_king", "arthurian"),
    (14244, "tristan_and_iseult", "arthurian"),
    (1972, "history_british_kings", "arthurian"),

    # 추가: 문학 고전
    (100, "complete_shakespeare", "literary"),
    (2000, "divine_comedy_dante", "literary"),
    (5200, "paradise_lost_milton", "literary"),
    (1232, "prince_machiavelli", "history"),

    # 추가: 동화/전설
    (4018, "japanese_fairy_tales", "japanese"),
    (932, "arabian_nights_burton", "arabian"),
]

OUTPUT_DIR = "poc/data/book_samples"


def download_book(gutenberg_id: int, filename: str, category: str):
    """Download a single book from Gutenberg"""
    filepath = f"{OUTPUT_DIR}/{filename}.txt"

    # 이미 존재하면 스킵
    if os.path.exists(filepath):
        size = os.path.getsize(filepath)
        if size > 10000:  # 10KB 이상이면 유효
            print(f"  [SKIP] {filename} already exists ({size:,} bytes)")
            return True

    # 다운로드 URL 시도
    urls = [
        f"https://www.gutenberg.org/cache/epub/{gutenberg_id}/pg{gutenberg_id}.txt",
        f"https://www.gutenberg.org/files/{gutenberg_id}/{gutenberg_id}-0.txt",
        f"https://www.gutenberg.org/files/{gutenberg_id}/{gutenberg_id}.txt",
    ]

    for url in urls:
        try:
            resp = requests.get(url, timeout=60)
            if resp.status_code == 200 and len(resp.text) > 10000:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(resp.text)
                print(f"  [OK] {filename} ({len(resp.text):,} chars) - {category}")
                return True
        except Exception as e:
            continue

    print(f"  [FAIL] {filename} (ID: {gutenberg_id})")
    return False


def main():
    print("=" * 70)
    print("Downloading books from Project Gutenberg")
    print("=" * 70)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    success = 0
    failed = 0
    skipped = 0

    for i, (gid, name, cat) in enumerate(BOOKS):
        print(f"[{i+1}/{len(BOOKS)}] {name}...")

        filepath = f"{OUTPUT_DIR}/{name}.txt"
        if os.path.exists(filepath) and os.path.getsize(filepath) > 10000:
            skipped += 1
            print(f"  [SKIP] already exists")
            continue

        if download_book(gid, name, cat):
            success += 1
        else:
            failed += 1

        # Rate limiting
        time.sleep(1)

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total: {len(BOOKS)}")
    print(f"Downloaded: {success}")
    print(f"Skipped (existing): {skipped}")
    print(f"Failed: {failed}")

    # 카테고리별 통계
    categories = {}
    for _, name, cat in BOOKS:
        filepath = f"{OUTPUT_DIR}/{name}.txt"
        if os.path.exists(filepath):
            categories[cat] = categories.get(cat, 0) + 1

    print("\nBy category:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
