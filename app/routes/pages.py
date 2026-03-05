import json
import logging
import os
from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

from app.db import engine
from app.services.scoring import score_row

logger = logging.getLogger("formulation_generator")

templates = Jinja2Templates(directory="app/templates")
router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@router.post("/recommend", response_class=HTMLResponse)
def recommend(
    request: Request,
    odor_type: str = Form(""),
    family_type: str = Form(""),
    tags: str = Form(""),
    odor_description: str = Form(""),
    intensity_1_10: int = Form(5),
    cannabis_forward: int = Form(0),
    fruity_forward: int = Form(0),
    dessert_forward: int = Form(0),
):
    req_payload = {
        "odor_type": odor_type,
        "family_type": family_type,
        "tags": tags,
        "odor_description": odor_description,
        "intensity_1_10": intensity_1_10,
        "cannabis_forward": cannabis_forward,
        "fruity_forward": fruity_forward,
        "dessert_forward": dessert_forward,
    }

    logger.info("FORM_SUBMIT payload=" + json.dumps(req_payload, ensure_ascii=False))

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT
                id,
                name,
                intensity_1_10,
                odor_description,
                aroma_color,
                odor_type,
                family_type,
                tags,
                cannabis_forward,
                fruity_forward,
                dessert_forward
            FROM formulations
        """)).mappings().all()

    scored: List[Tuple[float, Dict[str, float], Dict[str, Any]]] = []
    for r in rows:
        s, breakdown = score_row(req_payload, dict(r))
        scored.append((s, breakdown, dict(r)))

    scored.sort(key=lambda x: x[0], reverse=True)
    top5 = scored[:5]

    logger.info("TOP5 " + json.dumps([
        {"name": x[2].get("name"), "score": round(x[0], 6), "why": x[1]}
        for x in top5
    ], ensure_ascii=False))

    # IMPORTANT: results only show name, description, intensity, aroma
    results = [
        {
            "name": r.get("name"),
            "odor_description": r.get("odor_description"),
            "intensity_1_10": r.get("intensity_1_10"),
            "aroma_color": r.get("aroma_color"),
            "score": round(s, 4),
        }
        for (s, _why, r) in top5
    ]

    return templates.TemplateResponse(
        "results.html",
        {
            "request": request,
            "req": req_payload,
            "results": results,
        },
    )