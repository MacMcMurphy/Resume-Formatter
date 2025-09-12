from pathlib import Path
from io import StringIO
from pdfminer.high_level import extract_text_to_fp

def extract_text_from_pdf(pdf_path: Path) -> str:
	output = StringIO()
	with open(pdf_path, "rb") as f:
		extract_text_to_fp(f, output, laparams=None)
	return output.getvalue()
