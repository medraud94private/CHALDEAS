"""
Kiwix ZIM Reader - CHALDEAS용 Wikipedia/Wikisource/Wikiquote 추출 도구

Usage:
    python kiwix_reader.py search "Napoleon"
    python kiwix_reader.py get "Napoleon" --output napoleon.txt
    python kiwix_reader.py info
"""

import argparse
import re
from pathlib import Path
from html.parser import HTMLParser

# ZIM 파일 경로
ZIM_DIR = Path(__file__).parent.parent.parent / "data" / "kiwix"
ZIM_FILES = {
    "wikipedia": ZIM_DIR / "wikipedia_en_nopic.zim",
    "wikisource": ZIM_DIR / "wikisource_en_nopic.zim",
    "wikiquote": ZIM_DIR / "wikiquote_en_nopic.zim",
}


class HTMLTextExtractor(HTMLParser):
    """HTML에서 텍스트만 추출"""

    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.skip_tags = {'script', 'style', 'nav', 'header', 'footer', 'aside'}
        self.current_skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self.current_skip += 1

    def handle_endtag(self, tag):
        if tag in self.skip_tags and self.current_skip > 0:
            self.current_skip -= 1
        if tag in ('p', 'div', 'br', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self.text_parts.append('\n')

    def handle_data(self, data):
        if self.current_skip == 0:
            self.text_parts.append(data)

    def get_text(self):
        text = ''.join(self.text_parts)
        # 연속 공백/줄바꿈 정리
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        return text.strip()


def html_to_text(html: str) -> str:
    """HTML을 텍스트로 변환"""
    parser = HTMLTextExtractor()
    parser.feed(html)
    return parser.get_text()


def get_archive(source: str = "wikipedia"):
    """ZIM 아카이브 열기"""
    from libzim.reader import Archive

    zim_path = ZIM_FILES.get(source)
    if not zim_path or not zim_path.exists():
        raise FileNotFoundError(f"ZIM file not found: {zim_path}")

    return Archive(str(zim_path))


def show_info():
    """모든 ZIM 파일 정보 출력"""
    from libzim.reader import Archive

    print("=== Kiwix ZIM Files ===\n")

    for name, path in ZIM_FILES.items():
        if path.exists():
            zim = Archive(str(path))
            size_gb = path.stat().st_size / (1024**3)
            print(f"{name}:")
            print(f"  Path: {path}")
            print(f"  Size: {size_gb:.1f} GB")
            print(f"  Entries: {zim.entry_count:,}")
            print()
        else:
            print(f"{name}: NOT FOUND ({path})\n")


def search_articles(query: str, source: str = "wikipedia", limit: int = 20):
    """문서 제목 검색"""
    zim = get_archive(source)

    query_lower = query.lower()
    results = []

    for i, entry in enumerate(zim):
        if entry.is_redirect:
            continue

        title = entry.title
        if query_lower in title.lower():
            results.append(title)
            if len(results) >= limit:
                break

    return results


def get_article(title: str, source: str = "wikipedia", as_html: bool = False) -> str:
    """문서 내용 가져오기"""
    zim = get_archive(source)

    # 경로 시도
    paths_to_try = [
        f"A/{title}",
        f"A/{title.replace(' ', '_')}",
        title,
        title.replace(' ', '_'),
    ]

    for path in paths_to_try:
        try:
            entry = zim.get_entry_by_path(path)
            if entry.is_redirect:
                # 리다이렉트 따라가기
                entry = entry.get_redirect_entry()

            item = entry.get_item()
            html = bytes(item.content).decode('utf-8')

            if as_html:
                return html
            return html_to_text(html)
        except KeyError:
            continue

    raise KeyError(f"Article not found: {title}")


def get_article_by_title_search(title: str, source: str = "wikipedia") -> tuple[str, str]:
    """제목으로 검색해서 문서 가져오기 (정확한 경로 모를 때)"""
    zim = get_archive(source)

    title_lower = title.lower().replace(' ', '_')

    for entry in zim:
        if entry.is_redirect:
            continue

        entry_title = entry.title.lower().replace(' ', '_')
        if entry_title == title_lower:
            item = entry.get_item()
            html = bytes(item.content).decode('utf-8')
            return entry.title, html_to_text(html)

    raise KeyError(f"Article not found: {title}")


# ============ CHALDEAS Integration Functions ============

def extract_person_info(title: str) -> dict:
    """인물 문서에서 정보 추출"""
    try:
        html = get_article(title, as_html=True)
        text = html_to_text(html)

        # 첫 문단 (보통 요약)
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        summary = paragraphs[0] if paragraphs else ""

        # 생몰년 추출 시도 (보통 첫 문장에 있음)
        birth_death = None
        date_match = re.search(r'\(([^)]*\d{3,4}[^)]*)\)', summary)
        if date_match:
            birth_death = date_match.group(1)

        return {
            "title": title,
            "summary": summary[:500],
            "birth_death": birth_death,
            "full_text": text,
        }
    except KeyError:
        return None


def extract_quotes(person_name: str) -> list[str]:
    """인물의 명언 추출"""
    try:
        text = get_article(person_name, source="wikiquote")

        # 명언은 보통 리스트 형태
        quotes = []
        for line in text.split('\n'):
            line = line.strip()
            if line and len(line) > 20 and not line.startswith('='):
                quotes.append(line)

        return quotes[:10]  # 최대 10개
    except KeyError:
        return []


def extract_source_text(title: str) -> dict:
    """Wikisource에서 1차 사료 추출"""
    try:
        text = get_article(title, source="wikisource")
        return {
            "title": title,
            "content": text,
            "source": "wikisource",
        }
    except KeyError:
        return None


# ============ CLI ============

def main():
    parser = argparse.ArgumentParser(description="Kiwix ZIM Reader")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # info
    subparsers.add_parser("info", help="Show ZIM file info")

    # search
    search_p = subparsers.add_parser("search", help="Search articles")
    search_p.add_argument("query", help="Search query")
    search_p.add_argument("--source", default="wikipedia", choices=ZIM_FILES.keys())
    search_p.add_argument("--limit", type=int, default=20)

    # get
    get_p = subparsers.add_parser("get", help="Get article content")
    get_p.add_argument("title", help="Article title")
    get_p.add_argument("--source", default="wikipedia", choices=ZIM_FILES.keys())
    get_p.add_argument("--html", action="store_true", help="Output as HTML")
    get_p.add_argument("--output", "-o", help="Output file")

    # person (CHALDEAS용)
    person_p = subparsers.add_parser("person", help="Extract person info")
    person_p.add_argument("name", help="Person name")

    args = parser.parse_args()

    if args.command == "info":
        show_info()

    elif args.command == "search":
        results = search_articles(args.query, args.source, args.limit)
        print(f"Found {len(results)} results for '{args.query}':\n")
        for title in results:
            print(f"  - {title}")

    elif args.command == "get":
        content = get_article(args.title, args.source, args.html)
        if args.output:
            Path(args.output).write_text(content, encoding='utf-8')
            print(f"Saved to {args.output}")
        else:
            print(content)

    elif args.command == "person":
        info = extract_person_info(args.name)
        if info:
            print(f"=== {info['title']} ===")
            if info['birth_death']:
                print(f"Dates: {info['birth_death']}")
            print(f"\nSummary:\n{info['summary']}")

            quotes = extract_quotes(args.name)
            if quotes:
                print(f"\n=== Quotes ===")
                for q in quotes[:5]:
                    print(f"  \"{q}\"")
        else:
            print(f"Person not found: {args.name}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
