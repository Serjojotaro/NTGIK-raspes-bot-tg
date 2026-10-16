import os
from dataclasses import dataclass, field

from core.config import BaseConfig, require_env


@dataclass(frozen=True)
class HttpConfig(BaseConfig):
    """aiogram implementation over Bot API HTTPS (HTTP/SOCKS5 proxy supported)."""

    bot_token: str = ""
    telegram_proxy: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_PROXY", "")
    )

    @classmethod
    def from_env(cls) -> "HttpConfig":
        return cls(bot_token=require_env("BOT_TOKEN"))
