from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "tasks.db"


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    task_model: str
    suggestion_model: str
    database_path: Path


def load_settings() -> Settings:
    load_dotenv(BASE_DIR / ".env")
    DATA_DIR.mkdir(exist_ok=True)
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        task_model=os.getenv("OPENAI_TASK_MODEL", "gpt-5.4-nano"),
        suggestion_model=os.getenv("OPENAI_SUGGESTION_MODEL", "gpt-5.4-mini"),
        database_path=DB_PATH,
    )
