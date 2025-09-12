from __future__ import annotations
from typing import List, Dict, Any, Optional
import logging
import json
from app.services.llm import get_openai_client

logger = logging.getLogger(__name__)

MODEL = "gpt-4o-mini"


def _get_client():
    return get_openai_client()


SUMMARY_RULES = (
    "You are a conservative proofreader. Fix ONLY clear spelling mistakes and spacing/comma errors.\n"
    "Rules:\n"
    "1) Do NOT rephrase or change meaning.\n"
    "2) Preserve technical terms, acronyms, proper nouns, and capitalization.\n"
    "3) Spacing/comma fixes allowed: remove double spaces, add a single space after commas and periods, remove spaces before commas/periods, collapse repeated commas, fix missing space after period when starting a new sentence.\n"
    "4) Do NOT change whether the sentence ends with a period. Leave final punctuation as-is.\n"
    "5) Return only the corrected text as plain text."
)


def proofread_summary_text(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return text
    client = _get_client()
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SUMMARY_RULES},
                {"role": "user", "content": f"Correct this paragraph conservatively:\n{text}"},
            ],
            temperature=0,
        )
        content = (resp.choices[0].message.content or "").strip()
        return content or text
    except Exception:
        logger.exception("proofread_summary_text: LLM call failed; returning original text")
        return text


BULLETS_RULES = (
    "You are a conservative proofreader for resume bullets.\n"
    "Decisions already made elsewhere (tense and end punctuation) must be preserved.\n"
    "Fix ONLY obvious spelling errors and spacing/comma issues.\n"
    "Rules:\n"
    "1) Do NOT alter meaning, order, or wording except to fix clear typos and spacing/comma mistakes.\n"
    "2) Preserve acronyms, product names, tech terms, and capitalization.\n"
    "3) Spacing/comma fixes allowed: remove double spaces, add single space after commas/periods, remove spaces before commas/periods, collapse doubled commas, fix missing space after periods mid-line.\n"
    "4) Do NOT change the presence or absence of a terminal period on any bullet. Leave end punctuation exactly as in input.\n"
    "5) Return ONLY a JSON object: {\"bullets\": [list of strings in same order]}."
)


def proofread_bullets_across_resume(experience: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Flatten bullets
    index_map: List[tuple[int, int]] = []
    flat: List[str] = []
    for ri, role in enumerate(experience or []):
        for bi, b in enumerate(role.get("bullets", []) or []):
            index_map.append((ri, bi))
            flat.append(str(b or "").strip())

    if not flat:
        return experience

    client = _get_client()
    user = (
        "Here are resume bullets as a JSON array. Fix only obvious spelling and spacing/comma errors.\n"
        "Do NOT alter end punctuation. Return JSON with key 'bullets'.\n"
        f"Bullets: {json.dumps(flat, ensure_ascii=False)}"
    )
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": BULLETS_RULES},
                {"role": "user", "content": user},
            ],
            temperature=0,
        )
        content = resp.choices[0].message.content or "{}"
        obj = json.loads(content)
        updated = obj.get("bullets") if isinstance(obj, dict) else None
        if not isinstance(updated, list) or len(updated) != len(flat):
            logger.warning("proofread_bullets_across_resume: unexpected response; leaving bullets unchanged")
            return experience
        new_experience = [dict(r) for r in experience]
        for (ri, bi), text in zip(index_map, updated):
            try:
                new_experience[ri]["bullets"][bi] = str(text)
            except Exception:
                pass
        return new_experience
    except Exception:
        logger.exception("proofread_bullets_across_resume: LLM call failed; leaving bullets unchanged")
        return experience


