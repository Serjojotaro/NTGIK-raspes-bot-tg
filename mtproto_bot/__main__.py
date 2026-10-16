import argparse
import asyncio
import logging
import sys

from telethon import TelegramClient
from telethon.network import ConnectionTcpMTProxyRandomizedIntermediate

from core.diagnostics import check_site, tcp_check
from core.scraper import NtgikClient
from core.storage import Storage
from .config import MTProtoConfig
from .handlers import register_handlers

log = logging.getLogger(__name__)

CONNECT_TIMEOUT = 30.0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m mtproto_bot",
        description="NTGIK schedule bot (Telethon over MTProto, optional MTProxy)",
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="run connectivity checks (MTProxy, Telegram DC login, schedule site) and exit",
    )
    return parser.parse_args()


def _build_client(config: MTProtoConfig) -> TelegramClient:
    kwargs = {}
    if config.has_proxy:
        kwargs["connection"] = ConnectionTcpMTProxyRandomizedIntermediate
        kwargs["proxy"] = config.proxy
        log.info(
            "Telegram MTProto traffic goes through MTProxy: %s:%s",
            config.proxy_host,
            config.proxy_port,
        )
    return TelegramClient(
        config.session_path, config.api_id, config.api_hash, **kwargs
    )


async def _login(client: TelegramClient, config: MTProtoConfig) -> bool:
    try:
        await asyncio.wait_for(
            client.start(bot_token=config.bot_token), timeout=CONNECT_TIMEOUT
        )
        me = await client.get_me()
    except asyncio.TimeoutError:
        if config.has_proxy:
            log.error(
                "[telegram] connect/login timeout in %ss via MTProxy %s:%s",
                CONNECT_TIMEOUT,
                config.proxy_host,
                config.proxy_port,
            )
        else:
            log.error(
                "[telegram] connect/login timeout in %ss — Telegram DCs are likely "
                "unreachable from this network, set MT_PROXY_*",
                CONNECT_TIMEOUT,
            )
        return False
    except Exception as exc:
        log.error(
            "[telegram] login failed (%s): %s", type(exc).__name__, str(exc)[:200]
        )
        return False
    log.info("[telegram] token OK: @%s (id=%s)", me.username, me.id)
    return True


async def _diagnose(client: TelegramClient, ntgik: NtgikClient, config: MTProtoConfig) -> bool:
    ok = True
    if config.has_proxy:
        proxy_ok = await tcp_check(
            f"{config.proxy_host}:{config.proxy_port}", default_port=443
        )
        ok = ok and proxy_ok
        if not proxy_ok:
            log.warning("[telegram] login will likely fail: MTProxy unreachable")
    else:
        log.info("[proxy] MT_PROXY_HOST/SECRET not set, connecting directly")
    try:
        ok = await _login(client, config) and ok
        site_ok = await check_site(ntgik)
    finally:
        await client.disconnect()
    if not site_ok:
        log.warning("[site] bot would start, but schedule requests will fail")
    return ok


async def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = MTProtoConfig.from_env()

    ntgik = NtgikClient(
        config.site_base_url, timeout=config.http_timeout, cache_ttl=config.cache_ttl
    )

    storage = Storage(config.db_path)
    await storage.init()

    client = _build_client(config)
    register_handlers(client, ntgik, storage)

    try:
        if args.diagnose:
            checks_ok = await _diagnose(client, ntgik, config)
            log.info("diagnostics finished: %s", "OK" if checks_ok else "FAILED")
            return 0 if checks_ok else 1
        if not await _login(client, config):
            log.error("login failed, aborting (run with --diagnose)")
            return 1
        log.info("MTProto client running, waiting for updates")
        await client.run_until_disconnected()
        return 0
    finally:
        await client.disconnect()
        await ntgik.close()
        await storage.close()


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        log.info("Bot stopped")
