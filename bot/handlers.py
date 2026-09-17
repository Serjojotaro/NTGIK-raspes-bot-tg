from __future__ import annotations

import logging
from datetime import date
from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from .formatter import format_day, format_week
from .keyboards import (
    CB_BACK_COURSES,
    CB_CHANGE,
    CB_COURSE,
    CB_GROUP,
    CB_PERIOD,
    CB_TODAY,
    CB_WEEK_TYPE,
    courses_kb,
    groups_kb,
    main_kb,
    periods_kb,
    week_switch_kb,
)
from .scraper import NtgikClient, Schedule, ScraperError
from .storage import Storage

log = logging.getLogger(__name__)

router = Router()


def _schedule_header(schedule: Schedule) -> str:
    week = "нечетная" if schedule.current_week_odd else "четная"
    return (
        f"Группа: <b>{escape(schedule.group)}</b>\n"
        f"Период: {escape(schedule.period)} (неделя {week})\n"
        f"Обновлено: {escape(schedule.updated) if schedule.updated else '—'}"
    )


async def _show_group_picker(message: Message, ntgik: NtgikClient) -> None:
    try:
        courses = await ntgik.get_courses()
    except ScraperError:
        log.exception("courses fetch failed")
        await message.answer("Сайт расписания сейчас недоступен, попробуйте позже.")
        return
    await message.answer(
        "Это бот расписания НТГиК.\n\nСначала выберите свой курс:",
        reply_markup=courses_kb(courses),
    )


async def _show_today(message: Message, ntgik: NtgikClient, storage: Storage) -> None:
    prefs = await storage.get_prefs(message.from_user.id)
    if prefs is None:
        await _show_group_picker(message, ntgik)
        return
    try:
        schedule = await ntgik.get_schedule(prefs.course, prefs.group)
    except ScraperError:
        log.exception("schedule fetch failed")
        await message.answer("Сайт расписания сейчас недоступен, попробуйте позже.")
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
    await message.answer(text, reply_markup=main_kb(schedule.current_week_odd))


async def _show_main_menu(message: Message, ntgik: NtgikClient, storage: Storage) -> None:
    prefs = await storage.get_prefs(message.from_user.id)
    if prefs is None:
        await _show_group_picker(message, ntgik)
        return
    try:
        schedule = await ntgik.get_schedule(prefs.course, prefs.group)
    except ScraperError:
        log.exception("schedule fetch failed")
        await message.answer(
            f"Ваша группа: <b>{escape(prefs.group)}</b>\n\n"
            "Сайт расписания сейчас недоступен, попробуйте позже."
        )
        return
    await message.answer(
        _schedule_header(schedule), reply_markup=main_kb(schedule.current_week_odd)
    )


# --- commands ----------------------------------------------------------------


@router.message(CommandStart())
async def cmd_start(
    message: Message, ntgik: NtgikClient, storage: Storage
) -> None:
    await _show_main_menu(message, ntgik, storage)


@router.message(Command("today"))
async def cmd_today(
    message: Message, ntgik: NtgikClient, storage: Storage
) -> None:
    await _show_today(message, ntgik, storage)


@router.message(Command("reset"))
async def cmd_reset(
    message: Message, ntgik: NtgikClient, storage: Storage
) -> None:
    await storage.clear_group(message.from_user.id)
    await _show_group_picker(message, ntgik)


# --- callbacks ---------------------------------------------------------------


@router.callback_query(F.data == CB_BACK_COURSES)
async def cb_back_courses(callback: CallbackQuery, ntgik: NtgikClient) -> None:
    try:
        courses = await ntgik.get_courses()
    except ScraperError:
        await callback.answer("Сайт недоступен", show_alert=True)
        return
    await callback.message.edit_text(
        "Выберите свой курс:", reply_markup=courses_kb(courses)
    )
    await callback.answer()


@router.callback_query(F.data.startswith(f"{CB_COURSE}:"))
async def cb_course(callback: CallbackQuery, ntgik: NtgikClient) -> None:
    course = int(callback.data.split(":", 1)[1])
    try:
        groups = await ntgik.get_groups(course)
    except ScraperError:
        log.exception("groups fetch failed")
        await callback.answer("Не удалось загрузить список групп", show_alert=True)
        return
    if not groups:
        await callback.answer("На этом курсе групп нет", show_alert=True)
        return
    await callback.message.edit_text(
        f"{course} курс. Выберите свою группу:",
        reply_markup=groups_kb(course, groups),
    )
    await callback.answer()


@router.callback_query(F.data.startswith(f"{CB_GROUP}:"))
async def cb_group(
    callback: CallbackQuery, ntgik: NtgikClient, storage: Storage
) -> None:
    _, course, group = callback.data.split(":", 2)
    await storage.set_group(callback.from_user.id, int(course), group)
    try:
        schedule = await ntgik.get_schedule(int(course), group)
    except ScraperError:
        log.exception("schedule fetch failed")
        await callback.message.edit_text(
            f"Группа сохранена: <b>{escape(group)}</b>.\n"
            "Сайт расписания сейчас недоступен, попробуйте позже."
        )
        await callback.answer()
        return
    await callback.message.edit_text(
        f"Группа сохранена: <b>{escape(group)}</b>\n\n{_schedule_header(schedule)}",
        reply_markup=main_kb(schedule.current_week_odd),
    )
    await callback.answer("Группа сохранена")


@router.callback_query(F.data == CB_TODAY)
async def cb_today(
    callback: CallbackQuery, ntgik: NtgikClient, storage: Storage
) -> None:
    await _show_today(callback.message, ntgik, storage)
    await callback.answer()


@router.callback_query(F.data == CB_PERIOD)
async def cb_period(
    callback: CallbackQuery, ntgik: NtgikClient, storage: Storage
) -> None:
    prefs = await storage.get_prefs(callback.from_user.id)
    if prefs is None:
        await callback.answer("Сначала выберите группу", show_alert=True)
        return
    try:
        schedule = await ntgik.get_schedule(prefs.course, prefs.group)
    except ScraperError:
        await callback.answer("Сайт недоступен", show_alert=True)
        return
    if not schedule.periods:
        await callback.answer("Периоды недоступны", show_alert=True)
        return
    await callback.message.edit_text(
        f"<b>{escape(schedule.group)}</b>. Выберите период:",
        reply_markup=periods_kb(schedule.periods),
    )
    await callback.answer()


@router.callback_query(F.data.startswith(f"{CB_WEEK_TYPE}:"))
async def cb_week(
    callback: CallbackQuery, ntgik: NtgikClient, storage: Storage
) -> None:
    prefs = await storage.get_prefs(callback.from_user.id)
    if prefs is None:
        await callback.answer("Сначала выберите группу", show_alert=True)
        return
    _, odd_flag, period = callback.data.split(":", 2)
    odd = odd_flag == "1"
    try:
        schedule = await ntgik.get_schedule(
            prefs.course, prefs.group, period or None
        )
    except ScraperError:
        log.exception("schedule fetch failed")
        await callback.answer("Сайт недоступен", show_alert=True)
        return
    week = next((w for w in schedule.weeks if w.odd == odd), None)
    if week is None:
        await callback.answer("Неделя не найдена в расписании", show_alert=True)
        return
    chunks = format_week(schedule, week)
    await callback.message.edit_text(
        chunks[0], reply_markup=week_switch_kb(odd, period)
    )
    for chunk in chunks[1:]:
        await callback.message.answer(chunk)
    await callback.answer()


@router.callback_query(F.data == CB_CHANGE)
async def cb_change(
    callback: CallbackQuery, ntgik: NtgikClient, storage: Storage
) -> None:
    await storage.clear_group(callback.from_user.id)
    await callback.message.delete()
    await _show_group_picker(callback.message, ntgik)
    await callback.answer()


@router.message()
async def fallback(message: Message, ntgik: NtgikClient, storage: Storage) -> None:
    await _show_main_menu(message, ntgik, storage)
