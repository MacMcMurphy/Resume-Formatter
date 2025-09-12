from __future__ import annotations
from typing import Optional
from openai import OpenAI
from app.config import OPENAI_API_KEY

_client: Optional[OpenAI] = None


def get_openai_client() -> OpenAI:
    global _client
    if _client is None:
        if not OPENAI_API_KEY:
            raise RuntimeError("OpenAI key missing. Set RESUME_FORMATTER_OPENAI_API_KEY in .env")
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def reset_openai_client() -> None:
    global _client
    _client = None


