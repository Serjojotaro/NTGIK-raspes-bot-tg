from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import aiosqlite


@dataclass(frozen=True)
class UserPrefs:
    user_id: int
    course: int
    group: str


class Storage:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def init(self) -> None:
        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id  INTEGER PRIMARY KEY,
                course   INTEGER NOT NULL,
                grp      TEXT    NOT NULL,
                updated  TEXT    NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        await self._db.commit()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        assert self._db is not None, "Storage.init() was not called"
        return self._db

    async def get_prefs(self, user_id: int) -> UserPrefs | None:
        async with self.db.execute(
            "SELECT user_id, course, grp FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return UserPrefs(user_id=row[0], course=row[1], group=row[2])

    async def set_group(self, user_id: int, course: int, group: str) -> None:
        await self.db.execute(
            """
            INSERT INTO users (user_id, course, grp, updated)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(user_id) DO UPDATE SET
                course = excluded.course,
                grp = excluded.grp,
                updated = excluded.updated
            """,
            (user_id, course, group),
        )
        await self.db.commit()

    async def clear_group(self, user_id: int) -> None:
        await self.db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        await self.db.commit()
