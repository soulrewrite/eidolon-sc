"""Her letters (GLOSSARY.md「信」, fork): what she would not say to the producer's face, written
down and left for him to find in the announcements one evening.

A letter is not a turn and not a reach-out: it is read, not talked over. Only a character the
user is close to writes them (亲近 and above), one every few days at most, in the evening —
or on a day that calls for it: his birthday, or the monthly return of the day they first
spoke. The content comes from the same places a turn's does: her sheet, the world setting,
the memories nearest their last words, and the last turns of their conversations; the
difference is what she is allowed to say when nobody is looking.
"""

import hashlib
import json
import logging
import sqlite3
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from eidolon.affinity import Affinities, Tier
from eidolon.database import connect
from eidolon.characters import Character
from eidolon.clock import Clock
from eidolon.letter_envelopes import Envelopes
from eidolon.live_config import LiveConfig
from eidolon.engine import ConversationEngine
from eidolon.reply_format import Segment
from eidolon.producer import effective_timezone, is_birthday
from eidolon.store import Conversation, Store

log = logging.getLogger(__name__)

TICK = timedelta(minutes=1)
"""How often it is looked whether an evening letter's time has come."""

EVENING = (time(18), time(22))
"""When in the producer's day she leaves a letter: an hour in it is drawn, one day to the next."""

TIERS: tuple[Tier, ...] = ("close", "intimate")
"""Who writes: the producers she is close to, or more."""

GAP_DAYS = (3, 7)
"""How many days at least between one letter and the next, drawn for each letter."""

WINDOW = timedelta(hours=26)
"""How long after its day a letter may still be delivered, the backend having been down."""

MAX_LETTERS_KEPT = 40
"""How many letters one character keeps for the user; the oldest go first."""

_SCHEMA = """
-- Her letters (GLOSSARY.md「信」, fork): what she wrote, when it appeared in the announcements
-- and when he read it. `segments` is the reply format's JSON, as a message's.
CREATE TABLE IF NOT EXISTS letters (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    character_id TEXT NOT NULL,
    trigger TEXT NOT NULL,
    written_at TEXT NOT NULL,
    delivered_at TEXT NOT NULL,
    segments TEXT NOT NULL,
    read_at TEXT,
    envelope_enza TEXT
);
CREATE INDEX IF NOT EXISTS letters_of_user ON letters (user_id, delivered_at);
"""


@dataclass(frozen=True)
class Letter:
    """One letter, as the user reads it."""

    id: str
    character_id: str
    trigger: str
    delivered_at: datetime
    segments: list[Segment]
    read: bool
    envelope_enza: str | None = None

    def as_json(self, character: Character) -> dict:
        return {
            "id": self.id,
            "character_id": self.character_id,
            "character_name": character.name,
            "character_name_zh": character.name_zh,
            "color": character.color,
            "signature_url": (
                f"/api/characters/{character.id}/signature" if character.signature else None
            ),
            "background_url": (
                f"/api/characters/{character.id}/background" if character.background else None
            ),
            "envelope_url": (
                f"/api/letters/{self.id}/envelope" if self.envelope_enza else None
            ),
            "trigger": self.trigger,
            "delivered_at": self.delivered_at.isoformat(),
            "segments": [{"ja": s.ja, "zh": s.zh} for s in self.segments],
            "read": self.read,
        }


def _drawn(seed: str, low: int, high: int) -> int:
    """A number in `[low, high]`, the same for the same `seed`: what is drawn must not change
    from one tick to the next, or her letter would never come due."""
    digest = hashlib.sha256(seed.encode()).digest()
    return low + int.from_bytes(digest[:4], "big") % (high - low + 1)


class Letters:
    """Her letters, on the database at `path` beside the conversations of `store`: decided on
    the affinity `affinities` says she has, written by `engine` on the model `config` leases,
    and read by the user in the announcements."""

    def __init__(
        self,
        path: Path,
        store: Store,
        engine: ConversationEngine,
        characters: Mapping[str, Character],
        config: LiveConfig,
        affinities: Affinities,
        clock: Clock,
        envelopes: "Envelopes | None" = None,
    ) -> None:
        self._store = store
        self._engine = engine
        self._characters = characters
        self._config = config
        self._affinities = affinities
        self._clock = clock
        self._envelopes = envelopes
        self._lock = threading.Lock()
        self._db = connect(path)
        self._db.row_factory = sqlite3.Row
        with self._lock, self._db:
            self._db.executescript(_SCHEMA)
            columns = {row[1] for row in self._db.execute("PRAGMA table_info(letters)")}
            if "envelope_enza" not in columns:  # 旧的库：补上这一列
                self._db.execute("ALTER TABLE letters ADD COLUMN envelope_enza TEXT")
        self._writing = False

    def close(self) -> None:
        with self._lock:
            self._db.close()

    async def keep_writing(self, until: Callable[[], bool] | None = None) -> None:
        """`deliver_due` at every `TICK`, until cancelled."""
        while True:
            await _sleep(TICK)
            if until is not None and until():
                return
            try:
                await self.deliver_due()
            except Exception:
                log.exception("delivering letters failed")

    async def deliver_due(self) -> None:
        """Leave a letter for every user and character whose evening, day or gap has come."""
        now = self._clock()
        for current in await _thread(self._store.current_conversations):
            try:
                await self._maybe(current.conversation, now)
            except Exception:
                log.exception("writing a letter to %s failed", current.conversation.id)

    async def _maybe(self, conversation: Conversation, now: datetime) -> None:
        character = self._characters.get(conversation.character_id)
        if character is None:
            return
        zone = ZoneInfo(effective_timezone(self._store.get_profile(conversation.user_id), None))
        local = now.astimezone(zone)
        trigger = self._trigger(conversation, local, zone)
        if trigger is None:
            return
        if self._written_today(conversation, local) or self._user_written_today(
            conversation, local
        ):
            return
        if self._writing:
            return
        self._writing = True
        try:
            lease = self._config.lease()
            try:
                segments = await self._engine.letter(conversation, lease.keys.chat_llm, trigger)
            finally:
                lease.release()
            if len(segments) < 2:
                log.warning("a letter to %s came out too short", conversation.character_id)
                return
            envelope = (
                await self._envelopes.for_idol(character.idol_id, now)
                if self._envelopes is not None
                else None
            )
            self._keep(conversation, segments, trigger, now, envelope)
            log.info("a letter from %s (%s)", conversation.character_id, trigger)
        finally:
            self._writing = False

    def _trigger(self, conversation: Conversation, local: datetime, zone: ZoneInfo) -> str | None:
        """Why she writes today, if she does: the day, else the evening and the gap."""
        tier = self._tier(conversation)
        if tier is None:
            return None
        if self._birthday(conversation, local):
            return "birthday"
        if self._anniversary(conversation, local):
            return "anniversary"
        if not EVENING[0] <= local.time() < EVENING[1]:
            return None
        drawn = _drawn(f"evening:{conversation.id}:{local.date()}", 0, _minutes(EVENING) - 1)
        due = datetime.combine(local.date(), EVENING[0], tzinfo=zone) + timedelta(minutes=drawn)
        if local < due:
            return None
        if self._gap_met(conversation, local):
            return "everyday"
        return None

    def _tier(self, conversation: Conversation) -> Tier | None:
        status = self._affinities.status(conversation.user_id, conversation.character_id)
        if status is None or status.cooling:
            return None
        return status.tier if status.tier in TIERS else None

    def _birthday(self, conversation: Conversation, local: datetime) -> bool:
        profile = self._store.get_profile(conversation.user_id)
        if profile.birthday is None:
            return False
        return is_birthday(profile.birthday, local.date())

    def _anniversary(self, conversation: Conversation, local: datetime) -> bool:
        """The monthly return of the day they first spoke: 30, 60, 90 days on."""
        first = self._store.first_message_at(conversation.user_id, conversation.character_id)
        if first is None:
            return False
        days = (local.date() - first.astimezone(local.tzinfo).date()).days
        return days > 0 and days % 30 == 0

    def _gap_met(self, conversation: Conversation, local: datetime) -> bool:
        last = self._last_delivered(conversation)
        if last is None:
            return True
        gap = _drawn(f"gap:{conversation.id}:{last.isoformat()}", *GAP_DAYS)
        return local >= (last.astimezone(local.tzinfo) + timedelta(days=gap))

    def _written_today(self, conversation: Conversation, local: datetime) -> bool:
        last = self._last_delivered(conversation)
        return last is not None and last.astimezone(local.tzinfo).date() == local.date()

    def _user_written_today(self, conversation: Conversation, local: datetime) -> bool:
        """Whether he has had a letter today from anyone: one an evening is enough, not one
        per close character at once."""
        with self._lock:
            rows = self._db.execute(
                "SELECT delivered_at FROM letters WHERE user_id = ? ORDER BY delivered_at DESC LIMIT 1",
                (conversation.user_id,),
            ).fetchone()
        if rows is None:
            return False
        return datetime.fromisoformat(rows["delivered_at"]).astimezone(local.tzinfo).date() == local.date()

    def _last_delivered(self, conversation: Conversation) -> datetime | None:
        with self._lock:
            row = self._db.execute(
                "SELECT delivered_at FROM letters WHERE user_id = ? AND character_id = ?"
                " ORDER BY delivered_at DESC LIMIT 1",
                (conversation.user_id, conversation.character_id),
            ).fetchone()
        return datetime.fromisoformat(row["delivered_at"]) if row else None

    def _keep(
        self,
        conversation: Conversation,
        segments: Sequence[Segment],
        trigger: str,
        now: datetime,
        envelope_enza: str | None = None,
    ) -> None:
        letter_id = hashlib.sha256(
            f"{conversation.id}:{now.isoformat()}".encode()
        ).hexdigest()[:16]
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO letters (id, user_id, character_id, trigger, written_at,"
                " delivered_at, segments, read_at, envelope_enza)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?)",
                (
                    letter_id,
                    conversation.user_id,
                    conversation.character_id,
                    trigger,
                    now.isoformat(),
                    now.isoformat(),
                    json.dumps([{"ja": s.ja, "zh": s.zh} for s in segments], ensure_ascii=False),
                    envelope_enza,
                ),
            )
            self._db.execute(
                "DELETE FROM letters WHERE user_id = ? AND character_id = ? AND id NOT IN"
                " (SELECT id FROM letters WHERE user_id = ? AND character_id = ?"
                "  ORDER BY delivered_at DESC LIMIT ?)",
                (
                    conversation.user_id,
                    conversation.character_id,
                    conversation.user_id,
                    conversation.character_id,
                    MAX_LETTERS_KEPT,
                ),
            )

    def of(self, user_id: str, characters: Mapping[str, Character]) -> list[Letter]:
        """Every letter the user has, the latest first."""
        with self._lock:
            rows = self._db.execute(
                "SELECT id, character_id, trigger, delivered_at, segments, read_at, envelope_enza"
                " FROM letters"
                " WHERE user_id = ? ORDER BY delivered_at DESC",
                (user_id,),
            ).fetchall()
        letters: list[Letter] = []
        for row in rows:
            if row["character_id"] not in characters:
                continue
            letters.append(
                Letter(
                    id=row["id"],
                    character_id=row["character_id"],
                    trigger=row["trigger"],
                    delivered_at=datetime.fromisoformat(row["delivered_at"]),
                    segments=[Segment(ja=s.get("ja", ""), zh=s.get("zh", ""))
                              for s in json.loads(row["segments"])],
                    read=row["read_at"] is not None,
                    envelope_enza=row["envelope_enza"],
                )
            )
        return letters

    def letter_of(self, user_id: str, letter_id: str) -> "Letter | None":
        """The user's one letter, if it is theirs."""
        with self._lock:
            row = self._db.execute(
                "SELECT id, character_id, trigger, delivered_at, segments, read_at, envelope_enza"
                " FROM letters WHERE user_id = ? AND id = ?",
                (user_id, letter_id),
            ).fetchone()
        if row is None:
            return None
        return Letter(
            id=row["id"],
            character_id=row["character_id"],
            trigger=row["trigger"],
            delivered_at=datetime.fromisoformat(row["delivered_at"]),
            segments=[Segment(ja=s.get("ja", ""), zh=s.get("zh", ""))
                      for s in json.loads(row["segments"])],
            read=row["read_at"] is not None,
            envelope_enza=row["envelope_enza"],
        )

    def envelope_path(self, enza_id: str) -> Path | None:
        return self._envelopes.path(enza_id) if self._envelopes is not None else None

    def mark_read(self, user_id: str, letter_id: str) -> bool:
        with self._lock, self._db:
            cur = self._db.execute(
                "UPDATE letters SET read_at = ? WHERE id = ? AND user_id = ? AND read_at IS NULL",
                (self._clock().isoformat(), letter_id, user_id),
            )
        return cur.rowcount > 0


def _minutes(window: tuple[time, time]) -> int:
    return (window[1].hour * 60 + window[1].minute) - (window[0].hour * 60 + window[0].minute)


async def _sleep(delta: timedelta) -> None:
    import asyncio

    await asyncio.sleep(delta.total_seconds())


async def _thread(fn):  # noqa: ANN001, ANN201
    import asyncio

    return await asyncio.to_thread(fn)


def add_letter_routes(app, store: Store, letters: Letters, characters: Mapping[str, Character]) -> None:  # noqa: ANN001
    """`/api/letters`: what she has written to the user, the latest first, and `/api/letters/{id}/read`."""
    from fastapi import HTTPException
    from fastapi.responses import Response

    from eidolon.sessions import UserId

    @app.get("/api/letters")
    async def list_letters(user_id: UserId) -> dict:
        return {
            "letters": [
                letter.as_json(characters[letter.character_id])
                for letter in letters.of(user_id, characters)
            ]
        }

    @app.get("/api/letters/{letter_id}/envelope")
    async def letter_envelope(letter_id: str, user_id: UserId) -> Response:
        from fastapi.responses import FileResponse

        letter = letters.letter_of(user_id, letter_id)
        path = letters.envelope_path(letter.envelope_enza) if letter and letter.envelope_enza else None
        if path is None or not path.exists():
            raise HTTPException(404, "没有这封信的信封")
        return FileResponse(
            path,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )

    @app.post("/api/letters/{letter_id}/read", status_code=204)
    async def read_letter(letter_id: str, user_id: UserId) -> None:
        if not letters.mark_read(user_id, letter_id):
            raise HTTPException(404, "没有这封信")


__all__ = ["Letters", "Letter", "add_letter_routes", "GAP_DAYS", "TIERS", "EVENING"]
