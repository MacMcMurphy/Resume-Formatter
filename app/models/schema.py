from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field

class ExperienceItem(BaseModel):
	company: str
	role: str
	location: Optional[str] = ""
	# Allow empty when source data lacks a reliable start date; otherwise enforce YYYY-MM
	start_date: str = Field(pattern=r"^(?:\d{4}-\d{2})?$")
	end_date: str  # "YYYY-MM" or "Present"
	summary: Optional[str] = ""
	bullets: List[str]

class EducationItem(BaseModel):
	school: str
	degree: Optional[str] = ""
	location: Optional[str] = ""
	grad_date: Optional[str] = ""

class Resume(BaseModel):
	candidate_name: str
	candidate_title: Optional[str] = ""
	summary: Optional[str] = ""
	core_skills: List[str]
	experience: List[ExperienceItem]
	education: List[EducationItem] = []
	certifications: List[str] = []
	clearances: List[str] = []

