import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from appdirs import user_data_dir, user_config_dir

# Constants
APP_NAME = "Resume Formatter"

# Project root (source dev mode). In bundled (PyInstaller) mode, resources are under sys._MEIPASS.
def _source_project_root() -> Path:
	return Path(__file__).resolve().parent.parent

def resource_path(relative_path: str) -> Path:
	"""Return a Path to a bundled resource (PyInstaller) or source path (dev)."""
	base = getattr(sys, "_MEIPASS", None)
	if base:
		return Path(base) / relative_path
	return _source_project_root() / relative_path

# Load .env in dev mode (from repository root) for convenience
_DEV_ENV = _source_project_root() / ".env"
if _DEV_ENV.exists():
	load_dotenv(_DEV_ENV)

# Per-user writable locations
USER_DATA_DIR = Path(user_data_dir(APP_NAME))
USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

USER_CONFIG_DIR = Path(user_config_dir(APP_NAME))
USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_PATH = USER_CONFIG_DIR / "config.json"

def _read_config_file() -> dict:
	try:
		if CONFIG_PATH.exists():
			return json.loads(CONFIG_PATH.read_text() or "{}")
	except Exception:
		pass
	return {}

def _write_config_file(cfg: dict) -> None:
	try:
		CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
		CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
	except Exception:
		print("[warn] failed to write config.json")

def get_saved_api_key() -> str:
	cfg = _read_config_file()
	return (cfg.get("RESUME_FORMATTER_OPENAI_API_KEY") or "").strip()

def save_api_key(key: str) -> None:
	cfg = _read_config_file()
	cfg["RESUME_FORMATTER_OPENAI_API_KEY"] = key.strip()
	_write_config_file(cfg)

# Resolve OpenAI key precedence: env var overrides saved config
OPENAI_API_KEY = os.getenv("RESUME_FORMATTER_OPENAI_API_KEY") or get_saved_api_key()
if not OPENAI_API_KEY:
	print("[warn] RESUME_FORMATTER_OPENAI_API_KEY is not set; extraction will fail until provided")

# Resource directories (bundled-safe)
TEMPLATES_DIR = resource_path("templates")
VIEWS_DIR = resource_path("app/views")

# Writable output directory under user data dir
OUTPUT_DIR = USER_DATA_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# support either Reference.docx or reference.docx from packaged templates
REFERENCE_DOCX = TEMPLATES_DIR / "Reference.docx"
if not REFERENCE_DOCX.exists():
	alt = TEMPLATES_DIR / "reference.docx"
	REFERENCE_DOCX = alt if alt.exists() else REFERENCE_DOCX
if not REFERENCE_DOCX.exists():
	print(f"[warn] reference.docx not found at {TEMPLATES_DIR}")

def get_pandoc_executable() -> str:
	"""Return path to bundled pandoc if present; else fallback to 'pandoc' on PATH."""
	# In a bundled app, we add the pandoc binary under 'bin/pandoc'
	bundled = resource_path("bin/pandoc")
	if bundled.exists():
		return str(bundled)
	return "pandoc"

# Increment per release
APP_VERSION = "0.2.0"
