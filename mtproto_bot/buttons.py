from telethon.tl.custom import Button

from core.keys import (
    CB_BACK_COURSES,
    CB_CHANGE,
    CB_COURSE,
    CB_GROUP,
    CB_PERIOD,
    CB_TODAY,
    CB_WEEK_TYPE,
)


def courses_kb(courses: list[int]) -> list[list[Button]]:
    buttons = [
        Button.inline(f"{course} курс", f"{CB_COURSE}:{course}".encode())
        for course in courses
    ]
    return [buttons[i:i + 2] for i in range(0, len(buttons), 2)]


def groups_kb(course: int, groups: list[str]) -> list[list[Button]]:
    buttons = [
        Button.inline(group, f"{CB_GROUP}:{course}:{group}".encode())
        for group in groups
    ]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([Button.inline("Назад к курсам", CB_BACK_COURSES.encode())])
    return rows


def main_kb(odd_week: bool) -> list[list[Button]]:
    return [
        [Button.inline("Сегодня", CB_TODAY.encode())],
        [Button.inline(
            "Расписание на неделю",
            f"{CB_WEEK_TYPE}:{int(odd_week)}:".encode(),
        )],
        [Button.inline("Выбрать период", CB_PERIOD.encode())],
        [Button.inline("Сменить группу", CB_CHANGE.encode())],
    ]


def periods_kb(periods: list[str]) -> list[list[Button]]:
    return [
        [Button.inline(period, f"{CB_WEEK_TYPE}:1:{period}".encode())]
        for period in periods
    ]


def week_switch_kb(odd: bool, period: str) -> list[list[Button]]:
    row = []
    for target_odd in (True, False):
        marker = "« " if target_odd == odd else ""
        marker += "Нечетная" if target_odd else "Четная"
        marker += " »" if target_odd == odd else ""
        row.append(
            Button.inline(
                marker, f"{CB_WEEK_TYPE}:{int(target_odd)}:{period}".encode()
            )
        )
    return [row]
