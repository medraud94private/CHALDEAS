"""
Chinese Text Project Collector

Website: https://ctext.org/
API: https://ctext.org/tools/api

Data includes:
- Pre-modern Chinese texts
- Confucian, Daoist, Buddhist classics
- Historical records

License: Non-commercial use permitted
"""
import httpx
import asyncio
from pathlib import Path
from typing import Optional
import json


class CTextCollector:
    """
    Collector for Chinese Text Project.

    Uses the official CText API.
    API Docs: https://ctext.org/tools/api
    """

    BASE_URL = "https://api.ctext.org"

    # API requires authentication for full access
    # Free tier has rate limits

    def __init__(self, output_dir: Path, api_key: Optional[str] = None):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get_textinfo(self, text_id: str) -> dict:
        """
        Get metadata about a text.

        Example: getlink?urn=ctp:analects
        """
        url = f"{self.BASE_URL}/gettext?urn={text_id}"
        if self.api_key:
            url += f"&apikey={self.api_key}"

        response = await self.client.get(url)
        response.raise_for_status()
        return response.json()

    async def get_text(self, text_id: str) -> dict:
        """
        Get full text content.

        Args:
            text_id: CText URN (e.g., "ctp:analects")
        """
        url = f"{self.BASE_URL}/gettext?urn={text_id}"
        if self.api_key:
            url += f"&apikey={self.api_key}"

        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching {text_id}: {e}")
            return {}

    async def search(self, query: str, limit: int = 100) -> list[dict]:
        """Search for texts."""
        url = f"{self.BASE_URL}/searchtexts?title={query}"
        if self.api_key:
            url += f"&apikey={self.api_key}"

        response = await self.client.get(url)
        response.raise_for_status()
        return response.json()

    async def collect_important_texts(self):
        """Collect the most important classical texts."""
        print("Collecting important Chinese classical texts...")

        for text_id, name in IMPORTANT_TEXTS:
            print(f"Fetching: {name}")
            try:
                data = await self.get_text(text_id)
                if data:
                    output_file = self.output_dir / f"{text_id.replace(':', '_')}.json"
                    with open(output_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    print(f"  Saved to {output_file}")

                # Rate limiting
                await asyncio.sleep(1)

            except Exception as e:
                print(f"  Error: {e}")

    async def close(self):
        await self.client.aclose()


# Important Chinese classical texts
IMPORTANT_TEXTS = [
    # Confucian Classics (四書五經)
    ("ctp:analects", "論語 (Analects of Confucius)"),
    ("ctp:mengzi", "孟子 (Mencius)"),
    ("ctp:daxue", "大學 (Great Learning)"),
    ("ctp:zhongyong", "中庸 (Doctrine of the Mean)"),
    ("ctp:book-of-changes", "易經 (I Ching)"),
    ("ctp:book-of-documents", "書經 (Book of Documents)"),
    ("ctp:book-of-odes", "詩經 (Book of Odes)"),
    ("ctp:spring-and-autumn-annals", "春秋 (Spring and Autumn Annals)"),

    # Daoist Classics
    ("ctp:dao-de-jing", "道德經 (Tao Te Ching)"),
    ("ctp:zhuangzi", "莊子 (Zhuangzi)"),
    ("ctp:liezi", "列子 (Liezi)"),

    # Historical Records
    ("ctp:shiji", "史記 (Records of the Grand Historian)"),
    ("ctp:hanshu", "漢書 (Book of Han)"),
    ("ctp:hou-hanshu", "後漢書 (Book of Later Han)"),
    ("ctp:sanguozhi", "三國志 (Records of Three Kingdoms)"),

    # Military & Strategy
    ("ctp:art-of-war", "孫子兵法 (Art of War)"),
    ("ctp:36-stratagems", "三十六計 (36 Stratagems)"),

    # Philosophy
    ("ctp:mozi", "墨子 (Mozi)"),
    ("ctp:xunzi", "荀子 (Xunzi)"),
    ("ctp:hanfeizi", "韓非子 (Han Feizi)"),
]


async def main():
    """Main entry point for CText collection."""
    output_dir = Path("data/raw/ctext")

    # Note: Get API key from https://ctext.org/tools/api
    api_key = None  # Set your API key here

    collector = CTextCollector(output_dir, api_key)

    try:
        await collector.collect_important_texts()
    finally:
        await collector.close()


if __name__ == "__main__":
    asyncio.run(main())
