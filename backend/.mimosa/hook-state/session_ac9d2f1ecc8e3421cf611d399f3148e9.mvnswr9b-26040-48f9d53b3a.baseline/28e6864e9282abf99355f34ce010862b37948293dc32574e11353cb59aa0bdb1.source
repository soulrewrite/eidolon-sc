"""她把「什么时候」说对（FORK.md「时间」）。

两条：礼物超过三小时要带时间，而且要说成「昨晚」而不是「昨天」；此刻要写清是哪一段。
只测纯函数，不起服务。
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from eidolon.engine import _narration  # pyright: ignore[reportPrivateUsage]
from eidolon.gift_catalog import Gift
from eidolon.producer import ProducerProfile, day_part, now_prompt
from eidolon.store import ConversationEvent

SHANGHAI = ZoneInfo("Asia/Shanghai")
CAKE = Gift(id="cake", name="蛋糕", category="food", rarity="common")


def at(hour: int, minute: int = 0, *, days_ago: int = 0, now: datetime | None = None) -> datetime:
    """今天（或 N 天前）那个钟点，在上海。"""
    base = (now or datetime(2026, 10, 24, 9, 0, tzinfo=SHANGHAI)).astimezone(SHANGHAI)
    day = (base - timedelta(days=days_ago)).replace(hour=hour, minute=minute, second=0, microsecond=0)
    return day


def given(*, created: datetime, liked: bool = True) -> ConversationEvent:
    return ConversationEvent(
        id=1,
        kind="gift",
        created_at=created.astimezone(UTC).isoformat(),
        gift_id="cake",
        liked=liked,
    )


def told(created: datetime, now: datetime) -> str:
    return _narration(given(created=created), {"cake": CAKE}, "Asia/Shanghai", now)


def test_a_gift_from_last_night_is_told_as_last_night():
    """今晚九点送的，第二天早上再说起，不能只说「昨天」——她会当成昨晚刚发生。"""
    now = datetime(2026, 10, 24, 9, 0, tzinfo=SHANGHAI)
    assert told(at(21, 14, days_ago=1, now=now), now) == "（昨晚 21:14，制作人送给你一份蛋糕。这是你喜欢的东西。）"


def test_a_gift_from_yesterday_morning_is_told_as_yesterday():
    now = datetime(2026, 10, 24, 9, 0, tzinfo=SHANGHAI)
    assert told(at(9, 30, days_ago=1, now=now), now).startswith("（昨天 09:30，")


def test_a_gift_three_hours_ago_is_still_just_given():
    """三小时以内不说时间：本来就新鲜，缀一句反而啰嗦。"""
    now = datetime(2026, 10, 24, 15, 0, tzinfo=SHANGHAI)
    assert told(at(12, 30, now=now), now) == "（制作人送给你一份蛋糕。这是你喜欢的东西。）"


def test_two_days_and_a_week_ago():
    now = datetime(2026, 10, 24, 9, 0, tzinfo=SHANGHAI)
    assert told(at(20, 0, days_ago=2, now=now), now).startswith("（前天 20:00，")
    assert told(at(20, 0, days_ago=4, now=now), now).startswith("（4 天前，")


def test_older_than_a_week():
    """一周以上：同一个月的说「这个月几号」，跨了月就说月份。"""
    now = datetime(2026, 10, 24, 9, 0, tzinfo=SHANGHAI)
    assert told(at(20, 0, days_ago=20, now=now), now).startswith("（这个月 4 日 20:00，")
    last_month = at(20, 0, days_ago=40, now=now)
    assert told(last_month, now).startswith(f"（{last_month.month} 月 {last_month.day} 日 20:00，")


@pytest.mark.parametrize(
    ("hour", "part"),
    [(3, "深夜"), (6, "清晨"), (9, "上午"), (12, "中午"), (15, "下午"), (18, "傍晚"), (21, "晚上"), (23, "深夜")],
)
def test_which_part_of_the_day_it_is(hour: int, part: str):
    assert day_part(datetime(2026, 10, 24, hour, 0, tzinfo=SHANGHAI)) == part


def test_now_prompt_says_the_part_of_the_day_and_how_to_read_times():
    """只给「14:05」她照样能把白天当晚上；也告诉她历史里的时间是过去的事。"""
    profile = ProducerProfile(form_of_address="producer", gender="male", timezone=None, birthday=None)
    prompt = now_prompt(profile, datetime(2026, 10, 24, 14, 5, tzinfo=SHANGHAI), "Asia/Shanghai", "typing")
    assert "14:05，下午" in prompt
    assert "别当成刚刚" in prompt
