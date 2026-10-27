"""她的一天（`schedules.py`）：作息解析、排班、此刻状态、提示词那几行。

不起服务，只测纯逻辑和一张临时库。
"""

from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import cast
from zoneinfo import ZoneInfo


from eidolon.characters import Character
from eidolon.schedules import Schedules, compose, read_routines
from eidolon.world import Live, LiveDay, World

ROUTINES = Path(__file__).resolve().parents[2] / "characters" / "routines.toml"
TOKYO = "Asia/Tokyo"


def character(name: str = "櫻木真乃", character_id: str = "mano") -> Character:
    return cast(
        "Character",
        Character(
            id=character_id,
            name=name,
            intro="",
            voice_id="v",
            sheet="",
            avatar=None,
            color="#ffbad6",
        ),
    )


def clock_at(day: date, hour: int, minute: int = 0):
    moment = datetime(day.year, day.month, day.day, hour, minute, tzinfo=ZoneInfo(TOKYO))
    return lambda: moment.astimezone(UTC)


def test_every_character_in_the_file_has_three_fields():
    routines = read_routines(ROUTINES)
    assert len(routines) >= 29
    for character_id, routine in routines.items():
        assert routine.sleep_text, character_id
        assert routine.bath in ("泡澡", "淋浴"), character_id
        assert routine.habit, character_id


def test_sleep_and_wake_are_read_from_the_sentence():
    routines = read_routines(ROUTINES)
    mano = routines["mano"]
    assert mano.session == time(23, 0) or mano.session == time(23, 30)
    assert mano.wake.hour in (6, 7)


def test_a_live_day_is_planned_as_a_live_day():
    day = date(2026, 12, 19)
    live = Live(
        name="shiny, the first REFRACT7IONS",
        days=(
            LiveDay(
                date=day, venue="ぴあアリーナMM", performers=("櫻木真乃",), absent=(), sources=()
            ),
        ),
        sources=(),
    )
    world = World(
        as_of=day,
        office="283",
        staff=(),
        units=(),
        idols=(),
        releases=(),
        songs=(),
        lives=(live,),
    )
    plan = compose(read_routines(ROUTINES)["mano"], character(), day, "u1", world)
    assert plan.live is not None and "ぴあアリーナMM" in plan.live
    assert any("彩排" in doing for _, doing in plan.entries)


def test_the_same_day_is_always_planned_the_same_way():
    day = date(2026, 10, 27)
    routine = read_routines(ROUTINES)["mano"]
    first = compose(routine, character(), day, "u1", None)
    again = compose(routine, character(), day, "u1", None)
    other_user = compose(routine, character(), day, "u2", None)
    assert first.entries == again.entries
    assert first.bath_at == again.bath_at
    assert (first.entries, first.bath_at) != (other_user.entries, other_user.bath_at)


def test_a_plan_is_three_to_six_segments_with_a_bath_before_sleep():
    day = date(2026, 10, 27)
    for seed_user in ("u1", "u2", "u3", "u4"):
        plan = compose(read_routines(ROUTINES)["mano"], character(), day, seed_user, None)
        assert 3 <= len(plan.entries) <= 6
        assert plan.bath_until <= plan.sleep or plan.sleep < plan.bath_at
        assert plan.wake <= plan.sleep or plan.sleep <= time(3, 0)


def test_she_is_asleep_bath_working_or_free(tmp_path):
    day = date(2026, 10, 27)
    schedules = Schedules(tmp_path / "s.db", {"mano": character()}, clock_at(day, 12), None, ROUTINES)
    plan = schedules.ensure("u1", "mano", TOKYO)
    assert plan is not None

    def state_at(hour: int, minute: int = 0) -> str:
        schedules._clock = clock_at(day, hour, minute)  # pyright: ignore[reportPrivateUsage]
        return schedules.now("u1", "mano", TOKYO)[0]

    assert state_at(plan.bath_at.hour, plan.bath_at.minute) == "bathing"
    assert state_at(plan.sleep.hour, plan.sleep.minute) == "sleeping"
    assert state_at(plan.wake.hour + 3, 0) in ("working", "free")
    schedules.close()


def test_the_prompt_lines_say_what_she_is_doing(tmp_path):
    day = date(2026, 10, 27)
    schedules = Schedules(tmp_path / "s.db", {"mano": character()}, clock_at(day, 14), None, ROUTINES)
    lines = schedules.prompt_lines("u1", "mano", TOKYO)
    assert lines[0] == "# 她的这一天"
    assert any("今天的安排" in line for line in lines)
    assert any("不必逐条背" in line for line in lines)
    schedules.close()


def test_a_character_without_routines_gets_nothing(tmp_path):
    schedules = Schedules(tmp_path / "s.db", {"mano": character()}, clock_at(date(2026, 10, 27), 12), None, ROUTINES)
    assert schedules.ensure("u1", "nobody", TOKYO) is None
    assert schedules.prompt_lines("u1", "nobody", TOKYO) == []
    schedules.close()


def test_the_same_day_is_not_planned_twice(tmp_path):
    day = date(2026, 10, 27)
    schedules = Schedules(tmp_path / "s.db", {"mano": character()}, clock_at(day, 12), None, ROUTINES)
    first = schedules.ensure("u1", "mano", TOKYO)
    later = Schedules(tmp_path / "s.db", {"mano": character()}, clock_at(day, 20), None, ROUTINES)
    again = later.ensure("u1", "mano", TOKYO)
    assert first is not None and again is not None
    assert first.entries == again.entries
    later.close()
    schedules.close()


def test_the_prompt_about_now_carries_her_day():
    """`now_prompt` 把行程那几行接在「此刻」后面（fork）。"""
    from eidolon.producer import ProducerProfile, now_prompt

    profile = ProducerProfile(timezone=TOKYO)
    moment = datetime(2026, 10, 27, 5, 0, tzinfo=UTC)
    prompt = now_prompt(
        profile,
        moment,
        TOKYO,
        "typing",
        schedule_lines=["# 她的这一天", "现在的状态：在洗澡。"],
    )
    assert "# 此刻" in prompt
    assert "# 她的这一天" in prompt
    assert "现在的状态：在洗澡。" in prompt
    assert prompt.index("# 此刻") < prompt.index("# 她的这一天")


def test_she_says_she_just_got_out_of_the_bath_only_once(tmp_path):
    """一段洗澡只说一次「刚洗完」：以前每回合都说，一晚上能说三四遍。"""
    day = date(2026, 10, 27)
    schedules = Schedules(tmp_path / "s.db", {"mano": character()}, clock_at(day, 12), None, ROUTINES)
    plan = schedules.ensure("u1", "mano", TOKYO)
    assert plan is not None

    schedules._clock = clock_at(day, plan.bath_at.hour, plan.bath_at.minute + 5)  # pyright: ignore[reportPrivateUsage]
    assert schedules.fresh_from_bath("u1", "mano", TOKYO) is True
    assert schedules.fresh_from_bath("u1", "mano", TOKYO) is False
    schedules.close()


def test_outside_the_bath_she_is_not_fresh_out_of_it(tmp_path):
    day = date(2026, 10, 27)
    schedules = Schedules(tmp_path / "s.db", {"mano": character()}, clock_at(day, 12), None, ROUTINES)
    assert schedules.fresh_from_bath("u1", "mano", TOKYO) is False
    schedules.close()
