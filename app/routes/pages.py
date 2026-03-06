from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()


@router.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "active_page": "generator",
            "active_tab": "generator",
        },
    )


@router.get("/activity")
async def activity(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "active_page": "activity",
            "active_tab": "activity",
        },
    )


@router.get("/settings")
async def settings(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "active_page": "settings",
            "active_tab": "settings",
        },
    )