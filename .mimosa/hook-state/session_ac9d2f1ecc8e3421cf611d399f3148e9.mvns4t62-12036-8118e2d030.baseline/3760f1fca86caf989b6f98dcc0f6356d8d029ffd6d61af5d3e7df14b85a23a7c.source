"""How much of a conversation the chat model reads each turn."""

from dataclasses import replace
from typing import Literal

import pytest

from eidolon.config import Settings, history_turns_from_env
from eidolon.engine import latest_turns
from eidolon.store import Message
from tests.conftest import ClientFactory
from tests.fakes import FakeLLM
from tests.test_text_turn import send_turn, start_conversation


def reply(n: int) -> list[str]:
    return [f"<ja>返事{n}</ja><zh>回复{n}</zh>"]


def exchange(n: int) -> list[tuple[str, str]]:
    return [("user", f"第{n}句"), ("assistant", f"<ja>返事{n}</ja><zh>回复{n}</zh>")]


async def talk(client_for, turns: int) -> tuple[FakeLLM, str]:
    """Take `turns` turns, then one more; the chat model's replies are numbered."""
    llm = FakeLLM(*[reply(n) for n in range(1, turns + 2)])
    client = client_for(llm)
    conversation_id = await start_conversation(client)
    for n in range(1, turns + 2):
        await send_turn(client, conversation_id, f"第{n}句")
    return llm, conversation_id


def history(llm: FakeLLM) -> list[tuple[str, str]]:
    """What the last prompt carries besides its system messages."""
    return [(m.role, m.content) for m in llm.prompts[-1] if m.role != "system"]


def told(llm: FakeLLM) -> str:
    """All the last prompt carries besides its system messages, as one text."""
    return "\n".join(content for _, content in history(llm))


async def test_prompt_carries_only_the_most_recent_turns(
    make_client: ClientFactory, settings: Settings
):
    llm, _ = await talk(lambda llm: make_client(llm, settings=replace(settings, history_turns=2)), 4)

    assert history(llm) == [*exchange(3), *exchange(4), ("user", "第5句")]


async def test_the_conversation_record_keeps_every_message(
    make_client: ClientFactory, settings: Settings
):
    client_settings = replace(settings, history_turns=1)
    _, conversation_id = await talk(lambda llm: make_client(llm, settings=client_settings), 3)

    reopened = make_client(FakeLLM(), settings=client_settings)
    messages = (await reopened.get(f"/api/conversations/{conversation_id}/messages")).json()
    assert [m["text"] for m in messages if m["role"] == "user"] == ["第1句", "第2句", "第3句", "第4句"]


def test_what_is_carried_opens_with_the_producer():
    def message(id: int, role: Literal["user", "character"]) -> Message:
        return Message(id, role, "话" if role == "user" else None, None, None, "", [])

    messages = [message(1, "character"), message(2, "user"), message(3, "character"),
                message(4, "character"), message(5, "user"), message(6, "character")]

    assert [m.id for m in latest_turns(messages, 1)] == [5, 6]
    assert [m.id for m in latest_turns(messages, 2)] == [2, 3, 4, 5, 6]
    assert [m.id for m in latest_turns(messages, 3)] == [2, 3, 4, 5, 6]
    assert [m.id for m in latest_turns(messages, None)] == [2, 3, 4, 5, 6]
    assert latest_turns(messages[:1], 2) == []


def test_the_limit_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("EIDOLON_HISTORY_TURNS", raising=False)
    assert history_turns_from_env() == 20

    monkeypatch.setenv("EIDOLON_HISTORY_TURNS", "8")
    assert history_turns_from_env() == 8

    monkeypatch.setenv("EIDOLON_HISTORY_TURNS", "0")
    assert history_turns_from_env() is None

    monkeypatch.setenv("EIDOLON_HISTORY_TURNS", "many")
    with pytest.raises(RuntimeError, match="EIDOLON_HISTORY_TURNS"):
        history_turns_from_env()


def test_the_reach_out_intervals_come_from_the_environment(monkeypatch: pytest.MonkeyPatch):
    """fork：她搭话的间隔范围可以按部署改（EIDOLON_REACH_OUT_INTERVALS），没写到的档位保持原样。"""
    from datetime import timedelta

    from eidolon.config import DEFAULT_REACH_OUT_INTERVALS, reach_out_intervals_from_env

    monkeypatch.delenv("EIDOLON_REACH_OUT_INTERVALS", raising=False)
    assert reach_out_intervals_from_env() == DEFAULT_REACH_OUT_INTERVALS

    monkeypatch.setenv("EIDOLON_REACH_OUT_INTERVALS", "intimate:1-3, close:2-8")
    intervals = reach_out_intervals_from_env()
    assert intervals["intimate"] == (timedelta(hours=1), timedelta(hours=3))
    assert intervals["close"] == (timedelta(hours=2), timedelta(hours=8))
    assert intervals["trust"] == DEFAULT_REACH_OUT_INTERVALS["trust"]

    monkeypatch.setenv("EIDOLON_REACH_OUT_INTERVALS", "close:2")
    assert reach_out_intervals_from_env()["close"] == (timedelta(hours=2), timedelta(hours=2))

    monkeypatch.setenv("EIDOLON_REACH_OUT_INTERVALS", "sweet:1-2")
    with pytest.raises(RuntimeError, match="不是档位"):
        reach_out_intervals_from_env()

    monkeypatch.setenv("EIDOLON_REACH_OUT_INTERVALS", "close:8-2")
    with pytest.raises(RuntimeError, match="范围不合理"):
        reach_out_intervals_from_env()
