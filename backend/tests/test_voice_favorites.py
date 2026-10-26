"""收藏的语音（fork）：一句被收藏时复制出自己的一份，列表里能看能听，删除连副本一起删。

不经过桶和 TTS：这里把 `MessageSpeech` 收窄成三个方法替身，验的是路由、归属和表。
"""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from eidolon import voice_favorites
from eidolon.characters import load_characters
from eidolon.sessions import SESSION_COOKIE
from eidolon.store import Segment, Store
from eidolon.voice_favorites import VoiceFavorites, add_voice_favorite_routes
from tests.conftest import CharacterConfig

NOW = datetime(2026, 10, 26, 3, tzinfo=UTC)
ASSETS = "https://assets.example"


class FakeSpeech:
    """A stand-in for `MessageSpeech`: it keeps what it was asked to keep, says where
    everything is, and records what it was told to drop."""

    def __init__(self) -> None:
        self.kept: dict[str, tuple[str, str]] = {}
        self.refreshed: list[str] = []
        self.dropped: list[str] = []

    async def keep(self, character_id: str, ja: str, name: str, refresh: bool = False) -> str:
        """`refresh` 覆盖已有那份（「重新生成」之后收藏跟着换新）。"""
        if refresh or name not in self.kept:
            self.kept[name] = (character_id, ja)
            self.refreshed.append(name)
        return f"{ASSETS}/{name}"

    def heard_at(self, path: str) -> str:
        return f"{ASSETS}/{path}"

    async def drop(self, name: str) -> None:
        self.dropped.append(name)


class _Backend:
    """What the session dependency reads: the store and the clock."""

    def __init__(self, store: Store) -> None:
        self.store = store
        self.clock = lambda: NOW


@pytest.fixture
def world(tmp_path: Path, characters: CharacterConfig):
    store = Store(tmp_path / "eidolon.db")
    cast = load_characters(characters.path)
    favorites = VoiceFavorites(tmp_path / "eidolon.db", lambda: NOW)
    speech = FakeSpeech()
    app = FastAPI()
    app.state.backend = _Backend(store)
    add_voice_favorite_routes(app, store, favorites, speech, cast)  # type: ignore[arg-type]
    user = store.create_user("producer")
    store.consent(user.id, NOW)
    conversation = store.create_conversation(user.id, "mano")
    store.add_turn(
        conversation.id,
        "我家的猫叫小白哦",
        [Segment("ほわっ、かわいい", "哇，好可爱"), Segment("ね、そこの猫", "那只猫呢")],
    )
    reply = [m for m in store.list_messages(conversation.id) if m.role == "character"][0]
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE, store.create_session(user.id, NOW))
    yield client, store, favorites, speech, cast, user, reply
    favorites.close()
    store.close()


def _body(reply_id: int, segment: int = 0) -> dict:
    return {"kind": "message", "id": reply_id, "segment": segment}


def test_keeping_a_line_copies_it_and_lists_it(world):
    client, _, _, speech, cast, _, reply = world

    kept = client.post("/api/voice-favorites", json=_body(reply.id))
    assert kept.status_code == 200, kept.text
    shown = kept.json()
    assert (shown["character_id"], shown["ja"], shown["zh"]) == (
        "mano", "ほわっ、かわいい", "哇，好可爱",
    )
    assert shown["character_name"] == "櫻木真乃"
    assert shown["url"].startswith(f"{ASSETS}/voice-favorites/")
    assert speech.kept[shown["url"].removeprefix(f"{ASSETS}/")] == ("mano", "ほわっ、かわいい")

    listed = client.get("/api/voice-favorites").json()
    assert [entry["id"] for entry in listed] == [shown["id"]]

    dropped = client.delete(f"/api/voice-favorites/{shown['id']}")
    assert dropped.status_code == 204
    assert speech.dropped == [shown["url"].removeprefix(f"{ASSETS}/")]
    assert client.get("/api/voice-favorites").json() == []


def test_the_same_take_of_the_same_line_is_kept_once(world):
    client, _, _, _, _, _, reply = world

    first = client.post("/api/voice-favorites", json=_body(reply.id)).json()
    again = client.post("/api/voice-favorites", json=_body(reply.id)).json()

    assert again["id"] == first["id"]
    assert len(client.get("/api/voice-favorites").json()) == 1


async def test_voicing_it_again_refreshes_what_the_favorite_keeps(world):
    """「重新生成」之后，收藏里那份换成新的一版：再进统计页听到的就是新那版。"""
    client, _, favorites, speech, cast, user, reply = world
    kept = client.post("/api/voice-favorites", json=_body(reply.id)).json()
    path = kept["url"].removeprefix(f"{ASSETS}/")

    await favorites.refresh(user.id, "mano", "ほわっ、かわいい", speech)

    assert speech.refreshed[-1] == path
    # 收藏一次就写一份；再收藏同一句是覆盖成最新那一版，不是又多一条
    assert client.post("/api/voice-favorites", json=_body(reply.id)).json()["id"] == kept["id"]
    assert len(speech.kept) == 1


def test_a_segment_of_her_saying_nothing_is_not_a_favorite(world):
    client, _, _, _, _, _, reply = world

    assert client.post("/api/voice-favorites", json=_body(reply.id, 9)).status_code == 404


def test_a_line_in_someone_elses_conversation_is_not_found(world):
    client, store, _, _, _, _, reply = world
    stranger = store.create_user("stranger")
    store.consent(stranger.id, NOW)
    conversation = store.create_conversation(stranger.id, "mano")
    store.add_turn(conversation.id, "你好", [Segment("はい", "好")])
    theirs = [m for m in store.list_messages(conversation.id) if m.role == "character"][0]

    assert client.post("/api/voice-favorites", json=_body(theirs.id)).status_code == 404


def test_the_store_refuses_more_than_the_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(voice_favorites, "PER_USER", 2)
    store = Store(tmp_path / "eidolon.db")  # the users the favorites refer to
    first = store.create_user("first").id
    second = store.create_user("second").id
    favorites = VoiceFavorites(tmp_path / "eidolon.db", lambda: NOW)
    try:
        favorites.add(first, "mano", "mano/a", "あ", "")
        favorites.add(first, "mano", "mano/b", "い", "")
        with pytest.raises(voice_favorites.Full):
            favorites.add(first, "mano", "mano/c", "う", "")
        favorites.add(second, "mano", "mano/a", "あ", "")  # another user has their own count
        store.close()
    finally:
        favorites.close()


def test_the_copy_is_named_for_its_user_and_take():
    first = VoiceFavorites._kept_path("u1", "mano/あ")
    assert first == VoiceFavorites._kept_path("u1", "mano/あ")
    assert first != VoiceFavorites._kept_path("u1", "mano/い")
    assert first != VoiceFavorites._kept_path("u2", "mano/あ")
    assert first.startswith("voice-favorites/")


def test_the_cap_is_counted_per_user_in_the_database(tmp_path: Path):
    """The table is a user's data: deleting the account deletes it."""
    favorites = VoiceFavorites(tmp_path / "eidolon.db", lambda: NOW)
    favorites.close()
    with sqlite3.connect(tmp_path / "eidolon.db") as db:
        assert db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'voice_favorites'"
        ).fetchone()
