import argparse
import asyncio
import logging
import sys

from aiohttp_socks import ProxyConnectionError
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError, TelegramUnauthorizedError

from core.diagnostics import check_site, tcp_check
from core.scraper import NtgikClient
from core.storage import Storage
from .config import HttpConfig
from .handlers import router

log = logging.getLogger(__name__)

TELEGRAM_TIMEOUT = 15.0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m http_bot",
        description="NTGIK schedule bot (aiogram over Bot API HTTPS)",
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="run connectivity checks (proxy, Telegram API, schedule site) and exit",
    )
    return parser.parse_args()


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


async def _diagnose(bot: Bot, client: NtgikClient, config: HttpConfig) -> bool:
    ok = True
    if config.telegram_proxy:
        proxy_ok = await tcp_check(config.telegram_proxy, default_port=3128)
        ok = ok and proxy_ok
        if not proxy_ok:
            log.warning("[telegram] check may fail because proxy is unreachable")
    else:
        log.info("[proxy] TELEGRAM_PROXY not set, connecting directly")
    ok = await _check_telegram(bot, proxy_set=bool(config.telegram_proxy)) and ok
    site_ok = await check_site(client)
    if not site_ok:
        log.warning("[site] bot will start, but schedule requests will fail")
    return ok


async def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = HttpConfig.from_env()

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
