FROM python:3.12-slim

# IMPL=http     — aiogram over Bot API HTTPS (TELEGRAM_PROXY for HTTP/SOCKS5 proxy)
# IMPL=mtproto  — Telethon over MTProto (MT_PROXY_* for MTProxy)
ARG IMPL=http

WORKDIR /app

COPY requirements-${IMPL}.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY core/ core/
COPY http_bot/ http_bot/
COPY mtproto_bot/ mtproto_bot/

ENV PYTHONUNBUFFERED=1 \
    DB_PATH=/data/bot.db \
    MT_SESSION=/data/ntgik-bot.session
VOLUME /data

CMD ["sh", "-c", "python -m ${IMPL}_bot"]
