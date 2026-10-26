"""收藏的语音（fork）：她说的一句，收进统计页，随时回听。

一句的身份是「她在哪段音频里说过这句话」——消息语音本来就按（音色 + 模型 + 这句话 +
读音表）内容寻址，同一个地址内容不变。收藏时把那一份 mp3 **复制**到
`voice-favorites/`，所以之后给这句点「重新合成」、或者把整段对话删掉，收藏里听到的
还是当初那一版。

只有收藏的主人能看、能删；删一份收藏连桶里那份副本一起删，不留垃圾。
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from eidolon.characters import Character
from eidolon.clock import Clock
from eidolon.database import connect
from eidolon.message_speech import MessageSpeech
from eidolon.sessions import UserId
from eidolon.store import Store

log = logging.getLogger(__name__)

DIRECTORY = "voice-favorites"
"""Where in the stands' bucket a kept fragment of speech is put."""

PER_USER = 500
"""How many a user may keep: enough for a long acquaintance, not enough for a runaway
mis-tap to fill the bucket."""

_SCHEMA = """
CREATE TABLE IF NOT EXISTS voice_favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(id),
    character_id TEXT NOT NULL,
    path TEXT NOT NULL,
    ja TEXT NOT NULL,
    zh TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (user_id, path)
);
CREATE INDEX IF NOT EXISTS voice_favorites_by_user ON voice_favorites(user_id);
"""


@dataclass(frozen=True)
class Favorite:
    """One kept line: whose it is, what she said, and where the kept take is."""

    id: int
    user_id: str
    character_id: str
    path: str
    ja: str
    zh: str
    created_at: str


class VoiceFavorites:
    """Every user's kept lines."""

    def __init__(self, path: Path, clock: Clock) -> None:
        self._db = connect(path)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._clock = clock
        with self._lock, self._db:
            self._db.executescript(_SCHEMA)

    def add(self, user_id: str, character_id: str, ja: str, zh: str) -> tuple[Favorite, bool]:
        """Keep the line, in a copy of its own; returns it and whether it is new. One the
        user already has (the same line from the same character) is the one kept, its copy
        left as it is (see `rotate` for when it is to be replaced). Raises `Full` past
        `PER_USER`."""
        now = self._clock().astimezone(UTC).isoformat()
        with self._lock, self._db:
            row = self._db.execute(
                "SELECT * FROM voice_favorites"
                " WHERE user_id = ? AND character_id = ? AND ja = ?",
                (user_id, character_id, ja),
            ).fetchone()
            if row is not None:
                return _favorite(row), False
            count = self._db.execute(
                "SELECT COUNT(*) FROM voice_favorites WHERE user_id = ?", (user_id,)
            ).fetchone()[0]
            if count >= PER_USER:
                raise Full
            path = self._new_path(user_id, character_id, ja)
            cursor = self._db.execute(
                "INSERT INTO voice_favorites (user_id, character_id, path, ja, zh, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, character_id, path, ja, zh, now),
            )
            assert cursor.lastrowid is not None
            row = self._db.execute(
                "SELECT * FROM voice_favorites WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        return _favorite(row), True

    def rotate(self, favorite: Favorite) -> str:
        """Give the favorite a fresh copy address, returning the one it had, to be deleted:
        the bucket serves these `immutable`, so a copy that is replaced has to move — the
        same address would be served from browsers' caches long after the new take."""
        path = self._new_path(favorite.user_id, favorite.character_id, favorite.ja)
        with self._lock, self._db:
            self._db.execute(
                "UPDATE voice_favorites SET path = ? WHERE id = ?", (path, favorite.id)
            )
        return favorite.path

    def remove(self, user_id: str, favorite_id: int) -> str | None:
        """Forget one of the user's favorites, returning the path of what it kept; None if
        they have no such favorite."""
        with self._lock, self._db:
            row = self._db.execute(
                "SELECT path FROM voice_favorites WHERE id = ? AND user_id = ?",
                (favorite_id, user_id),
            ).fetchone()
            if row is None:
                return None
            self._db.execute("DELETE FROM voice_favorites WHERE id = ?", (favorite_id,))
        return row["path"]

    async def refresh(
        self, user_id: str, character_id: str, ja: str, speech: MessageSpeech
    ) -> None:
        """Put the take she just voiced again where every favorite of this user's for that
        line is heard from (fork): 「重新生成」之后，收藏里听到的就是新那一版。Each is given
        a new address first, so no browser keeps serving the old take."""
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM voice_favorites"
                " WHERE user_id = ? AND character_id = ? AND ja = ?",
                (user_id, character_id, ja),
            ).fetchall()
        for row in rows:
            old = self.rotate(_favorite(row))
            url = await speech.keep(character_id, ja, self._path_of(row["id"]), refresh=True)
            if url is not None:
                await speech.drop(old)

    def _path_of(self, favorite_id: int) -> str:
        with self._lock:
            row = self._db.execute(
                "SELECT path FROM voice_favorites WHERE id = ?", (favorite_id,)
            ).fetchone()
        assert row is not None
        return row["path"]

    def listed(self, user_id: str) -> list[Favorite]:
        """The user's kept lines, newest first."""
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM voice_favorites WHERE user_id = ? ORDER BY id DESC",
                (user_id,),
            ).fetchall()
        return [_favorite(row) for row in rows]

    def close(self) -> None:
        with self._lock:
            self._db.close()

    @staticmethod
    def _new_path(user_id: str, character_id: str, ja: str) -> str:
        """A fresh address for a kept copy. The bucket serves these `immutable`, so a copy
        that is replaced has to move: kept at the same address, the old take would be served
        from browsers' caches long after."""
        nonce = secrets.token_hex(6)
        digest = hashlib.sha256(
            f"{user_id}\n{character_id}\n{ja}\n{nonce}".encode()
        ).hexdigest()[:16]
        return f"{DIRECTORY}/{digest}.mp3"


class Full(RuntimeError):
    """The user keeps as many as `PER_USER`; one more is refused."""


class FavoriteInput(BaseModel):
    """What is to be kept: a segment of one of her replies (`message`) or of a reach-out
    (`reach_out`), as the speech player names it."""

    kind: Literal["message", "reach_out"]
    id: int
    segment: int = 0


def add_voice_favorite_routes(
    app: FastAPI,
    store: Store,
    favorites: VoiceFavorites,
    speech: MessageSpeech,
    characters: dict[str, Character],
) -> None:
    @app.post("/api/voice-favorites")
    async def keep(body: FavoriteInput, user_id: UserId) -> dict:
        """Keep the line, copying its take so that saying it again leaves it as it was."""
        found = (
            store.message_segments(body.id, user_id)
            if body.kind == "message"
            else store.reach_out_segments(body.id, user_id)
        )
        if found is None:
            raise HTTPException(404, "没有这一句")
        character_id, segments_json = found
        segments = json.loads(segments_json or "[]")
        if not 0 <= body.segment < len(segments):
            raise HTTPException(404, "没有这一句")
        ja = segments[body.segment].get("ja") or ""
        zh = segments[body.segment].get("zh") or ""
        if not ja.strip():
            raise HTTPException(404, "这一句没有语音")
        kept, created = favorites.add(user_id, character_id, ja, zh)
        # 已经收藏过的：换一个新地址再拷（桶上这些是 immutable，原地覆盖浏览器看不到）。
        old = None if created else favorites.rotate(kept)
        path = favorites._path_of(kept.id)
        url = await speech.keep(character_id, ja, path, refresh=True)
        if url is None:
            if created:
                favorites.remove(user_id, kept.id)
            raise HTTPException(503, "这一句现在存不下来，稍后再试")
        if old is not None:
            await speech.drop(old)
        return _shown(kept, url, characters)

    @app.delete("/api/voice-favorites/{favorite_id}", status_code=204)
    async def forget(favorite_id: int, user_id: UserId) -> None:
        path = favorites.remove(user_id, favorite_id)
        if path is None:
            raise HTTPException(404, "没有这条收藏")
        await speech.drop(path)

    @app.get("/api/voice-favorites")
    def kept(user_id: UserId) -> list[dict]:
        """Newest first; each says whose line it is and where it is heard from."""
        return [
            _shown(favorite, speech.heard_at(favorite.path), characters)
            for favorite in favorites.listed(user_id)
        ]


def _shown(favorite: Favorite, url: str, characters: dict[str, Character]) -> dict:
    character = characters.get(favorite.character_id)
    return {
        "id": favorite.id,
        "character_id": favorite.character_id,
        "character_name": character.name if character else None,
        "color": character.color if character else None,
        "ja": favorite.ja,
        "zh": favorite.zh,
        "url": url,
        "created_at": favorite.created_at,
    }


def _favorite(row) -> Favorite:
    return Favorite(
        row["id"], row["user_id"], row["character_id"], row["path"], row["ja"], row["zh"],
        row["created_at"],
    )
