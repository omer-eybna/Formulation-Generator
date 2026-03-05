import csv
from datetime import datetime, timezone
from pathlib import Path

def _project_root() -> Path:
    # app/utils/csv_logger.py -> app/utils -> app -> PROJECT_ROOT
    return Path(__file__).resolve().parents[2]

LOG_FILE = _project_root() / "logs" / "recommendation_logs.csv"

def log_request(user_input: dict, results: list[dict]) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    file_exists = LOG_FILE.exists()

    with LOG_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        if not file_exists:
            writer.writerow([
                "timestamp_utc",
                "odor_type",
                "family_type",
                "intensity",
                "tags",
                "odor_description",
                "cannabis_forward",
                "fruity_forward",
                "dessert_forward",
                "top1_name",
                "top2_name",
                "top3_name",
                "top4_name",
                "top5_name",
            ])

        ts = datetime.now(timezone.utc).isoformat()

        def safe_result(i: int) -> str | None:
            return results[i].get("name") if i < len(results) and isinstance(results[i], dict) else None

        writer.writerow([
            ts,
            user_input.get("odor_type"),
            user_input.get("family_type"),
            user_input.get("intensity_1_10") or user_input.get("intensity"),
            user_input.get("tags"),
            user_input.get("odor_description"),
            user_input.get("cannabis_forward"),
            user_input.get("fruity_forward"),
            user_input.get("dessert_forward"),
            safe_result(0),
            safe_result(1),
            safe_result(2),
            safe_result(3),
            safe_result(4),
        ])