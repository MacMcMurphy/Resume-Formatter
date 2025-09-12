import logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import app.config as cfg
from app.routers.convert import router as convert_router

# Configure logging
logging.basicConfig(
	level=logging.INFO,
	format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Resume Formatter", version=cfg.APP_VERSION)

# Serve output files for download
app.mount("/files", StaticFiles(directory=str(cfg.OUTPUT_DIR)), name="files")

templates = Jinja2Templates(directory=str(cfg.VIEWS_DIR))

@app.on_event("startup")
async def on_startup():
	logger.info("App starting. version=%s", cfg.APP_VERSION)
	logger.info("reference_docx_exists=%s path=%s", cfg.REFERENCE_DOCX.exists(), cfg.REFERENCE_DOCX)
	logger.info("openai_key_present=%s", bool(cfg.OPENAI_API_KEY))

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
	if not cfg.OPENAI_API_KEY:
		return RedirectResponse(url="/setup", status_code=302)
	return templates.TemplateResponse("index.html", {"request": request, "version": cfg.APP_VERSION})

@app.get("/setup", response_class=HTMLResponse)
async def setup(request: Request):
	return templates.TemplateResponse("setup.html", {"request": request, "version": cfg.APP_VERSION})

# API routes
app.include_router(convert_router, prefix="/api")
