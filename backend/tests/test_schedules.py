"""她的一天（`schedules.py`）：作息解析、排班、此刻状态、提示词那几行。

不起服务，只测纯逻辑和一张临时库。
"""

from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import cast
from zoneinfo import ZoneInfo


from eidolon.characters import Character
from eidolon.engine import parse_schedule
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

    # 洗澡开始后五分钟：用 timedelta 加，别拿 minute + 5（55 分就溢出了）
    at_bath = datetime.combine(day, plan.bath_at) + timedelta(minutes=5)
    schedules._clock = lambda: at_bath.replace(tzinfo=ZoneInfo(TOKYO)).astimezone(UTC)  # pyright: ignore[reportPrivateUsage]
    assert schedules.fresh_from_bath("u1", "mano", TOKYO) is True
    assert schedules.fresh_from_bath("u1", "mano", TOKYO) is False
    schedules.close()


def test_outside_the_bath_she_is_not_fresh_out_of_it(tmp_path):
    day = date(2026, 10, 27)
    schedules = Schedules(tmp_path / "s.db", {"mano": character()}, clock_at(day, 12), None, ROUTINES)
    assert schedules.fresh_from_bath("u1", "mano", TOKYO) is False
    schedules.close()


def test_the_model_plan_is_read_line_by_line():
    """模型写的行程按「HH:MM–HH:MM 一句话」读；读不成样子就当没写。"""
    good = """06:20–06:50 闹钟响了两遍才起床
08:30–10:00 在事务所整理练习资料
11:00–12:30 和同组合的人一起练习
21:40–22:00 收拾好就睡了"""
    assert parse_schedule(good) == [
        ("06:20–06:50", "闹钟响了两遍才起床"),
        ("08:30–10:00", "在事务所整理练习资料"),
        ("11:00–12:30", "和同组合的人一起练习"),
        ("21:40–22:00", "收拾好就睡了"),
    ]
    assert parse_schedule("今天大概会很忙吧。") is None
    assert parse_schedule("") is None


def test_a_model_plan_keeps_her_sleep_and_bath(tmp_path):
    """模型只管「几点在做什么」，睡觉和洗澡的时间还是按 routines 来。"""
    day = date(2026, 10, 27)
    schedules = Schedules(tmp_path / "s.db", {"mano": character()}, clock_at(day, 6), None, ROUTINES)
    base = schedules.ensure("u1", "mano", TOKYO)
    assert base is not None
    started = base.wake.strftime("%H:%M")
    plan = schedules.put_model_plan(
        "u1", "mano", day,
        [(f"{started}–12:00", "练习"), ("13:00–17:00", "上课"), ("18:00–21:00", "自由时间")],
    )
    assert plan is not None and plan.written_by == "model"
    reread = schedules.plan("u1", "mano", day)
    assert reread is not None
    assert reread.written_by == "model"
    assert reread.sleep == base.sleep and reread.bath_at == base.bath_at
    assert any(what == "练习" for _, what in reread.entries)
    schedules.close()


def test_sleep_and_wake_are_read_from_their_own_clause():
    """「0 点前后睡、6 点前后起」不能被读成「0 点起」——那会让睡觉窗口变成一整天。"""
    from eidolon.schedules import _sleep_and_wake

    assert _sleep_and_wake("0 点前后睡、6 点前后起；特技是早起") == (time(0, 0), time(6, 0))
    assert _sleep_and_wake("22 点前后睡、6 点起，早睡早起") == (time(22, 0), time(6, 0))
    assert _sleep_and_wake("1 点以后睡、9 点半起") == (time(1, 0), time(9, 30))
    # 读不出来就退回 23:00 / 07:00
    assert _sleep_and_wake("困了就睡") == (time(23, 0), time(7, 0))


def test_a_model_plan_is_cleaned_before_it_is_kept(tmp_path):
    """洗澡由 routines 管，模型写的洗澡要删掉；别人的名字换成「同组合的人」；越过睡觉的段丢掉。"""
    day = date(2026, 10, 27)
    schedules = Schedules(
        tmp_path / "s.db", {"mano": character(), "toru": character("浅倉透", "toru")},
        clock_at(day, 6), None, ROUTINES,
    )
    base = schedules.ensure("u1", "mano", TOKYO)
    assert base is not None
    plan = schedules.put_model_plan(
        "u1", "mano", day,
        [
            (f"{base.wake:%H:%M}–07:10", "起床后给浅仓透发消息，顺手泡澡"),
            ("09:00–11:00", "去事务所上课"),
            ("13:00–15:00", "练习"),
            ("16:00–17:00", "去超市买晚饭"),
            (f"{base.sleep:%H:%M}–23:59", "睡前刷手机"),  # 从睡觉那一刻才开始，直接丢掉
        ],
    )
    assert plan is not None
    texts = " ".join(what for _, what in plan.entries)
    assert "泡澡" not in texts
    assert "浅倉透" not in texts
    assert all(when.split("–")[1] <= base.sleep.strftime("%H:%M") for when, _ in plan.entries)


def test_an_entry_across_midnight_is_trimmed_at_her_bedtime(tmp_path):
    """她 00:10 睡，最后一段写到 00:20 就要截到 00:10，别让人在她睡着以后还在活动。"""
    day = date(2026, 10, 27)
    schedules = Schedules(tmp_path / "s.db", {"kogane": character("月岡恋鐘", "kogane")}, clock_at(day, 6), None, ROUTINES)
    base = schedules.ensure("u1", "kogane", TOKYO)
    assert base is not None
    plan = schedules.put_model_plan(
        "u1", "kogane", day,
        [
            ("09:00–11:00", "去事务所上课"),
            ("14:00–16:00", "练习"),
            ("19:00–20:00", "做饭"),
            ("22:30–00:20", "收拾厨房"),
        ],
    )
    assert plan is not None
    last = plan.entries[-1][0].split("–")[1]
    assert last <= base.sleep.strftime("%H:%M")
    schedules.close()
    schedules.close()


def test_while_she_is_bathing_the_prompt_does_not_say_so(tmp_path):
    """洗澡的事只由 engine 的洗澡规则说一次；这里的「现在状态」不能再写「在洗澡」，
    否则两套说法打架——实测她会一会儿说刚洗完、一会儿说还在洗。"""
    day = date(2026, 10, 27)
    schedules = Schedules(tmp_path / "s.db", {"mano": character()}, clock_at(day, 12), None, ROUTINES)
    plan = schedules.ensure("u1", "mano", TOKYO)
    assert plan is not None
    inside = datetime.combine(day, plan.bath_at) + timedelta(minutes=3)
    schedules._clock = lambda: inside.replace(tzinfo=ZoneInfo(TOKYO)).astimezone(UTC)  # pyright: ignore[reportPrivateUsage]
    lines = schedules.prompt_lines("u1", "mano", TOKYO)
    joined = "\n".join(lines)
    assert "在洗澡" not in joined
    assert "手机不在手边" in joined
    # 覆盖当前这一刻的那一段也别列出来（别让她念「21:00 洗澡」）
    assert not any(f"{plan.bath_at:%H:%M}" in line for line in lines if line.startswith("今天的安排"))
    schedules.close()


def test_right_after_the_bath_she_says_it_once(tmp_path):
    day = date(2026, 10, 27)
    schedules = Schedules(tmp_path / "s.db", {"mano": character()}, clock_at(day, 12), None, ROUTINES)
    plan = schedules.ensure("u1", "mano", TOKYO)
    assert plan is not None
    after = datetime.combine(day, plan.bath_until) + timedelta(minutes=5)
    schedules._clock = lambda: after.replace(tzinfo=ZoneInfo(TOKYO)).astimezone(UTC)  # pyright: ignore[reportPrivateUsage]
    assert schedules.just_out_of_bath("u1", "mano", TOKYO) is True
    assert schedules.just_out_of_bath("u1", "mano", TOKYO) is False
    # 过了 20 分钟就不再说
    late = datetime.combine(day, plan.bath_until) + timedelta(minutes=40)
    schedules._clock = lambda: late.replace(tzinfo=ZoneInfo(TOKYO)).astimezone(UTC)  # pyright: ignore[reportPrivateUsage]
    assert schedules.just_out_of_bath("u1", "mano", TOKYO) is False
    schedules.close()
