import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from sqlalchemy import text

logger = logging.getLogger("formulation_generator")

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


def _parse_numeric(x: Any) -> Optional[float]:
    """
    Accepts:
      - 3, 3.5, "2"
      - "2.2/5" (convert to 0..10 scale => (2.2/5)*10 = 4.4)
      - NaN/None => None
    """
    if x is None:
        return None
    try:
        if pd.isna(x):
            return None
    except Exception:
        pass

    s = str(x).strip()
    if s == "":
        return None

    # fraction like 2.2/5
    m = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*([0-9]+(?:\.[0-9]+)?)\s*$", s)
    if m:
        num = float(m.group(1))
        den = float(m.group(2))
        if den == 0:
            return None
        # normalize fraction to 0..10 scale
        return (num / den) * 10.0

    # normal float
    try:
        return float(s)
    except Exception:
        return None


def read_csv_safely(csv_file: Path) -> pd.DataFrame:
    # Try utf-8 first, then fall back
    try:
        return pd.read_csv(csv_file, encoding="utf-8")
    except UnicodeDecodeError:
        logger.warning("CSV utf-8 decode failed; retrying with latin-1 encoding")
        return pd.read_csv(csv_file, encoding="latin-1")


def init_db_and_load_if_needed(engine, csv_path: str) -> None:
    with engine.begin() as conn:
        conn.execute(text(SCHEMA_SQL))
        count = conn.execute(text("SELECT COUNT(*) FROM formulations")).scalar() or 0
        if count > 0:
            logger.info(f"DB already has {count} formulations. Skipping CSV load.")
            return

    csv_file = Path(csv_path).resolve()
    if not csv_file.exists():
        raise RuntimeError(f"CSV not found: {csv_file}")

    df = read_csv_safely(csv_file)

    uuid_col = "uuid" if "uuid" in df.columns else ("UUID" if "UUID" in df.columns else None)
    if not uuid_col:
        raise RuntimeError("formulations.csv must include a uuid column named 'uuid' (or 'UUID').")

    records = []
    for _, r in df.iterrows():
        raw = r.to_dict()

        records.append({
            "id": raw.get(uuid_col),
            "name": raw.get("Name"),
            "product_code": raw.get("Product Code"),
            "intensity_1_10": _parse_numeric(raw.get("Intensity 1-10")),
            "odor_type": raw.get("Odor Type"),
            "odor_description": raw.get("Odor Description"),
            "tags": raw.get("Tags"),
            "family_type": raw.get("Family Type"),
            "main_terpenes": raw.get("Main Terpenes"),
            "cannabis_forward": _parse_numeric(raw.get("Cannabis Forward")),
            "fruity_forward": _parse_numeric(raw.get("Fruity Forward")),
            "dessert_forward": _parse_numeric(raw.get("Dessert Forward")),
            "aroma_color": raw.get("Aroma Color"),
            "notes_color_secondary": raw.get("Notes Color (Secondary)"),
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