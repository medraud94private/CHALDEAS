"""Download all FGO/History/Mythology related books from Project Gutenberg - Extended V2

추가된 서번트 커버:
- Vlad III (Dracula)
- Mephistopheles (Faust)
- Nero, Caligula (Roman Emperors)
- David, Solomon, Martha, Salome (Bible)
- Robin Hood
- Pirates (Blackbeard, Drake, Anne Bonny)
- Russian (Ivan, Anastasia, Dobrynya)
- Chinese (Qin Shi Huang, Lu Bu, Zhuge Liang)
- Aztec/Maya (Quetzalcoatl)
- Theseus, Perseus (Greek heroes)
- Britomart (Faerie Queene)
"""
import requests
import os
import time

# 책 목록: (Gutenberg ID, 파일명, 카테고리, 관련 서번트)
BOOKS = [
    # =========================================
    # 🔴 NEW - 빠진 서번트 커버
    # =========================================

    # Vlad III / Dracula
    (345, "dracula_stoker", "literary", "Vlad III, Carmilla background"),

    # Mephistopheles / Faust
    (14591, "faust_goethe", "literary", "Mephistopheles"),
    (779, "doctor_faustus_marlowe", "literary", "Mephistopheles"),

    # Roman Emperors (Nero, Caligula, etc.)
    (6400, "lives_of_caesars_suetonius", "history", "Nero, Caligula, Caesar, Romulus"),
    (15886, "annals_tacitus", "history", "Nero, Roman history"),
    (10828, "history_rome_livy", "history", "Romulus, Roman foundation"),

    # Bible related (David, Solomon, Martha, Salome, Queen of Sheba)
    (8300, "bible_kjv_old_testament", "religion", "David, Solomon, Queen of Sheba"),
    (8044, "bible_kjv_new_testament", "religion", "Martha, Salome, Jesus stories"),
    (2848, "josephus_jewish_antiquities", "history", "Jewish history, Solomon"),

    # Robin Hood
    (10148, "robin_hood_pyle", "legend", "Robin Hood"),
    (6500, "robin_hood_ballads", "legend", "Robin Hood"),

    # Pirates (Edward Teach, Francis Drake, Anne Bonny, Bartholomew Roberts)
    (40580, "history_of_piracy", "history", "Blackbeard, Anne Bonny, pirates"),
    (26350, "buccaneers_marooners", "history", "Pirates, Caribbean"),
    (8411, "sir_francis_drake", "history", "Francis Drake"),

    # Russian (Ivan the Terrible, Anastasia, Dobrynya Nikitich)
    (45895, "russian_fairy_tales", "folklore", "Russian servants background"),
    (28536, "cossack_fairy_tales", "folklore", "Russian/Ukrainian folklore"),
    (14300, "hero_tales_finland", "folklore", "Finnish/Russian epics"),

    # Chinese (Qin Shi Huang, Lu Bu, Zhuge Liang, Wu Zetian)
    (17147, "romance_three_kingdoms_partial", "chinese", "Lu Bu, Zhuge Liang, Red Hare"),
    (3341, "chinese_fairy_book", "folklore", "Chinese mythology background"),
    (13323, "myths_china", "mythology", "Chinese servants background"),

    # Journey to the West (Xuanzang Sanzang)
    (23962, "journey_to_west", "chinese", "Xuanzang Sanzang"),

    # Aztec/Maya (Quetzalcoatl, Tezcatlipoca)
    (20008, "popol_vuh", "mythology", "Maya mythology, Quetzalcoatl"),
    (1535, "conquest_of_mexico_prescott", "history", "Aztec history"),
    (19601, "myths_of_mexico_peru", "mythology", "Aztec/Maya servants"),

    # Greek heroes expanded (Theseus, Perseus, Europa)
    (22381, "theseus_kingsley", "greek", "Theseus"),
    (22382, "perseus_kingsley", "greek", "Perseus, Medusa"),

    # Faerie Queene (Britomart)
    (15272, "faerie_queene_spenser", "literary", "Britomart"),
    (590, "faerie_queene_book1", "literary", "Faerie Queene canto 1"),

    # Paul Bunyan / American folklore
    (31761, "paul_bunyan", "folklore", "Paul Bunyan"),
    (32384, "american_myths_legends", "folklore", "American servants"),

    # Wild West (Billy the Kid, Calamity Jane)
    (14322, "calamity_jane_autobiography", "history", "Calamity Jane"),
    (46652, "wild_west_stories", "history", "Billy the Kid, Wild West"),

    # Salem Witch Trials (Abigail Williams)
    (28513, "salem_witchcraft", "history", "Abigail Williams, Salem"),
    (12829, "wonders_invisible_world", "history", "Salem witch trials"),

    # Semiramis / Assyrian
    (18728, "semiramis_queen", "history", "Semiramis"),

    # Van Gogh (letters)
    (28427, "van_gogh_letters", "art", "Van Gogh"),

    # =========================================
    # 기존 책 목록 (유지)
    # =========================================

    # Tier 1: 최우선 (이미 있음)
    (1251, "le_morte_darthur", "arthurian", "Arthur, Lancelot, etc"),
    (6130, "iliad_homer", "greek", "Achilles, Hector, Paris"),
    (228, "aeneid_virgil", "roman", "Aeneas, Romulus"),

    # Greek/Troy
    (1727, "odyssey_homer", "greek", "Odysseus, Circe, Penelope"),
    (830, "argonautica", "greek", "Jason, Medea, Atalante"),
    (674, "plutarch_lives", "greek", "Alexander, Caesar, Cleopatra, 50+"),
    (2131, "herodotus_histories", "greek", "Leonidas, Darius III, Xerxes"),
    (26073, "metamorphoses_ovid", "roman", "Medusa, various myths"),
    (11681, "gilgamesh_epic", "mesopotamian", "Gilgamesh, Enkidu"),

    # Norse
    (1152, "volsunga_saga", "norse", "Sigurd, Brynhild"),
    (7321, "nibelungenlied", "germanic", "Siegfried, Brynhild, Kriemhild"),
    (14726, "poetic_edda", "norse", "Valkyrie, Norse gods"),
    (18947, "prose_edda", "norse", "Norse mythology"),
    (16328, "beowulf", "germanic", "Beowulf"),

    # Celtic
    (16464, "cattle_raid_cooley", "celtic", "Cu Chulainn, Fergus, Medb"),
    (14465, "gods_and_fighting_men", "celtic", "Fionn, Diarmuid"),
    (2892, "irish_fairy_tales", "celtic", "Irish mythology"),

    # Indian
    (24869, "ramayana", "indian", "Rama"),
    (7864, "mahabharata", "indian", "Arjuna, Karna, Ashwatthama"),

    # Arthurian
    (610, "idylls_of_the_king", "arthurian", "Arthurian knights"),
    (14244, "tristan_and_iseult", "arthurian", "Tristan"),
    (1972, "history_british_kings", "arthurian", "Arthur history"),

    # Carolingian
    (3747, "orlando_furioso", "carolingian", "Astolfo, Bradamante"),
    (391, "song_of_roland", "carolingian", "Charlemagne, Roland"),

    # Literary servants
    (84, "frankenstein", "literary", "Frankenstein"),
    (1184, "count_of_monte_cristo", "literary", "Edmond Dantes"),
    (1661, "sherlock_holmes_complete", "literary", "Sherlock Holmes, Moriarty"),
    (43, "dr_jekyll_mr_hyde", "literary", "Jekyll & Hyde"),
    (996, "don_quixote", "literary", "Don Quixote"),
    (175, "phantom_of_opera", "literary", "Phantom"),
    (100, "complete_shakespeare", "literary", "Shakespeare"),
    (2000, "divine_comedy_dante", "literary", "Dante"),
    (5200, "paradise_lost_milton", "literary", "Paradise Lost"),

    # History/Biography
    (1351, "joan_of_arc_twain", "history", "Jeanne d'Arc"),
    (3567, "napoleon_biography", "history", "Napoleon"),
    (1301, "french_revolution_carlyle", "history", "Marie Antoinette, Sanson"),
    (25759, "lives_of_artists_vasari", "history", "Leonardo da Vinci"),
    (17007, "book_of_five_rings", "japanese", "Miyamoto Musashi"),
    (24439, "geronimo_story", "history", "Geronimo"),
    (1232, "prince_machiavelli", "history", "Machiavelli"),

    # Mythology compilations
    (4928, "bulfinch_mythology", "mythology", "General mythology"),
    (17321, "babylonian_legends", "mesopotamian", "Mesopotamian"),
    (7145, "book_of_dead_egyptian", "egyptian", "Egyptian"),

    # Fairy tales
    (1597, "andersen_fairy_tales", "literary", "Hans Andersen, Nursery Rhyme"),
    (2591, "grimm_fairy_tales", "literary", "Nursery Rhyme"),
    (4018, "japanese_fairy_tales", "japanese", "Japanese folklore"),
    (932, "arabian_nights_burton", "arabian", "Scheherazade"),
]

OUTPUT_DIR = "poc/data/book_samples"


def download_book(gutenberg_id: int, filename: str, category: str, servants: str):
    """Download a single book from Gutenberg"""
    filepath = f"{OUTPUT_DIR}/{filename}.txt"

    # 이미 존재하면 스킵
    if os.path.exists(filepath):
        size = os.path.getsize(filepath)
        if size > 10000:  # 10KB 이상이면 유효
            print(f"  [SKIP] {filename} already exists ({size:,} bytes)")
            return "skip"

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
                print(f"  [OK] {filename} ({len(resp.text):,} chars)")
                print(f"       Servants: {servants}")
                return "success"
        except Exception as e:
            continue

    print(f"  [FAIL] {filename} (ID: {gutenberg_id})")
    return "fail"


def main():
    print("=" * 70)
    print("Downloading FGO-related books from Project Gutenberg (V2)")
    print("=" * 70)
    print(f"Total books in list: {len(BOOKS)}")
    print()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    stats = {"success": 0, "skip": 0, "fail": 0}

    for i, (gid, name, cat, servants) in enumerate(BOOKS):
        print(f"[{i+1}/{len(BOOKS)}] {name} ({cat})...")

        result = download_book(gid, name, cat, servants)
        stats[result] += 1

        # Rate limiting (only if downloaded)
        if result == "success":
            time.sleep(1)

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total: {len(BOOKS)}")
    print(f"Downloaded: {stats['success']}")
    print(f"Skipped (existing): {stats['skip']}")
    print(f"Failed: {stats['fail']}")

    # 카테고리별 통계
    categories = {}
    for _, name, cat, _ in BOOKS:
        filepath = f"{OUTPUT_DIR}/{name}.txt"
        if os.path.exists(filepath):
            categories[cat] = categories.get(cat, 0) + 1

    print("\nBy category:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
