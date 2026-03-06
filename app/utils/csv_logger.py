from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "recommendation_logs.csv"

HEADER = [
    "timestamp_utc",
    "client_ip",
    "user_agent",
    "odor_type",
    "family_type",
    "tags",
    "odor_description",
    "intensity_1_10",
    "cannabis_forward",
    "fruity_forward",
    "dessert_forward",
    "top1_name",
    "top1_score",
    "top2_name",
    "top2_score",
    "top3_name",
    "top3_score",
    "top4_name",
    "top4_score",
    "top5_name",
    "top5_score",
]


def _safe(v: Any) -> str:
    if v is None:
        return ""
    return str(v)


def log_request(req_payload: Dict[str, Any], top5: List[Dict[str, Any]], request=None) -> str:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")

    client_ip = ""
    user_agent = ""
    if request is not None:
        try:
            client_ip = (request.client.host if request.client else "") or ""
        except Exception:
            client_ip = ""
        try:
            user_agent = request.headers.get("user-agent", "") or ""
        except Exception:
            user_agent = ""

    row = {
        "timestamp_utc": ts,
        "client_ip": client_ip,
        "user_agent": user_agent,
        "odor_type": _safe(req_payload.get("odor_type")),
        "family_type": _safe(req_payload.get("family_type")),
        "tags": _safe(req_payload.get("tags")),
        "odor_description": _safe(req_payload.get("odor_description")),
        "intensity_1_10": _safe(req_payload.get("intensity_1_10")),
        "cannabis_forward": _safe(req_payload.get("cannabis_forward")),
        "fruity_forward": _safe(req_payload.get("fruity_forward")),
        "dessert_forward": _safe(req_payload.get("dessert_forward")),
    }

    for i in range(5):
        name_key = f"top{i+1}_name"
        score_key = f"top{i+1}_score"
        if i < len(top5):
            row[name_key] = _safe(top5[i].get("name"))
            row[score_key] = _safe(top5[i].get("score"))
        else:
            row[name_key] = ""
            row[score_key] = ""

    file_exists = LOG_FILE.exists()

    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADER)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
        f.flush()
        os.fsync(f.fileno())

    return str(LOG_FILE)