import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine

from app.routes.recommend import router as recommend_router
from app.services.loader import init_db_and_load_if_needed

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
CSV_PATH = os.getenv("FORMULATIONS_CSV", "./data/formulations.csv")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL missing in .env")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

app = FastAPI(title="Formulation Generator")

# templates + static
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# routes
app.include_router(recommend_router)

@app.on_event("startup")
def startup_event():
    init_db_and_load_if_needed(engine, CSV_PATH)

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "active_page": "generator",
            "active_tab": "generator",
        },
    )
