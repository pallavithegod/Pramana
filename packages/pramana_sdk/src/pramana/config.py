"""Validated server configuration; no hosted LLM fallbacks."""

import os
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, SecretStr, field_validator


class Settings(BaseModel):
    serpapi_key: SecretStr = SecretStr("")
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b"
    max_searches: int = Field(default=8, ge=1, le=50)
    max_tool_calls: int = Field(default=16, ge=1, le=50)
    timeout_seconds: int = Field(default=180, ge=10, le=600)
    max_concurrent_chats: int = Field(default=2, ge=1, le=8)
    runtime_db: Path = Path("data/runtime/pramana.sqlite")

    @field_validator("ollama_base_url")
    @classmethod
    def local_model_only(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Ollama must run on local loopback over HTTP")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Ollama URL must not include credentials, queries or fragments")
        return value.rstrip("/")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            serpapi_key=SecretStr(os.getenv("SERPAPI_KEY", "")),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
            max_searches=int(os.getenv("PRAMANA_MAX_SEARCHES", "8")),
            max_tool_calls=int(os.getenv("PRAMANA_MAX_TOOL_CALLS", "16")),
            timeout_seconds=int(os.getenv("PRAMANA_TIMEOUT_SECONDS", "180")),
            max_concurrent_chats=int(os.getenv("PRAMANA_MAX_CONCURRENT_CHATS", "2")),
            runtime_db=Path(os.getenv("PRAMANA_RUNTIME_DB", "data/runtime/pramana.sqlite")),
        )
