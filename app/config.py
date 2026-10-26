import json
import os

from pydantic import BaseModel, Field


class Settings(BaseModel):
    gemini_api_key: str = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY", "").strip())
    gemini_model: str = Field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-flash-latest").strip())
    ai_timeout_seconds: int = Field(default_factory=lambda: int(os.getenv("AI_TIMEOUT_SECONDS", "15")))
    rate_limit_per_min: int = Field(default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_MIN", "30")))
    trusted_proxy_count: int = Field(default_factory=lambda: int(os.getenv("TRUSTED_PROXY_COUNT", "0")))
    allowed_origins: list[str] = Field(default_factory=lambda: Settings._parse_origins(os.getenv("ALLOWED_ORIGINS", "*")))

    @staticmethod
    def _parse_origins(val: str) -> list[str]:
        val = val.strip()
        if not val or val == "*":
            return ["*"]
        if val.startswith("[") and val.endswith("]"):
            try:
                parsed = json.loads(val)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            except Exception:
                pass
        return [item.strip() for item in val.split(",") if item.strip()]


# Global singleton settings object
settings = Settings()
