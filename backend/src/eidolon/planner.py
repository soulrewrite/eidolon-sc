"""她们的日程由模型来排（fork，PLAN-20261027-daily-and-news 的 1A）。

规则版（`schedules.compose`）排出来的日子太整齐，第二天就看得出是模板。这里让聊天模型
照人设写：三到六段、留白、最多两个临时变数，那天有她的 live 就排进去。

排好的还是进 `schedules` 表（`written_by = 'model'`），调用方一行都不用改；
模型答得不成样子、服务挂了，就留着规则版那份——`ensure()` 已经排好了，不会空着。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from eidolon.characters import Character
from eidolon.clock import Clock
from eidolon.live_config import LiveConfig
from eidolon.engine import ConversationEngine
from eidolon.producer import effective_timezone
from eidolon.schedules import Schedules
from eidolon.store import Store
from eidolon.world import World

log = logging.getLogger(__name__)

PLAN_TICK = timedelta(minutes=20)
"""多久看一次：哪位今天的日子还没让模型写。"""

ACTIVE = timedelta(days=7)
"""最近这么久聊过的才排——不再来往的人不用每天给她写安排。"""


async def keep_planning(
    store: Store,
    engine: ConversationEngine,
    config: LiveConfig,
    schedules: Schedules,
    clock: Clock,
    characters: Mapping[str, Character],
    world: World | None = None,
) -> None:
    """每 `PLAN_TICK` 给还没排的人让模型写一份今天的日子，直到被取消。"""
    while True:
        await asyncio.sleep(PLAN_TICK.total_seconds())
        try:
            await plan_today(store, engine, config, schedules, clock, characters, world)
        except Exception:
            log.exception("planning her day failed")


async def plan_today(
    store: Store,
    engine: ConversationEngine,
    config: LiveConfig,
    schedules: Schedules,
    clock: Clock,
    characters: Mapping[str, Character],
    world: World | None = None,
) -> int:
    """给今天还没有模型行程的人排一份，返回排了几位。"""
    now = clock()
    planned = 0
    for current in await asyncio.to_thread(store.current_conversations):
        conversation = current.conversation
        if current.ended or conversation.character_id not in characters:
            continue
        if current.last_contact is None or now - current.last_contact > ACTIVE:
            continue
        timezone = effective_timezone(store.get_profile(conversation.user_id), None)
        day = now.astimezone(ZoneInfo(timezone)).date()
        plan = schedules.plan(conversation.user_id, conversation.character_id, day)
        if plan is not None and plan.written_by == "model":
            continue
        if await plan_one(
            engine, config, schedules, characters, world,
            conversation.user_id, conversation.character_id, day,
        ):
            planned += 1
    return planned


async def plan_one(
    engine: ConversationEngine,
    config: LiveConfig,
    schedules: Schedules,
    characters: Mapping[str, Character],
    world: World | None,
    user_id: str,
    character_id: str,
    day: date,
) -> bool:
    """让模型给这一位写一天。写不出来就是 False，规则版那份留着。"""
    character = characters.get(character_id)
    routine = schedules.routine_text(character_id)
    if character is None or routine is None:
        return False
    note = _note_of(day, character, world)
    for _attempt in range(2):  # 清洗后不成样子就再写一次
        lease = config.lease()
        try:
            entries = await engine.schedule_for(
                character, routine, day, note, lease.keys.chat_llm
            )
        finally:
            lease.release()
        if entries and schedules.put_model_plan(user_id, character_id, day, entries):
            return True
    return False


def _note_of(day: date, character: Character, world: World | None) -> str:
    """今天有什么跟世界设定对得上的事：她的 live、碟的发售。"""
    notes: list[str] = []
    if world is not None:
        for live in world.lives:
            for live_day in live.days:
                if live_day.date == day and character.name in live_day.performers:
                    notes.append(f"今天有你的演出：{live.name}（{live_day.venue}），把它排进去。")
    return "\n".join(notes) if notes else "今天没有演出，是平常的一天。"
