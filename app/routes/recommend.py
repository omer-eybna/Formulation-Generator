from pathlib import Path
import time
from decimal import Decimal

import requests
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

from app.services.matching import recommend
from app.utils.csv_logger import LOG_FILE, log_request

BASE_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()

# n8n test webhook
N8N_WEBHOOK_URL = "http://localhost:5678/webhook-test/formulation-submitted"


def make_json_safe(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {k: make_json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [make_json_safe(v) for v in value]
    return value


@router.post("/recommend")
async def recommend_route(request: Request):
    form = await request.form()

    req_payload = {
        "odor_type": (form.get("odor_type") or "").strip(),
        "family_type": (form.get("family_type") or "").strip(),
        "tags": (form.get("tags") or "").strip(),
        "odor_description": (form.get("odor_description") or "").strip(),
        "intensity_1_10": form.get("intensity_1_10") or 5,
        "cannabis_forward": form.get("cannabis_forward") or 0,
        "fruity_forward": form.get("fruity_forward") or 0,
        "dessert_forward": form.get("dessert_forward") or 0,
    }

    t0 = time.time()

    results = await run_in_threadpool(recommend, req_payload)
    top5 = results[:5]
    t1 = time.time()

    log_path = await run_in_threadpool(log_request, req_payload, top5, request)
    t2 = time.time()

    print(
        f"[TIMING] recommend(): {(t1 - t0):.3f}s | "
        f"log_request(): {(t2 - t1):.3f}s | total: {(t2 - t0):.3f}s"
    )
    print("[CSV LOG] wrote row to:", log_path)
    print("[CSV LOG] LOG_FILE constant:", LOG_FILE)

    if top5:
        print("[DEBUG] first result:", top5[0])
        print("[DEBUG] first result keys:", list(top5[0].keys()))

    try:
        webhook_payload = {
            "request": make_json_safe(req_payload),
            "top5": make_json_safe(top5),
        }

        response = requests.post(N8N_WEBHOOK_URL, json=webhook_payload, timeout=5)
        print("[N8N] webhook sent:", response.status_code)

    except Exception as e:
        print("[N8N] webhook failed:", e)

    return templates.TemplateResponse(
        "results.html",
        {
            "request": request,
            "results": top5,
            "req": req_payload,
            "active_page": "generator",
            "active_tab": "results",
            "csv_path": str(LOG_FILE),
        },
    )