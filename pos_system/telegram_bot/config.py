from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_ENV_FILE = ROOT_DIR / ".env.telegram"


class ConfigError(RuntimeError):
    pass


def _parse_env_file(env_path: Path) -> Dict[str, str]:
    if not env_path.exists():
        raise ConfigError(f"Missing environment file: {env_path}")

    values: Dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


@dataclass(frozen=True)
class TelegramBotSettings:
    bot_token: str
    owner_telegram_id: str
    google_sheet_id: str
    env_file: Path
    ai_enabled: bool
    ai_provider: str
    openrouter_api_key: str
    openrouter_base_url: str
    openrouter_model: str
    telegram_import_interval_seconds: int
    telegram_import_flag_path: Path

    @property
    def owner_id(self) -> int | None:
        if not self.owner_telegram_id.strip():
            return None
        try:
            return int(self.owner_telegram_id.strip())
        except ValueError as exc:
            raise ConfigError("OWNER_TELEGRAM_ID must be numeric when provided.") from exc

    def is_authorized(self, telegram_user_id: int) -> bool:
        owner_id = self.owner_id
        if owner_id is None:
            return True
        return telegram_user_id == owner_id

    def authorization_notice(self, telegram_user_id: int) -> str:
        owner_id = self.owner_id
        if owner_id is None:
            return (
                "Warning: OWNER_TELEGRAM_ID is empty, so access is temporarily open. "
                f"Your Telegram user id is {telegram_user_id}."
            )
        if telegram_user_id == owner_id:
            return f"Authorized owner access. Your Telegram user id is {telegram_user_id}."
        return (
            "Access denied for this account. "
            f"Your Telegram user id is {telegram_user_id}. Allowed owner id is {owner_id}."
        )


def load_settings(env_file: str | Path | None = None) -> TelegramBotSettings:
    env_path = Path(env_file) if env_file else DEFAULT_ENV_FILE
    env_path = env_path if env_path.is_absolute() else (ROOT_DIR / env_path).resolve()
    values = _parse_env_file(env_path)

    bot_token = values.get("TELEGRAM_BOT_TOKEN", "").strip()
    google_sheet_id = values.get("GOOGLE_SHEET_ID", "").strip()
    owner_telegram_id = values.get("OWNER_TELEGRAM_ID", "").strip()
    ai_enabled = values.get("AI_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
    ai_provider = values.get("AI_PROVIDER", "openrouter").strip().lower() or "openrouter"
    openrouter_api_key = values.get("OPENROUTER_API_KEY", "").strip()
    openrouter_base_url = values.get("OPENROUTER_BASE_URL", "").strip() or "https://openrouter.ai/api/v1"
    openrouter_model = values.get("OPENROUTER_MODEL", "").strip() or "google/gemini-2.5-flash"
    interval_raw = values.get("TELEGRAM_IMPORT_INTERVAL_SECONDS", "10").strip() or "10"
    try:
        telegram_import_interval_seconds = max(1, int(interval_raw))
    except ValueError as exc:
        raise ConfigError("TELEGRAM_IMPORT_INTERVAL_SECONDS must be numeric.") from exc
    telegram_import_flag_path = ROOT_DIR / "telegram_import_now.flag"

    if not bot_token:
        raise ConfigError("TELEGRAM_BOT_TOKEN is required in .env.telegram")
    if not google_sheet_id:
        raise ConfigError("GOOGLE_SHEET_ID is required in .env.telegram")

    return TelegramBotSettings(
        bot_token=bot_token,
        owner_telegram_id=owner_telegram_id,
        google_sheet_id=google_sheet_id,
        env_file=env_path,
        ai_enabled=ai_enabled,
        ai_provider=ai_provider,
        openrouter_api_key=openrouter_api_key,
        openrouter_base_url=openrouter_base_url.rstrip("/"),
        openrouter_model=openrouter_model,
        telegram_import_interval_seconds=telegram_import_interval_seconds,
        telegram_import_flag_path=telegram_import_flag_path,
    )
