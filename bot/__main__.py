import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from .config import Config
from .handlers import router
from .scraper import NtgikClient
from .storage import Storage

log = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = Config.from_env()

    storage = Storage(config.db_path)
    await storage.init()

    client = NtgikClient(
        config.site_base_url, timeout=config.http_timeout, cache_ttl=config.cache_ttl
    )

    session = (
        AiohttpSession(proxy=config.telegram_proxy)
        if config.telegram_proxy
        else None
    )
    if session is not None:
        log.info("Telegram API traffic goes through proxy: %s",
                 config.telegram_proxy.split("@")[-1])

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=session,
    )

    dp = Dispatcher()
    dp.include_router(router)

    try:
        me = await bot.get_me()
        log.info("Starting bot @%s", me.username)
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, ntgik=client, storage=storage)
    finally:
        await client.close()
        await storage.close()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot stopped")
