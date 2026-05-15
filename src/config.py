from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


ENV_PATH = Path(__file__).resolve().parent / ".env"
DEFAULT_JWT_EXPIRE_MINUTES = 60
DEFAULT_ALLOWED_ORIGINS = (
    "http://127.0.0.1:8001,"
    "http://127.0.0.1:8010,"
    "http://localhost:8010,"
    "https://multi-db-react-agent-259390522728.us-central1.run.app"
)

load_dotenv(ENV_PATH,override=False)


class Settings:
    def _required(self, name: str) -> str:
        value = os.environ.get(name)
        if not value:
            raise RuntimeError(f"{name} must be configured.")
        return value

    @property
    def openai_api_key(self) -> str:
        return self._required("OPENAI_API_KEY")

    @property
    def supabase_uri(self) -> str:
        return self._required("SUPABASE_URI")

    @property
    def mongo_uri(self) -> str:
        return self._required("MONGO_URI")

    @property
    def google_client_id(self) -> str:
        return os.environ.get("GOOGLE_CLIENT_ID", "")

    @property
    def jwt_secret_key(self) -> str:
        return self._required("JWT_SECRET_KEY")

    @property
    def jwt_expire_minutes(self) -> int:
        return int(os.environ.get("JWT_EXPIRE_MINUTES", DEFAULT_JWT_EXPIRE_MINUTES))

    @property
    def allowed_origins(self) -> list[str]:
        raw_origins = os.environ.get("ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS)
        return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


settings = Settings()
