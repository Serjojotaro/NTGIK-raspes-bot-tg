from __future__ import annotations

import logging
from datetime import date
from html import escape

from telethon import TelegramClient, events

from core.formatter import format_day, format_week
from core.keys import (
    CB_BACK_COURSES,
    CB_CHANGE,
    CB_COURSE,
    CB_GROUP,
    CB_PERIOD,
    CB_TODAY,
    CB_WEEK_TYPE,
)
from core.scraper import NtgikClient, Schedule, ScraperError
from core.storage import Storage
from .buttons import courses_kb, groups_kb, main_kb, periods_kb, week_switch_kb

log = logging.getLogger(__name__)

HTML = "html"


def _schedule_header(schedule: Schedule) -> str:
    week = "нечетная" if schedule.current_week_odd else "четная"
    return (
        f"Группа: <b>{escape(schedule.group)}</b>\n"
        f"Период: {escape(schedule.period)} (неделя {week})\n"
        f"Обновлено: {escape(schedule.updated) if schedule.updated else '—'}"
    )


def register_handlers(client: TelegramClient, ntgik: NtgikClient, storage: Storage) -> None:

    async def reply_menu(chat_id: int, prefs_course: int, prefs_group: str) -> None:
        try:
            schedule = await ntgik.get_schedule(prefs_course, prefs_group)
        except ScraperError:
            log.exception("schedule fetch failed")
            await client.send_message(
                chat_id,
                f"Ваша группа: <b>{escape(prefs_group)}</b>\n\n"
                "Сайт расписания сейчас недоступен, попробуйте позже.",
                parse_mode=HTML,
            )
            return
        await client.send_message(
            chat_id,
            _schedule_header(schedule),
            buttons=main_kb(schedule.current_week_odd),
            parse_mode=HTML,
        )

    async def show_group_picker(chat_id: int) -> None:
        try:
            courses = await ntgik.get_courses()
        except ScraperError:
            log.exception("courses fetch failed")
            await client.send_message(
                chat_id, "Сайт расписания сейчас недоступен, попробуйте позже."
            )
            return
        await client.send_message(
            chat_id,
            "Это бот расписания НТГиК.\n\nСначала выберите свой курс:",
            buttons=courses_kb(courses),
        )

    async def show_today(event) -> None:
        prefs = await storage.get_prefs(event.sender_id)
        if prefs is None:
            await show_group_picker(event.chat_id)
            return
        try:
            schedule = await ntgik.get_schedule(prefs.course, prefs.group)
        except ScraperError:
            log.exception("schedule fetch failed")
            await event.respond("Сайт расписания сейчас недоступен, попробуйте позже.")
            return
        today = date.today()
        found = schedule.day_for(today)
        if found is None:
            text = (
                f"<b>{escape(schedule.group)}</b>\n"
                f"Сегодня ({today.strftime('%d.%m.%Y')}) занятий нет или дата "
                "не входит в текущий период."
            )
        else:
            week, day = found
            text = format_day(schedule, week, day)
        await event.respond(
            text, buttons=main_kb(schedule.current_week_odd), parse_mode=HTML
        )

    # --- commands --------------------------------------------------------

    @client.on(events.NewMessage(pattern=r"^/start"))
    async def cmd_start(event):
        prefs = await storage.get_prefs(event.sender_id)
        if prefs is None:
            await show_group_picker(event.chat_id)
        else:
            await reply_menu(event.chat_id, prefs.course, prefs.group)

    @client.on(events.NewMessage(pattern=r"^/today"))
    async def cmd_today(event):
        await show_today(event)

    @client.on(events.NewMessage(pattern=r"^/reset"))
    async def cmd_reset(event):
        await storage.clear_group(event.sender_id)
        await show_group_picker(event.chat_id)

    # --- callbacks -------------------------------------------------------

    @client.on(events.CallbackQuery())
    async def on_callback(event):
        data = event.data.decode()
        chat_id = event.chat_id
        user_id = event.sender_id

        if data == CB_BACK_COURSES:
            await _cb_courses(event)
        elif data.startswith(f"{CB_COURSE}:"):
            await _cb_course(event, int(data.split(":", 1)[1]))
        elif data.startswith(f"{CB_GROUP}:"):
            await _cb_group(event, data)
        elif data == CB_TODAY:
            await show_today(event)
        elif data == CB_PERIOD:
            await _cb_period(event)
        elif data.startswith(f"{CB_WEEK_TYPE}:"):
            await _cb_week(event, data)
        elif data == CB_CHANGE:
            await storage.clear_group(user_id)
            await event.delete()
            await show_group_picker(chat_id)
        await event.answer()

    async def _cb_courses(event):
        try:
            courses = await ntgik.get_courses()
        except ScraperError:
            await event.answer("Сайт недоступен", alert=True)
            return
        await event.edit("Выберите свой курс:", buttons=courses_kb(courses))

    async def _cb_course(event, course: int):
        try:
            groups = await ntgik.get_groups(course)
        except ScraperError:
            log.exception("groups fetch failed")
            await event.answer("Не удалось загрузить список групп", alert=True)
            return
        if not groups:
            await event.answer("На этом курсе групп нет", alert=True)
            return
        await event.edit(
            f"{course} курс. Выберите свою группу:", buttons=groups_kb(course, groups)
        )

    async def _cb_group(event, data: str):
        _, course, group = data.split(":", 2)
        await storage.set_group(event.sender_id, int(course), group)
        try:
            schedule = await ntgik.get_schedule(int(course), group)
        except ScraperError:
            log.exception("schedule fetch failed")
            await event.edit(
                f"Группа сохранена: <b>{escape(group)}</b>.\n"
                "Сайт расписания сейчас недоступен, попробуйте позже.",
                parse_mode=HTML,
            )
            return
        await event.edit(
            f"Группа сохранена: <b>{escape(group)}</b>\n\n{_schedule_header(schedule)}",
            buttons=main_kb(schedule.current_week_odd),
            parse_mode=HTML,
        )

    async def _cb_period(event):
        prefs = await storage.get_prefs(event.sender_id)
        if prefs is None:
            await event.answer("Сначала выберите группу", alert=True)
            return
        try:
            schedule = await ntgik.get_schedule(prefs.course, prefs.group)
        except ScraperError:
            await event.answer("Сайт недоступен", alert=True)
            return
        if not schedule.periods:
            await event.answer("Периоды недоступны", alert=True)
            return
        await event.edit(
            f"<b>{escape(schedule.group)}</b>. Выберите период:",
            buttons=periods_kb(schedule.periods),
            parse_mode=HTML,
        )

    async def _cb_week(event, data: str):
        prefs = await storage.get_prefs(event.sender_id)
        if prefs is None:
            await event.answer("Сначала выберите группу", alert=True)
            return
        _, odd_flag, period = data.split(":", 2)
        odd = odd_flag == "1"
        try:
            schedule = await ntgik.get_schedule(prefs.course, prefs.group, period or None)
        except ScraperError:
            log.exception("schedule fetch failed")
            await event.answer("Сайт недоступен", alert=True)
            return
        week = next((w for w in schedule.weeks if w.odd == odd), None)
        if week is None:
            await event.answer("Неделя не найдена в расписании", alert=True)
            return
        chunks = format_week(schedule, week)
        await event.edit(chunks[0], buttons=week_switch_kb(odd, period), parse_mode=HTML)
        for chunk in chunks[1:]:
            await event.respond(chunk, parse_mode=HTML)

    # --- fallback ---------------------------------------------------------

    @client.on(events.NewMessage())
    async def fallback(event):
        # Telethon invokes every matching handler: commands are handled
        # separately, don't react to them twice here.
        if (event.raw_text or "").lstrip().startswith("/"):
            return
        prefs = await storage.get_prefs(event.sender_id)
        if prefs is None:
            await show_group_picker(event.chat_id)
        else:
            await reply_menu(event.chat_id, prefs.course, prefs.group)
