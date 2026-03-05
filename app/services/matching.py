# app/services/matching.py
from app.db import engine
from sqlalchemy import text
from app.services.scoring import score_row  # your existing scoring fn

def recommend(req_payload: dict):
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT
              id,
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
        """)).mappings().all()

    scored = []
    for r in rows:
        row = dict(r)
        s, why = score_row(req_payload, row)

        scored.append({
            "name": row.get("name"),
            "description": row.get("odor_description"),
            "intensity": row.get("intensity_1_10"),
            "aroma": row.get("aroma_color"),

            "score": float(s),
            "why": why,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored