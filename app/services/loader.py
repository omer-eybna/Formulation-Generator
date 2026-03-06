import json
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS formulations (
    id TEXT PRIMARY KEY,
    name TEXT,
    product_code TEXT,
    intensity_1_10 NUMERIC,
    odor_type TEXT,
    odor_description TEXT,
    tags TEXT,
    family_type TEXT,
    main_terpenes TEXT,
    cannabis_forward TEXT,
    fruity_forward TEXT,
    dessert_forward TEXT,
    aroma_color TEXT,
    notes_color_secondary TEXT,
    raw JSONB
);
"""


def _safe_value(v: Any):
    if pd.isna(v):
        return None
    return v


def init_db_and_load_if_needed(engine, csv_path: Path) -> None:
    csv_path = Path(csv_path)

    with engine.begin() as conn:
        conn.execute(text(SCHEMA_SQL))
        count = conn.execute(text("SELECT COUNT(*) FROM formulations")).scalar() or 0
        if count > 0:
            print(f"[DB] formulations already loaded: {count}")
            return

    if not csv_path.exists():
        raise RuntimeError(f"CSV file not found: {csv_path}")

    # robust encoding handling
    try:
        df = pd.read_csv(csv_path, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(csv_path, encoding="latin1")

    if "uuid" not in df.columns:
        raise RuntimeError("formulations.csv must contain a 'uuid' column")

    records = []
    for _, row in df.iterrows():
        raw = {k: _safe_value(v) for k, v in row.to_dict().items()}

        records.append(
            {
                "id": str(raw.get("uuid")),
                "name": _safe_value(raw.get("Name")),
                "product_code": _safe_value(raw.get("Product Code")),
                "intensity_1_10": _safe_value(raw.get("Intensity 1-10")),
                "odor_type": _safe_value(raw.get("Odor Type")),
                "odor_description": _safe_value(raw.get("Odor Description")),
                "tags": _safe_value(raw.get("Tags")),
                "family_type": _safe_value(raw.get("Family Type")),
                "main_terpenes": _safe_value(raw.get("Main Terpenes")),
                "cannabis_forward": _safe_value(raw.get("Cannabis Forward")),
                "fruity_forward": _safe_value(raw.get("Fruity Forward")),
                "dessert_forward": _safe_value(raw.get("Dessert Forward")),
                "aroma_color": _safe_value(raw.get("Aroma Color")),
                "notes_color_secondary": _safe_value(raw.get("Notes Color (Secondary)")),
                "raw": json.dumps(raw, ensure_ascii=False, default=str),
            }
        )

    insert_sql = text(
        """
        INSERT INTO formulations (
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
        """
    )

    with engine.begin() as conn:
        conn.execute(insert_sql, records)

    print(f"[DB] loaded {len(records)} formulations from {csv_path}")