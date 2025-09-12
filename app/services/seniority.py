from __future__ import annotations
from typing import Any, Dict, List, Optional
import json
import logging
from datetime import date
from app.services.llm import get_openai_client

logger = logging.getLogger(__name__)

MODEL = "gpt-4o-mini"


def _get_client():
    return get_openai_client()


SYSTEM_PROMPT = (
    "You are an expert resume analyst. Determine the correct seniority LEVEL using ONLY the oldest work start date.\n"
    "Rules (absolute):\n"
    "- If the start date of the OLDEST position is over 11 years ago, level = 'SME'.\n"
    "- If between 6 and 10 years ago (inclusive), level = 'Senior'.\n"
    "- If between 0 and 5 years ago (inclusive), level = 'Journeyman'.\n"
    "- Return ONLY the level token (Journeyman|Senior|SME), no quotes or extra words.\n"
)


def infer_java_full_stack_seniority(ss_work: List[Dict[str, Any]] | None, internal_experience: List[Dict[str, Any]] | None) -> str:
    """Ask the LLM to choose the seniority title from the oldest start date.

    ss_work: list of skill-scope 'work' entries with 'startDate' (YYYY-MM-DD) if available.
    internal_experience: list of normalized roles with 'start_date' like 'MM/YYYY' or 'YYYY-MM'.
    Returns a plain title string or empty string on failure.
    """
    client = _get_client()
    today = date.today().isoformat()
    payload = {
        "today": today,
        "ss_work": ss_work or [],
        "internal_experience": internal_experience or [],
    }
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": (
                    "Use 'today' to compute years since the OLDEST start date found in either list.\n"
                    "Prefer precise ISO dates from 'ss_work.startDate' when present.\n"
                    "Fallback to 'internal_experience.start_date' strings if needed.\n"
                    "Return ONLY the title text. Here is the data as JSON:\n" + json.dumps(payload, ensure_ascii=False)
                )},
            ],
            temperature=0,
        )
        title = (resp.choices[0].message.content or "").strip()
        # Basic whitelist to avoid odd outputs
        allowed = {"Journeyman", "Senior", "SME"}
        if title in allowed:
            return title
        logger.warning("seniority_llm: unexpected level '%s'", title)
        return ""
    except Exception:
        logger.exception("seniority_llm: LLM call failed")
        return ""


