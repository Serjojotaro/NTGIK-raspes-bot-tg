import argparse
import asyncio
import logging
import socket
import sys
from functools import partial
from urllib.parse import urlparse

from aiohttp_socks import ProxyConnectionError
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError, TelegramUnauthorizedError

from .config import Config
from .handlers import router
from .scraper import NtgikClient, ScraperError
from .storage import Storage

log = logging.getLogger(__name__)

PROXY_TIMEOUT = 5.0
TELEGRAM_TIMEOUT = 15.0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m bot", description="NTGIK schedule Telegram bot"
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="run connectivity checks (proxy, Telegram API, schedule site) and exit",
    )
    return parser.parse_args()


async def _check_proxy(proxy_url: str) -> bool:
    parsed = urlparse(proxy_url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme in ("http", "https") else 1080)
    if not host:
        log.error("[proxy] invalid TELEGRAM_PROXY value: %s", proxy_url)
        return False
    connector = partial(socket.create_connection, (host, port), PROXY_TIMEOUT)
    try:
        sock = await asyncio.get_running_loop().run_in_executor(None, connector)
    except OSError as exc:
        log.error("[proxy] cannot reach %s:%s: %s", host, port, exc)
        return False
    sock.close()
    return True


async def _check_telegram(bot: Bot, proxy_set: bool) -> bool:
    try:
        me = await asyncio.wait_for(bot.get_me(), timeout=TELEGRAM_TIMEOUT)
    except asyncio.TimeoutError:
        if proxy_set:
            log.error(
                "[telegram] no response in %ss through the configured proxy",
                TELEGRAM_TIMEOUT,
            )
        else:
            log.error(
                "[telegram] api.telegram.org unreachable in %ss — network likely "
                "blocks Telegram, set TELEGRAM_PROXY",
                TELEGRAM_TIMEOUT,
            )
        return False
    except TelegramUnauthorizedError:
        log.error("[telegram] token rejected by Bot API (check BOT_TOKEN)")
        return False
    except (TelegramNetworkError, ProxyConnectionError, OSError) as exc:
        log.error("[telegram] network error via current session: %s", exc)
        return False
    except Exception as exc:
        log.error("[telegram] check failed: %s: %s", type(exc).__name__, exc)
        return False
    log.info("[telegram] token OK: @%s (id=%s)", me.username, me.id)
    return True


async def _check_site(client: NtgikClient) -> bool:
    try:
        courses = await client.get_courses()
    except ScraperError as exc:
        log.warning("[site] schedule site failed: %s", exc)
        return False
    log.info("[site] OK, courses: %s", courses)
    return True


async def _diagnose(bot: Bot, client: NtgikClient, config: Config) -> bool:
    ok = True
    if config.telegram_proxy:
        proxy_ok = await _check_proxy(config.telegram_proxy)
        ok = ok and proxy_ok
        if not proxy_ok:
            log.warning("[telegram] check may fail because proxy is unreachable")
    else:
        log.info("[proxy] TELEGRAM_PROXY not set, connecting directly")
    ok = await _check_telegram(bot, proxy_set=bool(config.telegram_proxy)) and ok
    site_ok = await _check_site(client)
    if not site_ok:
        log.warning("[site] bot will start, but schedule requests will fail")
    return ok


async def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = Config.from_env()

    client = NtgikClient(
        config.site_base_url, timeout=config.http_timeout, cache_ttl=config.cache_ttl
    )

    session = (
        AiohttpSession(proxy=config.telegram_proxy)
        if config.telegram_proxy
        else None
    )
    if session is not None:
        log.info(
            "Telegram API traffic goes through proxy: %s",
            config.telegram_proxy.split("@")[-1],
        )

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=session,
    )

    try:
        checks_ok = await _diagnose(bot, client, config)
        if args.diagnose:
            log.info("diagnostics finished: %s", "OK" if checks_ok else "FAILED")
            return 0 if checks_ok else 1
        if not checks_ok:
            log.error("startup checks failed, aborting (run with --diagnose)")
            return 1

        storage = Storage(config.db_path)
        await storage.init()

        dp = Dispatcher()
        dp.include_router(router)
        log.info("Starting polling")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, ntgik=client, storage=storage)
        return 0
    finally:
        await client.close()
        await bot.session.close()


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        log.info("Bot stopped")
