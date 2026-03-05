from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool
import time

from app.services.matching import recommend
from app.utils.csv_logger import log_request, LOG_FILE

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


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

    # 1) heavy scoring (CPU + DB) -> threadpool
    results = await run_in_threadpool(recommend, req_payload)
    top5 = results[:5]
    t1 = time.time()

    # 2) file logging (blocking IO) -> threadpool
    log_path = await run_in_threadpool(log_request, req_payload, top5, request)
    t2 = time.time()

    print(f"[TIMING] recommend(): {(t1 - t0):.3f}s | log_request(): {(t2 - t1):.3f}s | total: {(t2 - t0):.3f}s")
    print("[CSV LOG] wrote row to:", log_path)
    print("[CSV LOG] LOG_FILE constant:", LOG_FILE)

    return templates.TemplateResponse(
        "results.html",
        {"request": request, "results": top5, "req": req_payload},
    )