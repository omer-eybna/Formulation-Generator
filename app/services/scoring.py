from typing import Any, Dict, List, Tuple
import numpy as np


def norm_text(s: Any) -> str:
    if s is None:
        return ""
    return str(s).strip().lower()


def tokenize(s: str) -> List[str]:
    s = norm_text(s).replace("/", " ").replace("|", " ")
    parts: List[str] = []
    for chunk in s.split(","):
        parts.extend(chunk.split())
    return [p for p in (c.strip() for c in parts) if len(p) >= 2]


def jaccard(a: List[str], b: List[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def intensity_similarity(req: float, val: float) -> float:
    return clamp01(1.0 - abs(req - val) / 9.0)


def forward_similarity(req_c: float, req_f: float, req_d: float,
                       c: float, f: float, d: float) -> float:
    v1 = np.array([req_c, req_f, req_d], dtype=float)
    v2 = np.array([c, f, d], dtype=float)
    if np.linalg.norm(v1) == 0 or np.linalg.norm(v2) == 0:
        return 0.0
    return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))


def score_row(req: Dict[str, Any], row: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
    odor_type_req = norm_text(req.get("odor_type"))
    family_req = norm_text(req.get("family_type"))
    tags_req = tokenize(req.get("tags", ""))
    desc_req = tokenize(req.get("odor_description", ""))

    odor_type = norm_text(row.get("odor_type"))
    family = norm_text(row.get("family_type"))
    tags = tokenize(row.get("tags", ""))
    desc = tokenize(row.get("odor_description", ""))

    odor_type_score = 1.0 if odor_type_req and odor_type_req == odor_type else (0.3 if odor_type_req and odor_type_req in odor_type else 0.0)
    family_score = 1.0 if family_req and family_req == family else (0.3 if family_req and family_req in family else 0.0)

    tags_score = jaccard(tags_req, tags)
    desc_score = jaccard(desc_req, desc)

    # intensity
    def fnum(x, default=0.0):
        try:
            return float(x)
        except Exception:
            return float(default)

    inten_req = fnum(req.get("intensity_1_10", 5), 5.0)
    inten_val = fnum(row.get("intensity_1_10", 5), 5.0)
    inten_score = intensity_similarity(inten_req, inten_val)

    # forwardness (0..10)
    req_c = fnum(req.get("cannabis_forward", 0))
    req_f = fnum(req.get("fruity_forward", 0))
    req_d = fnum(req.get("dessert_forward", 0))

    c = fnum(row.get("cannabis_forward", 0))
    f = fnum(row.get("fruity_forward", 0))
    d = fnum(row.get("dessert_forward", 0))

    forward_score = clamp01((forward_similarity(req_c, req_f, req_d, c, f, d) + 1.0) / 2.0)

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