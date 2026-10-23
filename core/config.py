import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class BaseConfig:
    """Settings shared by all bot implementations."""

    site_base_url: str = field(
        default_factory=lambda: os.getenv(
            "SITE_BASE_URL", "https://xn--80aapkb3algkc.xn--c1akgjz.xn--p1ai"
        )
    )
    db_path: str = field(default_factory=lambda: os.getenv("DB_PATH", "bot.db"))
    http_timeout: float = field(
        default_factory=lambda: float(os.getenv("HTTP_TIMEOUT", "20"))
    )
    cache_ttl: float = field(
        default_factory=lambda: float(os.getenv("CACHE_TTL", "300"))
    )


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"{name} is not set. Copy .env.example to .env or export {name}."
        )
    return value
