from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

CB_COURSE = "c"
CB_GROUP = "g"
CB_BACK_COURSES = "back:courses"
CB_TODAY = "m:today"
CB_PERIOD = "m:period"
CB_CHANGE = "m:change"
CB_WEEK_TYPE = "w"


def courses_kb(courses: list[int]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for course in courses:
        builder.button(text=f"{course} курс", callback_data=f"{CB_COURSE}:{course}")
    builder.adjust(2)
    return builder.as_markup()


def groups_kb(course: int, groups: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for group in groups:
        builder.button(
            text=group, callback_data=f"{CB_GROUP}:{course}:{group}"
        )
    builder.adjust(2, 2, 2)
    builder.row(
        InlineKeyboardButton(text="Назад к курсам", callback_data=CB_BACK_COURSES)
    )
    return builder.as_markup()


def main_kb(odd_week: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Сегодня", callback_data=CB_TODAY)
    builder.button(
        text="Расписание на неделю", callback_data=f"{CB_WEEK_TYPE}:{int(odd_week)}:"
    )
    builder.button(text="Выбрать период", callback_data=CB_PERIOD)
    builder.button(text="Сменить группу", callback_data=CB_CHANGE)
    builder.adjust(1)
    return builder.as_markup()


def periods_kb(periods: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for period in periods:
        builder.button(
            text=period, callback_data=f"{CB_WEEK_TYPE}:1:{period}"
        )
    builder.adjust(1)
    return builder.as_markup()


def week_switch_kb(odd: bool, period: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for target_odd in (True, False):
        marker = "« " if target_odd == odd else ""
        marker += "Нечетная" if target_odd else "Четная"
        marker += " »" if target_odd == odd else ""
        builder.button(
            text=marker, callback_data=f"{CB_WEEK_TYPE}:{int(target_odd)}:{period}"
        )
    builder.adjust(2)
    return builder.as_markup()
