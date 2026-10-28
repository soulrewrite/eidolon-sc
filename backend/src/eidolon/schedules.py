"""她的一天：行程、作息和洗澡（fork，PLAN-20261027-daily-and-news）。

她有自己的安排：每天一份「大概在做什么」，加上几点睡、几点洗澡。对话、搭话和来信
都读这份安排，所以她答得出「现在在干嘛」，也不会下午三点说自己刚起床。

数据从 `characters/routines.toml`（作息与洗澡习惯）和 `world.json`（那天有没有 live）来，
按（用户, 角色, 日期）存进 `schedules` 表，每天过了 5 点重排一份。

第一版是**规则排的**：时间段 + 1–2 个小变数（临时加练、下雨改室内），live 日一定排
live。模型写的版本排在下一步（`PLAN-20261027-daily-and-news` 第 3 步的第二半），
两者共用这张表，换实现不影响调用方。
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import sqlite3
import threading
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from eidolon.characters import Character
from eidolon.clock import Clock
from eidolon.database import connect
from eidolon.world import World

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schedules (
    user_id TEXT NOT NULL,
    character_id TEXT NOT NULL,
    day TEXT NOT NULL,
    entries TEXT NOT NULL,
    sleep TEXT NOT NULL,
    bath_at TEXT NOT NULL,
    bath_until TEXT NOT NULL,
    wake TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    bath_told INTEGER NOT NULL DEFAULT 0,
    bathed_told INTEGER NOT NULL DEFAULT 0,
    written_by TEXT NOT NULL DEFAULT 'rules',
    PRIMARY KEY (user_id, character_id, day)
);
"""

REFRESH_HOUR = 5

BATHED_GRACE = timedelta(minutes=20)
"""洗完这么久之内，第一次说话还能说「刚洗完」。"""
"""过了这个点（用户时区）就当她换了新的一天。"""

VARIABLES = (
    "临时加练，比平时晚走一小时",
    "下雨，户外的安排改到室内",
    "被叫去帮忙，午休没歇成",
    "路上堵了一会儿，到得比预计晚",
    "有人送来慰问的点心，歇下来吃了",
    "器材出了小问题，折腾了一阵",
)

MORNING = ("练习", "课程", "事务所的碰头")
AFTERNOON = ("练习", "拍摄", "课", "和组合的人对台词")
EVENING = ("自由时间", "看剧本", "和朋友吃饭", "在事务所收尾")


@dataclass(frozen=True)
class Routine:
    """她在 `routines.toml` 里的作息：睡、起、洗澡。"""

    sleep_text: str
    bath: str
    habit: str
    session: time
    """几点睡（按作息文字里写的钟点推出来）。"""
    wake: time
    """几点起。"""
    bath_minutes: int
    """洗澡大概多少分钟。"""


@dataclass(frozen=True)
class Plan:
    """她某一天的样子。"""

    day: date
    entries: tuple[tuple[str, str], ...]
    """（时间段, 在做什么），例如（"09:00–12:00", "练习"）。"""
    live: str | None
    """那天有她出演的 live 时，场馆和演出名。"""
    sleep: time
    wake: time
    bath_at: time
    bath_until: time
    written_by: str = "rules"
    """`rules`（规则版兜底）还是 `model`（模型写的）。"""


def _clock_in(clause: str, marker: str) -> time | None:
    """在**同一个分句**里找「N 点(半) …标记」的钟点。

    以前在整句里搜，会跨过分号：「0 点前后睡、6 点前后起」被读成「0 点起」，
    于是她的起床时间变成 00:00，睡觉窗口整天都是。
    """
    # 时间要紧挨着标记词：「0 点前后睡、6 点前后起」不能把 0 读成起床时间
    found = re.search(rf"(\d{{1,2}})\s*点(半)?[^0-9]{{0,6}}?{marker}", clause)
    if found is None:
        return None
    hour = int(found.group(1))
    if not 0 <= hour <= 23:
        return None
    return time(hour, 30 if found.group(2) else 0)


def _sleep_and_wake(text: str) -> tuple[time, time]:
    """从作息里读「几点睡」「几点起」；读不出来或明显不对就用 23:00 / 7:00。"""
    clauses = [part for part in re.split(r"[；;。]", text) if part.strip()]
    session: time | None = None
    wake: time | None = None
    for clause in clauses:
        if session is None and "睡" in clause:
            session = _clock_in(clause, "睡")
        if wake is None and "起" in clause:
            wake = _clock_in(clause, "起")
    if session is None or not (session.hour >= 19 or session.hour <= 4):
        session = time(23, 0)
    if wake is None or not (4 <= wake.hour <= 11):
        wake = time(7, 0)
    return session, wake


def read_routines(path: Path) -> dict[str, Routine]:
    """`routines.toml` 里每位一行的作息；缺字段的跳过（部署者写错不该让服务起不来）。"""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    out: dict[str, Routine] = {}
    for character_id, entry in data.items():
        if not isinstance(entry, dict):
            continue
        sleep_text = str(entry.get("sleep", ""))
        bath = str(entry.get("bath", "泡澡"))
        session, wake = _sleep_and_wake(sleep_text)
        out[character_id] = Routine(
            sleep_text=sleep_text,
            bath=bath,
            habit=str(entry.get("bath_habit", "")),
            session=session,
            wake=wake,
            bath_minutes=35 if bath == "淋浴" else 45,
        )
    return out


def _seed(user_id: str, character_id: str, day: date) -> int:
    """同一（用户, 角色, 日期）永远同一个种子。

    不能用内置 `hash()`：字符串哈希每个进程加盐，换个进程同一天就排得不一样，
    测试也会时过时不过。
    """
    digest = hashlib.sha256(f"{user_id}|{character_id}|{day.isoformat()}".encode()).digest()
    return int.from_bytes(digest[:4], "big") % (2**31)


def _live_of(world: World | None, character: Character, day: date) -> str | None:
    """那天有她出演的 live 就是场馆和演出名。"""
    if world is None:
        return None
    for live in world.lives:
        for live_day in live.days:
            if live_day.date != day:
                continue
            if character.name in live_day.performers:
                return f"{live.name}（{live_day.venue}）"
    return None


def compose(
    routine: Routine, character: Character, day: date, user_id: str, world: World | None
) -> Plan:
    """排她这一天的安排：3–6 段、留空白、1–2 个小变数，live 日一定排 live。"""
    rng = random.Random(_seed(user_id, character.id, day))
    live = _live_of(world, character, day)

    entries: list[tuple[str, str]] = []
    if live is not None:
        entries.append(("上午", "彩排"))
        entries.append(("下午–晚上", f"{live}"))
        entries.append(("夜里", "回到住处，筋疲力尽"))
    else:
        entries.append((f"{routine.wake:%H:%M}–12:00", rng.choice(MORNING)))
        entries.append(("13:00–17:00", rng.choice(AFTERNOON)))
        entries.append(("18:00–21:00", rng.choice(EVENING)))

    variables = rng.choice([0, 1, 1, 2])
    for _ in range(variables):
        candidate = rng.choice(VARIABLES)
        if all(candidate not in what for _, what in entries):
            entries.append(("（临时）", candidate))

    session = _shift(routine.session, rng.choice([-20, 0, 0, 20]))
    wake = _shift(routine.wake, rng.choice([-10, 0, 0, 15]))
    bath_at = _shift(session, -(routine.bath_minutes + rng.choice([20, 30, 40])))
    bath_until = _shift(bath_at, routine.bath_minutes)

    entries.sort(key=lambda item: item[0])
    return Plan(
        day=day,
        entries=tuple(entries),
        live=live,
        sleep=session,
        wake=wake,
        bath_at=bath_at,
        bath_until=bath_until,
    )


def _shift(clock: time, minutes: int) -> time:
    anchor = datetime.combine(date(2000, 1, 1), clock) + timedelta(minutes=minutes)
    return anchor.time()


class Schedules:
    """每位（用户, 角色）每天的安排，存在 `path` 这张库上。"""

    def __init__(
        self,
        path: Path,
        characters: Mapping[str, Character],
        clock: Clock,
        world: World | None = None,
        routines: Path | None = None,
    ) -> None:
        self._characters = characters
        self._clock = clock
        self._world = world
        self._routines = read_routines(routines) if routines is not None else {}
        self._lock = threading.Lock()
        self._db = connect(path)
        self._db.row_factory = sqlite3.Row
        with self._lock, self._db:
            self._db.executescript(_SCHEMA)
            columns = {row[1] for row in self._db.execute("PRAGMA table_info(schedules)")}
            if "bath_told" not in columns:  # 老库补列
                self._db.execute(
                    "ALTER TABLE schedules ADD COLUMN bath_told INTEGER NOT NULL DEFAULT 0"
                )
            if "bathed_told" not in columns:
                self._db.execute(
                    "ALTER TABLE schedules ADD COLUMN bathed_told INTEGER NOT NULL DEFAULT 0"
                )
            if "written_by" not in columns:
                self._db.execute(
                    "ALTER TABLE schedules ADD COLUMN written_by TEXT NOT NULL DEFAULT 'rules'"
                )

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # —— 读 ——

    def plan(self, user_id: str, character_id: str, day: date) -> Plan | None:
        """那天排过的安排；没排过就是 None。"""
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM schedules WHERE user_id = ? AND character_id = ? AND day = ?",
                (user_id, character_id, day.isoformat()),
            ).fetchone()
        if row is None:
            return None
        return Plan(
            day=date.fromisoformat(row["day"]),
            entries=tuple(tuple(item) for item in json.loads(row["entries"])),
            live=None,
            sleep=time.fromisoformat(row["sleep"]),
            wake=time.fromisoformat(row["wake"]),
            bath_at=time.fromisoformat(row["bath_at"]),
            bath_until=time.fromisoformat(row["bath_until"]),
            written_by=row["written_by"] if "written_by" in row.keys() else "rules",
        )

    def ensure(self, user_id: str, character_id: str, timezone: str) -> Plan | None:
        """今天还没排就排一份；角色不在名单里、或者没有作息数据时返回 None。"""
        character = self._characters.get(character_id)
        if character is None:
            return None
        routine = self._routines.get(character_id)
        if routine is None:
            return None
        day = self._clock().astimezone(ZoneInfo(timezone)).date()
        existing = self.plan(user_id, character_id, day)
        if existing is not None:
            return existing
        planned = compose(routine, character, day, user_id, self._world)
        with self._lock, self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO schedules"
                " (user_id, character_id, day, entries, sleep, bath_at, bath_until, wake, generated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    user_id,
                    character_id,
                    planned.day.isoformat(),
                    json.dumps(planned.entries, ensure_ascii=False),
                    planned.sleep.isoformat(),
                    planned.bath_at.isoformat(),
                    planned.bath_until.isoformat(),
                    planned.wake.isoformat(),
                    self._clock().isoformat(),
                ),
            )
        return planned

    def routine_text(self, character_id: str) -> str | None:
        """给模型的作息原文（她几点睡、几点起、洗澡的小习惯）。"""
        routine = self._routines.get(character_id)
        if routine is None:
            return None
        return f"{routine.sleep_text} {'泡澡' if routine.bath == '泡澡' else '淋浴'}。{routine.habit}"

    BATH_WORDS = ("泡澡", "洗澡", "泡汤", "お風呂", "シャワー", "浴缸")
    """模型不该写的：洗澡另有安排（`bath_at`–`bath_until`），写进来会变成两套真相。"""

    def sanitize(
        self, character_id: str, entries: Sequence[tuple[str, str]], sleep: time, wake: time
    ) -> list[tuple[str, str]] | None:
        """把模型写的行程收拾干净：去掉洗澡、不点别人的名、不越过睡觉时间。

        剩下的不足三段就整份不用（退回规则版）。
        """
        out: list[tuple[str, str]] = []
        for when, what in entries:
            if any(word in what for word in self.BATH_WORDS):
                continue
            # 全名和名都要挡：模型常写「円香」而不是「樋口円香」
            for other_id, other in self._characters.items():
                if other_id == character_id:
                    continue
                for token in (other.name, other.name[2:]):
                    if len(token) >= 2 and token in what:
                        what = what.replace(token, "同组合的人")
            start_end = re.match(r"(\d{2}):(\d{2})[–-](\d{2}):(\d{2})", when)
            if start_end is None:
                continue
            # 一天的时间轴从起床算起：跨过午夜的时间加 24 小时，这样「22:30–00:20」
            # 和「00:10 睡」才比得了大小（以前按 sleep < wake 判，凌晨睡的反而漏了）。
            wake_min = wake.hour * 60 + wake.minute
            sleep_min = sleep.hour * 60 + sleep.minute
            if sleep_min <= wake_min:
                sleep_min += 24 * 60
            start_min = int(start_end.group(1)) * 60 + int(start_end.group(2))
            end_min = int(start_end.group(3)) * 60 + int(start_end.group(4))
            if start_min < wake_min:
                start_min += 24 * 60
            if end_min < start_min:
                end_min += 24 * 60
            if start_min >= sleep_min:
                continue
            end_min = min(end_min, sleep_min)
            if end_min <= start_min:
                continue
            out.append((
                f"{start_min % 1440 // 60:02d}:{start_min % 60:02d}"
                f"–{end_min % 1440 // 60:02d}:{end_min % 60:02d}",
                what.strip(),
            ))
        return out if len(out) >= 3 else None

    def put_model_plan(
        self, user_id: str, character_id: str, day: date, entries: Sequence[tuple[str, str]]
    ) -> Plan | None:
        """把模型写的行程写进表里；作息（睡、起、洗澡）仍按 routines 的来。

        模型只管「几点到几点在做什么」，睡觉和洗澡这种会被别的功能读到的东西不交给它。
        """
        character = self._characters.get(character_id)
        routine = self._routines.get(character_id)
        if character is None or routine is None:
            return None
        base = self.plan(user_id, character_id, day) or self.ensure(user_id, character_id, "Asia/Tokyo")
        if base is None:
            return None
        cleaned = self.sanitize(character_id, entries, base.sleep, base.wake)
        if cleaned is None:
            return None
        entries = cleaned
        plan = Plan(
            day=day,
            entries=tuple(entries),
            live=base.live,
            sleep=base.sleep,
            wake=base.wake,
            bath_at=base.bath_at,
            bath_until=base.bath_until,
            written_by="model",
        )
        with self._lock, self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO schedules"
                " (user_id, character_id, day, entries, sleep, bath_at, bath_until, wake,"
                "  generated_at, bath_told, written_by)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'model')",
                (
                    user_id, character_id, day.isoformat(),
                    json.dumps(plan.entries, ensure_ascii=False),
                    plan.sleep.isoformat(), plan.bath_at.isoformat(),
                    plan.bath_until.isoformat(), plan.wake.isoformat(),
                    self._clock().isoformat(),
                ),
            )
        return plan

    def forget(self, user_id: str, character_id: str, day: date) -> None:
        """把那天排好的丢掉，下次 `ensure` 重排一份（开发接口用）。"""
        with self._lock, self._db:
            self._db.execute(
                "DELETE FROM schedules WHERE user_id = ? AND character_id = ? AND day = ?",
                (user_id, character_id, day.isoformat()),
            )

    def _without_now(self, plan: Plan, clock: time) -> tuple[tuple[str, str], ...]:
        """去掉覆盖当前这一刻的那一段：洗澡时别让她念出「21:00 洗澡」。"""
        kept: list[tuple[str, str]] = []
        for when, doing in plan.entries:
            found = re.match(r"(\d{1,2}):(\d{2})[–-](\d{1,2}):(\d{2})", when)
            if found is not None:
                start = time(int(found.group(1)), int(found.group(2)))
                end = time(int(found.group(3)), int(found.group(4)))
                if _between(clock, start, end):
                    continue
            kept.append((when, doing))
        return tuple(kept) if kept else plan.entries

    def just_out_of_bath(self, user_id: str, character_id: str, timezone: str) -> bool:
        """是不是刚洗完（洗完那一刻起 20 分钟内，且这一段还没说过）。"""
        plan = self.ensure(user_id, character_id, timezone)
        if plan is None:
            return False
        here = self._clock().astimezone(ZoneInfo(timezone)).time()
        until = (datetime.combine(plan.day, plan.bath_until) + BATHED_GRACE).time()
        if not _between(here, plan.bath_until, until):
            return False
        with self._lock, self._db:
            row = self._db.execute(
                "SELECT bathed_told FROM schedules"
                " WHERE user_id = ? AND character_id = ? AND day = ?",
                (user_id, character_id, plan.day.isoformat()),
            ).fetchone()
            if row is None or row["bathed_told"]:
                return False
            self._db.execute(
                "UPDATE schedules SET bathed_told = 1"
                " WHERE user_id = ? AND character_id = ? AND day = ?",
                (user_id, character_id, plan.day.isoformat()),
            )
        return True

    def now(self, user_id: str, character_id: str, timezone: str) -> tuple[str, str]:
        """她现在在干嘛：("sleeping" | "bathing" | "working" | "free", 一句人话)。"""
        plan = self.ensure(user_id, character_id, timezone)
        if plan is None:
            return "free", ""
        local = self._clock().astimezone(ZoneInfo(timezone))
        here = local.time()
        if _between(here, plan.sleep, plan.wake):
            return "sleeping", f"在睡觉（{plan.sleep:%H:%M} 睡的，{plan.wake:%H:%M} 起）"
        if _between(here, plan.bath_at, plan.bath_until):
            return "bathing", "在洗澡"
        if _between(here, plan.wake, plan.sleep):
            return "working", _what_now(plan, here)
        return "free", ""

    def fresh_from_bath(self, user_id: str, character_id: str, timezone: str) -> bool:
        """她是不是**刚刚**洗完（这一段洗澡里还没说过）。

        洗完的「刚洗完」只能说一次：同一段洗澡里再说话，她就是正常状态了。以前每回合都说，
        一夜之间能说三四遍「我刚洗完」，像失忆。
        """
        plan = self.ensure(user_id, character_id, timezone)
        if plan is None:
            return False
        here = self._clock().astimezone(ZoneInfo(timezone)).time()
        if not _between(here, plan.bath_at, plan.bath_until):
            return False
        with self._lock, self._db:
            row = self._db.execute(
                "SELECT bath_told FROM schedules WHERE user_id = ? AND character_id = ? AND day = ?",
                (user_id, character_id, plan.day.isoformat()),
            ).fetchone()
            if row is None or row["bath_told"]:
                return False
            self._db.execute(
                "UPDATE schedules SET bath_told = 1"
                " WHERE user_id = ? AND character_id = ? AND day = ?",
                (user_id, character_id, plan.day.isoformat()),
            )
        return True

    def prompt_lines(self, user_id: str, character_id: str, timezone: str) -> list[str]:
        """塞进提示词的那几行：现在在干嘛、今天剩下什么、最近三天的大事。"""
        plan = self.ensure(user_id, character_id, timezone)
        if plan is None:
            return []
        state, what = self.now(user_id, character_id, timezone)
        if state == "bathing":
            # 洗澡这件事只由 engine 的洗澡规则说一次。这里再写「在洗澡」，两套说法会打架：
            # 模型一会儿说刚洗完、一会儿说还在洗（2026-10-28 实测）。
            lines = ["# 她的这一天", "现在的状态：手机不在手边，过一会儿才看得到消息。"]
            shown = self._without_now(plan, self._clock().astimezone(ZoneInfo(timezone)).time())
        else:
            lines = ["# 她的这一天", f"现在的状态：{what or state}。"]
            shown = plan.entries
        lines.append("今天的安排：" + "；".join(f"{when} {doing}" for when, doing in shown) + "。")
        if plan.live is not None:
            lines.append(f"今天是她的演出日：{plan.live}。")
        lines.append("被问到在做什么时，照这个说，允许有出入，不必逐条背。")
        return lines


def _between(clock: time, start: time, end: time) -> bool:
    if start <= end:
        return start <= clock < end
    return clock >= start or clock < end


def _what_now(plan: Plan, clock: time) -> str:
    for when, doing in plan.entries:
        found = re.match(r"(\d{1,2}):(\d{2})[–-](\d{1,2}):(\d{2})", when)
        if found is None:
            continue
        start = time(int(found.group(1)), int(found.group(2)))
        end = time(int(found.group(3)), int(found.group(4)))
        if _between(clock, start, end):
            return doing
    return "空档，没什么安排"
