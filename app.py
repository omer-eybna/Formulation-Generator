import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, text

# -----------------------
# Env + Logging
# -----------------------
ROOT = Path(__file__).resolve().parent
load_dotenv(dotenv_path=ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
CSV_PATH = os.getenv("FORMULATIONS_CSV", "./data/formulations.csv")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL missing in .env")

logger = logging.getLogger("formulation_generator")
logger.setLevel(logging.INFO)
fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

ch = logging.StreamHandler()
ch.setFormatter(fmt)
logger.addHandler(ch)

fh = logging.FileHandler("app.log")
fh.setFormatter(fmt)
logger.addHandler(fh)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

app = FastAPI(title="Formulation Generator")

# -----------------------
# DB Schema (minimal + raw JSON)
# -----------------------
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS formulations (
  id UUID PRIMARY KEY,
  name TEXT,
  product_code TEXT,
  intensity_1_10 NUMERIC,
  odor_type TEXT,
  odor_description TEXT,
  tags TEXT,
  family_type TEXT,
  main_terpenes TEXT,
  cannabis_forward NUMERIC,
  fruity_forward NUMERIC,
  dessert_forward NUMERIC,
  aroma_color TEXT,
  notes_color_secondary TEXT,
  raw JSONB
);

CREATE INDEX IF NOT EXISTS idx_formulations_odor_type ON formulations ((lower(odor_type)));
CREATE INDEX IF NOT EXISTS idx_formulations_family_type ON formulations ((lower(family_type)));
CREATE INDEX IF NOT EXISTS idx_formulations_name ON formulations ((lower(name)));
"""

# -----------------------
# Helpers
# -----------------------
def nan_to_none(v: Any) -> Any:
    if v is None:
        return None
    try:
        if isinstance(v, float) and np.isnan(v):
            return None
    except Exception:
        pass
    return v

def norm_text(s: Any) -> str:
    if s is None:
        return ""
    return str(s).strip().lower()

def tokenize(s: str) -> List[str]:
    s = norm_text(s).replace("/", " ").replace("|", " ")
    parts: List[str] = []
    for chunk in s.split(","):
        parts.extend(chunk.split())
    return [p for p in [c.strip() for c in parts] if len(p) >= 2]

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

def parse_forward_value(x: Any) -> float:
    """
    Parses:
      - 2          -> 2.0
      - "2"        -> 2.0
      - "2.2/5"    -> 4.4   (scaled to /10)
      - None/NaN   -> 0.0
    """
    x = nan_to_none(x)
    if x is None:
        return 0.0
    if isinstance(x, (int, float)):
        return float(x)

    s = str(x).strip()
    if not s:
        return 0.0

    if "/" in s:
        try:
            num_s, den_s = s.split("/", 1)
            num = float(num_s.strip())
            den = float(den_s.strip())
            if den == 0:
                return 0.0
            return num * (10.0 / den)  # scale to 0..10
        except Exception:
            return 0.0

    try:
        return float(s)
    except Exception:
        return 0.0

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

    odor_type_score = (
        1.0 if odor_type_req and odor_type_req == odor_type
        else (0.3 if odor_type_req and odor_type_req in odor_type else 0.0)
    )
    family_score = (
        1.0 if family_req and family_req == family
        else (0.3 if family_req and family_req in family else 0.0)
    )

    tags_score = jaccard(tags_req, tags)
    desc_score = jaccard(desc_req, desc)

    try:
        inten_req = float(req.get("intensity_1_10", 5))
    except Exception:
        inten_req = 5.0
    try:
        inten_val = float(nan_to_none(row.get("intensity_1_10")) or 5.0)
    except Exception:
        inten_val = 5.0
    inten_score = intensity_similarity(inten_req, inten_val)

    req_c = parse_forward_value(req.get("cannabis_forward", 0))
    req_f = parse_forward_value(req.get("fruity_forward", 0))
    req_d = parse_forward_value(req.get("dessert_forward", 0))

    c = parse_forward_value(row.get("cannabis_forward", 0))
    f = parse_forward_value(row.get("fruity_forward", 0))
    d = parse_forward_value(row.get("dessert_forward", 0))

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

def read_formulations_csv(csv_file: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(csv_file, encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return pd.read_csv(csv_file, encoding="cp1252")
        except UnicodeDecodeError:
            return pd.read_csv(csv_file, encoding="latin-1")

# -----------------------
# Load CSV into DB (only if empty)
# -----------------------
def init_db_and_load_if_needed() -> None:
    with engine.begin() as conn:
        conn.execute(text(SCHEMA_SQL))
        count = conn.execute(text("SELECT COUNT(*) FROM formulations")).scalar() or 0
        if count > 0:
            logger.info(f"DB already has {count} formulations. Skipping CSV load.")
            return

    csv_file = Path(CSV_PATH).resolve()
    if not csv_file.exists():
        raise RuntimeError(f"CSV not found: {csv_file}")

    df = read_formulations_csv(csv_file)

    uuid_col = "uuid" if "uuid" in df.columns else ("UUID" if "UUID" in df.columns else None)
    if not uuid_col:
        raise RuntimeError("formulations.csv must include a uuid column named 'uuid'")

    records: List[Dict[str, Any]] = []
    for _, r in df.iterrows():
        raw0 = r.to_dict()
        raw = {k: nan_to_none(v) for k, v in raw0.items()}

        # IMPORTANT: parse forward columns into numeric BEFORE insert
        c_fw = parse_forward_value(raw.get("Cannabis Forward"))
        f_fw = parse_forward_value(raw.get("Fruity Forward"))
        d_fw = parse_forward_value(raw.get("Dessert Forward"))

        records.append({
            "id": raw.get(uuid_col),
            "name": raw.get("Name"),
            "product_code": raw.get("Product Code"),
            "intensity_1_10": nan_to_none(raw.get("Intensity 1-10")),
            "odor_type": raw.get("Odor Type"),
            "odor_description": raw.get("Odor Description"),
            "tags": raw.get("Tags"),
            "family_type": raw.get("Family Type"),
            "main_terpenes": raw.get("Main Terpenes"),

            # store numeric values (safe for Postgres NUMERIC)
            "cannabis_forward": c_fw,
            "fruity_forward": f_fw,
            "dessert_forward": d_fw,

            "aroma_color": raw.get("Aroma Color"),
            "notes_color_secondary": raw.get("Notes Color (Secondary)"),

            # keep the entire original row (including "2.2/5") in JSON
            "raw": json.dumps(raw, ensure_ascii=False),
        })

    ins = text("""
        INSERT INTO formulations(
            id, name, product_code, intensity_1_10, odor_type, odor_description, tags,
            family_type, main_terpenes, cannabis_forward, fruity_forward, dessert_forward,
            aroma_color, notes_color_secondary, raw
        )
        VALUES (
            :id, :name, :product_code, :intensity_1_10, :odor_type, :odor_description, :tags,
            :family_type, :main_terpenes, :cannabis_forward, :fruity_forward, :dessert_forward,
            :aroma_color, :notes_color_secondary, CAST(:raw AS jsonb)
        )
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            product_code = EXCLUDED.product_code,
            intensity_1_10 = EXCLUDED.intensity_1_10,
            odor_type = EXCLUDED.odor_type,
            odor_description = EXCLUDED.odor_description,
            tags = EXCLUDED.tags,
            family_type = EXCLUDED.family_type,
            main_terpenes = EXCLUDED.main_terpenes,
            cannabis_forward = EXCLUDED.cannabis_forward,
            fruity_forward = EXCLUDED.fruity_forward,
            dessert_forward = EXCLUDED.dessert_forward,
            aroma_color = EXCLUDED.aroma_color,
            notes_color_secondary = EXCLUDED.notes_color_secondary,
            raw = EXCLUDED.raw
    """)

    with engine.begin() as conn:
        conn.execute(ins, records)

    logger.info(f"Loaded {len(records)} formulations from {csv_file}")

@app.on_event("startup")
def startup_event():
    init_db_and_load_if_needed()

# -----------------------
# HTML + CSS (inline, single file)
# -----------------------
CSS = """
:root{
  --bg-dark:#0b1020;
  --panel:#121a33;
  --panel-2:#0e1530;
  --text-main:#e7ecff;
  --text-muted:#a8b3d6;
  --accent-blue:#5b7cfa;
  --line:#263258;
  --border-radius-sm: 12px;
  --border-radius-lg: 16px;
  --transition-speed: 180ms ease;
}
*{box-sizing:border-box}
body{
  margin:0;
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
  background: radial-gradient(1200px 600px at 20% 0%, #13204a 0%, var(--bg-dark) 55%);
  color:var(--text-main);
}
.formulation-screen{max-width:1100px;margin:0 auto;padding:32px 18px 42px;}
.screen-header{font-size:34px;font-weight:800;margin:0 0 6px;}
.phase-subtitle{color:var(--text-muted);font-size:.9rem;margin:0 0 18px;}
.ai-assistant-text{
  background: rgba(18,26,51,0.85);
  border: 1px solid var(--line);
  border-radius: var(--border-radius-lg);
  padding: 14px 16px;
  line-height: 1.5;
  box-shadow: 0 10px 30px rgba(0,0,0,0.35);
}
.card{
  background: rgba(18,26,51,0.85);
  border:1px solid var(--line);
  border-radius: var(--border-radius-lg);
  padding:18px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.35);
  margin:16px 0;
}
h3{font-size:18px;margin:8px 0 12px;}
.muted{color:var(--text-muted);font-size:.85rem;margin:0 0 12px;}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;}
@media (max-width:860px){.grid{grid-template-columns:1fr;}}
.field label{display:block;font-size:12px;color:var(--text-muted);margin-bottom:6px;}
.field input,.field textarea{
  width:100%;
  background: var(--panel-2);
  border:1px solid var(--line);
  color:var(--text-main);
  border-radius: var(--border-radius-sm);
  padding:10px 12px;
  outline:none;
}
.field textarea{min-height:92px;resize:vertical;}
.field input:focus,.field textarea:focus{border-color:#6e8bff;}
.hint{font-size:12px;color:var(--text-muted);margin-top:6px;}
.slider-group{margin:16px 0;}
.slider-labels{display:flex;justify-content:space-between;color:var(--text-muted);font-size:.85rem;margin-bottom:8px;}
.eybna-slider{width:100%;accent-color:var(--accent-blue);}
.table{width:100%;border-collapse:collapse;overflow:hidden;border-radius:var(--border-radius-sm);margin-top:10px;}
.table th,.table td{border-bottom:1px solid var(--line);padding:10px;text-align:left;vertical-align:top;font-size:13px;}
.table th{color:var(--text-muted);font-weight:600;}
.table tr:hover td{background:rgba(255,255,255,0.03);}
.name{font-weight:800;}
.pill{
  display:inline-block;
  background: rgba(30,42,85,0.6);
  border:1px solid var(--line);
  padding:4px 8px;
  border-radius:999px;
  font-variant-numeric: tabular-nums;
}
.why{color:var(--text-muted);font-size:12px;}
.action-bar{
  display:flex;
  justify-content:space-between;
  align-items:center;
  gap:12px;
  margin-top:2rem;
  padding-top:1.5rem;
  border-top:1px solid rgba(255,255,255,0.1);
}
.action-right{display:flex;gap:10px;align-items:center;flex-wrap:wrap;}
.btn{
  padding:.75rem 1.5rem;
  border-radius: var(--border-radius-sm);
  font-weight:600;
  cursor:pointer;
  border:none;
  transition: var(--transition-speed);
}
.btn-secondary{background:transparent;color:var(--text-muted);}
.btn-secondary:hover{color:var(--text-main);}
.btn-primary{background:var(--text-main);color:var(--bg-dark);}
.btn-primary:hover{background:var(--accent-blue);color:#0b1020;}
.btn-crm-sync{background:#262930;color:#fff;border:1px solid #3d424e;}
.btn-crm-sync:hover{background:#3d424e;}
"""

def render_page(body_html: str, title: str = "Formulation Generator") -> HTMLResponse:
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{title}</title>
<style>{CSS}</style>
</head>
<body>
{body_html}
</body>
</html>"""
    return HTMLResponse(html)

# -----------------------
# Routes
# -----------------------
@app.get("/", response_class=HTMLResponse)
def home():
    body = """
<div class="formulation-screen">
  <div class="screen-header">Formulation Generator</div>
  <p class="phase-subtitle">Demo: match the closest 5 formulations from formulations.csv</p>

  <div class="ai-assistant-text">
    <strong>AI:</strong> Give me the sensory direction and constraints — I’ll return the closest 5 products.
  </div>

  <div class="card">
    <form method="post" action="/recommend">

      <h3>User request</h3>
      <div class="grid">
        <div class="field">
          <label>Odor Type (exact-ish match)</label>
          <input name="odor_type" placeholder="e.g., Diesel" />
          <div class="hint">Matches against formulations.csv “Odor Type”.</div>
        </div>

        <div class="field">
          <label>Family Type</label>
          <input name="family_type" placeholder="e.g., Herbal" />
        </div>

        <div class="field">
          <label>Tags (comma separated)</label>
          <input name="tags" placeholder="e.g., pine, herbal, glue, peppery" />
        </div>

        <div class="field">
          <label>Intensity (1–10)</label>
          <input name="intensity_1_10" type="number" min="1" max="10" value="5" />
        </div>
      </div>

      <div class="field" style="margin-top:14px;">
        <label>Odor Description (free text)</label>
        <textarea name="odor_description" placeholder="Describe what you want..."></textarea>
      </div>

      <h3 style="margin-top:18px;">Forward profile</h3>
      <p class="muted">These sliders bias the match to products tagged as cannabis/fruity/dessert forward.</p>

      <div class="slider-group">
        <div class="slider-labels"><span>Cannabis Forward</span><span>10</span></div>
        <input type="range" min="0" max="10" value="0" class="eybna-slider" name="cannabis_forward">
      </div>

      <div class="slider-group">
        <div class="slider-labels"><span>Fruity Forward</span><span>10</span></div>
        <input type="range" min="0" max="10" value="0" class="eybna-slider" name="fruity_forward">
      </div>

      <div class="slider-group">
        <div class="slider-labels"><span>Dessert Forward</span><span>10</span></div>
        <input type="range" min="0" max="10" value="0" class="eybna-slider" name="dessert_forward">
      </div>

      <div class="action-bar">
        <button type="button" class="btn btn-secondary" onclick="window.location.href='/'">Reset</button>
        <div class="action-right">
          <button type="submit" class="btn btn-primary">Suggest 5 Products ⚗️</button>
        </div>
      </div>

    </form>
  </div>
</div>
"""
    return render_page(body, title="Formulation Generator")

@app.post("/recommend", response_class=HTMLResponse)
def recommend_route(
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
            SELECT id, name, product_code, intensity_1_10, odor_type, odor_description, tags,
                   family_type, main_terpenes, cannabis_forward, fruity_forward, dessert_forward,
                   aroma_color, notes_color_secondary
            FROM formulations
        """)).mappings().all()

    scored = []
    for r in rows:
        s, breakdown = score_row(req_payload, dict(r))
        scored.append((s, breakdown, dict(r)))

    scored.sort(key=lambda x: x[0], reverse=True)
    top5 = scored[:5]

    rows_html = ""
    for idx, (s, why, r) in enumerate(top5, start=1):
        rows_html += f"""
        <tr>
          <td>{idx}</td>
          <td class="name">{r.get("name","") or "—"}</td>
          <td>{r.get("product_code","") or "—"}</td>
          <td>{r.get("odor_type","") or "—"}</td>
          <td>{r.get("family_type","") or "—"}</td>
          <td>{r.get("intensity_1_10","") or "—"}</td>
          <td><span class="pill">{round(s,4)}</span></td>
          <td class="why">
            odor {why["odor_type"]},
            family {why["family_type"]},
            tags {why["tags"]},
            desc {why["description"]},
            intensity {why["intensity"]},
            forward {why["forwardness"]}
          </td>
        </tr>
        """

    body = f"""
<div class="formulation-screen">
  <div class="screen-header">Top 5 Matches</div>
  <p class="phase-subtitle">Closest 5 products to your request</p>

  <div class="card">
    <h3>Request summary</h3>
    <div class="muted"><b>Odor Type:</b> {odor_type or "—"} • <b>Family:</b> {family_type or "—"} • <b>Intensity:</b> {intensity_1_10}</div>
    <div class="muted"><b>Tags:</b> {tags or "—"}</div>
    <div class="muted"><b>Description:</b> {odor_description or "—"}</div>
    <div class="muted"><b>Forward:</b> cannabis {cannabis_forward}, fruity {fruity_forward}, dessert {dessert_forward}</div>
  </div>

  <div class="card">
    <h3>Top 5</h3>
    <table class="table">
      <thead>
        <tr>
          <th>#</th>
          <th>Name</th>
          <th>Product Code</th>
          <th>Odor Type</th>
          <th>Family</th>
          <th>Intensity</th>
          <th>Score</th>
          <th>Why</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>

    <div class="action-bar">
      <button type="button" class="btn btn-secondary" onclick="window.location.href='/'">← Back</button>
      <div class="action-right">
        <button type="button" class="btn btn-primary" onclick="window.location.href='/'">Refine request</button>
      </div>
    </div>
  </div>
</div>
"""
    return render_page(body, title="Top 5 Matches")
