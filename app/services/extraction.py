from typing import Any, Dict, Optional
import json
import logging
from app.services.llm import get_openai_client
from app.services.skill_scope_schema import JSON_RESUME_SCHEMA

logger = logging.getLogger(__name__)

_client: Optional[object] = None

SYSTEM_PROMPT = (
    "You are an expert resume parser. Extract the entire resume into a single JSON object strictly matching the provided schema.\n"
    "Rules for 'work':\n"
    "1) Put each bullet verbatim into 'highlights'.\n"
    "2) Set 'is_current' based on endDate vs today.\n"
    "3) Sort jobs reverse-chronologically and include 'role_order' (1 for most recent).\n"
    "Rules for 'skills':\n"
    "1) Under the 'skills' JSON key, create a single object in the list.\n"
    "2) Set the 'name' field of this object to 'Technical Skills'.\n"
    "3) Find all technical skills in the resume text. Place them as a single, flat list of strings in the 'keywords' field.\n"
    "4) Do not categorize the skills (e.g., 'Databases', 'CI/CD'). The result should be a simple list like ['Java', 'Spring Boot', 'SQL', 'Docker'].\n"
    "Rules for 'education':\n"
    "1) For 'studyType', use common abbreviations: 'B.S.' for a Bachelor of Science, 'B.A.' for a Bachelor of Arts, 'M.S.' for a Master of Science, etc. Do not write out the full name.\n"
    "2) For 'area', include the major. If a minor is specified, format it as '{Major} with a Minor in {Minor}'.\n"
    "3) For 'endDate', provide only the four-digit graduation year.\n"
    "4) Do not include the university's location.\n"
    "Return only valid JSON. If a value is not found, use empty string or empty list."
)

MODEL = "gpt-4o-mini"


def _get_client():
	global _client
	if _client is None:
		_client = get_openai_client()
	return _client


def extract_to_json(scrubbed_text: str) -> Dict[str, Any]:
	client = _get_client()
	system_prompt = f"""
{SYSTEM_PROMPT}

Full JSON Schema:
{json.dumps(JSON_RESUME_SCHEMA, indent=2)}
"""
	resp = client.chat.completions.create(
		model=MODEL,
		response_format={"type": "json_object"},
		messages=[
			{"role": "system", "content": system_prompt},
			{"role": "user", "content": f"Here is the full resume text:\n\n{scrubbed_text}"},
		],
		temperature=0,
	)
	content = resp.choices[0].message.content or "{}"
	try:
		return json.loads(content)
	except Exception:
		logger.error("extraction: invalid JSON returned by model; returning empty object. snip=%s", content[:1000])
		return {} 