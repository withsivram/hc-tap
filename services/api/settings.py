# services/api/settings.py
import os

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()  # loads .env from repo root


class Settings(BaseModel):
    APP_RUN_ID: str = os.getenv("RUN_ID", "LOCAL")
    NOTES_DIR: str = os.getenv("NOTES_DIR", "fixtures/notes")
    ENRICHED_DIR: str = os.getenv("ENRICHED_DIR", "fixtures/enriched/entities")
    RUN_MANIFEST: str = os.getenv("RUN_MANIFEST", "fixtures/runs_LOCAL.json")


settings = Settings()
