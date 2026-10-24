"""歌曲与专辑（fork，FORK.md「歌曲」）。

她唱过的歌和出过的碟都在世界设定里（`world.json` 的 `songs` / `releases`，由 `eidolon world
sync` 从 Lantis、im@sparql 等资料站导入）。这里把它们按偶像拆开给前端，另外配一个「这首歌在
网易云是哪一首」的查找——前端只放外链播放器，音频始终在网易云那边，我们不碰。

查找结果缓存在 `MUSIC_CACHE_PATH`（默认 `/data/music-cache.json`）：同一个曲名只问一次，
网易云那边限流也不至于把页面卡住。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from eidolon.world import World

log = logging.getLogger(__name__)

NETEASE_SEARCH = "https://music.163.com/api/search/get/web"
"""网易云的搜索接口：国内的源，直连即可，不用代理。"""

# 网易云对没有 User-Agent、没有 Referer 的请求直接给空结果
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer": "https://music.163.com/",
    "Accept": "application/json",
}


def cache_path() -> Path:
    """查找结果的缓存文件，部署者可以用 `EIDOLON_MUSIC_CACHE` 换位置。"""
    return Path(os.environ.get("EIDOLON_MUSIC_CACHE", "/data/music-cache.json"))


@dataclass(frozen=True)
class Track:
    """一首歌：她在哪几张碟里唱过、和谁一起。"""

    id: str
    title: str
    singers: tuple[str, ...]
    releases: tuple[str, ...]
    special_unit: str | None = None

    def described(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "singers": list(self.singers),
            "releases": list(self.releases),
            "special_unit": self.special_unit,
        }


@dataclass(frozen=True)
class Album:
    """一张碟，带着曲目表。"""

    catalog: str
    title: str
    date: str
    tracks: tuple[str, ...]
    songs: tuple[str, ...]

    def described(self) -> dict[str, Any]:
        return {
            "catalog": self.catalog,
            "title": self.title,
            "date": self.date,
            "tracks": list(self.tracks),
            "songs": list(self.songs),
        }


class MusicLibrary:
    """世界设定里她唱过的歌，按偶像和碟两种切法。"""

    def __init__(self, world: World | None, path: Path | None = None) -> None:
        self._tracks: list[Track] = []
        self._albums: list[Album] = []
        self._by_singer: dict[str, list[Track]] = {}
        self._path = path if path is not None else cache_path()
        self._found: dict[str, dict[str, Any] | None] = {}
        self._lock = asyncio.Lock()
        self._load_cache()
        if world is None:
            return

        self._tracks = [
            Track(
                id=song.id,
                title=song.title,
                singers=tuple(song.singers),
                releases=tuple(song.releases),
                special_unit=song.special_unit,
            )
            for song in world.songs
        ]
        for track in self._tracks:
            for singer in track.singers:
                self._by_singer.setdefault(singer, []).append(track)
        self._albums = [
            Album(
                catalog=release.catalog,
                title=release.title,
                date=release.date.isoformat(),
                tracks=tuple(track.title for track in release.tracks),
                songs=tuple(track.song for track in release.tracks if track.song),
            )
            for release in sorted(world.releases, key=lambda r: r.date, reverse=True)
        ]
        if len(self._tracks) == 0:
            log.warning("世界设定里没有曲目，歌曲页会是空的")

    @property
    def is_empty(self) -> bool:
        return not self._tracks

    def songs(self, singer: str | None = None) -> list[Track]:
        """她唱过的歌：`singer` 是日文名（世界设定里就是这么写的），不传就是全部。"""
        if singer is None:
            return self._tracks
        return self._by_singer.get(singer, [])

    def singer_names(self) -> list[str]:
        """有歌的偶像，按世界设定里的顺序。"""
        return [name for name in self._by_singer]

    def albums(self) -> list[Album]:
        return self._albums

    def album(self, catalog: str) -> Album | None:
        return next((album for album in self._albums if album.catalog == catalog), None)

    def cached(self, title: str) -> dict[str, Any] | None:
        """已经查过的结果（查过但没有，记成 None，不重复问）。"""
        return self._found.get(title)

    async def lookup(self, client: httpx.AsyncClient, title: str) -> dict[str, Any] | None:
        """这首歌在网易云是哪一首：`{id, name, artists, album}`，没有就是 None。"""
        cached = self.cached(title)
        if title in self._found:
            return cached

        async with self._lock:
            if title in self._found:
                return self._found[title]
            found = await self._ask(client, title)
            # 只缓存「查到」和「确实没有」，网络故障不写进缓存
            if found is not False:
                self._found[title] = found
                await asyncio.to_thread(self._save_cache)
            return found if found is not False else None

    async def _ask(self, client: httpx.AsyncClient, title: str) -> dict[str, Any] | None | bool:
        """问一次网易云。返回 False 表示这次没问成（不要缓存）。"""
        keyword = f"{title} シャイニーカラーズ"
        try:
            response = await client.get(
                NETEASE_SEARCH,
                params={"s": keyword, "type": 1, "limit": 10, "offset": 0},
                headers=HEADERS,
                timeout=10.0,
            )
        except httpx.HTTPError as error:
            log.warning("网易云搜索失败（%s）：%r", title, error)
            return False
        if response.status_code != 200:
            log.warning("网易云搜索返回 HTTP %s（%s）", response.status_code, title)
            return False
        try:
            payload = response.json()
        except ValueError:
            return False
        songs = (payload.get("result") or {}).get("songs") or []
        best = _best_match(title, songs)
        if best is None:
            return None
        return {
            "id": str(best["id"]),
            "name": best.get("name"),
            "artists": [artist.get("name") for artist in best.get("artists") or []],
            "album": (best.get("album") or {}).get("name"),
            "duration": best.get("duration"),
        }

    def _load_cache(self) -> None:
        try:
            self._found = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self._found = {}

    def _save_cache(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._found, ensure_ascii=False, indent=0), encoding="utf-8"
            )
        except OSError as error:
            log.warning("歌曲缓存写不进去：%r", error)


def _normalise(text: str) -> str:
    """比曲名时把空白、标点抹平：`Spread the Wings!!` 与 `Spread the Wings` 算同一首。"""
    return "".join(ch for ch in text.lower() if ch.isalnum())


def _best_match(title: str, songs: list[dict[str, Any]]) -> dict[str, Any] | None:
    """挑一条：曲名相同的优先，其次是包含关系，都没有就算没有。"""
    wanted = _normalise(title)
    if not wanted:
        return None
    for song in songs:
        if _normalise(str(song.get("name") or "")) == wanted:
            return song
    for song in songs:
        name = _normalise(str(song.get("name") or ""))
        if name and (wanted in name or name in wanted):
            return song
    return None
