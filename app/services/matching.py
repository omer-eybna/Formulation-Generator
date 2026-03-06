from typing import Any, Dict, List

from sqlalchemy import text

from app.db import engine
from app.services.scoring import score_row


def recommend(req_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT
                    name,
                    odor_description,
                    intensity_1_10,
                    aroma_color,
                    odor_type,
                    family_type,
                    tags,
                    cannabis_forward,
                    fruity_forward,
                    dessert_forward
                FROM formulations
                """
            )
        ).mappings().all()

    scored: List[Dict[str, Any]] = []
    for r in rows:
        row = dict(r)
        score, why = score_row(req_payload, row)

        scored.append(
            {
                "name": row.get("name"),
                "description": row.get("odor_description"),
                "intensity": row.get("intensity_1_10"),
                "aroma": row.get("aroma_color"),
                "score": round(score, 6),
                "why": why,
            }
        )

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored