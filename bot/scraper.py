"""Scraper for расписание.нтгик.рф (mode=1, students schedule).

The site is a plain PHP form cascade:
  POST index.php?mode=1  Kurs=N            -> list of groups (NamePodGrup)
  POST ... NamePodGrup=<group>             -> schedule table for the period
  POST ... RangeNedel=<period option>      -> schedule for a specific period
The table contains both odd and even weeks; every day header carries a date.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

_DAY_RE = re.compile(r"^(\w+)\s*\((\d{2})\.(\d{2})\.(\d{4})\)$")
_PAIR_RE = re.compile(r"(\d+)\s*пара")
_TIME_RE = re.compile(r"(\d{2}:\d{2}\s*-\s*\d{2}:\d{2})")
_PERIOD_RE = re.compile(r"Текущий период:\s*<b>(.*?)</b>", re.S)
_EMPTY_CELL = re.compile(r"^[\s\xa0]*$")


class ScraperError(Exception):
    """Site is unavailable or returned unexpected markup."""


@dataclass
class Lesson:
    number: int
    time: str
    subjects: list[str] = field(default_factory=list)
    note: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.subjects and not self.note


@dataclass
class Day:
    name: str
    date: date
    lessons: list[Lesson] = field(default_factory=list)


@dataclass
class Week:
    odd: bool
    days: list[Day] = field(default_factory=list)


@dataclass
class Schedule:
    group: str
    period: str
    periods: list[str]
    updated: str
    current_week_odd: bool
    weeks: list[Week] = field(default_factory=list)

    @property
    def current_week(self) -> Week | None:
        for week in self.weeks:
            if week.odd == self.current_week_odd:
                return week
        return None

    def day_for(self, target: date) -> tuple[Week, Day] | None:
        for week in self.weeks:
            for day in week.days:
                if day.date == target:
                    return week, day
        return None


def _clean(text: str) -> str:
    return re.sub(r"[\s\xa0]+", " ", text).strip()


def _parse_table(soup: BeautifulSoup) -> list[Week]:
    table = soup.find("table")
    if table is None:
        raise ScraperError("Schedule table not found on the page")

    weeks: list[Week] = []
    week: Week | None = None
    day: Day | None = None

    for tr in table.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if not cells:
            continue

        first = cells[0]
        if "colspan" in first.attrs and len(cells) == 1:
            text = _clean(first.get_text())
            if "НЕДЕЛЯ" in text:
                week = Week(odd="НЕЧЕТНАЯ" in text)
                weeks.append(week)
                day = None
                continue
            match = _DAY_RE.match(text)
            if match and week is not None:
                day = Day(
                    name=match.group(1).capitalize(),
                    date=date(
                        int(match.group(4)), int(match.group(3)), int(match.group(2))
                    ),
                )
                week.days.append(day)
            continue

        if tr.get("id") != "text_table_content" or week is None or day is None:
            continue

        time_text = _clean(first.get_text())
        pair_match = _PAIR_RE.search(time_text)
        if not pair_match:
            continue
        time_match = _TIME_RE.search(time_text)
        lesson = Lesson(
            number=int(pair_match.group(1)),
            time=time_match.group(1).replace(" ", "") if time_match else "",
        )

        subject_cells = cells[1:-1] if len(cells) > 2 else cells[1:]
        split_subgroups = all(c.get("colspan") == "1" for c in subject_cells)
        for index, cell in enumerate(subject_cells):
            text = _clean(cell.get_text())
            if _EMPTY_CELL.match(text):
                continue
            if split_subgroups and len(subject_cells) > 1:
                lesson.subjects.append(f"{index + 1} подг.: {text}")
            else:
                lesson.subjects.append(text)

        if len(cells) > 2:
            note = _clean(cells[-1].get_text())
            if note and not _EMPTY_CELL.match(note):
                lesson.note = note
        day.lessons.append(lesson)

    if not weeks:
        raise ScraperError("No weeks parsed from the schedule table")
    return weeks


def _current_week_from_page(soup: BeautifulSoup) -> bool | None:
    header = soup.find("h2")
    if header is None:
        return None
    text = _clean(header.get_text()).upper()
    if "НЕЧЕТНАЯ" in text:
        return True
    if "ЧЕТНАЯ" in text:
        return False
    return None


def parse_courses(html: str) -> list[int]:
    soup = BeautifulSoup(html, "html.parser")
    select = soup.find("select", attrs={"name": "Kurs"})
    if select is None:
        raise ScraperError("Course selector not found")
    courses = []
    for option in select.find_all("option"):
        value = (option.get("value") or "").strip()
        if value.isdigit():
            courses.append(int(value))
    return courses


def parse_groups(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    select = soup.find("select", attrs={"name": "NamePodGrup"})
    if select is None:
        raise ScraperError("Group selector not found")
    return [
        value.strip()
        for option in select.find_all("option")
        if (value := (option.get("value") or "").strip())
    ]


def parse_schedule(html: str, group: str) -> Schedule:
    soup = BeautifulSoup(html, "html.parser")

    periods = [
        value.strip()
        for option in soup.select("select[name=RangeNedel] option")
        if (value := (option.get("value") or "").strip())
    ]
    match = _PERIOD_RE.search(html)
    period = _clean(match.group(1)) if match else ""
    updated_match = re.search(r"Обновлено:\s*([\d. :]+)", _clean(soup.get_text()))
    updated = updated_match.group(1) if updated_match else ""

    weeks = _parse_table(soup)
    schedule = Schedule(
        group=group,
        period=period,
        periods=periods,
        updated=updated,
        current_week_odd=_current_week_from_page(soup) or weeks[0].odd,
        weeks=weeks,
    )
    # trust explicit day dates over the page header when today is inside a week
    today = datetime.now().date()
    if schedule.day_for(today) is not None:
        found_week, _ = schedule.day_for(today)
        schedule.current_week_odd = found_week.odd
    return schedule


class NtgikClient:
    BASE_FORM = {"id_Forma": "", "id_Fak": ""}

    def __init__(self, base_url: str, timeout: float = 20.0, cache_ttl: float = 300.0):
        self._url = base_url.rstrip("/") + "/index.php"
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": "NTGIK-schedule-telegram-bot/1.0"},
            follow_redirects=True,
        )
        self._cache_ttl = cache_ttl
        self._cache: dict[str, tuple[float, str]] = {}

    async def close(self) -> None:
        await self._client.aclose()

    async def _get(self, params: dict[str, str], cache_key: str) -> str:
        cached = self._cache.get(cache_key)
        now = time.monotonic()
        if cached and now - cached[0] < self._cache_ttl:
            return cached[1]
        html = await self._request("GET", params=params)
        self._cache[cache_key] = (now, html)
        return html

    async def _post(self, data: dict[str, str], cache_key: str) -> str:
        cached = self._cache.get(cache_key)
        now = time.monotonic()
        if cached and now - cached[0] < self._cache_ttl:
            return cached[1]
        html = await self._request("POST", params={"mode": "1"}, data=data)
        self._cache[cache_key] = (now, html)
        return html

    async def _request(self, method: str, **kwargs) -> str:
        try:
            response = await self._client.request(method, self._url, **kwargs)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ScraperError(f"Site request failed: {exc}") from exc
        if "РАСПИСАНИЕ" not in response.text.upper():
            raise ScraperError("Unexpected response from the site")
        return response.text

    async def get_courses(self) -> list[int]:
        html = await self._get({"mode": "1"}, "courses")
        return parse_courses(html)

    async def get_groups(self, course: int) -> list[str]:
        html = await self._post(
            {**self.BASE_FORM, "Kurs": str(course)}, f"groups:{course}"
        )
        return parse_groups(html)

    async def get_schedule(
        self, course: int, group: str, period: str | None = None
    ) -> Schedule:
        data = {**self.BASE_FORM, "Kurs": str(course), "NamePodGrup": group}
        if period:
            data["RangeNedel"] = period
        html = await self._post(data, f"schedule:{course}:{group}:{period or ''}")
        return parse_schedule(html, group)
