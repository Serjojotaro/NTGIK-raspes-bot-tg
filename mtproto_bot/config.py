import os
from dataclasses import dataclass, field

from core.config import BaseConfig, require_env


@dataclass(frozen=True)
class MTProtoConfig(BaseConfig):
    """Telethon implementation over the MTProto protocol (bot login by token).

    Optional MTProxy (tg://proxy) support: set MT_PROXY_HOST/PORT/SECRET.
    """

    bot_token: str = ""
    api_id: int = 0
    api_hash: str = ""
    proxy_host: str = field(default_factory=lambda: os.getenv("MT_PROXY_HOST", ""))
    proxy_port: int = field(default_factory=lambda: int(os.getenv("MT_PROXY_PORT", "443")))
    proxy_secret: str = field(default_factory=lambda: os.getenv("MT_PROXY_SECRET", ""))
    session_path: str = field(
        default_factory=lambda: os.getenv("MT_SESSION", "ntgik-bot.session")
    )

    @classmethod
    def from_env(cls) -> "MTProtoConfig":
        api_id = require_env("API_ID")
        if not api_id.isdigit():
            raise RuntimeError("API_ID must be an integer (see my.telegram.org)")
        return cls(
            bot_token=require_env("BOT_TOKEN"),
            api_id=int(api_id),
            api_hash=require_env("API_HASH"),
        )

    @property
    def has_proxy(self) -> bool:
        return bool(self.proxy_host and self.proxy_secret)

    @property
    def proxy(self) -> tuple[str, int, str] | None:
        if not self.has_proxy:
            return None
        return (self.proxy_host, self.proxy_port, self.proxy_secret)
