import os
import logging
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[1]  # project root
load_dotenv(dotenv_path=ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL missing in .env")

logger = logging.getLogger("formulation_generator")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    future=True,
)