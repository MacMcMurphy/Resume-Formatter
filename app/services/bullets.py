from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple
import logging
import json
from app.services.llm import get_openai_client

logger = logging.getLogger(__name__)

MODEL = "gpt-4o-mini"


def _get_client():
    return get_openai_client()


SYSTEM_INSTRUCTIONS = (
    "You are a precise copy editor. You will receive a list of resume bullet points.\n"
    "Decide BOTH of the following using majority rule across the bullets:\n"
    "(A) Punctuation style: whether bullets should end with a period (.) or not.\n"
    "(B) Verb tense: whether bullets should be in past or present tense.\n"
    "Then minimally edit ALL bullets to conform to the chosen punctuation and tense.\n"
    "Rules:\n"
    "1) MINIMAL edits only. Do not reword, reorder, or add content.\n"
    "2) If a bullet lacks a clear leading verb, leave wording except for trailing period consistency.\n"
    "3) Preserve numbers, proper nouns, acronyms, and technical terms exactly.\n"
    "4) If a bullet already matches the chosen style/tense, leave it unchanged.\n"
    "5) Return ONLY valid JSON in the shape: {\"punctuation\": \"period\"|\"none\", \"tense\": \"past\"|\"present\", \"bullets\": [list of strings in input order]}.\n"
)


def harmonize_bullets_across_resume(experience: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Apply consistent punctuation and tense to all bullets across the resume using LLM majority rule.

    Returns a new experience list with bullets minimally edited. On failure, returns the input unchanged.
    """
    # Flatten bullets with (role_index, bullet_index, text)
    index_map: List[Tuple[int, int]] = []
    flat: List[str] = []
    for ri, role in enumerate(experience or []):
        for bi, b in enumerate(role.get("bullets", []) or []):
            index_map.append((ri, bi))
            flat.append(str(b or "").strip())

    if not flat:
        return experience

    client = _get_client()
    user = (
        "Here are the bullets in order as a JSON array. Decide majority punctuation and tense, then minimally edit all to match.\n"
        f"Bullets: {json.dumps(flat, ensure_ascii=False)}\n"
        "Return JSON object with keys 'punctuation', 'tense', and 'bullets' (same length/order)."
    )

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTIONS},
                {"role": "user", "content": user},
            ],
            temperature=0,
        )
        content = resp.choices[0].message.content or "{}"
        obj = json.loads(content)
        updated = obj.get("bullets") if isinstance(obj, dict) else None
        if not isinstance(updated, list) or len(updated) != len(flat):
            logger.warning("harmonize_bullets_across_resume: unexpected response; leaving bullets unchanged")
            return experience
        # Rebuild experience with updated bullets
        new_experience = [dict(r) for r in experience]
        for (ri, bi), text in zip(index_map, updated):
            try:
                new_experience[ri]["bullets"][bi] = str(text)
            except Exception:
                # Safety guard: ignore bad indices
                pass
        return new_experience
    except Exception:
        logger.exception("harmonize_bullets_across_resume: LLM call failed; leaving bullets unchanged")
        return experience


