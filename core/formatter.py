from __future__ import annotations

from html import escape

from .scraper import Day, Lesson, Schedule, Week

TELEGRAM_LIMIT = 4096
_WEEK_TITLES = {True: "Нечетная неделя", False: "Четная неделя"}


def _format_lesson(lesson: Lesson) -> str:
    parts = [f"<b>{lesson.number}.</b> {escape(lesson.time)}"]
    if lesson.subjects:
        parts.append("  ".join(escape(s) for s in lesson.subjects))
    if lesson.note:
        parts.append(f"[{escape(lesson.note)}]")
    return " ".join(parts)


def _format_day(day: Day) -> str | None:
    lessons = [lesson for lesson in day.lessons if not lesson.is_empty]
    if not lessons:
        return None
    lines = [f"<u>{escape(day.name)}, {day.date.strftime('%d.%m.%Y')}</u>"]
    lines.extend(_format_lesson(lesson) for lesson in lessons)
    return "\n".join(lines)


def format_day(schedule: Schedule, week: Week, day: Day) -> str:
    header = (
        f"<b>{escape(schedule.group)}</b> · {_week_title(week.odd)} · "
        f"{escape(schedule.period)}"
    )
    body = _format_day(day)
    if body is None:
        return f"{header}\nЗанятий нет"
    return f"{header}\n\n{body}"


def format_week(schedule: Schedule, week: Week) -> list[str]:
    header = (
        f"<b>{escape(schedule.group)}</b> · {_week_title(week.odd)}\n"
        f"Период: {escape(schedule.period)}"
    )
    chunks: list[str] = []
    current = header
    for day in week.days:
        block = _format_day(day)
        if block is None:
            continue
        candidate = f"{current}\n\n{block}"
        if len(candidate) > TELEGRAM_LIMIT and current != header:
            chunks.append(current)
            current = f"{header} (продолжение)"
            current = f"{current}\n\n{block}"
        else:
            current = candidate
    chunks.append(current)

    if len(chunks) == 1 and chunks[0] == header:
        chunks = [f"{header}\n\nНа этой неделе занятий нет"]
    return chunks


def _week_title(odd: bool) -> str:
    return _WEEK_TITLES[odd]
