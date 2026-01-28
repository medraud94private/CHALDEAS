"""
FGO 전체 서번트 → 구텐베르크 검색 키워드 완전판
"""

# 서번트 이름 → 검색 키워드 매핑
SERVANT_KEYWORDS = {
    # ============================================
    # 그리스/트로이
    # ============================================
    "Achilles": ["achilles", "iliad", "trojan war", "patroclus", "peleus"],
    "Hector": ["hector", "iliad", "trojan war", "troy", "priam"],
    "Paris": ["paris", "iliad", "helen of troy", "trojan"],
    "Penthesilea": ["penthesilea", "amazon queen", "trojan war"],
    "Odysseus": ["odysseus", "ulysses", "odyssey", "homer", "ithaca"],
    "Circe": ["circe", "odyssey", "witch", "aeaea"],
    "Jason": ["jason", "argonaut", "golden fleece", "medea", "argo"],
    "Medea": ["medea", "argonaut", "jason", "colchis", "euripides"],
    "Atalante": ["atalanta", "atalante", "argonaut", "arcadia", "calydonian"],
    "Heracles": ["hercules", "heracles", "twelve labors", "alcmena"],
    "Perseus": ["perseus", "medusa", "andromeda", "danae"],
    "Theseus": ["theseus", "minotaur", "ariadne", "athens", "labyrinth"],
    "Orion": ["orion", "artemis", "hunter", "constellation"],
    "Chiron": ["chiron", "centaur", "achilles teacher", "pelion"],
    "Asclepius": ["asclepius", "aesculapius", "medicine god", "apollo son"],
    "Europa": ["europa", "zeus bull", "crete", "phoenicia"],
    "Caenis": ["caenis", "caeneus", "poseidon", "lapith"],
    "Dioscuri": ["castor", "pollux", "dioscuri", "gemini", "leda"],
    "Medusa": ["medusa", "gorgon", "perseus", "athena"],
    "Euryale": ["euryale", "gorgon", "phorcys"],
    "Stheno": ["stheno", "gorgon", "immortal"],
    "Asterios": ["asterios", "minotaur", "crete", "pasiphae"],
    "Gorgon": ["gorgon", "medusa", "monster"],
    "Astraea": ["astraea", "justice", "virgo", "dike"],

    # ============================================
    # 메소포타미아
    # ============================================
    "Gilgamesh": ["gilgamesh", "uruk", "enkidu", "mesopotamia", "epic"],
    "Enkidu": ["enkidu", "gilgamesh", "clay", "humbaba"],
    "Ishtar": ["ishtar", "inanna", "babylon", "mesopotamia", "goddess"],
    "Ereshkigal": ["ereshkigal", "underworld", "irkalla", "kur"],
    "Tiamat": ["tiamat", "chaos", "babylon", "marduk"],

    # ============================================
    # 인도
    # ============================================
    "Arjuna": ["arjuna", "mahabharata", "pandava", "krishna", "bhagavad"],
    "Karna": ["karna", "mahabharata", "surya", "kunti"],
    "Rama": ["rama", "ramayana", "sita", "ravana", "ayodhya"],
    "Ashwatthama": ["ashwatthama", "drona", "mahabharata", "brahmastra"],
    "Parvati": ["parvati", "shiva", "hindu goddess", "durga"],
    "Lakshmi Bai": ["lakshmi bai", "rani", "jhansi", "1857 rebellion"],
    "Bhima": ["bhima", "mahabharata", "pandava", "hanuman son"],
    "Duryodhana": ["duryodhana", "mahabharata", "kaurava", "kurukshetra"],
    "Durga": ["durga", "mahishasura", "goddess", "shakti"],

    # ============================================
    # 켈트
    # ============================================
    "Cu Chulainn": ["cu chulainn", "cuchulain", "ulster", "setanta", "tain bo"],
    "Scathach": ["scathach", "shadow land", "dun scaith", "warrior woman"],
    "Fergus mac Roich": ["fergus", "ulster", "exile", "medb"],
    "Diarmuid Ua Duibhne": ["diarmuid", "fianna", "love spot", "grainne"],
    "Fionn mac Cumhaill": ["fionn", "finn mccool", "fianna", "fenian", "salmon"],
    "Medb": ["medb", "maeve", "connacht", "ulster cycle", "cattle raid"],
    "Manannan mac Lir": ["manannan", "sea god", "tuatha", "irish mythology"],

    # ============================================
    # 북유럽
    # ============================================
    "Siegfried": ["siegfried", "sigurd", "nibelungen", "fafnir", "dragon slayer"],
    "Sigurd": ["sigurd", "volsung", "fafnir", "brynhild", "regin"],
    "Brynhild": ["brynhild", "brunhild", "valkyrie", "sigurd", "gunnar"],
    "Valkyrie": ["valkyrie", "odin", "valhalla", "chooser of slain"],
    "Beowulf": ["beowulf", "grendel", "hrothgar", "geats"],
    "Eric Bloodaxe": ["eric bloodaxe", "viking", "norway", "york"],
    "Kriemhild": ["kriemhild", "nibelungen", "siegfried wife", "burgundy"],
    "Thrud": ["thrud", "thor daughter", "valkyrie"],
    "Hildr": ["hildr", "valkyrie", "hedin"],
    "Ortlinde": ["ortlinde", "valkyrie"],

    # ============================================
    # 아서왕
    # ============================================
    "Altria Pendragon": ["arthur", "king arthur", "excalibur", "camelot", "pendragon"],
    "Lancelot": ["lancelot", "round table", "guinevere", "du lac"],
    "Tristan": ["tristan", "isolde", "iseult", "cornwall", "mark"],
    "Gawain": ["gawain", "green knight", "round table", "lot"],
    "Mordred": ["mordred", "camlann", "round table", "rebellion"],
    "Bedivere": ["bedivere", "excalibur", "round table", "last knight"],
    "Merlin": ["merlin", "wizard", "arthur", "viviane", "nimue"],
    "Galahad": ["galahad", "holy grail", "round table", "pure knight"],
    "Percival": ["percival", "grail", "round table", "fisher king"],
    "Gareth": ["gareth", "round table", "lynette", "beaumains"],
    "Morgan": ["morgan le fay", "morgana", "avalon", "fairy"],
    "Oberon": ["oberon", "fairy king", "midsummer", "titania"],
    "Lady Avalon": ["avalon", "lady lake", "excalibur"],

    # ============================================
    # 샤를마뉴
    # ============================================
    "Charlemagne": ["charlemagne", "carolingian", "roland", "holy roman"],
    "Roland": ["roland", "chanson", "charlemagne", "roncevaux", "durandal"],
    "Astolfo": ["astolfo", "orlando furioso", "paladin", "hippogriff"],
    "Bradamante": ["bradamante", "orlando furioso", "ruggiero", "female knight"],
    "Mandricardo": ["mandricardo", "orlando furioso", "hector armor"],

    # ============================================
    # 로마
    # ============================================
    "Romulus": ["romulus", "remus", "rome foundation", "mars son"],
    "Gaius Julius Caesar": ["julius caesar", "caesar", "rubicon", "rome", "gallic"],
    "Nero Claudius": ["nero", "roman emperor", "rome", "fire", "fiddle"],
    "Caligula": ["caligula", "roman emperor", "gaius", "mad"],
    "Spartacus": ["spartacus", "gladiator", "slave revolt", "thrace"],
    "Boudica": ["boudica", "boudicca", "iceni", "britain", "revolt"],
    "Locusta": ["locusta", "poison", "nero", "roman"],

    # ============================================
    # 이집트
    # ============================================
    "Ozymandias": ["ramesses", "ozymandias", "egypt pharaoh", "shelley"],
    "Nitocris": ["nitocris", "egypt queen", "pharaoh", "herodotus"],
    "Cleopatra": ["cleopatra", "egypt", "ptolemy", "antony", "caesar"],

    # ============================================
    # 페르시아/중동
    # ============================================
    "Arash": ["arash", "persian", "archer", "kamangir", "iran"],
    "Darius III": ["darius", "persia", "achaemenid", "alexander"],
    "Scheherazade": ["scheherazade", "arabian nights", "thousand one nights", "shahryar"],
    "Queen of Sheba": ["queen sheba", "solomon", "ethiopia", "makeda"],
    "Semiramis": ["semiramis", "assyria", "babylon queen", "hanging gardens"],

    # ============================================
    # 성경/유대
    # ============================================
    "David": ["king david", "goliath", "psalms", "israel", "bathsheba"],
    "Solomon": ["king solomon", "wisdom", "temple", "sheba", "proverbs"],
    "Martha": ["martha", "bethany", "lazarus", "bible", "tarasque"],
    "Salome": ["salome", "john baptist", "herod", "dance"],

    # ============================================
    # 문학
    # ============================================
    "Sherlock Holmes": ["sherlock holmes", "conan doyle", "detective", "watson"],
    "James Moriarty": ["moriarty", "professor", "sherlock", "criminal"],
    "Frankenstein": ["frankenstein", "mary shelley", "monster", "creature"],
    "Phantom of the Opera": ["phantom opera", "erik", "gaston leroux", "christine"],
    "Henry Jekyll": ["jekyll", "hyde", "stevenson", "transformation"],
    "Edmond Dantes": ["monte cristo", "dantes", "dumas", "chateau if"],
    "Don Quixote": ["don quixote", "cervantes", "sancho", "windmill", "la mancha"],
    "Hans Christian Andersen": ["hans andersen", "fairy tales", "denmark", "mermaid"],
    "William Shakespeare": ["shakespeare", "hamlet", "macbeth", "othello", "bard"],
    "Dante Alighieri": ["dante alighieri", "divine comedy", "inferno", "beatrice"],
    "Murasaki Shikibu": ["murasaki shikibu", "tale of genji", "heian"],
    "Sei Shounagon": ["sei shonagon", "pillow book", "heian"],
    "Nursery Rhyme": ["nursery rhyme", "fairy tale", "alice", "wonderland"],
    "Voyager": ["voyager", "little prince", "saint exupery"],

    # ============================================
    # 프랑스 역사
    # ============================================
    "Napoleon": ["napoleon", "bonaparte", "waterloo", "emperor"],
    "Marie Antoinette": ["marie antoinette", "french revolution", "versailles", "guillotine"],
    "Jeanne d'Arc": ["joan of arc", "jeanne darc", "orleans", "maid", "rouen"],
    "Chevalier d'Eon": ["chevalier eon", "spy", "dragoon", "louis xv"],
    "Charles-Henri Sanson": ["sanson", "executioner", "guillotine", "paris"],
    "Charlotte Corday": ["charlotte corday", "marat", "assassination", "girondist"],
    "Gilles de Rais": ["gilles de rais", "bluebeard", "joan of arc", "marshal"],

    # ============================================
    # 르네상스/예술
    # ============================================
    "Leonardo da Vinci": ["leonardo", "da vinci", "renaissance", "mona lisa"],
    "Van Gogh": ["van gogh", "painter", "starry night", "ear"],

    # ============================================
    # 그리스 기타
    # ============================================
    "Iskandar": ["alexander", "great", "macedon", "persia", "conquest"],
    "Leonidas I": ["leonidas", "sparta", "thermopylae", "300", "xerxes"],

    # ============================================
    # 동유럽
    # ============================================
    "Vlad III": ["vlad", "dracula", "impaler", "wallachia", "tepes"],
    "Ivan the Terrible": ["ivan", "terrible", "tsar", "russia", "oprichnina"],
    "Anastasia": ["anastasia", "romanov", "russia", "grand duchess"],
    "Dobrynya Nikitich": ["dobrynya", "bogatyr", "russian", "bylina", "dragon"],
    "Grigori Rasputin": ["rasputin", "monk", "russia", "romanov"],

    # ============================================
    # 중국
    # ============================================
    "Qin Shi Huang": ["qin shi huang", "first emperor", "china", "terracotta"],
    "Wu Zetian": ["wu zetian", "empress", "tang", "china", "zhou"],
    "Lu Bu Fengxian": ["lu bu", "three kingdoms", "red hare", "diaochan"],
    "Zhuge Liang": ["zhuge liang", "kongming", "three kingdoms", "strategist"],
    "Xiang Yu": ["xiang yu", "chu", "han dynasty", "liu bang"],
    "Chen Gong": ["chen gong", "three kingdoms", "lu bu advisor"],
    "Red Hare": ["red hare", "lu bu", "three kingdoms", "horse"],
    "Prince of Lan Ling": ["lanling", "prince", "mask", "northern qi"],
    "Qin Liangyu": ["qin liangyu", "ming", "sichuan", "white pole"],
    "Yu Mei-ren": ["yu meiren", "consort yu", "xiang yu", "poppy"],
    "Yang Guifei": ["yang guifei", "tang", "xuanzong", "beauty"],
    "Xuanzang Sanzang": ["xuanzang", "journey west", "tripitaka", "pilgrimage"],
    "Nezha": ["nezha", "lotus", "li jing", "deification gods"],
    "Taigong Wang": ["jiang ziya", "taigong", "zhou", "fengshen"],
    "Zhang Jue": ["zhang jue", "yellow turban", "three kingdoms"],
    "Huyan Zhuo": ["huyan zhuo", "water margin", "outlaws marsh"],
    "Huang Feihu": ["huang feihu", "fengshen", "investiture gods"],

    # ============================================
    # 일본
    # ============================================
    "Miyamoto Musashi": ["musashi", "miyamoto", "five rings", "samurai", "ganryu"],
    "Oda Nobunaga": ["nobunaga", "oda", "sengoku", "unification"],
    "Okita Souji": ["okita soji", "shinsengumi", "bakumatsu"],
    "Hijikata Toshizo": ["hijikata", "shinsengumi", "hakodate"],
    "Saito Hajime": ["saito hajime", "shinsengumi", "mibu wolves"],
    "Sakamoto Ryouma": ["sakamoto ryoma", "bakumatsu", "meiji"],
    "Ushiwakamaru": ["yoshitsune", "minamoto", "benkei", "genpei"],
    "Musashibou Benkei": ["benkei", "yoshitsune", "warrior monk"],
    "Tomoe Gozen": ["tomoe gozen", "female samurai", "yoshinaka"],
    "Minamoto-no-Raikou": ["minamoto raikou", "yorimitsu", "shuten doji"],
    "Sakata Kintoki": ["kintoki", "golden boy", "kintaro", "raikou"],
    "Watanabe-no-Tsuna": ["watanabe tsuna", "ibaraki", "rashomon"],
    "Shuten-Douji": ["shuten doji", "oni", "ooe mountain"],
    "Ibaraki-Douji": ["ibaraki doji", "oni", "arm"],
    "Tamamo-no-Mae": ["tamamo", "fox", "nine tails", "daji"],
    "Kiyohime": ["kiyohime", "anchin", "dojoji", "serpent"],
    "Suzuka Gozen": ["suzuka gozen", "demon", "suzuka mountain"],
    "Ibuki-Douji": ["ibuki doji", "yamata orochi", "dragon"],
    "Taira-no-Kagekiyo": ["kagekiyo", "taira", "genpei"],
    "Nagao Kagetora": ["uesugi kenshin", "nagao", "sengoku", "echigo"],
    "Mori Nagayoshi": ["mori nagayoshi", "demon", "sengoku"],
    "Himiko": ["himiko", "yamatai", "shaman queen", "japan"],
    "Sen-no-Rikyu": ["sen rikyu", "tea ceremony", "wabi sabi"],
    "Takasugi Shinsaku": ["takasugi", "choshu", "bakumatsu"],
    "Senji Muramasa": ["muramasa", "swordsmith", "demon blade"],

    # ============================================
    # 미국/서부
    # ============================================
    "Geronimo": ["geronimo", "apache", "native american", "warrior"],
    "Billy the Kid": ["billy kid", "outlaw", "wild west", "bonney"],
    "Calamity Jane": ["calamity jane", "wild west", "deadwood", "hickok"],
    "Paul Bunyan": ["paul bunyan", "lumberjack", "babe blue ox", "folklore"],
    "Thomas Edison": ["thomas edison", "inventor", "electric", "bulb"],
    "Nikola Tesla": ["nikola tesla", "electricity", "inventor", "ac current"],

    # ============================================
    # 해적
    # ============================================
    "Francis Drake": ["francis drake", "privateer", "armada", "golden hind"],
    "Edward Teach": ["blackbeard", "edward teach", "pirate", "queen anne"],
    "Anne Bonny": ["anne bonny", "mary read", "pirate", "caribbean"],
    "Bartholomew Roberts": ["bartholomew roberts", "black bart", "pirate"],
    "Christopher Columbus": ["columbus", "christopher", "america discovery", "1492"],

    # ============================================
    # 아즈텍/마야
    # ============================================
    "Quetzalcoatl": ["quetzalcoatl", "feathered serpent", "aztec", "toltec"],
    "Tezcatlipoca": ["tezcatlipoca", "smoking mirror", "aztec", "jaguar"],
    "Jaguar Warrior": ["jaguar warrior", "aztec", "mesoamerica"],
    "Kukulcan": ["kukulcan", "maya", "feathered serpent"],
    "Tlaloc": ["tlaloc", "rain god", "aztec"],

    # ============================================
    # 기타 역사
    # ============================================
    "Zenobia": ["zenobia", "palmyra", "queen", "roman"],
    "Jacques de Molay": ["jacques molay", "templar", "knights templar", "philip iv"],
    "Florence Nightingale": ["florence nightingale", "nurse", "crimea", "lamp"],
    "Attila": ["attila", "hun", "scourge god", "catalaunian"],
    "Altera": ["attila", "hun", "scourge god"],
    "Helena Blavatsky": ["blavatsky", "theosophy", "occult", "isis unveiled"],
    "Paracelsus": ["paracelsus", "alchemy", "medicine", "swiss"],
    "Avicebron": ["avicebron", "solomon ibn gabirol", "golem", "jewish"],
    "Abigail Williams": ["abigail williams", "salem witch", "massachusetts", "trials"],
    "Pope Johanna": ["pope joan", "female pope", "legend"],
    "Konstantinos XI": ["constantine xi", "fall constantinople", "1453", "byzantine"],
    "Robin Hood": ["robin hood", "sherwood", "outlaw", "merry men", "nottingham"],
    "William Tell": ["william tell", "apple", "crossbow", "swiss"],
    "Kyokutei Bakin": ["bakin", "hakkenden", "edo", "author"],
    "Mary Anning": ["mary anning", "fossil", "lyme regis", "paleontology"],
    "Antonio Salieri": ["salieri", "composer", "mozart rival"],
    "Wolfgang Amadeus Mozart": ["mozart", "amadeus", "composer", "vienna"],

    # ============================================
    # FGO 오리지널/Fate 캐릭터 (구텐베르크 매칭 어려움)
    # ============================================
    # Emiya, Mash, BB, Koyanskaya, Mysterious Heroine 등은 제외
}

# 서번트가 매칭되는 구텐베르크 책 카테고리
BOOK_CATEGORIES = {
    "iliad_homer": ["Achilles", "Hector", "Paris", "Penthesilea", "Diomedes"],
    "odyssey_homer": ["Odysseus", "Circe", "Penelope", "Polyphemus"],
    "argonautica": ["Jason", "Medea", "Atalante", "Heracles"],
    "metamorphoses_ovid": ["Medusa", "Perseus", "Europa", "Orion"],
    "gilgamesh_epic": ["Gilgamesh", "Enkidu"],
    "mahabharata": ["Arjuna", "Karna", "Ashwatthama", "Bhima", "Duryodhana"],
    "ramayana": ["Rama"],
    "le_morte_darthur": ["Altria Pendragon", "Lancelot", "Tristan", "Gawain", "Mordred", "Bedivere", "Galahad", "Percival", "Gareth"],
    "idylls_of_the_king": ["Altria Pendragon", "Lancelot", "Merlin"],
    "tristan_and_iseult": ["Tristan"],
    "cattle_raid_cooley": ["Cu Chulainn", "Fergus mac Roich", "Medb"],
    "celtic_mythology": ["Cu Chulainn", "Scathach", "Fionn mac Cumhaill", "Diarmuid Ua Duibhne"],
    "gods_and_fighting_men": ["Fionn mac Cumhaill", "Diarmuid Ua Duibhne"],
    "nibelungenlied": ["Siegfried", "Kriemhild", "Brynhild"],
    "volsunga_saga": ["Sigurd", "Brynhild"],
    "beowulf": ["Beowulf"],
    "poetic_edda": ["Valkyrie", "Brynhild", "Sigurd"],
    "prose_edda": ["Valkyrie"],
    "song_of_roland": ["Charlemagne", "Roland"],
    "orlando_furioso": ["Astolfo", "Bradamante", "Mandricardo", "Charlemagne", "Roland"],
    "plutarch_lives": ["Iskandar", "Julius Caesar", "Cleopatra", "Romulus", "Spartacus", "Alexander"],
    "herodotus_histories": ["Leonidas I", "Darius III", "Xerxes"],
    "divine_comedy_dante": ["Dante Alighieri"],
    "frankenstein": ["Frankenstein"],
    "phantom_of_opera": ["Phantom of the Opera"],
    "count_of_monte_cristo": ["Edmond Dantes"],
    "sherlock_holmes_complete": ["Sherlock Holmes", "James Moriarty"],
    "dr_jekyll_mr_hyde": ["Henry Jekyll"],
    "don_quixote": ["Don Quixote"],
    "complete_shakespeare": ["William Shakespeare"],
    "andersen_fairy_tales": ["Hans Christian Andersen"],
    "arabian_nights": ["Scheherazade"],
    "napoleon_biography": ["Napoleon"],
    "french_revolution_carlyle": ["Marie Antoinette", "Charlotte Corday", "Charles-Henri Sanson"],
    "joan_of_arc_twain": ["Jeanne d'Arc", "Gilles de Rais"],
    "lives_of_artists_vasari": ["Leonardo da Vinci"],
    "book_of_five_rings": ["Miyamoto Musashi"],
    "geronimo_story": ["Geronimo"],
    "greek_roman_myths": ["Heracles", "Perseus", "Theseus", "Medusa", "Europa", "Orion"],
    "bulfinch_mythology": ["Heracles", "Perseus", "Theseus", "Jason", "Achilles"],
    "egyptian_mythology": ["Ozymandias", "Nitocris", "Cleopatra"],
    "japanese_mythology": ["Tamamo-no-Mae", "Shuten-Douji", "Kiyohime", "Suzuka Gozen"],
    "chinese_mythology": ["Nezha", "Xuanzang Sanzang"],
    "norse_mythology": ["Valkyrie", "Siegfried", "Brynhild"],
    "babylonian_legends": ["Gilgamesh", "Ishtar", "Tiamat"],
}

if __name__ == "__main__":
    print(f"Total keyword mappings: {len(SERVANT_KEYWORDS)}")
    print(f"Total book categories: {len(BOOK_CATEGORIES)}")
