import json
import os
from pathlib import Path

from pydantic import BaseModel, Field

# Load .env file into os.environ if present (does not overwrite existing environment variables)
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.is_file():
    try:
        with open(_env_path, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    _k = _k.strip()
                    _v = _v.strip().strip("'\"")
                    if _k and _k not in os.environ:
                        os.environ[_k] = _v
    except Exception:
        pass


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
