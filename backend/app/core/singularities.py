"""
CHALDEAS Singularities & Lostbelts

FGO 세계관 기반 큐레이션된 역사 시대 분류
유저들에게 역사적 맥락과 함께 이벤트를 탐색할 수 있는 가이드 제공
"""
from typing import List, Dict, Any
from dataclasses import dataclass, asdict


@dataclass
class HistoricalEra:
    """역사 시대 정의"""
    id: str
    name: str
    name_ko: str
    name_jp: str
    era_type: str  # singularity, lostbelt, special
    order: int
    year_start: int  # BCE는 음수
    year_end: int
    location: str
    description: str
    description_ko: str
    keywords: List[str]  # 검색 키워드
    related_figures: List[str]  # 관련 인물
    image_url: str = ""


# 7개 특이점 (Singularities)
SINGULARITIES: List[HistoricalEra] = [
    HistoricalEra(
        id="singularity_f",
        name="Fuyuki - Flame Contaminated City",
        name_ko="특이점 F - 불염오염도시 퓨이네스",
        name_jp="特異点F 炎上汚染都市 冬木",
        era_type="singularity",
        order=0,
        year_start=2004,
        year_end=2004,
        location="Fuyuki, Japan",
        description="The starting point of the Grand Order. A city consumed by flames after a Holy Grail War gone wrong.",
        description_ko="그랜드 오더의 시작점. 성배전쟁이 틀어지면서 불타오른 도시.",
        keywords=["holy grail", "grail war", "fuyuki", "2004"],
        related_figures=["Mash Kyrielight", "Caster Cu Chulainn"]
    ),
    HistoricalEra(
        id="singularity_1",
        name="Orleans - Wicked Dragon Hundred Years' War",
        name_ko="특이점 1 - 백년전쟁의 용 오를레앙",
        name_jp="第一特異点 邪竜百年戦争 オルレアン",
        era_type="singularity",
        order=1,
        year_start=1431,
        year_end=1431,
        location="France",
        description="The Hundred Years' War era, where Joan of Arc was burned at the stake. Dragons and revenge consume France.",
        description_ko="잔다르크가 화형당한 백년전쟁 시대. 용과 복수가 프랑스를 집어삼킨다.",
        keywords=["hundred years war", "joan of arc", "france", "orleans", "1431", "medieval"],
        related_figures=["Jeanne d'Arc", "Gilles de Rais", "Marie Antoinette", "Amadeus Mozart"]
    ),
    HistoricalEra(
        id="singularity_2",
        name="Septem - Eternal Madness Empire",
        name_ko="특이점 2 - 영원 광염제국 세프템",
        name_jp="第二特異点 永続狂気帝国 セプテム",
        era_type="singularity",
        order=2,
        year_start=60,
        year_end=60,
        location="Roman Empire",
        description="The Roman Empire at its height under Emperor Nero. United Servants wage war against Rome.",
        description_ko="네로 황제 치하의 로마 제국 전성기. 연합 서번트들이 로마에 맞서 싸운다.",
        keywords=["rome", "roman empire", "nero", "caesar", "60 CE", "ancient rome"],
        related_figures=["Nero Claudius", "Romulus", "Julius Caesar", "Caligula", "Boudica"]
    ),
    HistoricalEra(
        id="singularity_3",
        name="Okeanos - Sealed Ends of the Four Seas",
        name_ko="특이점 3 - 봉쇄종말사해 오케아노스",
        name_jp="第三特異点 封鎖終局四海 オケアノス",
        era_type="singularity",
        order=3,
        year_start=1573,
        year_end=1573,
        location="Atlantic Ocean",
        description="The Age of Exploration. Pirates, adventurers, and legendary ships sail the endless seas.",
        description_ko="대항해시대. 해적과 모험가, 전설의 배들이 끝없는 바다를 항해한다.",
        keywords=["age of exploration", "pirates", "1573", "atlantic", "drake", "columbus", "jason"],
        related_figures=["Francis Drake", "Blackbeard", "Jason", "Medea", "Heracles"]
    ),
    HistoricalEra(
        id="singularity_4",
        name="London - Death World in the City of Demonic Fog",
        name_ko="특이점 4 - 사계마폭도시 런던",
        name_jp="第四特異点 死界魔霧都市 ロンドン",
        era_type="singularity",
        order=4,
        year_start=1888,
        year_end=1888,
        location="London, England",
        description="Victorian London shrouded in demonic fog. Jack the Ripper's era meets magical threats.",
        description_ko="악마적 안개에 휩싸인 빅토리아 시대 런던. 잭 더 리퍼의 시대가 마술적 위협과 만난다.",
        keywords=["london", "1888", "victorian", "jack the ripper", "industrial revolution", "fog"],
        related_figures=["Mordred", "Jack the Ripper", "Frankenstein", "Nikola Tesla", "Charles Babbage"]
    ),
    HistoricalEra(
        id="singularity_5",
        name="E Pluribus Unum - North American Myth War",
        name_ko="특이점 5 - 북미신화대전 이 플루리버스 우눔",
        name_jp="第五特異点 北米神話大戦 イ・プルーリバス・ウナム",
        era_type="singularity",
        order=5,
        year_start=1783,
        year_end=1783,
        location="North America",
        description="American Revolutionary War era. Celtic and Native American myths clash on the new continent.",
        description_ko="미국 독립전쟁 시대. 켈트와 아메리카 원주민 신화가 신대륙에서 충돌한다.",
        keywords=["american revolution", "1783", "north america", "celtic", "native american", "independence"],
        related_figures=["Cu Chulainn", "Scathach", "Medb", "Geronimo", "Florence Nightingale"]
    ),
    HistoricalEra(
        id="singularity_6",
        name="Camelot - Sacred Round Table Realm",
        name_ko="특이점 6 - 신성원탁영역 캐멀롯",
        name_jp="第六特異点 神聖円卓領域 キャメロット",
        era_type="singularity",
        order=6,
        year_start=1273,
        year_end=1273,
        location="Jerusalem / Holy Land",
        description="The Crusades era. The Lion King's Camelot descends upon the Holy Land.",
        description_ko="십자군 시대. 사자왕의 캐멀롯이 성지에 강림한다.",
        keywords=["crusades", "1273", "jerusalem", "camelot", "round table", "holy land", "knights"],
        related_figures=["Artoria Pendragon", "Bedivere", "Lancelot", "Gawain", "Ozymandias", "Nitocris"]
    ),
    HistoricalEra(
        id="singularity_7",
        name="Babylonia - Absolute Demonic Front",
        name_ko="특이점 7 - 절대마수전선 바빌로니아",
        name_jp="第七特異点 絶対魔獣戦線 バビロニア",
        era_type="singularity",
        order=7,
        year_start=-2655,
        year_end=-2655,
        location="Mesopotamia",
        description="Ancient Mesopotamia, the cradle of civilization. The final battle against the Beasts of Humanity.",
        description_ko="문명의 요람, 고대 메소포타미아. 인류의 짐승에 맞선 최종 결전.",
        keywords=["mesopotamia", "babylonia", "gilgamesh", "sumeria", "2655 BCE", "uruk", "ancient"],
        related_figures=["Gilgamesh", "Enkidu", "Ishtar", "Ereshkigal", "Quetzalcoatl", "Merlin"]
    ),
]

# 솔로몬의 시대
SOLOMON_ERA = HistoricalEra(
    id="solomon",
    name="Solomon - The Time of the Final Singularity",
    name_ko="종장 - 솔로몬의 시대",
    name_jp="終局特異点 冠位時間神殿 ソロモン",
    era_type="special",
    order=8,
    year_start=-970,
    year_end=-931,
    location="Jerusalem",
    description="The reign of King Solomon, the wisest king. The Temple of Time awaits at the end of all singularities.",
    description_ko="가장 지혜로운 왕 솔로몬의 치세. 모든 특이점의 끝에서 시간신전이 기다린다.",
    keywords=["solomon", "jerusalem", "970 BCE", "temple", "wisdom", "israel", "king"],
    related_figures=["King Solomon", "Goetia", "David"]
)

# 7개 이문대 (Lostbelts)
LOSTBELTS: List[HistoricalEra] = [
    HistoricalEra(
        id="lostbelt_1",
        name="Anastasia - Permafrost Empire",
        name_ko="이문대 1 - 영구동토제국 아나스타시아",
        name_jp="Lostbelt No.1 永久凍土帝国 アナスタシア",
        era_type="lostbelt",
        order=1,
        year_start=1570,
        year_end=1570,
        location="Russia",
        description="An alternate Russia where Ivan the Terrible's rule never ended, frozen in eternal ice.",
        description_ko="이반 뇌제의 통치가 끝나지 않은 대체 러시아. 영원한 얼음에 갇혀있다.",
        keywords=["russia", "1570", "ivan the terrible", "tsar", "permafrost", "yaga"],
        related_figures=["Ivan the Terrible", "Anastasia", "Atalante Alter", "Avicebron"]
    ),
    HistoricalEra(
        id="lostbelt_2",
        name="Gotterdammerung - Eternal Ice-Flame Century",
        name_ko="이문대 2 - 무간빙염세기 게팅스머그",
        name_jp="Lostbelt No.2 無間氷焔世紀 ゲッテルデメルング",
        era_type="lostbelt",
        order=2,
        year_start=-1000,
        year_end=-1000,
        location="Scandinavia",
        description="Norse mythology made real. A world where Ragnarok is perpetually about to begin.",
        description_ko="실현된 북유럽 신화. 라그나로크가 영원히 시작되려 하는 세계.",
        keywords=["scandinavia", "norse", "ragnarok", "1000 BCE", "valkyrie", "surtr"],
        related_figures=["Scathach-Skadi", "Brynhildr", "Sigurd", "Napoleon", "Surtr"]
    ),
    HistoricalEra(
        id="lostbelt_3",
        name="SIN - Land of Unified Knowledge",
        name_ko="이문대 3 - 인지통합진국 SIN",
        name_jp="Lostbelt No.3 人智統合真国 シン",
        era_type="lostbelt",
        order=3,
        year_start=-210,
        year_end=-210,
        location="China",
        description="Qin Shi Huang's immortal empire. A utopia where humanity evolved beyond conflict.",
        description_ko="진시황의 불멸 제국. 인류가 갈등을 초월하여 진화한 유토피아.",
        keywords=["china", "qin", "210 BCE", "first emperor", "terracotta", "immortal"],
        related_figures=["Qin Shi Huang", "Yu Mei-ren", "Xiang Yu", "Spartacus", "Jing Ke"]
    ),
    HistoricalEra(
        id="lostbelt_4",
        name="Yuga Kshetra - Genesis Destruction Cycle",
        name_ko="이문대 4 - 창세멸망윤회 유가크셰트라",
        name_jp="Lostbelt No.4 創世滅亡輪廻 ユガ・クシェートラ",
        era_type="lostbelt",
        order=4,
        year_start=-10000,
        year_end=-10000,
        location="India",
        description="Indian mythology's cosmic cycle. Gods walk the earth in an endless cycle of creation and destruction.",
        description_ko="인도 신화의 우주적 순환. 신들이 창조와 파괴의 무한 순환 속에 지상을 걷는다.",
        keywords=["india", "hindu", "yuga", "10000 BCE", "arjuna", "karna", "gods"],
        related_figures=["Arjuna Alter", "Karna", "Ashwatthama", "Ganesha", "Lakshmi Bai"]
    ),
    HistoricalEra(
        id="lostbelt_5",
        name="Atlantis & Olympus - Interstellar Mountain City",
        name_ko="이문대 5 - 대서양에 떠오른 별 / 신대거인해양 아틀란티스",
        name_jp="Lostbelt No.5 神代巨神海洋 アトランティス / 星間都市山脈 オリュンポス",
        era_type="lostbelt",
        order=5,
        year_start=-12000,
        year_end=-12000,
        location="Greece / Atlantis",
        description="Greek gods as alien machines. The Age of Gods never ended, and Olympus rules from the heavens.",
        description_ko="외계 기계로서의 그리스 신들. 신대가 끝나지 않았고, 올림포스가 하늘에서 다스린다.",
        keywords=["greece", "atlantis", "olympus", "12000 BCE", "gods", "machine gods", "titans"],
        related_figures=["Zeus", "Europa", "Caenis", "Jason", "Musashi", "Orion"]
    ),
    HistoricalEra(
        id="lostbelt_6",
        name="Avalon le Fae - Fairy Round Table Domain",
        name_ko="이문대 6 - 요정원탁영역 아발론 르 페",
        name_jp="Lostbelt No.6 妖精円卓領域 アヴァロン・ル・フェ",
        era_type="lostbelt",
        order=6,
        year_start=500,
        year_end=500,
        location="Britain",
        description="A Britain where fairies rule instead of humans. The story of the 'Child of Prophecy'.",
        description_ko="인간 대신 요정이 다스리는 브리튼. '예언의 아이'의 이야기.",
        keywords=["britain", "avalon", "fairies", "500 CE", "round table", "morgan", "arthurian"],
        related_figures=["Morgan", "Artoria Caster", "Oberon", "Percival", "Melusine", "Barghest"]
    ),
    HistoricalEra(
        id="lostbelt_7",
        name="Nahui Mictlan - Golden Sea Tree Domain",
        name_ko="이문대 7 - 황금수림해역 나후이 믹틀란",
        name_jp="Lostbelt No.7 黄金樹海紀行 ナウイ・ミクトラン",
        era_type="lostbelt",
        order=7,
        year_start=-5000,
        year_end=-5000,
        location="South America",
        description="Aztec and Mayan mythology realized. The land of the dinosaur kingdom and Mictlan's depths.",
        description_ko="실현된 아즈텍과 마야 신화. 공룡 왕국과 믹틀란의 심연.",
        keywords=["mexico", "aztec", "maya", "5000 BCE", "dinosaurs", "mictlan", "tezcatlipoca"],
        related_figures=["Tezcatlipoca", "Quetzalcoatl", "Camazotz", "Kukulkan", "Daybit"]
    ),
]

# 15개 특별 에피소드 (추가 역사 시대)
SPECIAL_EPISODES: List[HistoricalEra] = [
    HistoricalEra(
        id="special_shinjuku",
        name="Shinjuku - Phantom Demon Realm",
        name_ko="아종특이점 1 - 악성격리마경 신주쿠",
        name_jp="亜種特異点Ⅰ 悪性隔絶魔境 新宿",
        era_type="special",
        order=101,
        year_start=1999,
        year_end=1999,
        location="Shinjuku, Japan",
        description="1999 Shinjuku trapped in eternal night. Moriarty's grand scheme unfolds.",
        description_ko="영원한 밤에 갇힌 1999년 신주쿠. 모리아티의 거대한 계획이 펼쳐진다.",
        keywords=["shinjuku", "1999", "tokyo", "moriarty", "phantom", "demon"],
        related_figures=["James Moriarty", "Jeanne d'Arc Alter", "EMIYA Alter", "Sherlock Holmes"]
    ),
    HistoricalEra(
        id="special_agartha",
        name="Agartha - Subterranean World",
        name_ko="아종특이점 2 - 전설지하세계 아가르타",
        name_jp="亜種特異点Ⅱ 伝承地底世界 アガルタ",
        era_type="special",
        order=102,
        year_start=2000,
        year_end=2000,
        location="Underground World",
        description="A hollow earth filled with legendary cities and empires ruled by famous queens.",
        description_ko="유명한 여왕들이 다스리는 전설적인 도시와 제국으로 가득 찬 지하 세계.",
        keywords=["agartha", "underground", "hollow earth", "queens", "el dorado"],
        related_figures=["Scheherazade", "Wu Zetian", "Penthesilea", "Dahut", "Megalos"]
    ),
    HistoricalEra(
        id="special_shimousa",
        name="Shimousa - Tournament of the Seven Swordmasters",
        name_ko="아종특이점 3 - 영령검호칠번승부 시모사",
        name_jp="亜種特異点Ⅲ 屍山血河舞台 下総国",
        era_type="special",
        order=103,
        year_start=1639,
        year_end=1639,
        location="Edo Japan",
        description="Edo period Japan. Seven heroic spirit swordmasters duel in a battle of blades.",
        description_ko="에도 시대 일본. 일곱 영령 검호들이 칼의 대결을 펼친다.",
        keywords=["edo", "japan", "1639", "samurai", "swordmasters", "shimabara"],
        related_figures=["Musashi", "Yagyu Munenori", "Shuten-Douji", "Houzouin Inshun", "Mochizuki Chiyome"]
    ),
    HistoricalEra(
        id="special_salem",
        name="Salem - Heretical Salem",
        name_ko="아종특이점 4 - 이단나락계 세일럼",
        name_jp="亜種特異点Ⅳ 禁忌降臨庭園 セイレム",
        era_type="special",
        order=104,
        year_start=1692,
        year_end=1692,
        location="Salem, Massachusetts",
        description="The Salem Witch Trials era. Abigail and Lovecraftian horrors lurk in Puritan New England.",
        description_ko="세일럼 마녀재판 시대. 에비게일과 러브크래프트적 공포가 청교도 뉴잉글랜드에 도사린다.",
        keywords=["salem", "1692", "witch trials", "massachusetts", "puritans", "lovecraft", "abigail"],
        related_figures=["Abigail Williams", "Queen of Sheba", "Circe", "Nezha", "Lavinia"]
    ),
    HistoricalEra(
        id="special_seraph",
        name="SE.RA.PH - Deep Sea Cyber Brain Paradise",
        name_ko="깊은 바다의 디지털 낙원 SE.RA.PH",
        name_jp="深海電脳楽土 SE.RA.PH",
        era_type="special",
        order=105,
        year_start=2030,
        year_end=2030,
        location="Cyberspace / Seraph",
        description="A digital paradise submerged beneath the sea. The story of BB and the Sakura Five.",
        description_ko="바다 밑에 가라앉은 디지털 낙원. BB와 사쿠라 파이브의 이야기.",
        keywords=["seraph", "cyberspace", "BB", "sakura five", "digital", "moon cell"],
        related_figures=["BB", "Meltryllis", "Passionlip", "Kiara Sessyoin", "Suzuka Gozen"]
    ),
    HistoricalEra(
        id="special_troy",
        name="Trojan War - The Fall of Troy",
        name_ko="특집 - 트로이 전쟁",
        name_jp="特別 トロイア戦争",
        era_type="special",
        order=106,
        year_start=-1180,
        year_end=-1180,
        location="Troy, Anatolia",
        description="The legendary Trojan War. Achilles, Hector, and the heroes of the Iliad clash.",
        description_ko="전설적인 트로이 전쟁. 아킬레우스, 헥토르, 그리고 일리아드의 영웅들이 격돌한다.",
        keywords=["troy", "trojan war", "1180 BCE", "achilles", "hector", "iliad", "homer"],
        related_figures=["Achilles", "Hector", "Paris", "Helen", "Odysseus", "Ajax"]
    ),
    HistoricalEra(
        id="special_alexander",
        name="Macedonian Empire - The Conqueror's Path",
        name_ko="특집 - 정복왕의 길",
        name_jp="特別 征服王の道",
        era_type="special",
        order=107,
        year_start=-356,
        year_end=-323,
        location="Macedonia / Persian Empire",
        description="Alexander the Great's conquest of the known world. From Macedonia to India.",
        description_ko="알렉산더 대왕의 세계 정복. 마케도니아에서 인도까지.",
        keywords=["alexander", "macedonia", "persia", "356 BCE", "conquest", "darius", "aristotle"],
        related_figures=["Alexander the Great", "Darius III", "Hephaestion", "Bucephalus"]
    ),
    HistoricalEra(
        id="special_punic",
        name="Punic Wars - Hannibal's Challenge",
        name_ko="특집 - 포에니 전쟁",
        name_jp="特別 ポエニ戦争",
        era_type="special",
        order=108,
        year_start=-264,
        year_end=-146,
        location="Mediterranean",
        description="Rome vs Carthage. Hannibal crosses the Alps with elephants.",
        description_ko="로마 대 카르타고. 한니발이 코끼리와 함께 알프스를 넘는다.",
        keywords=["punic war", "rome", "carthage", "hannibal", "264 BCE", "elephants", "scipio"],
        related_figures=["Hannibal Barca", "Scipio Africanus", "Romulus"]
    ),
    HistoricalEra(
        id="special_mongol",
        name="Mongol Empire - Genghis Khan's Legacy",
        name_ko="특집 - 몽골 제국",
        name_jp="特別 モンゴル帝国",
        era_type="special",
        order=109,
        year_start=1206,
        year_end=1294,
        location="Eurasia",
        description="The largest contiguous empire in history. From the steppes to the gates of Europe.",
        description_ko="역사상 가장 큰 연속 제국. 초원에서 유럽의 문까지.",
        keywords=["mongol", "genghis khan", "1206", "eurasia", "conquest", "kublai khan", "steppe"],
        related_figures=["Genghis Khan", "Kublai Khan", "Subotai", "Marco Polo"]
    ),
    HistoricalEra(
        id="special_renaissance",
        name="Renaissance - The Rebirth of Civilization",
        name_ko="특집 - 르네상스",
        name_jp="特別 ルネサンス",
        era_type="special",
        order=110,
        year_start=1400,
        year_end=1600,
        location="Italy / Europe",
        description="The rebirth of art, science, and humanism. Da Vinci, Michelangelo, and the masters.",
        description_ko="예술, 과학, 인본주의의 부활. 다빈치, 미켈란젤로, 그리고 거장들.",
        keywords=["renaissance", "italy", "1400", "da vinci", "michelangelo", "art", "florence"],
        related_figures=["Leonardo da Vinci", "Michelangelo", "Cesare Borgia", "Machiavelli"]
    ),
    HistoricalEra(
        id="special_french_revolution",
        name="French Revolution - Liberty's Price",
        name_ko="특집 - 프랑스 혁명",
        name_jp="特別 フランス革命",
        era_type="special",
        order=111,
        year_start=1789,
        year_end=1799,
        location="France",
        description="The fall of monarchy and rise of the guillotine. Marie Antoinette's last days.",
        description_ko="군주제의 몰락과 단두대의 등장. 마리 앙투아네트의 마지막 날들.",
        keywords=["french revolution", "1789", "guillotine", "bastille", "marie antoinette", "robespierre"],
        related_figures=["Marie Antoinette", "Charlotte Corday", "Sanson", "Napoleon Bonaparte"]
    ),
    HistoricalEra(
        id="special_napoleon",
        name="Napoleonic Wars - The Emperor's March",
        name_ko="특집 - 나폴레옹 전쟁",
        name_jp="特別 ナポレオン戦争",
        era_type="special",
        order=112,
        year_start=1803,
        year_end=1815,
        location="Europe",
        description="Napoleon's conquest of Europe. From Austerlitz to Waterloo.",
        description_ko="나폴레옹의 유럽 정복. 아우스터리츠에서 워털루까지.",
        keywords=["napoleon", "1803", "waterloo", "austerlitz", "emperor", "france", "europe"],
        related_figures=["Napoleon Bonaparte", "Wellington", "Nelson"]
    ),
    HistoricalEra(
        id="special_meiji",
        name="Meiji Restoration - Japan's Transformation",
        name_ko="특집 - 메이지 유신",
        name_jp="特別 明治維新",
        era_type="special",
        order=113,
        year_start=1868,
        year_end=1912,
        location="Japan",
        description="Japan's rapid modernization. Samurai give way to industrialization.",
        description_ko="일본의 급격한 근대화. 사무라이가 산업화에 자리를 내준다.",
        keywords=["meiji", "japan", "1868", "modernization", "samurai", "industrialization", "restoration"],
        related_figures=["Oda Nobunaga", "Okita Souji", "Sakamoto Ryoma", "Hijikata Toshizo"]
    ),
    HistoricalEra(
        id="special_egypt",
        name="Ancient Egypt - The Gift of the Nile",
        name_ko="특집 - 고대 이집트",
        name_jp="特別 古代エジプト",
        era_type="special",
        order=114,
        year_start=-3000,
        year_end=-30,
        location="Egypt",
        description="The civilization of pyramids and pharaohs. From the Old Kingdom to Cleopatra.",
        description_ko="피라미드와 파라오의 문명. 고왕국에서 클레오파트라까지.",
        keywords=["egypt", "pharaoh", "pyramid", "3000 BCE", "nile", "cleopatra", "tutankhamun"],
        related_figures=["Ozymandias", "Nitocris", "Cleopatra", "Iskandar", "Moses"]
    ),
    HistoricalEra(
        id="special_persia",
        name="Persian Empire - Flame of Zoroaster",
        name_ko="특집 - 페르시아 제국",
        name_jp="特別 ペルシア帝国",
        era_type="special",
        order=115,
        year_start=-550,
        year_end=651,
        location="Persia / Iran",
        description="From Cyrus the Great to the Sassanids. The fire of Ahura Mazda burns eternal.",
        description_ko="키루스 대왕에서 사산 왕조까지. 아후라 마즈다의 불꽃이 영원히 타오른다.",
        keywords=["persia", "iran", "550 BCE", "cyrus", "darius", "zoroaster", "sassanid"],
        related_figures=["Cyrus the Great", "Darius III", "Arash", "Hassan-i Sabbah"]
    ),
]


def get_all_eras() -> List[HistoricalEra]:
    """모든 역사 시대 반환"""
    return SINGULARITIES + [SOLOMON_ERA] + LOSTBELTS + SPECIAL_EPISODES


def get_era_by_id(era_id: str) -> HistoricalEra:
    """ID로 역사 시대 조회"""
    for era in get_all_eras():
        if era.id == era_id:
            return era
    return None


def get_eras_by_type(era_type: str) -> List[HistoricalEra]:
    """타입별 역사 시대 조회"""
    return [era for era in get_all_eras() if era.era_type == era_type]


def find_matching_era(year: int, location: str = None) -> List[HistoricalEra]:
    """연도/위치로 관련 시대 찾기"""
    matches = []
    for era in get_all_eras():
        # 연도가 시대 범위 내에 있는지 확인
        if era.year_start <= year <= era.year_end:
            matches.append(era)
        # 위치 키워드 매칭
        elif location:
            location_lower = location.lower()
            if location_lower in era.location.lower() or any(
                location_lower in kw for kw in era.keywords
            ):
                matches.append(era)

    return sorted(matches, key=lambda x: abs(x.year_start - year))


def to_api_response(eras: List[HistoricalEra]) -> List[Dict[str, Any]]:
    """API 응답용 변환"""
    return [asdict(era) for era in eras]
