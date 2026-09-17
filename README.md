# NTGIK Schedule Bot

Telegram-бот расписания занятий НТГиК ([расписание.нтгик.рф](https://расписание.нтгик.рф)).

При первом запуске бот предлагает выбрать курс и группу, выбор сохраняется в SQLite.
Дальше расписание отдаётся сразу по вашей группе. Группу можно сбросить и выбрать заново.

## Команды и кнопки

- `/start` — меню: сегодняшние занятия, расписание на неделю, выбор периода
- `/today` — занятия на сегодня
- `/reset` — сбросить группу и выбрать заново
- Кнопки: **Сегодня**, **Расписание на неделю** (с переключением нечетная/четная),
  **Выбрать период**, **Сменить группу**

## Запуск

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # вписать BOT_TOKEN
export $(grep -v '^#' .env | xargs)
python -m bot
```

## Docker

```bash
docker build -t ntgik-bot .
docker run -d --restart unless-stopped \
  -e BOT_TOKEN=... -v ntgik-bot-data:/data \
  --name ntgik-bot ntgik-bot
```

## Настройки (переменные окружения)

| Переменная | По умолчанию | Описание |
|---|---|---|
| `BOT_TOKEN` | — | Токен от @BotFather (обязательно) |
| `TELEGRAM_PROXY` | — | HTTP/SOCKS5-прокси только для Telegram API, напр. `http://user:pass@host:3128` или `socks5://host:1080` (сайт расписания всегда ходит напрямую) |
| `DB_PATH` | `bot.db` | Путь к SQLite |
| `SITE_BASE_URL` | `https://xn--80aapkb3algkc.xn--c1akgjz.xn--p1ai` | База сайта расписания |
| `HTTP_TIMEOUT` | `20` | Таймаут HTTP, сек |
| `CACHE_TTL` | `300` | Кеш страниц сайта, сек |

## Структура

- `bot/scraper.py` — клиент и парсер сайта (каскад форм: курс → группа → период)
- `bot/storage.py` — SQLite: сохранённая группа пользователя
- `bot/formatter.py` — форматирование расписания под сообщения Telegram
- `bot/handlers.py` — команды и inline-логика (aiogram 3)
