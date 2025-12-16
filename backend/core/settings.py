import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import List, Any

# Đường dẫn cố định để đọc cấu hình
SETTINGS_PATH = Path(__file__).resolve().parent.parent / "config" / "settings.json"


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return False


def _coerce_positive_int(value: Any, default: int) -> int:
    try:
        num = int(value)
        return num if num > 0 else default
    except (TypeError, ValueError):
        return default


def _parse_profile_ids(value: Any) -> List[str]:
    if isinstance(value, list):
        items = value
    elif isinstance(value, str):
        items = value.split(",")
    else:
        return []

    return [str(item).strip() for item in items if str(item).strip()]


@dataclass
class Settings:
    api_key: str
    headless: bool = False
    target_url: str = "https://facebook.com"
    profile_ids: List[str] = field(default_factory=list)
    run_minutes: int = 30
    rest_minutes: int = 120


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Đọc và cache cấu hình từ settings.json.
    Gọi get_settings.cache_clear() nếu cần reload.
    """
    if not SETTINGS_PATH.exists():
        raise FileNotFoundError(f"Không tìm thấy file cấu hình: {SETTINGS_PATH}")

    with SETTINGS_PATH.open(encoding="utf-8") as f:
        try:
            raw = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f"settings.json không hợp lệ: {exc}") from exc

    return Settings(
        api_key=str(raw.get("API_KEY", "")),
        headless=_parse_bool(raw.get("HEADLESS", False)),
        target_url=str(raw.get("TARGET_URL", "https://facebook.com")),
        profile_ids=_parse_profile_ids(raw.get("PROFILE_IDS", [])),
        run_minutes=_coerce_positive_int(raw.get("RUN_MINUTES", 30), 30),
        rest_minutes=_coerce_positive_int(raw.get("REST_MINUTES", 120), 120),
    )


def reload_settings() -> Settings:
    """Xóa cache và đọc lại settings.json (dùng khi file đổi nội dung)."""
    get_settings.cache_clear()
    return get_settings()

