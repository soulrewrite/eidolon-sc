"""她们关注社区（fork，PLAN-20261027-daily-and-news 第 5 步）。

偶像会看官方账号上的消息，然后主动找制作人聊一句。这条搭话走搭话那条通道
（`reach_outs.say_about`），所以出现在对话列表里、可以回。

第一版只接了**能稳抓的源**：Lantis 的 CD 情报（`shinycolors.lantis.jp/releaseinfo/`，
服务器渲染，带发售日和完整碟名）。官方门户的 NEWS 页是纯客户端渲染，curl 只有壳，
要等第 6 步的无头浏览器一起做。

节奏按 Master 定的：**午休一条、晚上一条，两条不重复**；本企划（283 / SC）的消息权重 ×5，
系列其他事务所 ×1；同一条 24 小时内不再推；`community_news` 表按 url 哈希去重。
"""

from __future__ import annotations

import hashlib
import html as html_module
import logging
import re
import sqlite3
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from eidolon.clock import Clock
from eidolon.database import connect
from eidolon.store import Store

log = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS community_news (
    url_hash TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    published TEXT,
    weight INTEGER NOT NULL,
    fetched_at TEXT NOT NULL,
    pushed_at TEXT
);
CREATE INDEX IF NOT EXISTS community_news_by_pushed ON community_news(pushed_at);
CREATE TABLE IF NOT EXISTS community_news_image (
    url_hash TEXT PRIMARY KEY,
    media_type TEXT NOT NULL,
    bytes BLOB NOT NULL
);
"""

LUNCH = (time(12, 0), time(13, 30))
EVENING = (time(19, 0), time(21, 0))
"""两个推送窗口（用户时区）：午休一条、晚上一条。"""

SC_WEIGHT = 5
OTHER_WEIGHT = 1
"""本企划的消息优先：283 / SHINY COLORS 的 ×5，系列其他事务所 ×1。"""

SC_MARKS = ("SHINY COLORS", "シャイニーカラーズ", "283", "シャニマス", "閃耀色彩", "闪耀色彩")

LANTIS_URL = "https://shinycolors.lantis.jp/releaseinfo/"
_ITEM = re.compile(
    r'href="https://shinycolors\.lantis\.jp/releaseinfo/([a-z0-9_-]+)/"'
    r'.*?data-text="([^"]+)"',
    re.S,
)
_DATE = re.compile(r"(20\d{2})\.(\d{2})\.(\d{2})")
_OG_IMAGE = re.compile(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', re.S)


@dataclass(frozen=True)
class Candidate:
    """一条可能推给她的消息。"""

    url: str
    title: str
    source: str
    published: date | None
    weight: int


def parse_lantis(page: str) -> list[Candidate]:
    """Lantis 的 CD 情报页：一张碟一条，标题在分享按钮的 `data-text` 里。

    日期按**条目自己的那一块**找：页面上十几张碟，取邻近文本会把上一张的日期算到下一张头上。
    """
    out: list[Candidate] = []
    blocks = page.split('class="release_box')[1:] or [page]
    for block in blocks:
        pair = _ITEM.search(block)
        if pair is None:
            continue
        slug, raw = pair.group(1), pair.group(2)
        title = html_module.unescape(raw).strip()
        if not title:
            continue
        found = _DATE.search(block)
        published = (
            date(int(found.group(1)), int(found.group(2)), int(found.group(3)))
            if found
            else None
        )
        weight = SC_WEIGHT if any(mark in title for mark in SC_MARKS) else OTHER_WEIGHT
        out.append(
            Candidate(
                url=f"https://shinycolors.lantis.jp/releaseinfo/{slug}/",
                title=title,
                source="lantis",
                published=published,
                weight=weight,
            )
        )
    return out


def _hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]


def _in_window(now: datetime, zone: ZoneInfo) -> bool:
    here = now.astimezone(zone).time()
    return LUNCH[0] <= here < LUNCH[1] or EVENING[0] <= here < EVENING[1]


class CommunityNews:
    """抓官方消息、挑一条，让她去找他说。"""

    def __init__(self, path: Path, store: Store, clock: Clock) -> None:
        self._store = store
        self._clock = clock
        self._lock = threading.Lock()
        self._db = connect(path)
        self._db.row_factory = sqlite3.Row
        with self._lock, self._db:
            self._db.executescript(_SCHEMA)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(20, connect=8),
            headers={"User-Agent": "Mozilla/5.0 (compatible; eidolon-sc community news)"},
            follow_redirects=True,
        )

    def close(self) -> None:
        with self._lock:
            self._db.close()

    async def aclose(self) -> None:
        await self._client.aclose()

    # —— 抓 ——

    async def fetch(self) -> list[Candidate]:
        found: list[Candidate] = []
        for url, parser in ((LANTIS_URL, parse_lantis),):
            try:
                response = await self._client.get(url)
                response.raise_for_status()
            except httpx.HTTPError as error:
                log.warning("社区消息抓取失败（%s）：%r", url, error)
                continue
            found.extend(parser(response.text))
        self._remember(found)
        return found

    def _remember(self, found: Sequence[Candidate]) -> None:
        stamp = self._clock().isoformat()
        with self._lock, self._db:
            for item in found:
                self._db.execute(
                    "INSERT OR IGNORE INTO community_news"
                    " (url_hash, source, title, url, published, weight, fetched_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        _hash(item.url),
                        item.source,
                        item.title,
                        item.url,
                        item.published.isoformat() if item.published else None,
                        item.weight,
                        stamp,
                    ),
                )

    async def image_of(self, candidate: Candidate) -> str | None:
        """这条消息的官方图（`og:image`），存进库里，返回取图用的键；抓不到就是 None。

        比截网页干净，也不用在镜像里装浏览器——图本来就是官方那张。
        """
        key = _hash(candidate.url)
        with self._lock:
            row = self._db.execute(
                "SELECT 1 FROM community_news_image WHERE url_hash = ?", (key,)
            ).fetchone()
        if row is not None:
            return key
        try:
            page = await self._client.get(candidate.url)
            page.raise_for_status()
        except httpx.HTTPError as error:
            log.warning("取消息页失败（%s）：%r", candidate.url, error)
            return None
        found = _OG_IMAGE.search(page.text)
        if found is None:
            return None
        image_url = found.group(1)
        try:
            picture = await self._client.get(image_url)
            picture.raise_for_status()
        except httpx.HTTPError as error:
            log.warning("取消息图失败（%s）：%r", image_url, error)
            return None
        media_type = picture.headers.get("content-type", "image/jpeg").split(";")[0]
        with self._lock, self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO community_news_image (url_hash, media_type, bytes)"
                " VALUES (?, ?, ?)",
                (key, media_type, picture.content),
            )
        return key

    def picture(self, key: str) -> tuple[bytes, str] | None:
        """取回存着的图：字节和类型。"""
        with self._lock:
            row = self._db.execute(
                "SELECT media_type, bytes FROM community_news_image WHERE url_hash = ?", (key,)
            ).fetchone()
        if row is None:
            return None
        return bytes(row["bytes"]), str(row["media_type"])

    # —— 挑 ——

    def next_to_push(self, since: datetime | None = None) -> Candidate | None:
        """还没推过的里面挑一条：权重高的先，同权重新的先；`since` 之后推过的不算。"""
        query = (
            "SELECT * FROM community_news WHERE pushed_at IS NULL"
            " ORDER BY weight DESC, published IS NULL, published DESC, fetched_at DESC LIMIT 1"
        )
        with self._lock:
            row = self._db.execute(query).fetchone()
        if row is None:
            return None
        if since is not None and row["published"]:
            published = date.fromisoformat(row["published"])
            if published < since.date():
                return None
        return Candidate(
            url=row["url"],
            title=row["title"],
            source=row["source"],
            published=date.fromisoformat(row["published"]) if row["published"] else None,
            weight=row["weight"],
        )

    def mark_pushed(self, candidate: Candidate) -> None:
        with self._lock, self._db:
            self._db.execute(
                "UPDATE community_news SET pushed_at = ? WHERE url_hash = ?",
                (self._clock().isoformat(), _hash(candidate.url)),
            )

    def pushed_today(self, timezone: str) -> int:
        day = self._clock().astimezone(ZoneInfo(timezone)).date().isoformat()
        with self._lock:
            row = self._db.execute(
                "SELECT count(*) FROM community_news WHERE pushed_at LIKE ?",
                (f"{day}%",),
            ).fetchone()
        return int(row[0])

    # —— 推 ——

    def window_now(self, timezone: str) -> bool:
        return _in_window(self._clock(), ZoneInfo(timezone))

    async def push_one(self, reach_outs, timezone: str, since: datetime | None = None) -> bool:
        """在窗口里就推一条：抓→挑→让她说→记下来。返回有没有推。"""
        if not self.window_now(timezone):
            return False
        if self.pushed_today(timezone) >= 2:
            return False
        await self.fetch()
        candidate = self.next_to_push(since)
        if candidate is None:
            return False
        conversation = await _most_recent(self._store, self._clock())
        if conversation is None:
            return False
        image = await self.image_of(candidate)
        said = await reach_outs.say_about(conversation, _about(candidate), image=image)
        if not said:
            return False
        self.mark_pushed(candidate)
        log.info("推了一条社区消息：%s", candidate.title)
        return True


WATCH_TICK = timedelta(minutes=10)


async def keep_watching(news: CommunityNews, reach_outs, timezone_for) -> None:
    """每 10 分钟看一眼：在窗口里、今天还没推满两条，就推一条。"""
    import asyncio

    while True:
        await asyncio.sleep(WATCH_TICK.total_seconds())
        try:
            await news.push_one(reach_outs, timezone_for())
        except Exception:
            log.exception("推送社区消息失败")


def _about(candidate: Candidate) -> str:
    when = f"（{candidate.published.isoformat()}）" if candidate.published else ""
    return f"{candidate.title}{when}"


async def _most_recent(store: Store, now: datetime):
    import asyncio

    current = await asyncio.to_thread(store.current_conversations)
    return current[0].conversation if current else None
