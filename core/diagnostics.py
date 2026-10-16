import asyncio
import logging
import socket
from functools import partial
from urllib.parse import urlparse

from .scraper import NtgikClient, ScraperError

log = logging.getLogger(__name__)

TCP_TIMEOUT = 5.0


async def tcp_check(url: str, default_port: int) -> bool:
    """Check that host:port of a proxy URL accepts TCP connections."""
    parsed = urlparse(url) if "://" in url else urlparse(f"//{url}")
    host = parsed.hostname
    port = parsed.port or default_port
    if not host:
        log.error("[proxy] invalid proxy value: %s", url)
        return False
    connector = partial(socket.create_connection, (host, port), TCP_TIMEOUT)
    try:
        sock = await asyncio.get_running_loop().run_in_executor(None, connector)
    except OSError as exc:
        log.error("[proxy] cannot reach %s:%s: %s", host, port, exc)
        return False
    sock.close()
    log.info("[proxy] %s:%s reachable", host, port)
    return True


async def check_site(client: NtgikClient) -> bool:
    try:
        courses = await client.get_courses()
    except ScraperError as exc:
        log.warning("[site] schedule site failed: %s", exc)
        return False
    log.info("[site] OK, courses: %s", courses)
    return True
