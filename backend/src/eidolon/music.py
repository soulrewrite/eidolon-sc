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
from collections.abc import Sequence
from typing import Any

import httpx

from eidolon.world import World

log = logging.getLogger(__name__)

NETEASE_SEARCH = "https://music.163.com/api/cloudsearch/pc"
"""网易云的搜索接口：国内的源，直连即可，不用代理。

用 `cloudsearch/pc` 而不是 `search/get/web`——后者现在把 `result` 换成一串加密的十六进制
（`{"result":"35b174…"}`），`cloudsearch` 还是明文。两种都别指望永远不变，所以解析写成容错式。
"""

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
        """这首歌在网易云是哪一首：`{id, name, artists, album}`，没有就是 None。

        标题能对上一首已知的歌时，把她和一起唱的人当歌手提示——企划同名曲太多。
        """
        track = next((song for song in self._tracks if song.title == title), None)
        hints: tuple[str, ...] = ("シャイニーカラーズ",)
        if track is not None:
            hints += track.singers
            if track.special_unit:
                hints += (track.special_unit,)
        cached = self.cached(title)
        if title in self._found:
            return cached

        async with self._lock:
            if title in self._found:
                return self._found[title]
            ok, found = await self._ask(client, title, hints)
            # 只缓存「查到」和「确实没有」，网络故障不写进缓存
            if ok:
                self._found[title] = found
                await asyncio.to_thread(self._save_cache)
                return found
            return None

    async def _ask(
        self,
        client: httpx.AsyncClient,
        title: str,
        hints: Sequence[str] = ("シャイニーカラーズ",),
    ) -> tuple[bool, dict[str, Any] | None]:
        """问一次网易云：`(问成了吗, 查到的那首或 None)`。没问成时不要缓存。

        只用曲名搜：带上「シャイニーカラーズ」反而会把结果带偏（「虹になれ」那次返回了
        一首松尾和子的歌）。查到之后再按歌手名挑，见 `_best_match`。
        """
        try:
            response = await client.get(
                NETEASE_SEARCH,
                params={"s": title, "type": 1, "limit": 10, "offset": 0},
                headers=HEADERS,
                timeout=10.0,
            )
        except httpx.HTTPError as error:
            log.warning("网易云搜索失败（%s）：%r", title, error)
            return False, None
        if response.status_code != 200:
            log.warning("网易云搜索返回 HTTP %s（%s）", response.status_code, title)
            return False, None
        try:
            payload = response.json()
        except ValueError:
            return False, None
        result = payload.get("result")
        if not isinstance(result, dict):
            # 加密过的响应（`{"result":"<十六进制>"}`）：这次没问到，别缓存成「没有」
            log.warning("网易云给的是加密结果（%s），换接口或等它恢复", title)
            return False, None
        songs = result.get("songs") or []
        best = _best_match(title, songs, hints)
        if best is None:
            return True, None
        # 网易云这两处不总是同一个形状：`album` 有时是对象、有时就是碟名，
        # `artists` 里也可能是字符串。按 object 猜就会 500（线上踩过一次）。
        # cloudsearch 用 `ar` / `al`，老接口用 `artists` / `album`，两种都认
        album = best.get("al", best.get("album"))
        artists = best.get("ar", best.get("artists")) or []
        return True, {
            "id": str(best["id"]),
            "name": best.get("name"),
            "artists": [
                artist.get("name") if isinstance(artist, dict) else str(artist)
                for artist in artists
            ],
            "album": album.get("name") if isinstance(album, dict) else (album or None),
            "duration": best.get("dt", best.get("duration")),
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


def _artists_of(song: dict[str, Any]) -> list[str]:
    artists = song.get("ar", song.get("artists")) or []
    names: list[str] = []
    for artist in artists:
        name = artist.get("name") if isinstance(artist, dict) else artist
        if name:
            names.append(str(name))
    return names


def _best_match(
    title: str, songs: list[dict[str, Any]], hints: Sequence[str] = ("シャイニーカラーズ",)
) -> dict[str, Any] | None:
    """挑一条，按 `(歌手对得上吗, 曲名差多少, 名字长度)` 排。

    歌手优先是必要的：「Spread the Wings!!」在网易云上还有 EXILE 的版本，
    只按曲名比会挑到别人。歌手只是加分项、不是门槛——翻唱、限定组合都可能有别的名义。
    """
    wanted = _normalise(title)
    if not wanted:
        return None
    scored: list[tuple[int, int, int, dict[str, Any]]] = []
    for song in songs:
        name = _normalise(str(song.get("name") or ""))
        if not name:
            continue
        if name == wanted:
            rank = 0
        elif wanted in name or name in wanted:
            rank = 1
        else:
            continue
        distances = [_artist_distance(_artists_of(song), hint) for hint in hints]
        by_artist = min(distances) if distances else 99
        scored.append((by_artist, rank, abs(len(name) - len(wanted)), song))
    if not scored:
        return None
    scored.sort(key=lambda item: item[:3])
    return scored[0][3]


def _artist_distance(artists: Sequence[str], hint: str) -> int:
    """歌手名里有没有 `hint`：命中 0，没命中 1。"""
    return 0 if any(hint in artist for artist in artists) else 1
