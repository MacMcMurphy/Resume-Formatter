from __future__ import annotations
from typing import List, Optional, Dict, Any
import logging
import re
from app.services.llm import get_openai_client

logger = logging.getLogger(__name__)

MODEL = "gpt-4o-mini"


def _get_client():
    return get_openai_client()


_SKILLS_HEADINGS = [
    r"^skills$",
    r"^technical\s+skills$",
    r"^core\s+competenc(?:y|ies)$",
    r"^technical\s+proficienc(?:y|ies)$",
    r"^technology\s+summary$",
    r"^tools\s*&\s*technologies$",
]
_HEADING_RE = re.compile("|".join(_SKILLS_HEADINGS), re.IGNORECASE)


def extract_candidate_skills_from_text(raw_text: str) -> List[str]:
    """Heuristically parse a candidate-provided skills section from raw resume text.

    Returns a list of skill tokens if a dedicated skills section is found; else [].
    """
    if not raw_text:
        return []

    lines = [l.strip() for l in raw_text.splitlines()]
    skills_lines: List[str] = []
    in_section = False
    for line in lines:
        if not in_section:
            if _HEADING_RE.search(line.lower()):
                in_section = True
                continue
        else:
            if not line or len(line) > 200:
                # stop on blank or suspiciously long line (likely next section)
                if skills_lines:
                    break
                else:
                    continue
            # Stop if line looks like a new section heading (all caps wordy line)
            if re.match(r"^[A-Z][A-Z\s&/-]{3,}$", line) and not re.search(r"[,;]", line):
                break
            skills_lines.append(line)

    # Tokenize collected lines
    tokens: List[str] = []
    for l in skills_lines:
        # split on commas/semicolons/bullets
        parts = re.split(r"[;,]|\s[-•·]\s", l)
        for p in parts:
            tok = p.strip().strip("-•· ")
            if not tok:
                continue
            # discard sentence-like content
            if len(tok) > 64 or re.search(r"\b(years?|experience|working with|proficient in)\b", tok, re.I):
                continue
            tokens.append(tok)

    # Deduplicate while preserving order (case-insensitive)
    seen = set()
    ordered: List[str] = []
    for t in tokens:
        key = t.lower()
        if key not in seen:
            seen.add(key)
            ordered.append(t)

    # Heuristic threshold: consider valid if we found at least 4 distinct items
    return ordered if len(ordered) >= 4 else []


def organize_skills_for_role(skills: List[str], experience: List[Dict[str, Any]], candidate_title: str = "") -> List[str]:
    """Use the LLM to reorder/group the given skills appropriately for the candidate's context.

    - No new skills may be added; no unrelated deletions.
    - May deduplicate near-duplicates by choosing one canonical form.
    - Output is returned as a JSON array of strings.
    """
    if not skills:
        return skills

    client = _get_client()
    exp_roles = ", ".join([e.get("role", "").strip() for e in (experience or []) if e.get("role")])
    sys = (
        "You are a resume editor. Reorder the provided list of skills to group similar items adjacently and to prioritize what makes sense for the candidate's likely role (e.g., Java full stack vs. cloud engineer).\n"
        "Rules: Do not invent new skills. You may deduplicate near-duplicates by keeping the most standard form (e.g., 'PostgreSQL' over 'Postgres'). Return ONLY a JSON array of strings in the desired order."
    )
    user = (
        f"Candidate title (may be empty): {candidate_title}\n"
        f"Experience roles: {exp_roles}\n"
        f"Skills to organize (array): {skills}\n"
        "Return only JSON array with the reordered (and deduplicated if necessary) skills."
    )

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": sys},
                {"role": "user", "content": user},
            ],
            temperature=0,
        )
        content = resp.choices[0].message.content or "{}"
        import json
        obj = json.loads(content)
        # Accept either {"skills": [...]} or just {"result": [...]} or direct [...]
        if isinstance(obj, list):
            ordered = obj
        elif isinstance(obj, dict):
            ordered = obj.get("skills") or obj.get("result") or []
        else:
            ordered = []
        # Fallback to original if something went wrong
        if not isinstance(ordered, list) or not ordered:
            logger.warning("organize_skills_for_role: unexpected response; keeping original order")
            return skills
        # Strip/clean strings and drop empties
        cleaned = [str(s).strip() for s in ordered if str(s).strip()]
        # Final dedupe preserving order
        seen = set()
        final: List[str] = []
        for s in cleaned:
            k = s.lower()
            if k not in seen:
                seen.add(k)
                final.append(s)
        return final or skills
    except Exception:
        logger.exception("organize_skills_for_role: LLM call failed; keeping original skills order")
        return skills


