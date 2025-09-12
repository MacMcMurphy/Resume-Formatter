from datetime import datetime
from pathlib import Path
import json
import logging
import tempfile
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import os
from typing import Dict

from app.config import OUTPUT_DIR, REFERENCE_DOCX, APP_VERSION, save_api_key
import app.config as cfg
from app.services.pdf_ingest import extract_text_from_pdf
from app.services.pii import scrub_text
from app.services.extraction import extract_to_json
from app.services.normalize import normalize_resume_data
from app.services.render import render_markdown_and_docx
from app.services.summary import polish_intro_summary, enforce_sme_in_summary, generate_intro_summary
from app.services.skills import extract_candidate_skills_from_text, organize_skills_for_role
from app.services.bullets import harmonize_bullets_across_resume
from app.services.proofread import proofread_summary_text, proofread_bullets_across_resume
from app.services.seniority import infer_java_full_stack_seniority
from app.models.schema import Resume

logger = logging.getLogger(__name__)

router = APIRouter()


# Utility to upsert a variable in the .env file
def _upsert_env_var(name: str, value: str) -> None:
    # Deprecated: we now persist in per-user config; keep env var for current process
    os.environ[name] = value


@router.get("/openai_key/status")
async def openai_key_status() -> Dict[str, bool]:
    present = bool(cfg.OPENAI_API_KEY)
    return {"present": present}


@router.post("/openai_key")
async def set_openai_key(payload: Dict[str, str]):
    key = (payload or {}).get("api_key", "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="api_key is required")
    try:
        _upsert_env_var("RESUME_FORMATTER_OPENAI_API_KEY", key)
        # Persist in per-user config
        save_api_key(key)
        # Update config variable dynamically
        import app.config as cfg
        cfg.OPENAI_API_KEY = key
        # Reset shared OpenAI client used by all services
        from app.services.llm import reset_openai_client
        reset_openai_client()
        logger.info("openai_key: updated and clients reset")
        return {"ok": True}
    except Exception as e:
        logger.exception("openai_key_update_failed")
        raise HTTPException(status_code=500, detail=f"Failed to set key: {e}")


def _skill_scope_to_internal(data: dict) -> dict:
	# Transform Skill Scope schema → internal schema expected by renderer
	basics = data.get("basics", {})
	work = data.get("work", [])
	education = data.get("education", [])
	skills_list = data.get("skills", [])

	core_skills = []
	for s in skills_list:
		# flatten keywords if present else name
		if s.get("keywords"):
			core_skills.extend(s["keywords"]) 
		elif s.get("name"):
			core_skills.append(s["name"]) 

	exp = []
	for w in work:
		start = w.get("startDate", "")
		end = w.get("endDate", "")
		# reduce to YYYY-MM if possible
		start = start[:7] if len(start) >= 7 else start
		end = "Present" if (w.get("is_current") or str(end).lower() in {"", "present"}) else (end[:7] if len(end) >= 7 else end)
		exp.append({
			"company": w.get("name", ""),
			"role": w.get("position", ""),
			"location": basics.get("location", {}).get("city", ""),
			"start_date": start,
			"end_date": end,
			"summary": w.get("summary", ""),
			"bullets": w.get("highlights", []) or [],
		})

	edu = []
	for e in education:
		degree_type = e.get("studyType", "")
		area = e.get("area", "")
		degree_full = ""
		if degree_type and area:
			degree_full = f"{degree_type} in {area}"
		elif degree_type:
			degree_full = degree_type
		elif area:
			degree_full = area
		
		edu.append({
			"school": e.get("institution", ""),
			"degree": degree_full,
			"location": "",
			"grad_date": (e.get("endDate", "")[:4] if e.get("endDate") else ""),
		})

	internal = {
		"candidate_name": basics.get("name", ""),
		"candidate_title": "Senior Java Full Stack Developer",  # Always use this title
		"summary": basics.get("summary", ""),
		"core_skills": core_skills,
		"experience": exp,
		"education": edu,
		"certifications": [c.get("name", "") for c in data.get("certificates", []) if c.get("name")],
		"clearances": [],
	}
	return internal


@router.get("/health")
async def health():
	return {"status": "ok", "version": APP_VERSION}


@router.post("/estimate")
async def estimate_resume_time(file: UploadFile = File(...)):
	"""
	Quickly estimates processing time based on extracted text length.
	Heuristic derived from recent logs: ~4s base + ~2.2ms per character.
	"""
	if not file.filename.lower().endswith(".pdf"):
		raise HTTPException(status_code=400, detail="Please upload a PDF file")

	content = await file.read()
	file_bytes = len(content)

	# Write to a temporary file for the existing extractor
	with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
		tmp.write(content)
		tmp.flush()
		try:
			raw_text = extract_text_from_pdf(Path(tmp.name))
		except Exception as e:
			raise HTTPException(status_code=500, detail=f"Estimate failed: {e}")

	char_count = len(raw_text or "")
	# Rough token estimate (chars ~ 4 * tokens)
	token_estimate = max(1, char_count // 4)

	# Heuristic: base + slope * chars (ms)
	base_ms = 4000
	per_char_ms = 2.2
	estimated_ms = int(base_ms + per_char_ms * char_count)

	# Clamp to sensible bounds
	estimated_ms = max(8000, min(90000, estimated_ms))

	return JSONResponse({
		"filename": file.filename,
		"file_bytes": file_bytes,
		"char_count": char_count,
		"token_estimate": token_estimate,
		"estimated_ms": estimated_ms,
		"estimated_seconds": round(estimated_ms / 1000, 1),
	})


@router.post("/process")
async def process_resume(file: UploadFile = File(...)):
	start = datetime.utcnow()
	logger.info("process_resume: start filename=%s", file.filename)
	if not file.filename.lower().endswith(".pdf"):
		raise HTTPException(status_code=400, detail="Please upload a PDF file")

	# Create a run directory
	stamp = start.strftime("%Y%m%d-%H%M%S")
	run_dir = OUTPUT_DIR / stamp
	run_dir.mkdir(parents=True, exist_ok=True)
	logger.info("process_resume: run_dir=%s", run_dir)

	pdf_path = run_dir / file.filename
	with pdf_path.open("wb") as f:
		content = await file.read()
		f.write(content)
	logger.info("process_resume: saved_pdf bytes=%d", len(content))

	# 1) Ingest
	try:
		raw_text = extract_text_from_pdf(pdf_path)
		logger.info("ingest: extracted_chars=%d", len(raw_text))
	except Exception as e:
		logger.exception("ingest_failed")
		raise HTTPException(status_code=500, detail=f"Ingest failed: {e}")
	if not raw_text.strip():
		raise HTTPException(status_code=422, detail="No text extracted from PDF. If scanned, OCR is needed.")

	# 2) PII scrub
	scrubbed_text, token_map = scrub_text(raw_text)
	logger.info("pii: tokens=%d", len(token_map))

	# 3) LLM extract to Skill Scope JSON
	try:
		ss_data = extract_to_json(scrubbed_text)
		logger.info("extraction: success")
	except Exception as e:
		logger.exception("extraction_failed")
		raise HTTPException(status_code=500, detail=f"Extraction failed: {e}")

	# Transform to internal schema
	internal = _skill_scope_to_internal(ss_data)

	# 3.1) Seniority inference for upload route
	try:
		level = infer_java_full_stack_seniority(ss_data.get("work", []), internal.get("experience", []))
		if level:
			base_title = internal.get("candidate_title", "Java Full Stack Developer") or "Java Full Stack Developer"
			internal["candidate_title"] = f"{level} {base_title}".strip()
			logger.info("seniority: %s", internal["candidate_title"])
		else:
			logger.info("seniority: inference returned empty; keeping default title")
	except Exception:
		logger.exception("seniority_infer_failed; keeping default title")

	# 4) Validate + normalize
	try:
		resume = Resume.model_validate(internal)
		logger.info("validation: ok")
	except Exception as e:
		logger.exception("validation_failed data=%s", json.dumps(internal)[:2000])
		raise HTTPException(status_code=422, detail=f"JSON validation failed: {e}")

	# Default honorific for upload route (no UI here)
	honorific = "Mr."
	normalized = normalize_resume_data(resume.model_dump())
	normalized["honorific"] = honorific if honorific in {"Mr.", "Ms."} else "Mr."
	logger.info("normalize: done skills=%d roles=%d", len(normalized.get("core_skills", [])), len(normalized.get("experience", [])))

	# 4.1) Summary handling: generate if missing; else polish
	try:
		if not normalized.get("summary") and normalized.get("candidate_name"):
			gen = generate_intro_summary(
				resume_text=scrubbed_text,
				candidate_name=normalized.get("candidate_name", ""),
				core_skills=normalized.get("core_skills", []),
				experience=normalized.get("experience", []),
				candidate_title=normalized.get("candidate_title", ""),
			)
			if gen:
				normalized["summary"] = gen
				logger.info("summary: generated new intro summary")
		elif normalized.get("summary") and normalized.get("candidate_name"):
			polished = polish_intro_summary(
				normalized["summary"],
				normalized["candidate_name"],
				resume_context=scrubbed_text,
				candidate_title=normalized.get("candidate_title", ""),
				core_skills=normalized.get("core_skills", []),
			)
			if polished and polished != normalized["summary"]:
				normalized["summary"] = polished
				logger.info("summary: polished by LLM")
		# Enforce SME wording in summary if title is SME
		if normalized.get("candidate_title"):
			updated = enforce_sme_in_summary(normalized.get("summary", ""), normalized["candidate_title"])
			if updated != normalized.get("summary", ""):
				normalized["summary"] = updated
				logger.info("summary: SME wording enforced")
	except Exception:
		logger.exception("summary_polish_failed; continuing with original summary")

	# 4.2) Skills: prefer candidate-listed skills; else organize extracted skills for role context
	try:
		candidate_listed = extract_candidate_skills_from_text(raw_text)
		if candidate_listed:
			normalized["core_skills"] = candidate_listed
			logger.info("skills: using candidate-listed skills count=%d", len(candidate_listed))
		else:
			ordered = organize_skills_for_role(normalized.get("core_skills", []), normalized.get("experience", []), normalized.get("candidate_title", ""))
			normalized["core_skills"] = ordered
			logger.info("skills: organized for role count=%d", len(ordered))
	except Exception:
		logger.exception("skills_handling_failed; continuing with extracted skills as-is")

	# 4.3) Harmonize bullets punctuation and tense via LLM (majority rule, minimal edits)
	try:
		roles_before = sum(len(r.get("bullets", [])) for r in normalized.get("experience", []))
		normalized["experience"] = harmonize_bullets_across_resume(normalized.get("experience", []))
		roles_after = sum(len(r.get("bullets", [])) for r in normalized.get("experience", []))
		if roles_after == roles_before:
			logger.info("bullets: harmonized punctuation/tense across %d bullets", roles_after)
		else:
			logger.warning("bullets: count mismatch before=%d after=%d", roles_before, roles_after)
	except Exception:
		logger.exception("bullets_harmonization_failed; continuing with original bullets")

	# 4.4) Conservative proofreading for summary and bullets (spelling/spacing/commas only)
	try:
		if normalized.get("summary"):
			pf = proofread_summary_text(normalized["summary"])
			if pf:
				normalized["summary"] = pf
			normalized["experience"] = proofread_bullets_across_resume(normalized.get("experience", []))
			logger.info("proofread: applied to summary and bullets")
	except Exception:
		logger.exception("proofread_failed; continuing without proofreading")

	# Persist JSON
	json_path = run_dir / "resume.json"
	json_path.write_text(json.dumps(normalized, indent=2))
	logger.info("persist: wrote_json=%s", json_path)

	# 5) Render Markdown and DOCX
	try:
		md_path, docx_path = render_markdown_and_docx(normalized, run_dir, REFERENCE_DOCX)
		logger.info("render: md=%s docx=%s", md_path, docx_path)
	except Exception as e:
		logger.exception("render_failed")
		raise HTTPException(status_code=500, detail=f"Render failed: {e}")

	duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)
	logger.info("process_resume: complete duration_ms=%d", duration_ms)
	return JSONResponse({
		"run_dir": str(run_dir),
		"json_url": f"/files/{run_dir.name}/resume.json",
		"markdown_url": f"/files/{run_dir.name}/{md_path.name}",
		"docx_url": f"/files/{run_dir.name}/{docx_path.name}",
		"reference_found": REFERENCE_DOCX.exists(),
		"duration_ms": duration_ms,
	})


@router.post("/ingest")
async def ingest_resume(file: UploadFile = File(...)):
	"""
	Upload a PDF, extract raw text, and create a run directory.
	Returns: { run_dir, raw_text, char_count }
	"""
	if not file.filename.lower().endswith(".pdf"):
		raise HTTPException(status_code=400, detail="Please upload a PDF file")

	start = datetime.utcnow()
	stamp = start.strftime("%Y%m%d-%H%M%S")
	run_dir = OUTPUT_DIR / stamp
	run_dir.mkdir(parents=True, exist_ok=True)

	pdf_path = run_dir / file.filename
	with pdf_path.open("wb") as f:
		content = await file.read()
		f.write(content)

	try:
		raw_text = extract_text_from_pdf(pdf_path)
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Ingest failed: {e}")
	if not raw_text.strip():
		raise HTTPException(status_code=422, detail="No text extracted from PDF. If scanned, OCR is needed.")

	return JSONResponse({
		"run_dir": str(run_dir),
		"raw_text": raw_text,
		"char_count": len(raw_text),
	})


@router.post("/process_text")
async def process_text(payload: dict):
	"""
	Continue processing from user-reviewed text. Expected payload fields:
	- run_dir: string path created by /ingest
	- text: cleaned text after user deletions
	- candidate_name: optional override for final document
	"""
	run_dir_str = (payload or {}).get("run_dir", "").strip()
	text = (payload or {}).get("text", "")
	candidate_name_override = (payload or {}).get("candidate_name", "").strip()
	title_override = (payload or {}).get("title", "").strip()
	exp_level = (payload or {}).get("experience_level", "").strip()
	exp_custom = (payload or {}).get("experience_custom", "").strip()
	honorific = (payload or {}).get("honorific", "Mr.").strip()

	if not run_dir_str:
		raise HTTPException(status_code=400, detail="run_dir is required")
	if not text.strip():
		raise HTTPException(status_code=400, detail="text is required")

	try:
		run_dir = Path(run_dir_str)
	except Exception:
		raise HTTPException(status_code=400, detail="Invalid run_dir path")
	if not run_dir.exists():
		raise HTTPException(status_code=404, detail="run_dir not found")

	# 1) PII scrub from the user-reviewed text (still apply conservative scrubbing)
	scrubbed_text, token_map = scrub_text(text)
	logger.info("pii: tokens=%d", len(token_map))

	# 2) LLM extract to Skill Scope JSON
	try:
		ss_data = extract_to_json(scrubbed_text)
		logger.info("extraction: success")
	except Exception as e:
		logger.exception("extraction_failed")
		raise HTTPException(status_code=500, detail=f"Extraction failed: {e}")

	# Transform to internal schema
	internal = _skill_scope_to_internal(ss_data)

	# Optional candidate name override
	if candidate_name_override:
		internal["candidate_name"] = candidate_name_override

	# Optional title override
	if title_override:
		internal["candidate_title"] = title_override

	# 3.1) Seniority inference (skip if user provided title/level)
	if not (title_override or exp_level or exp_custom):
		try:
			title = infer_java_full_stack_seniority(ss_data.get("work", []), internal.get("experience", []))
			if title:
				internal["candidate_title"] = title
				logger.info("seniority: %s", internal["candidate_title"])
			else:
				logger.info("seniority: inference returned empty; keeping default title")
		except Exception:
			logger.exception("seniority_infer_failed; keeping default title")

	# 4) Validate + normalize
	try:
		resume = Resume.model_validate(internal)
		logger.info("validation: ok")
	except Exception as e:
		logger.exception("validation_failed data=%s", json.dumps(internal)[:2000])
		raise HTTPException(status_code=422, detail=f"JSON validation failed: {e}")

	normalized = normalize_resume_data(resume.model_dump())
	normalized["honorific"] = honorific if honorific in {"Mr.", "Ms."} else "Mr."
	if exp_level or exp_custom:
		normalized["experience_level"] = (exp_custom or exp_level).strip()
	logger.info("normalize: done skills=%d roles=%d", len(normalized.get("core_skills", [])), len(normalized.get("experience", [])))

	# 4.1) Summary handling: generate if missing; else polish
	try:
		if not normalized.get("summary") and normalized.get("candidate_name"):
			lvl = (exp_custom or exp_level).strip() if (exp_custom or exp_level) else ""
			title_for_prompt = normalized.get("candidate_title", "")
			if lvl and lvl.lower() in {"senior", "sme"}:
				title_for_prompt = f"{lvl} {title_for_prompt}".strip()
			gen = generate_intro_summary(
				resume_text=text,
				candidate_name=normalized.get("candidate_name", ""),
				core_skills=normalized.get("core_skills", []),
				experience=normalized.get("experience", []),
				candidate_title=title_for_prompt,
			)
			if gen:
				last = (normalized.get("candidate_name", "").strip().split() or [""])[-1]
				normalized["summary"] = f"{normalized.get('honorific','Mr.')} {last} is {gen.lstrip()}"
				logger.info("summary: generated new intro summary")
		elif normalized.get("summary") and normalized.get("candidate_name"):
			lvl = (exp_custom or exp_level).strip() if (exp_custom or exp_level) else ""
			title_for_prompt = normalized.get("candidate_title", "")
			if lvl and lvl.lower() in {"senior", "sme"}:
				title_for_prompt = f"{lvl} {title_for_prompt}".strip()
			polished = polish_intro_summary(
				normalized["summary"],
				normalized["candidate_name"],
				resume_context=text,
				candidate_title=title_for_prompt,
				core_skills=normalized.get("core_skills", []),
			)
			if polished and polished != normalized["summary"]:
				last = (normalized.get("candidate_name", "").strip().split() or [""])[-1]
				normalized["summary"] = f"{normalized.get('honorific','Mr.')} {last} is {polished.lstrip()}"
				logger.info("summary: polished by LLM")
		lvl = (exp_custom or exp_level).strip() if (exp_custom or exp_level) else ""
		if lvl.lower() == "sme":
			updated = enforce_sme_in_summary(normalized.get("summary", ""), "SME")
			if updated != normalized.get("summary", ""):
				normalized["summary"] = updated
				logger.info("summary: SME wording enforced (explicit)")
	except Exception:
		logger.exception("summary_polish_failed; continuing with original summary")

	# 4.2) Skills handling
	try:
		candidate_listed = extract_candidate_skills_from_text(text)
		if candidate_listed:
			normalized["core_skills"] = candidate_listed
			logger.info("skills: using candidate-listed skills count=%d", len(candidate_listed))
		else:
			ordered = organize_skills_for_role(normalized.get("core_skills", []), normalized.get("experience", []), normalized.get("candidate_title", ""))
			normalized["core_skills"] = ordered
			logger.info("skills: organized for role count=%d", len(ordered))
	except Exception:
		logger.exception("skills_handling_failed; continuing with extracted skills as-is")

	# 4.3) Harmonize bullets
	try:
		roles_before = sum(len(r.get("bullets", [])) for r in normalized.get("experience", []))
		normalized["experience"] = harmonize_bullets_across_resume(normalized.get("experience", []))
		roles_after = sum(len(r.get("bullets", [])) for r in normalized.get("experience", []))
		if roles_after == roles_before:
			logger.info("bullets: harmonized punctuation/tense across %d bullets", roles_after)
		else:
			logger.warning("bullets: count mismatch before=%d after=%d", roles_before, roles_after)
	except Exception:
		logger.exception("bullets_harmonization_failed; continuing with original bullets")

	# 4.4) Proofread
	try:
		if normalized.get("summary"):
			pf = proofread_summary_text(normalized["summary"])
			if pf:
				normalized["summary"] = pf
			normalized["experience"] = proofread_bullets_across_resume(normalized.get("experience", []))
			logger.info("proofread: applied to summary and bullets")
	except Exception:
		logger.exception("proofread_failed; continuing without proofreading")

	# Persist JSON
	json_path = run_dir / "resume.json"
	json_path.write_text(json.dumps(normalized, indent=2))
	logger.info("persist: wrote_json=%s", json_path)

	# Render Markdown and DOCX
	try:
		md_path, docx_path = render_markdown_and_docx(normalized, run_dir, REFERENCE_DOCX)
		logger.info("render: md=%s docx=%s", md_path, docx_path)
	except Exception as e:
		logger.exception("render_failed")
		raise HTTPException(status_code=500, detail=f"Render failed: {e}")

	return JSONResponse({
		"run_dir": str(run_dir),
		"json_url": f"/files/{run_dir.name}/resume.json",
		"markdown_url": f"/files/{run_dir.name}/{md_path.name}",
		"docx_url": f"/files/{run_dir.name}/{docx_path.name}",
		"reference_found": REFERENCE_DOCX.exists(),
	})
