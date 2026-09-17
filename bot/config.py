import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Config:
    bot_token: str
    site_base_url: str = field(
        default_factory=lambda: os.getenv(
            "SITE_BASE_URL", "https://xn--80aapkb3algkc.xn--c1akgjz.xn--p1ai"
        )
    )
    db_path: str = field(default_factory=lambda: os.getenv("DB_PATH", "bot.db"))
    telegram_proxy: str = field(default_factory=lambda: os.getenv("TELEGRAM_PROXY", ""))
    http_timeout: float = field(
        default_factory=lambda: float(os.getenv("HTTP_TIMEOUT", "20"))
    )
    cache_ttl: float = field(
        default_factory=lambda: float(os.getenv("CACHE_TTL", "300"))
    )

    @classmethod
    def from_env(cls) -> "Config":
        token = os.getenv("BOT_TOKEN")
        if not token:
            raise RuntimeError(
                "BOT_TOKEN is not set. Copy .env.example to .env or export BOT_TOKEN."
            )
        return cls(bot_token=token)
