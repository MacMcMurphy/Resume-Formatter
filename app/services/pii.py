import re
from typing import Tuple, Dict

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:(?:\+?1[ .-]?)?(?:\(\d{3}\)|\d{3})[ .-]?\d{3}[ .-]?\d{4})")
ADDRESS_HINT = re.compile(r"\d+\s+[^\n,]+(?:Street|St\.|Avenue|Ave\.|Road|Rd\.|Boulevard|Blvd\.|Lane|Ln\.|Drive|Dr\.)", re.IGNORECASE)
URL_RE = re.compile(r"(?:(?:https?://)[^\s)]+|(?:www\.[^\s)]+)|\b[a-zA-Z0-9.-]+\.(?:com|org|net|io|ai|co|edu|gov|us|uk|ca|de|fr|au|in|nz)(?:/[\w\-./?%&=+#]*)?)")


def _tokenize(text: str, pattern: re.Pattern, token_prefix: str, token_map: Dict[str, str]) -> str:
	idx = 1
	def repl(m: re.Match) -> str:
		nonlocal idx
		val = m.group(0)
		token = f"[[{token_prefix}_{idx}]]"
		token_map[token] = val
		idx += 1
		return token
	return pattern.sub(repl, text)


def scrub_text(text: str) -> Tuple[str, Dict[str, str]]:
	"""Return scrubbed text and a token->original map."""
	token_map: Dict[str, str] = {}
	scrubbed = text
	scrubbed = _tokenize(scrubbed, EMAIL_RE, "EMAIL", token_map)
	scrubbed = _tokenize(scrubbed, PHONE_RE, "PHONE", token_map)
	scrubbed = _tokenize(scrubbed, URL_RE, "URL", token_map)
	# Address is heuristic; keep it conservative
	scrubbed = _tokenize(scrubbed, ADDRESS_HINT, "ADDR", token_map)
	return scrubbed, token_map

