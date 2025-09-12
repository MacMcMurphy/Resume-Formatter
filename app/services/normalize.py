from __future__ import annotations
from typing import Dict, Any, List
import re
from rapidfuzz import fuzz

SYNONYMS = {
	"node": "Node.js",
	"nodejs": "Node.js",
	"node.js": "Node.js",
	"postgres": "PostgreSQL",
	"gcp": "GCP",
	"ms sql": "SQL Server",
	"mongo": "MongoDB",
}

MONTHS = {
	"jan": "01", "january": "01",
	"feb": "02", "february": "02",
	"mar": "03", "march": "03",
	"apr": "04", "april": "04",
	"may": "05",
	"jun": "06", "june": "06",
	"jul": "07", "july": "07",
	"aug": "08", "august": "08",
	"sep": "09", "sept": "09", "september": "09",
	"oct": "10", "october": "10",
	"nov": "11", "november": "11",
	"dec": "12", "december": "12",
}

PRESENT_TERMS = {
	"present", "current", "now", "till now", "till date", "to date",
	"until now", "till present", "ongoing"
}


def _canon_skill(s: str) -> str:
	key = s.strip().lower()
	if key in SYNONYMS:
		return SYNONYMS[key]
	# fuzzy pass
	best = max(SYNONYMS.keys(), key=lambda k: fuzz.partial_ratio(key, k))
	if fuzz.partial_ratio(key, best) >= 90:
		return SYNONYMS[best]
	# title-case for words except well-known all-caps acronyms
	return s.strip()


def _norm_date(s: str) -> str:
	s = (s or "").strip()
	if not s:
		return s
	low = s.lower()
	# Map any present-like terms
	if low in PRESENT_TERMS:
		return "Present"
	# Remove trailing punctuation
	clean = re.sub(r"[\.,]$", "", low)
	# 1) Formats like YYYY-MM or YYYY-MM-DD or YYYY/MM
	m = re.match(r"^(\d{4})[\-/](\d{1,2})(?:[\-/]\d{1,2})?$", clean)
	if m:
		yyyy = int(m.group(1))
		mm = int(m.group(2))
		mm = 1 if mm < 1 else 12 if mm > 12 else mm
		return f"{mm:02d}/{yyyy}"
	# 2) Formats like MM-YYYY, M/YYYY, MM/YYYY
	m = re.match(r"^(\d{1,2})[\-/](\d{2,4})$", clean)
	if m:
		mm = int(m.group(1))
		y = m.group(2)
		yyyy = int(y) if len(y) == 4 else (2000 + int(y) if int(y) < 50 else 1900 + int(y))
		mm = 1 if mm < 1 else 12 if mm > 12 else mm
		return f"{mm:02d}/{yyyy}"
	# 3) Formats like 'Month YYYY' or 'Mon YYYY'
	m = re.match(r"^(\w{3,9})\s+(\d{4})$", clean)
	if m:
		mon = MONTHS.get(m.group(1)[:3]) or MONTHS.get(m.group(1))
		if mon:
			return f"{mon}/{m.group(2)}"
	# 4) Year only -> default to January
	m = re.match(r"^(\d{4})$", clean)
	if m:
		return f"01/{m.group(1)}"
	# If none matched but contains a month name anywhere and a year
	m = re.search(r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)", clean)
	y = re.search(r"(\d{4})", clean)
	if m and y:
		mon = MONTHS.get(m.group(1)) or MONTHS.get(m.group(1)[:3])
		if mon:
			return f"{mon}/{y.group(1)}"
	# Fallback: return original string (capitalized Present if detected loosely)
	return "Present" if "present" in low else s


def _clean_bullet(b: str) -> str:
	b = b.strip().lstrip("-•·• ").strip()
	return b


def normalize_resume_data(data: Dict[str, Any]) -> Dict[str, Any]:
	data = dict(data)
	# skills
	skills: List[str] = data.get("core_skills", [])
	skills = [_canon_skill(s) for s in skills]
	seen = set()
	deduped: List[str] = []
	for s in skills:
		key = s.lower()
		if key not in seen and s:
			seen.add(key)
			deduped.append(s)
	data["core_skills"] = deduped
	# experience dates and bullets
	for role in data.get("experience", []):
		if "start_date" in role:
			role["start_date"] = _norm_date(role["start_date"])
		if "end_date" in role:
			role["end_date"] = _norm_date(role["end_date"])
		role["bullets"] = [_clean_bullet(b) for b in role.get("bullets", []) if _clean_bullet(b)]
	return data

