"""
FGO 서번트 전체 매핑 기반 book_list.json 생성
"""
import json
from pathlib import Path
from servant_keywords_full import SERVANT_KEYWORDS, BOOK_CATEGORIES

OUTPUT_FILE = Path(__file__).parent / "book_list.json"
PROJECT_ROOT = Path(__file__).parent.parent.parent
BOOKS_DIR = PROJECT_ROOT / "poc" / "data" / "book_samples"

# 현재 다운로드된 책 파일들
AVAILABLE_BOOKS = {
    # 그리스/트로이
    "iliad_homer": {"size_mb": 1.2, "status": "pending"},
    "odyssey_homer": {"size_mb": 0.7, "status": "pending"},
    "argonautica": {"size_mb": 0.36, "status": "pending"},
    "metamorphoses_ovid": {"size_mb": 0.85, "status": "pending"},

    # 메소포타미아
    "gilgamesh_epic": {"size_mb": 0.25, "status": "pending"},
    "babylonian_legends": {"size_mb": 0.69, "status": "pending"},

    # 인도
    "mahabharata": {"size_mb": 1.4, "status": "pending"},
    "ramayana": {"size_mb": 2.4, "status": "pending"},

    # 켈트
    "cattle_raid_cooley": {"size_mb": 0.76, "status": "pending"},
    "celtic_mythology": {"size_mb": 0.89, "status": "pending"},
    "gods_and_fighting_men": {"size_mb": 0.9, "status": "pending"},
    "irish_fairy_tales": {"size_mb": 0.39, "status": "pending"},

    # 북유럽
    "nibelungenlied": {"size_mb": 0.68, "status": "pending"},
    "volsunga_saga": {"size_mb": 0.35, "status": "pending"},
    "beowulf": {"size_mb": 0.3, "status": "pending"},
    "poetic_edda": {"size_mb": 0.53, "status": "pending"},
    "prose_edda": {"size_mb": 0.41, "status": "pending"},
    "norse_mythology": {"size_mb": 0.62, "status": "done"},

    # 아서왕
    "le_morte_darthur": {"size_mb": 0.9, "status": "pending"},
    "idylls_of_the_king": {"size_mb": 0.51, "status": "pending"},
    "tristan_and_iseult": {"size_mb": 0.16, "status": "pending"},
    "history_british_kings": {"size_mb": 0.1, "status": "pending"},

    # 샤를마뉴
    "song_of_roland": {"size_mb": 0.22, "status": "pending"},
    "orlando_furioso": {"size_mb": 1.7, "status": "pending"},

    # 그리스/로마 역사
    "plutarch_lives": {"size_mb": 4.2, "status": "extracting"},
    "herodotus_histories": {"size_mb": 0.9, "status": "pending"},
    "aeneid_virgil": {"size_mb": 0.74, "status": "pending"},

    # 문학
    "frankenstein": {"size_mb": 0.45, "status": "pending"},
    "phantom_of_opera": {"size_mb": 0.5, "status": "pending"},
    "count_of_monte_cristo": {"size_mb": 2.8, "status": "pending"},
    "sherlock_holmes_complete": {"size_mb": 0.61, "status": "pending"},
    "dr_jekyll_mr_hyde": {"size_mb": 0.16, "status": "pending"},
    "don_quixote": {"size_mb": 2.4, "status": "pending"},
    "complete_shakespeare": {"size_mb": 5.8, "status": "pending"},
    "divine_comedy_dante": {"size_mb": 2.2, "status": "pending"},
    "paradise_lost_milton": {"size_mb": 0.14, "status": "pending"},

    # 동화/민화
    "andersen_fairy_tales": {"size_mb": 0.33, "status": "pending"},
    "grimm_fairy_tales": {"size_mb": 0.56, "status": "pending"},
    "arabian_nights": {"size_mb": 0.62, "status": "done"},
    "arabian_nights_burton": {"size_mb": 0.06, "status": "pending"},
    "japanese_fairy_tales": {"size_mb": 0.4, "status": "pending"},

    # 역사 전기
    "napoleon_biography": {"size_mb": 2.9, "status": "pending"},
    "french_revolution_carlyle": {"size_mb": 2.1, "status": "pending"},
    "joan_of_arc_twain": {"size_mb": 0.4, "status": "pending"},
    "lives_of_artists_vasari": {"size_mb": 0.51, "status": "pending"},
    "book_of_five_rings": {"size_mb": 0.27, "status": "pending"},
    "geronimo_story": {"size_mb": 0.16, "status": "pending"},
    "prince_machiavelli": {"size_mb": 0.31, "status": "pending"},
    "marcus_aurelius_meditations": {"size_mb": 0.73, "status": "pending"},

    # 신화 종합
    "greek_roman_myths": {"size_mb": 0.87, "status": "done"},
    "bulfinch_mythology": {"size_mb": 0.67, "status": "pending"},
    "egyptian_mythology": {"size_mb": 0.58, "status": "pending"},
    "japanese_mythology": {"size_mb": 0.39, "status": "pending"},
    "chinese_mythology": {"size_mb": 0.7, "status": "pending"},
    "book_of_dead_egyptian": {"size_mb": 0.09, "status": "pending"},

    # 철학
    "plato_republic": {"size_mb": 1.3, "status": "pending"},
}


def get_servants_for_book(book_id: str) -> list:
    """책에 매칭되는 서번트 목록 반환"""
    return BOOK_CATEGORIES.get(book_id, [])


def get_books_for_servant(servant_name: str) -> list:
    """서번트에 매칭되는 책 목록 반환"""
    books = []
    for book_id, servants in BOOK_CATEGORIES.items():
        if servant_name in servants:
            books.append(book_id)
    return books


def generate_book_list():
    """전체 book_list.json 생성"""

    # 우선순위별 분류
    priority_1_epic = []      # 서사시/핵심 신화 (10+ 서번트)
    priority_2_legend = []    # 전설/영웅담 (5-10 서번트)
    priority_3_history = []   # 역사 전기 (직접 매칭)
    priority_4_literature = [] # 문학 (문학 서번트)
    priority_5_mythology = [] # 신화 종합 (배경자료)
    priority_6_supplement = [] # 보조 자료

    for book_id, info in AVAILABLE_BOOKS.items():
        servants = get_servants_for_book(book_id)

        book_entry = {
            "id": book_id,
            "file": f"{book_id}.txt",
            "status": info["status"],
            "size_mb": info["size_mb"],
            "servants": servants,
            "servant_count": len(servants)
        }

        # 우선순위 분류
        if book_id in ["iliad_homer", "odyssey_homer", "mahabharata", "le_morte_darthur", "plutarch_lives"]:
            priority_1_epic.append(book_entry)
        elif book_id in ["argonautica", "cattle_raid_cooley", "nibelungenlied", "volsunga_saga",
                         "gilgamesh_epic", "herodotus_histories", "beowulf", "ramayana",
                         "song_of_roland", "orlando_furioso", "celtic_mythology", "gods_and_fighting_men"]:
            priority_2_legend.append(book_entry)
        elif book_id in ["napoleon_biography", "french_revolution_carlyle", "joan_of_arc_twain",
                         "lives_of_artists_vasari", "book_of_five_rings", "geronimo_story"]:
            priority_3_history.append(book_entry)
        elif book_id in ["frankenstein", "phantom_of_opera", "count_of_monte_cristo",
                         "sherlock_holmes_complete", "dr_jekyll_mr_hyde", "don_quixote",
                         "complete_shakespeare", "divine_comedy_dante", "andersen_fairy_tales"]:
            priority_4_literature.append(book_entry)
        elif book_id in ["greek_roman_myths", "bulfinch_mythology", "egyptian_mythology",
                         "japanese_mythology", "chinese_mythology", "norse_mythology",
                         "babylonian_legends", "metamorphoses_ovid"]:
            priority_5_mythology.append(book_entry)
        else:
            priority_6_supplement.append(book_entry)

    # 각 그룹 내에서 서번트 수로 정렬
    for group in [priority_1_epic, priority_2_legend, priority_3_history,
                  priority_4_literature, priority_5_mythology, priority_6_supplement]:
        group.sort(key=lambda x: (-x["servant_count"], x["id"]))

    result = {
        "priority_1_epic": {
            "description": "서사시/핵심 (다수 서번트)",
            "total_servants": sum(b["servant_count"] for b in priority_1_epic),
            "books": priority_1_epic
        },
        "priority_2_legend": {
            "description": "전설/영웅담",
            "total_servants": sum(b["servant_count"] for b in priority_2_legend),
            "books": priority_2_legend
        },
        "priority_3_history": {
            "description": "역사 전기",
            "total_servants": sum(b["servant_count"] for b in priority_3_history),
            "books": priority_3_history
        },
        "priority_4_literature": {
            "description": "문학 서번트",
            "total_servants": sum(b["servant_count"] for b in priority_4_literature),
            "books": priority_4_literature
        },
        "priority_5_mythology": {
            "description": "신화 종합",
            "total_servants": sum(b["servant_count"] for b in priority_5_mythology),
            "books": priority_5_mythology
        },
        "priority_6_supplement": {
            "description": "보조 자료",
            "total_servants": sum(b["servant_count"] for b in priority_6_supplement),
            "books": priority_6_supplement
        }
    }

    # 통계
    total_books = len(AVAILABLE_BOOKS)
    total_servants_covered = len(set(
        s for books in BOOK_CATEGORIES.values() for s in books
    ))

    result["_summary"] = {
        "total_books": total_books,
        "total_servants_in_mapping": total_servants_covered,
        "total_keyword_mappings": len(SERVANT_KEYWORDS)
    }

    return result


def main():
    print("=" * 60)
    print("Generating book_list.json from FGO servant mappings")
    print("=" * 60)

    result = generate_book_list()

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\nSaved to: {OUTPUT_FILE}")

    # 통계 출력
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total books: {result['_summary']['total_books']}")
    print(f"Servants covered by books: {result['_summary']['total_servants_in_mapping']}")
    print(f"Keyword mappings: {result['_summary']['total_keyword_mappings']}")

    print("\nBy priority:")
    for key in ["priority_1_epic", "priority_2_legend", "priority_3_history",
                "priority_4_literature", "priority_5_mythology", "priority_6_supplement"]:
        data = result[key]
        print(f"  {key}: {len(data['books'])} books, {data['total_servants']} servant refs")


if __name__ == "__main__":
    main()
