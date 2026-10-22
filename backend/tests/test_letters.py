"""Her letters (GLOSSARY.md「信」, fork): what she would not say to his face, left in the
announcements one evening.

Only a character the producer is close to writes them, one every few days, in the evening of
his day — or on a day that calls for it. Driven through the backend's external API, the
evenings taken by hand (`Letters.deliver_due`), the clock set to one, and the affinity kept
where a test needs it."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from eidolon.config import Settings
from eidolon.letters import GAP_DAYS
from tests.conftest import ClientFactory
from tests.fakes import FAKE_JUDGE, FakeClock, FakeLLM
from tests.test_affinity import keep
from tests.test_reach_outs import backend_of, live_in
from tests.test_text_turn import send_turn, start_conversation

REPLY = ["<ja>はい</ja><zh>好的</zh>"]
LETTER = [
    "<ja>[softly] プロデューサーさんへ</ja><zh>致制作人</zh>",
    "<ja>今日は、ちゃんと言えなかったことを書きます。</ja><zh>今天，我把没能说出口的话写下来。</zh>",
    "<ja>また明日、事務所で。</ja><zh>明天，事务所见。</zh>",
]
"""What her chat model writes when asked for a letter: an opening, a body, a closing."""

EVENING = "Etc/GMT-7"
"""A zone where 14:59 UTC is 21:59, the last minute of the evening, whenever the tests run."""


@pytest.fixture
def settings(settings: Settings) -> Settings:
    """With the judge model, affinity on, and reach-outs on as letters go by them."""
    return replace(settings, judge=FAKE_JUDGE, affinity_and_gifts=True)


async def talked(make_client: ClientFactory, *replies, at: datetime | None = None):
    """A client whose producer has spoken with Mano once, on a clock set to `at` (an evening
    by default), living in `EVENING`."""
    clock = FakeClock(at or datetime(2026, 10, 22, 14, 59, tzinfo=UTC))
    llm = FakeLLM(REPLY, *replies)
    client = make_client(llm, clock=clock)
    await live_in(client, EVENING)
    conversation = await start_conversation(client)
    await send_turn(client, conversation, "今日はありがとう")
    return client, llm, clock, conversation


def letters_of(client_letters: dict) -> list[dict]:
    return client_letters["letters"]


async def test_only_she_who_is_close_writes(make_client: ClientFactory, settings: Settings):
    """信任 writes no letters; 亲近 does."""
    for value, expected in ((50, 0), (70, 1)):
        client, _, clock, conversation = await talked(
            make_client, LETTER, at=datetime(2026, 10, 22, 14, 59, tzinfo=UTC)
        )
        keep(settings.database_path, "producer", value, clock.now)

        await backend_of(client).letters.deliver_due()

        got = (await client.get("/api/letters")).json()
        assert len(letters_of(got)) == expected, value


async def test_a_letter_comes_in_the_evening_and_is_read_once(
    make_client: ClientFactory, settings: Settings
):
    client, llm, clock, conversation = await talked(
        make_client, LETTER, at=datetime(2026, 10, 22, 14, 59, tzinfo=UTC)
    )
    keep(settings.database_path, "producer", 70, clock.now)

    await backend_of(client).letters.deliver_due()

    [letter] = letters_of((await client.get("/api/letters")).json())
    assert letter["character_name"] == "櫻木真乃"
    assert letter["trigger"] in ("everyday", "birthday", "anniversary")
    assert [s["ja"] for s in letter["segments"]][1].startswith("今日は")
    assert letter["read"] is False

    res = await client.post(f"/api/letters/{letter['id']}/read")
    assert res.status_code == 204
    [again] = letters_of((await client.get("/api/letters")).json())
    assert again["read"] is True


async def test_no_second_letter_before_the_gap(make_client: ClientFactory, settings: Settings):
    """One letter a day at most, and none again before the drawn gap."""
    client, _, clock, _ = await talked(make_client, LETTER, LETTER)
    keep(settings.database_path, "producer", 70, clock.now)

    await backend_of(client).letters.deliver_due()
    assert len(letters_of((await client.get("/api/letters")).json())) == 1

    clock.advance(days=GAP_DAYS[1] + 1)
    await backend_of(client).letters.deliver_due()
    assert len(letters_of((await client.get("/api/letters")).json())) == 2


async def test_nothing_is_written_in_the_morning(make_client: ClientFactory, settings: Settings):
    client, _, clock, _ = await talked(
        make_client, LETTER, at=datetime(2026, 10, 22, 1, 40, tzinfo=UTC)  # 08:40 there
    )
    keep(settings.database_path, "producer", 70, clock.now)

    await backend_of(client).letters.deliver_due()

    assert letters_of((await client.get("/api/letters")).json()) == []
