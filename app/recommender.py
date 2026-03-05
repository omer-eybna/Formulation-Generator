import numpy as np
from sqlalchemy import text

from .db import engine


def _norm_text(s):
    if s is None:
        return ""
    return str(s).strip().lower()


def _tokenize(s):
    s = _norm_text(s).replace("/", " ").replace("|", " ")
    parts = []
    for chunk in s.split(","):
        parts.extend(chunk.split())
    return [p for p in [c.strip() for c in parts] if len(p) >= 2]


def _jaccard(a, b):
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def _clamp01(x):
    return max(0.0, min(1.0, x))


def _intensity_similarity(req, val):
    # intensity in [1..10]
    return _clamp01(1.0 - abs(req - val) / 9.0)


def _forward_similarity(req_c, req_f, req_d, c, f, d):
    v1 = np.array([req_c, req_f, req_d], dtype=float)
    v2 = np.array([c, f, d], dtype=float)
    if np.linalg.norm(v1) == 0 or np.linalg.norm(v2) == 0:
        return 0.0
    return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))


def _fnum(x, default=0.0):
    """
    Converts values like:
      - "2"
      - 2
      - "2.2/5"   -> 2.2
      - ""/None   -> default
      - NaN       -> default
    """
    try:
        if x is None:
            return float(default)

        s = str(x).strip()
        if s == "" or s.lower() == "nan":
            return float(default)

        # handle "2.2/5"
        if "/" in s:
            s = s.split("/", 1)[0].strip()

        return float(s)
    except Exception:
        return float(default)


def _score_row(req, row):
    odor_type_req = _norm_text(req.get("odor_type"))
    family_req = _norm_text(req.get("family_type"))
    tags_req = _tokenize(req.get("tags", ""))
    desc_req = _tokenize(req.get("odor_description", ""))

    odor_type = _norm_text(row.get("odor_type"))
    family = _norm_text(row.get("family_type"))
    tags = _tokenize(row.get("tags", ""))
    desc = _tokenize(row.get("odor_description", ""))

    odor_type_score = (
        1.0 if odor_type_req and odor_type_req == odor_type
        else (0.3 if odor_type_req and odor_type_req in odor_type else 0.0)
    )
    family_score = (
        1.0 if family_req and family_req == family
        else (0.3 if family_req and family_req in family else 0.0)
    )

    tags_score = _jaccard(tags_req, tags)
    desc_score = _jaccard(desc_req, desc)

    inten_req = _fnum(req.get("intensity_1_10", 5), default=5.0)
    inten_val = _fnum(row.get("intensity_1_10", 5), default=5.0)
    inten_score = _intensity_similarity(inten_req, inten_val)

    req_c = _fnum(req.get("cannabis_forward", 0), default=0.0)
    req_f = _fnum(req.get("fruity_forward", 0), default=0.0)
    req_d = _fnum(req.get("dessert_forward", 0), default=0.0)

    c = _fnum(row.get("cannabis_forward", 0), default=0.0)
    f = _fnum(row.get("fruity_forward", 0), default=0.0)
    d = _fnum(row.get("dessert_forward", 0), default=0.0)

    forward_cos = _forward_similarity(req_c, req_f, req_d, c, f, d)  # [-1..1]
    forward_score = _clamp01((forward_cos + 1.0) / 2.0)             # -> [0..1]

    total = (
        0.22 * odor_type_score +
        0.18 * family_score +
        0.18 * tags_score +
        0.12 * desc_score +
        0.20 * inten_score +
        0.10 * forward_score
    )

    breakdown = {
        "odor_type": round(odor_type_score, 4),
        "family_type": round(family_score, 4),
        "tags": round(tags_score, 4),
        "description": round(desc_score, 4),
        "intensity": round(inten_score, 4),
        "forwardness": round(forward_score, 4),
    }

    return float(total), breakdown


def get_formulations():
    q = text("""
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
    """)
    with engine.connect() as conn:
        rows = conn.execute(q).mappings().all()
    return [dict(r) for r in rows]

def recommend(req_payload):
    """
    Returns a list of dicts sorted by descending score.
    Each dict includes:
      - name
      - odor_description
      - intensity_1_10
      - aroma_color
      - score
      - why (breakdown)
    """
    rows = get_formulations()

    scored = []
    for r in rows:
        s, why = _score_row(req_payload, r)
        scored.append({
            "name": r.get("name"),
            "odor_description": r.get("odor_description"),
            "intensity_1_10": r.get("intensity_1_10"),
            "aroma_color": r.get("aroma_color"),
            "score": round(s, 6),
            "why": why,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored
