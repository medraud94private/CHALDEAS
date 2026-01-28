# 소스/책 관리 시스템

## 소스 타입 분류

### 지원 소스 타입
| 타입 | 코드 | 설명 | 예시 |
|------|------|------|------|
| **책/문서** | `book` | Project Gutenberg 등 공개 도메인 책 | Iliad, Odyssey |
| **위키데이터** | `wikidata` | 구조화된 엔티티 데이터 | Q12345 (Achilles) |
| **위키피디아** | `wikipedia` | 백과사전 아티클 | en.wikipedia.org/wiki/Achilles |
| **학술DB** | `academic` | Perseus, JSTOR 등 | Perseus Digital Library |
| **게임데이터** | `game` | Atlas Academy FGO 데이터 | servant profiles |
| **1차사료** | `primary` | 원본 사료 번역 | 헤로도토스 원문 |
| **2차사료** | `secondary` | 연구/해석 자료 | 학술 논문 |

### 소스별 신뢰도 기준
| 타입 | 기본 신뢰도 | 설명 |
|------|------------|------|
| primary | 5 | 원본 사료 |
| book (고전) | 4 | 검증된 번역본 |
| wikidata | 4 | 구조화된 데이터 |
| wikipedia | 3 | 커뮤니티 검증 |
| academic | 5 | 학술 검증 |
| game | 2 | 창작물 (FGO 레이어용) |
| secondary | 3 | 해석 포함 |

---

## 현황

### 현재 Source 스키마
```python
class Source(Base):
    id = Column(Integer, primary_key=True)
    name = Column(String(255))           # 소스 이름
    type = Column(String(50))            # primary, secondary, digital_archive
    url = Column(String(500))            # URL
    author = Column(String(255))         # 저자
    publication_year = Column(Integer)   # 출판년도
    description = Column(Text)
    archive_type = Column(String(50))    # gutenberg, perseus, ctext, etc.
    document_id = Column(String(255))    # 원본 파일 ID
    document_path = Column(String(500))  # 파일 경로
    title = Column(String(500))          # 전체 제목
    original_year = Column(Integer)      # 원저 작성년도 (BCE는 음수)
    language = Column(String(10))        # en, la, gr, zh, etc.
    reliability = Column(Integer)        # 1-5
```

### 문제점

1. **처리 상태 없음**: NER 추출 완료 여부 추적 불가
2. **중복 체크 어려움**: 같은 책이 다른 이름으로 들어갈 수 있음
3. **FGO 레이어 연결 없음**: 어떤 서번트와 연결되는지 불명확

---

## 제안: Source 스키마 확장

### 추가 필드
```python
# 처리 상태 추적
processing_status = Column(String(20))  # pending, in_progress, completed, failed
processed_at = Column(DateTime)         # 처리 완료 시각
extraction_model = Column(String(50))   # llama3.1, gpt-5.1, etc.
chunks_total = Column(Integer)          # 전체 청크 수
chunks_processed = Column(Integer)      # 처리된 청크 수

# 중복 방지
gutenberg_id = Column(Integer, unique=True)  # Project Gutenberg ID
isbn = Column(String(20), unique=True)       # ISBN (있는 경우)
file_hash = Column(String(64))               # 파일 SHA256 해시

# 엔티티 추출 결과
persons_extracted = Column(Integer)     # 추출된 인물 수
locations_extracted = Column(Integer)   # 추출된 장소 수
events_extracted = Column(Integer)      # 추출된 이벤트 수

# FGO 관련
fgo_relevant = Column(Boolean)          # FGO 서번트 관련 여부
fgo_servants_covered = Column(Text)     # 관련 서번트 JSON 리스트
```

### 처리 상태 흐름
```
pending → in_progress → completed
                     ↘ failed
```

---

## 현재 보유 책 목록

### 로컬 파일 (`poc/data/book_samples/`)

| 파일명 | Gutenberg ID | 크기 | 처리 상태 | 추출 결과 |
|--------|-------------|------|----------|----------|
| greek_roman_myths.txt | - | 886KB | ✅ 완료 | 800 persons |
| bulfinch_mythology.txt | 4928 | 688KB | ✅ 완료 | 743 persons |
| odyssey_homer.txt | 1727 | 718KB | ✅ 완료 | 281 persons |
| arabian_nights.txt | 128 | 629KB | ✅ 완료 | 157 persons |
| herodotus_histories.txt | 2131 | 916KB | ✅ 완료 | 382 persons |
| norse_mythology.txt | - | 632KB | ✅ 완료 | 486 persons |
| plutarch_lives.txt | 674 | 4.32MB | 🔄 43% | ~400 persons |
| plato_republic.txt | 1497 | 1.27MB | ✅ 완료 | 201 persons |
| marcus_aurelius_meditations.txt | 2680 | 751KB | ✅ 완료 | 20 persons |
| mahabharata.txt | 7864 | 1.39MB | ⏳ 대기 | - |
| gilgamesh_epic.txt | - | 252KB | ⏳ 대기 | - |
| celtic_mythology.txt | - | 906KB | ⏳ 대기 | - |
| egyptian_mythology.txt | - | 596KB | ⏳ 대기 | - |
| japanese_mythology.txt | - | 403KB | ⏳ 대기 | - |
| chinese_mythology.txt | - | 714KB | ⏳ 대기 | - |

### 다운로드 필요 책

| 책 제목 | Gutenberg ID | 예상 크기 | 우선순위 | FGO 서번트 |
|---------|-------------|----------|----------|------------|
| Le Morte d'Arthur | 1251 | ~1.5MB | 1 | 원탁 기사 ~20명 |
| Iliad | 6130 | ~1MB | 1 | Achilles, Hector 등 |
| Argonautica | 830 | ~300KB | 2 | Jason, Medea |
| Volsunga Saga | 1152 | ~150KB | 2 | Sigurd, Brynhildr |
| Cattle Raid of Cooley | 16464 | ~200KB | 2 | Cu Chulainn |
| Frankenstein | 84 | ~400KB | 3 | Frankenstein |
| Count of Monte Cristo | 1184 | ~2.5MB | 3 | Edmond Dantes |
| Complete Sherlock Holmes | 1661 | ~3MB | 3 | Holmes, Moriarty |
| Beowulf | 16328 | ~150KB | 3 | Beowulf |
| Metamorphoses (Ovid) | 26073 | ~800KB | 2 | 로마 신화 |

---

## 중복 방지 전략

### 1. Gutenberg ID로 체크
```python
def is_book_registered(gutenberg_id: int) -> bool:
    return db.query(Source).filter(
        Source.gutenberg_id == gutenberg_id
    ).first() is not None
```

### 2. 파일 해시로 체크
```python
import hashlib

def get_file_hash(filepath: str) -> str:
    with open(filepath, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()

def is_file_registered(filepath: str) -> bool:
    file_hash = get_file_hash(filepath)
    return db.query(Source).filter(
        Source.file_hash == file_hash
    ).first() is not None
```

### 3. 이름 유사도 체크
```python
from difflib import SequenceMatcher

def find_similar_sources(name: str, threshold: float = 0.8):
    sources = db.query(Source).all()
    similar = []
    for source in sources:
        ratio = SequenceMatcher(None, name.lower(), source.name.lower()).ratio()
        if ratio >= threshold:
            similar.append((source, ratio))
    return similar
```

---

## 임포트 워크플로우

### 1. 책 등록
```python
def register_book(
    filepath: str,
    gutenberg_id: int | None = None,
    title: str,
    author: str,
    original_year: int | None = None
):
    # 중복 체크
    if gutenberg_id and is_book_registered(gutenberg_id):
        raise ValueError(f"Book {gutenberg_id} already registered")

    file_hash = get_file_hash(filepath)
    if is_file_registered(filepath):
        raise ValueError(f"File already registered (hash: {file_hash})")

    # 등록
    source = Source(
        name=title,
        type="primary",
        archive_type="gutenberg" if gutenberg_id else None,
        gutenberg_id=gutenberg_id,
        document_path=filepath,
        file_hash=file_hash,
        author=author,
        original_year=original_year,
        processing_status="pending"
    )
    db.add(source)
    db.commit()
    return source
```

### 2. NER 추출 시작
```python
def start_extraction(source_id: int, model: str = "llama3.1"):
    source = db.query(Source).get(source_id)
    source.processing_status = "in_progress"
    source.extraction_model = model
    db.commit()
```

### 3. 추출 완료
```python
def complete_extraction(
    source_id: int,
    persons: int,
    locations: int,
    events: int
):
    source = db.query(Source).get(source_id)
    source.processing_status = "completed"
    source.processed_at = datetime.utcnow()
    source.persons_extracted = persons
    source.locations_extracted = locations
    source.events_extracted = events
    db.commit()
```

---

## 다음 작업

1. [ ] Source 모델에 처리 상태 필드 추가 (마이그레이션)
2. [ ] 기존 책들 Source 테이블에 등록
3. [ ] 추출 결과 Source와 연결
4. [ ] 중복 방지 유틸리티 구현
5. [ ] FGO 서번트 매핑 필드 추가

---

## 신규 책 수배 목록

### Tier 1: 최우선 (다수 서번트 커버)

| 책 | Gutenberg ID | URL | 서번트 | 비고 |
|----|-------------|-----|--------|------|
| **Le Morte d'Arthur** | 1251 | gutenberg.org/ebooks/1251 | Arthur, Lancelot, Mordred 등 ~20명 | 원탁기사 원전 |
| **Iliad (Homer)** | 6130 | gutenberg.org/ebooks/6130 | Achilles, Hector, Paris 등 ~15명 | 트로이 전쟁 |
| **Aeneid (Virgil)** | 228 | gutenberg.org/ebooks/228 | Romulus, 로마 건국 | 로마 건국 신화 |

### Tier 2: 높은 우선순위 (핵심 서번트)

| 책 | Gutenberg ID | URL | 서번트 | 비고 |
|----|-------------|-----|--------|------|
| **Volsunga Saga** | 1152 | gutenberg.org/ebooks/1152 | Sigurd, Brynhildr | 북유럽 원전 |
| **Argonautica** | 830 | gutenberg.org/ebooks/830 | Jason, Medea | 아르고호 원정 |
| **Cattle Raid of Cooley** | 16464 | gutenberg.org/ebooks/16464 | Cu Chulainn, Medb | 켈트 원전 |
| **Nibelungenlied** | 7321 | gutenberg.org/ebooks/7321 | Siegfried, Kriemhild | 독일 영웅 서사시 |
| **Ramayana** | 24869 | gutenberg.org/ebooks/24869 | Rama | 인도 2대 서사시 |
| **Poetic Edda** | 14726 | gutenberg.org/ebooks/14726 | Odin, Thor, Valkyrie | 북유럽 신화 원전 |
| **Prose Edda** | 18947 | gutenberg.org/ebooks/18947 | Skadi, Loki | 북유럽 신화 |

### Tier 3: 개별 서번트 전용

| 책 | Gutenberg ID | URL | 서번트 | 비고 |
|----|-------------|-----|--------|------|
| **Frankenstein** | 84 | gutenberg.org/ebooks/84 | Frankenstein | 필수 원전 |
| **Count of Monte Cristo** | 1184 | gutenberg.org/ebooks/1184 | Edmond Dantes | 필수 원전 |
| **Sherlock Holmes (Complete)** | 1661 | gutenberg.org/ebooks/1661 | Holmes, Moriarty | 문학 서번트 |
| **Dr Jekyll and Mr Hyde** | 43 | gutenberg.org/ebooks/43 | Jekyll/Hyde | 단편 |
| **Beowulf** | 16328 | gutenberg.org/ebooks/16328 | Beowulf | 앵글로색슨 서사시 |
| **Don Quixote** | 996 | gutenberg.org/ebooks/996 | Don Quixote | 스페인 문학 |
| **Phantom of the Opera** | 175 | gutenberg.org/ebooks/175 | Phantom | 프랑스 문학 |
| **Orlando Furioso** | 3747 | gutenberg.org/ebooks/3747 | Astolfo, Roland | 샤를마뉴 전설 |
| **Song of Roland** | 391 | gutenberg.org/ebooks/391 | Roland, Charlemagne | 프랑스 서사시 |

### Tier 4: 역사 인물 전기

| 책 | Gutenberg ID | URL | 서번트 | 비고 |
|----|-------------|-----|--------|------|
| **Joan of Arc (Twain)** | 1351 | gutenberg.org/ebooks/1351 | Jeanne d'Arc | 전기 소설 |
| **Napoleon Biography** | 3567 | gutenberg.org/ebooks/3567 | Napoleon | 전기 |
| **French Revolution (Carlyle)** | 1301 | gutenberg.org/ebooks/1301 | Marie Antoinette | 프랑스 혁명사 |
| **Lives of Artists (Vasari)** | 25759 | gutenberg.org/ebooks/25759 | da Vinci | 르네상스 예술가 |
| **Book of Five Rings** | 17007 | gutenberg.org/ebooks/17007 | Musashi | 무사시 원저 |
| **Geronimo's Story** | 24439 | gutenberg.org/ebooks/24439 | Geronimo | 자서전 |

### Tier 5: 신화/종교 텍스트

| 책 | Gutenberg ID | URL | 서번트 | 비고 |
|----|-------------|-----|--------|------|
| **Metamorphoses (Ovid)** | 26073 | gutenberg.org/ebooks/26073 | 그리스/로마 신 | 변신 이야기 |
| **Book of the Dead** | 7145 | gutenberg.org/ebooks/7145 | 이집트 신화 | 이집트 사후세계 |
| **Babylonian Legends** | 17321 | gutenberg.org/ebooks/17321 | Tiamat | 메소포타미아 |
| **Andersen's Fairy Tales** | 1597 | gutenberg.org/ebooks/1597 | Hans Andersen | 동화 원전 |
| **Grimm's Fairy Tales** | 2591 | gutenberg.org/ebooks/2591 | Nursery Rhyme | 동화 |

### 비-Gutenberg 소스 (웹/번역 필요)

| 책 | 소스 | 서번트 | 비고 |
|----|------|--------|------|
| **삼국지연의** | 중문 웹 | Lu Bu, Zhuge Liang | 영문 번역본 필요 |
| **서유기** | 중문 웹 | Xuanzang | 영문 번역본 필요 |
| **사기** | 중문 웹 | Qin Shi Huang, Xiang Yu | 부분 번역 존재 |
| **헤이케 이야기** | 일문 웹 | Ushiwakamaru, Benkei | 영문 번역본 필요 |
| **고사기/일본서기** | 일문 웹 | 일본 신화 | 부분 번역 존재 |
| **샤나메** | 페르시아 | Arash | 영문 번역본 필요 |

---

## 다운로드 스크립트

```python
# poc/scripts/download_gutenberg_books.py
import requests
import os

BOOKS = [
    (1251, "le_morte_darthur"),
    (6130, "iliad_homer"),
    (1152, "volsunga_saga"),
    (84, "frankenstein"),
    (1184, "count_of_monte_cristo"),
    # ... 추가
]

def download_book(gutenberg_id: int, filename: str):
    url = f"https://www.gutenberg.org/cache/epub/{gutenberg_id}/pg{gutenberg_id}.txt"
    resp = requests.get(url)
    if resp.status_code == 200:
        filepath = f"poc/data/book_samples/{filename}.txt"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(resp.text)
        print(f"Downloaded: {filepath}")
    else:
        print(f"Failed: {gutenberg_id}")

if __name__ == "__main__":
    os.makedirs("poc/data/book_samples", exist_ok=True)
    for gid, name in BOOKS:
        download_book(gid, name)
```

---

## 관련 문서

- `docs/planning/FGO_DATA_LAYER_AND_SOURCES.md` - FGO 레이어 설계
- `docs/planning/FGO_SERVANT_BOOK_MAPPING.md` - 서번트-책 매핑
- `docs/planning/BOOK_EXTRACTION_COMPARISON.md` - 추출 모델 비교
