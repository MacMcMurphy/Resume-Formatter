import json
from pathlib import Path
from app.config import TEMPLATES_DIR

DEFAULT_STYLE_NAMES = {
	"title": "Custom Header 1",
	"candidate_title": "Custom Header 2", 
	"summary": "Custom Paragraph 1",
	"skills_body": "Custom Paragraph 1",
	"job_header": "Custom Header 2",
	"role_header": "Custom Heading 1",
	"body": "Custom Paragraph 1",
	"bullet": "Custom Bullets 1",
	"section_heading": "Custom Heading 1",
	"spacer": "Spacer",
}


def load_style_names() -> dict:
	path: Path = TEMPLATES_DIR / "style_map.json"
	names = DEFAULT_STYLE_NAMES.copy()
	if path.exists():
		try:
			user_map = json.loads(path.read_text())
			if isinstance(user_map, dict):
				names.update(user_map)
		except Exception:
			pass
	return names
