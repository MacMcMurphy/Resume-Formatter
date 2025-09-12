from __future__ import annotations
from typing import Optional
import re
import logging
from app.services.llm import get_openai_client

logger = logging.getLogger(__name__)

MODEL = "gpt-4o-2024-05-13"


def _get_client():
    return get_openai_client()


INSTRUCTIONS = (
    "You are a precise copy editor. Rewrite the provided intro paragraph to strictly satisfy all rules with PURPOSEFUL edits.\n"
    "Goals:\n"
    "- DO NOT include the candidate name or the 'Mr./Ms. <LastName> is' prefix. Return only the body text.\n"
    "- MINIMIZE pronouns; prefer action/noun-phrase structures like 'Implemented X', 'Expert in Y'.\n"
    "- Replace vague language (e.g., 'variety of', 'various things', 'numerous') with specific technologies and domains found in the resume.\n"
    "- Keep facts strictly grounded in the resume; do not invent skills, domains, or metrics.\n"
    "- Match the style, tone, and approximate length of the template guide below without copying phrases verbatim.\n"
    "- Preserve technical terms exactly as in the resume (e.g., Spring Boot, Kafka, Angular).\n"
    "- No markdown, no quotes. Return plain text only.\n"
)

TEMPLATE_GUIDE = (
    "Reference template (style and length only; do not copy wording):\n"
    "Mr. Pierce is a results-driven Senior Software Developer/Architect with 15+ years of experience in designing and developing robust, scalable applications using Java, Kotlin, and modern frameworks like Spring Boot, Angular, and React. Proven expertise in microservices architecture, cloud technologies (AWS, GCP), and backend distributed systems. Demonstrated success in finance, hospitality, and telecommunications domains, delivering high-quality solutions with a focus on performance, reliability, and security. Strong skills in API integration, Kafka streaming, and full-stack development, coupled with Agile methodologies and DevOps practices. Experienced in building and deploying scalable, cloud-native applications using containerization technologies like Docker and Kubernetes. Proven success in automating infrastructure with Terraform, enhancing deployment efficiency and reducing errors. Passionate about leveraging Generative AI and assistive AI tools to drive innovation and improve application performance and user experience.\n"
)


def polish_intro_summary(original_summary: str, candidate_name: str, resume_context: str | None = None, candidate_title: str | None = None, core_skills: list[str] | None = None) -> str:
    """Use the LLM to minimally rewrite the intro paragraph.

    - Ensures third person
    - Prefixes with Mr./Ms. <LastName> is ...
    - Chooses Mr./Ms. by inferring gender from name
    """
    summary = (original_summary or "").strip()
    # Do not require or use the candidate name; keep it local
    if not summary:
        return original_summary

    client = _get_client()
    context_bits = []
    if candidate_title:
        context_bits.append(f"Likely role/title: {candidate_title}")
    if core_skills:
        # Keep to a reasonable length
        top = ", ".join(core_skills[:40])
        context_bits.append(f"Top technologies from resume: {top}")
    if resume_context:
        context_bits.append(f"Resume context (verbatim):\n{resume_context}")

    prompt = (
        ("\n".join(context_bits) + "\n\n" if context_bits else "")
        + f"Original intro paragraph (verbatim):\n{summary}\n\n"
        + f"{TEMPLATE_GUIDE}\n"
        + "Rewrite the paragraph now following all rules and the template's style/length. Return only the body text without any name prefix."
    )

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": INSTRUCTIONS},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        content = (resp.choices[0].message.content or "").strip()
        return content or original_summary
    except Exception:
        logger.exception("polish_intro_summary: LLM call failed; returning original summary")
        return original_summary


def generate_intro_summary(
    resume_text: str,
    candidate_name: str,
    core_skills: list[str] | None = None,
    experience: list[dict] | None = None,
    candidate_title: str | None = None,
) -> str:
    """Generate a new intro summary from the resume content when none exists.

    Requirements:
    - Third person only, prefixed with Mr./Ms. <LastName> is ...
    - Use the provided template ONLY as a stylistic guide; do not copy wording.
    - Base ALL facts strictly on the resume input (text, skills, experience, title).
    - 3–5 concise sentences; no markdown or quotes.
    - Preserve technical terms as they appear in the resume.
    """
    text = (resume_text or "").strip()
    # Name stays local; do not send it
    if not text:
        return ""

    client = _get_client()
    sys = (
        "You are a resume writer. Create a concise professional summary using ONLY the provided resume data.\n"
        "Style guide (do not copy wording):\n"
        "- Tone: results-driven, senior, confident but factual.\n"
        "- Structure: 3–5 sentences, third-person, start with 'Mr./Ms. <LastName> is'.\n"
        "- After the first sentence, minimize pronouns; prefer action/noun-phrase structures like 'Implemented X', 'Expert in Y'.\n"
        "- Target the likely role (use provided title if present; otherwise infer from experience).\n"
        "- Content sources: strictly from resume text, skills, experience, and title provided.\n"
        "- Forbidden: inventing numbers, technologies, domains, or vague phrasing (e.g., 'variety of', 'various things').\n"
        "- Keep product and technology names exactly as found.\n"
        "- Match the style, tone, and approximate length of the template guide; do not copy exact sentences.\n"
        "- No markdown, no quotes. Return plain text only.\n"
        f"\n{TEMPLATE_GUIDE}"
    )
    # Provide structured hints, but the model must rely only on them and the raw text
    user = (
        f"Candidate title (optional): {candidate_title or ''}\n"
        f"Skills list (optional): {', '.join(core_skills or [])}\n"
        f"Experience roles (optional): {', '.join([str(r.get('role','')) for r in (experience or []) if r.get('role')])}\n\n"
        "Resume text (verbatim):\n"
        f"{text}\n\n"
        "Write the 3–5 sentence summary now, following the style guide and using only information available above. Do NOT include any name/prefix; return only the body text."
    )

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": sys},
                {"role": "user", "content": user},
            ],
            temperature=0,
        )
        content = (resp.choices[0].message.content or "").strip()
        return content
    except Exception:
        logger.exception("generate_intro_summary: LLM call failed")
        return ""


_SENIOR_WORD_RE = re.compile(r"\b[Ss]enior\b")


def enforce_sme_in_summary(summary_text: str, candidate_title: str) -> str:
    """If the inferred title is SME, replace standalone 'senior' in the summary with 'SME'.

    Conservative: only replaces the exact word 'Senior/senior' at word boundaries.
    Does not touch 'seniority' or other substrings.
    """
    if not summary_text or not candidate_title:
        return summary_text
    if not candidate_title.strip().startswith("SME"):
        return summary_text
    return _SENIOR_WORD_RE.sub("SME", summary_text)


