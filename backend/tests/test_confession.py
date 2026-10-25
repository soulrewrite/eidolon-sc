"""The confession (fork, PLAN-20261025 B): how a confession she may accept is judged,
answered and kept, and what being a couple changes of what she is told."""

import sqlite3
from dataclasses import replace
from datetime import UTC, datetime

import httpx

from eidolon.config import Settings
from eidolon.engine import COUPLE_AT, CONFESSING, couple_prompt
from tests.conftest import ClientFactory
from tests.fakes import FAKE_JUDGE, FakeLLM, FakeServiceClients, Judging
from tests.test_affinity import keep
from tests.test_reach_outs import backend_of
from tests.test_text_turn import send_turn, start_conversation

VALUE = COUPLE_AT + 2  # in the top tier, over the bar
CONFESSION = "我喜欢你，不是对偶像的那种喜欢。你愿意做我的女朋友吗？"


def judging(*judgings: Judging) -> FakeServiceClients:
    """The deployer's judge models answering each affinity turn as `judgings` script them."""
    clients = FakeServiceClients()
    clients.judge.judgings = list(judgings)
    return clients


def with_affinity(settings: Settings) -> Settings:
    """With affinity on, judged by the fake judge."""
    return replace(settings, judge=FAKE_JUDGE, affinity_and_gifts=True)


def couple_since(database, character: str = "mano") -> datetime | None:
    """When the producer and `character` became a couple in `database`; None if never."""
    with sqlite3.connect(database) as db:
        row = db.execute(
            "SELECT since FROM couples WHERE user_id ="
            " (SELECT id FROM users WHERE name = 'producer') AND character_id = ?",
            (character,),
        ).fetchone()
    return datetime.fromisoformat(row[0]) if row else None


def prompts_of(llm: FakeLLM) -> list[str]:
    """Every prompt it received, as one string each."""
    return ["\n".join(m.content for m in prompt) for prompt in llm.prompts]


async def confession_client(
    make_client: ClientFactory, settings: Settings, llm: FakeLLM
) -> httpx.AsyncClient:
    """A client whose user is intimate past the bar with Mano, his next words judged a
    confession, her model replying from `llm`'s script."""
    client = make_client(
        llm,
        clients=judging(Judging(), Judging(confess=True)),
        settings=with_affinity(settings),
    )
    conversation = await start_conversation(client)
    await send_turn(client, conversation, "我来练习了")
    keep(settings.database_path, "producer", VALUE, datetime.now(UTC))
    return client


async def test_his_confession_at_the_top_is_answered_by_her_and_kept(
    make_client: ClientFactory, settings: Settings
):
    """His confession, her model answering 接受: the reply she gives is told to be the
    accepting one, they are a couple from this turn, and every turn after tells her so."""
    llm = FakeLLM(
        ["<ja>はい</ja><zh>好的</zh>"],
        ["接受"],
        ["<ja>うん……！プロデューサー、大好きですっ</ja><zh>嗯……！制作人，我最喜欢你</zh>"],
        ["<ja>おはよう</ja><zh>早上好</zh>"],
    )
    client = await confession_client(make_client, settings, llm)
    conversation = await start_conversation(client)

    await send_turn(client, conversation, CONFESSION)

    assert "你们就是恋人了" in prompts_of(llm)[-1]
    assert couple_since(settings.database_path) is not None
    await send_turn(client, conversation, "早上好呀")
    told = prompts_of(llm)[-1]
    assert "# 你们的关系" in told and "是恋人" in told
    assert "小声，但比谁都认真" in told  # her couple_note from characters.toml


async def test_her_answer_need_not_be_accepting(
    make_client: ClientFactory, settings: Settings
):
    """Her model answering 拒绝: she is told to refuse gently; they do not become a
    couple, and no couple section is told after."""
    llm = FakeLLM(
        ["<ja>はい</ja><zh>好的</zh>"],
        ["拒绝"],
        ["<ja>ごめんね……</ja><zh>对不起……</zh>"],
        ["<ja>うん</ja><zh>嗯</zh>"],
    )
    client = await confession_client(make_client, settings, llm)
    conversation = await start_conversation(client)

    await send_turn(client, conversation, CONFESSION)

    assert "温柔但诚实地拒绝" in prompts_of(llm)[-1]
    assert couple_since(settings.database_path) is None
    await send_turn(client, conversation, "那我们还是好朋友")
    assert "# 你们的关系" not in prompts_of(llm)[-1]


async def test_a_confession_below_the_bar_is_not_hers_to_answer(
    make_client: ClientFactory, settings: Settings
):
    """A confession in the top tier but short of the bar, or in a lower one: however many
    times he confesses, no stage direction of ours is told and they never become a couple."""
    for value in (COUPLE_AT - 5, 60.0):
        llm = FakeLLM(["<ja>はい</ja><zh>好的</zh>"], ["<ja>えっ……</ja><zh>诶……</zh>"])
        client = make_client(
            llm,
            clients=judging(Judging(), Judging(confess=True)),
            settings=with_affinity(settings),
        )
        conversation = await start_conversation(client)
        await send_turn(client, conversation, "我来练习了")
        keep(settings.database_path, "producer", value, datetime.now(UTC))

        await send_turn(client, conversation, CONFESSION)

        assert CONFESSING["accepted"] not in prompts_of(llm)[-1]
        assert couple_since(settings.database_path) is None


async def test_no_confession_nothing_of_it(
    make_client: ClientFactory, settings: Settings
):
    """Ordinary words at the top of intimacy: no stage direction, no couple, however
    warm they are."""
    llm = FakeLLM(["<ja>はい</ja><zh>好的</zh>"], ["<ja>ありがとう</ja><zh>谢谢</zh>"])
    client = make_client(
        llm, clients=judging(), settings=with_affinity(settings)
    )
    conversation = await start_conversation(client)
    await send_turn(client, conversation, "我来练习了")
    keep(settings.database_path, "producer", VALUE, datetime.now(UTC))

    await send_turn(client, conversation, "我很喜欢你的歌")

    assert "告白" not in prompts_of(llm)[-1]
    assert couple_since(settings.database_path) is None


async def test_the_couples_of_one_are_not_the_couples_of_another(
    make_client: ClientFactory, settings: Settings
):
    """Becoming a couple with one character leaves the others as they were: each is her
    own answer to his own confession."""
    llm = FakeLLM(
        ["<ja>はい</ja><zh>好的</zh>"], ["接受"], ["<ja>うん！</ja><zh>嗯！</zh>"],
        ["<ja>うん</ja><zh>嗯</zh>"],
    )
    client = await confession_client(make_client, settings, llm)
    conversation = await start_conversation(client)
    await send_turn(client, conversation, CONFESSION)
    assert couple_since(settings.database_path, character="mano") is not None
    assert couple_since(settings.database_path, character="hiori") is None


async def test_the_confession_letter_comes_the_day_they_became_a_couple(
    make_client: ClientFactory, settings: Settings
):
    """The day she accepted: her letter says so, once — and the everyday letter of that
    evening is not written as well."""
    llm = FakeLLM(
        ["<ja>はい</ja><zh>好的</zh>"], ["接受"], ["<ja>うん……！</ja><zh>嗯……！</zh>"],
        ["<ja>プロデューサーへ。</ja><zh>致制作人。</zh>",
         "<ja>今日で恋人になって、なんだか不思議です。</ja>"
         "<zh>今天起成了恋人，感觉有点不可思议。</zh>"],
    )
    client = await confession_client(make_client, settings, llm)
    conversation = await start_conversation(client)
    await send_turn(client, conversation, CONFESSION)
    assert couple_since(settings.database_path) is not None

    backend = backend_of(client)
    await backend.letters.deliver_due()

    with sqlite3.connect(settings.database_path) as db:
        letters = db.execute(
            "SELECT trigger FROM letters WHERE user_id ="
            " (SELECT id FROM users WHERE name = 'producer') AND character_id = 'mano'"
            " ORDER BY delivered_at"
        ).fetchall()
    assert ["confession"] == [trigger for (trigger,) in letters]

    await backend.letters.deliver_due()  # once, however often the day is looked at
    with sqlite3.connect(settings.database_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM letters WHERE trigger = 'confession'"
        ).fetchone()[0] == 1


def test_couple_prompt_without_a_note_tells_the_plain_rule():
    """No couple_note of her own: the plain rule, that she may love as herself."""
    told = couple_prompt(datetime.now(UTC), None, "Asia/Shanghai")
    assert "你们从" in told and "恋人" in told and "不要变成另一个人" in told
