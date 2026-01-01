"""
PoC Configuration
"""
from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # App
    app_name: str = "CHALDEAS V1 PoC"
    debug: bool = True

    # Database (SQLite for PoC) - absolute path
    database_url: str = f"sqlite+aiosqlite:///{os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'chaldeas_poc.db')}"

    # LLM Provider: "ollama" (free, local) or "openai" (paid, cloud)
    llm_provider: str = "ollama"  # Default to free local

    # Ollama (Local - FREE)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"  # Best for NER and chain generation

    # OpenAI (Cloud - PAID, fallback)
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-5-nano"  # 저렴하고 빠름
    openai_fallback_model: str = "gpt-5.1-chat-latest"  # 고품질 폴백

    # Chain Generation Model (uses llm_provider setting)
    chain_model: str = "gpt-5-nano"  # Only used when llm_provider="openai"

    # Paths
    base_dir: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
