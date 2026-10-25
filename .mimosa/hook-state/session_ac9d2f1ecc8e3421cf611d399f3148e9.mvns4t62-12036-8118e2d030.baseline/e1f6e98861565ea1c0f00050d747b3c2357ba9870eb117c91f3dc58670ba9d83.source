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
import re
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


UNIT_READINGS = {
    "illumination STARS": "イルミネーションスターズ",
    "L'Antica": "アンティーカ",
    "放課後クライマックスガールズ": "放課後クライマックスガールズ",
    "ALSTROEMERIA": "アルストロメリア",
    "Straylight": "ストレイライト",
    "noctchill": "ノクチル",
    "SHHis": "シーズ",
    "CoMETIK": "コメティック",
}
"""组合名在网易云上是片假名写的（世界设定里是拉丁名），挑歌手时两种都要认。"""


DJ_PROGRAMS_ENV = "EIDOLON_MUSIC_DJ_PROGRAMS"


def dj_programs_path() -> Path:
    """电台节目清单：一行一个网易云节目 id（`music.163.com/#/dj?id=…` 里那串数字）。

    没单独上架的歌常常只在这些节目里，比如「With you（大崎甘奈Ver.）」。
    文件不存在就当没有，功能自然关掉。
    """
    return Path(os.environ.get(DJ_PROGRAMS_ENV, "/data/music-dj.txt"))


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
        self._cv_of: dict[str, str] = {}
        self._unit_of: dict[str, str] = {}
        self._path = path if path is not None else cache_path()
        self._found: dict[str, dict[str, Any] | None] = {}
        self._programs: list[str] = []
        self._lock = asyncio.Lock()
        self._load_cache()
        self._programs = _read_program_ids()
        if world is None:
            return

        # 网易云上很多独唱版的歌手写的是声优本人（FELICE（櫻木真乃Ver.）的歌手是関根瞳），
        # 世界设定里有 CV 名，拿来一起当歌手提示
        self._cv_of = {idol.name: idol.cv for idol in world.idols if idol.cv}
        self._unit_of = {idol.name: idol.unit for idol in world.idols if idol.unit}
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

    def alternatives(self, title: str) -> list[str]:
        """同一首在别的碟上的网易云 id：这张没版权时换下一张。"""
        hit = self._found.get(title)
        if not isinstance(hit, dict):
            return []
        return [str(other) for other in hit.get("alternatives") or [] if other]

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
        # 组合名也要认：网易云上这些歌的歌手常常写成「イルミネーションスターズ」这种；
        # 独唱版则挂在声优名下（関根瞳），所以 CV 也一起当提示
        hints: tuple[str, ...] = ("シャイニーカラーズ", *UNIT_READINGS.values())
        terms: list[str] = []
        if track is not None:
            hints += track.singers
            hints += tuple(self._cv_of[name] for name in track.singers if name in self._cv_of)
            if track.special_unit:
                hints += (track.special_unit,)
            if track.singers:
                first = track.singers[0]
                if first in self._cv_of:
                    terms.append(self._cv_of[first])
                unit = self._unit_of.get(first)
                if unit:
                    terms.append(UNIT_READINGS.get(unit, unit))
                terms.append(first)
        cached = self.cached(title)
        if title in self._found:
            return cached

        async with self._lock:
            if title in self._found:
                return self._found[title]
            ok, found = await self._ask(client, title, hints, terms)
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
        terms: Sequence[str] = (),
    ) -> tuple[bool, dict[str, Any] | None]:
        """问一次网易云：`(问成了吗, 查到的那首或 None)`。没问成时不要缓存。

        只用曲名搜：带上「シャイニーカラーズ」反而会把结果带偏（「虹になれ」那次返回了
        一首松尾和子的歌）。查到之后再按歌手名挑，见 `_best_match`。
        """
        # 一条候选都没搜到，多半是被网易云限流了（同一关键词连着问会被掐），
        # 这种不写进缓存——下次再问一次，别把「限流」记成「没有这首」。
        saw_any = False
        must: tuple[str, ...] = ()
        named = _version_singer(title)
        if named:
            must = (named, self._cv_of.get(named, ""))
        for keyword in _keywords(title, terms):
            ok, found, had_candidates = await self._search(client, keyword, title, hints, must)
            if not ok:
                return False, None
            saw_any = saw_any or had_candidates
            if found is not None:
                return True, found
        if found := await self._from_programs(client, title):
            return True, found
        return (True, None) if saw_any else (False, None)

    async def _search(
        self,
        client: httpx.AsyncClient,
        keyword: str,
        title: str,
        hints: Sequence[str],
        must: Sequence[str] = (),
    ) -> tuple[bool, dict[str, Any] | None, bool]:
        """按 `keyword` 搜一次，再按 `title` 挑。

        返回 `(问成了吗, 挑中的那首, 有没有候选)`——最后一个用来区分「限流没搜到」
        与「搜到了但对不上歌手」。
        """
        try:
            response = await client.get(
                NETEASE_SEARCH,
                params={"s": keyword, "type": 1, "limit": 10, "offset": 0},
                headers=HEADERS,
                timeout=10.0,
            )
        except httpx.HTTPError as error:
            log.warning("网易云搜索失败（%s）：%r", keyword, error)
            return False, None, False
        if response.status_code != 200:
            log.warning("网易云搜索返回 HTTP %s（%s）", response.status_code, keyword)
            return False, None, False
        try:
            payload = response.json()
        except ValueError:
            return False, None, False
        result = payload.get("result")
        if not isinstance(result, dict):
            # 加密过的响应（`{"result":"<十六进制>"}`）：这次没问到，别缓存成「没有」
            log.warning("网易云给的是加密结果（%s），换接口或等它恢复", keyword)
            return False, None, False
        songs = result.get("songs") or []
        best = _best_match(title, songs, hints)
        if best is not None and must:
            # 点名的版本（`With you（大崎甘奈Ver.）`）如果只挑到基础版，就收紧一次：
            # 对不上那位宁可不要，也别把组合版当成独唱版。
            # 但只在「挑中的正好是基础版」时收紧——不然会把一堆本来能对上的版本曲筛掉。
            if _normalise(str(best.get("name") or "")) == _normalise(_bare_title(title)):
                best = _best_match(title, songs, hints, must)
        if best is None:
            return True, None, bool(songs)
        best["_alternatives"] = _other_copies(title, songs, hints, best)
        # 网易云这两处不总是同一个形状：`album` 有时是对象、有时就是碟名，
        # `artists` 里也可能是字符串。按 object 猜就会 500（线上踩过一次）。
        # cloudsearch 用 `ar` / `al`，老接口用 `artists` / `album`，两种都认
        album = best.get("al", best.get("album"))
        artists = best.get("ar", best.get("artists")) or []
        # 同一首可能有好几张碟（2023 Ver.、合集、演唱會），有一张没版权就换下一张
        alternatives = [
            str(other["id"])
            for other in (best.get("_alternatives") or [])
            if str(other.get("id")) != str(best.get("id"))
        ][:3]
        return True, {
            "id": str(best["id"]),
            "name": best.get("name"),
            "artists": [
                artist.get("name") if isinstance(artist, dict) else str(artist)
                for artist in artists
            ],
            "album": album.get("name") if isinstance(album, dict) else (album or None),
            "duration": best.get("dt", best.get("duration")),
            "alternatives": alternatives,
        }, True

    async def _from_programs(self, client: httpx.AsyncClient, title: str) -> dict[str, Any] | None:
        """单曲搜不到时，去电台节目里找同名的那一期（节目音频也有 mainTrackId，能直接播）。"""
        if not self._programs:
            return None
        wanted = _normalise(title)
        if not wanted:
            return None

        for program_id in self._programs:
            info = await self._program(client, program_id)
            if info is None:
                continue
            name, track = info["name"], info["id"]
            folded = _normalise(name)
            if folded == wanted or wanted in folded or folded in wanted:
                return {
                    "id": track,
                    "name": name,
                    "artists": ["电台节目"],
                    "album": None,
                    "duration": None,
                    "via": "dj",
                }
        return None

    async def _program(self, client: httpx.AsyncClient, program_id: str) -> dict[str, Any] | None:
        """一期节目的名字和它的 `mainTrackId`；查过的记下来，不再问。"""
        key = f"dj:{program_id}"
        cached = self._found.get(key)
        if cached is not None:
            return cached
        try:
            response = await client.get(
                "https://music.163.com/api/dj/program/detail",
                params={"id": program_id},
                headers=HEADERS,
                timeout=10.0,
            )
            program = (response.json() or {}).get("program") or {}
        except (httpx.HTTPError, ValueError):
            return None
        name, track = program.get("name"), program.get("mainTrackId")
        if not name or not track:
            return None
        found = {"name": str(name), "id": str(track)}
        self._found[key] = found
        await asyncio.to_thread(self._save_cache)
        return found

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


def _read_program_ids() -> list[str]:
    """一行一个 id，`#` 开头的跳过。"""
    try:
        text = dj_programs_path().read_text(encoding="utf-8")
    except OSError:
        return []
    ids: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            ids.append(stripped)
    return ids


def _normalise(text: str) -> str:
    """比曲名时把空白、标点抹平：`Spread the Wings!!` 与 `Spread the Wings` 算同一首。"""
    return "".join(ch for ch in text.lower() if ch.isalnum())


_VERSION_SUFFIX = re.compile(r"^(.*?)[（(]([^）)]*)[）)]\s*$")

_NOT_A_PERFORMANCE = re.compile(r"(off\s*vocal|instrumental|inst\.|カラオケ|伴奏)", re.IGNORECASE)
"""伴奏版不是这首歌：`Spread the Wings!! (Off Vocal)` 放出来是没人唱的。"""

_PARENS = re.compile(r"[（(][^）)]*[）)]")
"""括号里的那截：`Migratory Echoes (アルストロメリア Ver.)` 的括号说的是「谁唱的」，不是歌名。"""

_TRUSTED_ALBUM = re.compile(r"(shiny\s*colors|シャイニーカラーズ|\b28\s*colors\b)", re.IGNORECASE)
"""这些碟名里带企划名的，基本可以认定是企划自己的录音（多人的群唱尤其常挂在整企划名下）。"""

_VER_SINGER = re.compile(r"[（(]\s*([^）)]*?)\s*(?:Ver\.?|ver\.?|版本?)\s*[）)]")
"""`With you（大崎甘奈Ver.）` 里点名的那位：大崎甘奈。"""
"""`FELICE（櫻木真乃Ver.）` 这种：括号里是版本说明，不是曲名的一部分。"""


def _version_singer(title: str) -> str | None:
    """曲名里「（某某Ver.）」点的是谁；没点名就是 None。"""
    match = _VER_SINGER.search(title)
    if not match:
        return None
    name = match.group(1).strip()
    # 只认人：`(2023 Ver.)` 这种是年份，不是谁唱的
    return name if name and not name.isdigit() else None


def _bare_title(title: str) -> str:
    """去掉「（某某Ver.）」之后的曲名。"""
    match = _VERSION_SUFFIX.match(title)
    return match.group(1).strip() if match and match.group(1).strip() else title


def _keywords(title: str, terms: Sequence[str] = ()) -> list[str]:
    """怎么搜这一首：曲名原样 → 去掉括号里的版本说明 → 再带上歌手 / 组合名。

    网易云对带全角括号的长串检索很差（`FELICE（櫻木真乃Ver.）` 搜出来是一堆别的歌），
    去掉括号再搜能中；而 `Sparkle` 这种常见词，单搜会被别人的同名歌淹掉，
    带上组合名（`Sparkle イルミネーションスターズ`）才排在前面。
    """
    match = _VERSION_SUFFIX.match(title)
    bare = match.group(1).strip() if match and match.group(1).strip() else title
    keywords = [title]
    if bare != title:
        keywords.append(bare)
    for term in list(terms)[:3]:
        if term and term not in keywords:
            keywords.append(f"{bare} {term}")
    return keywords


def _trusted_album(song: dict[str, Any]) -> bool:
    """这首所在的碟是不是企划自己的（`THE IDOLM@STER SHINY COLORS …` / `-28 colors-`）。"""
    album = song.get("al", song.get("album"))
    name = album.get("name") if isinstance(album, dict) else album
    return bool(name and _TRUSTED_ALBUM.search(str(name)))


def _artists_of(song: dict[str, Any]) -> list[str]:
    artists = song.get("ar", song.get("artists")) or []
    names: list[str] = []
    for artist in artists:
        name = artist.get("name") if isinstance(artist, dict) else artist
        if name:
            names.append(str(name))
    return names


def _best_match(
    title: str,
    songs: list[dict[str, Any]],
    hints: Sequence[str] = ("シャイニーカラーズ",),
    must: Sequence[str] = (),
) -> dict[str, Any] | None:
    """挑一条，按 `(歌手对得上吗, 曲名差多少, 名字长度)` 排。

    歌手优先是必要的：「Spread the Wings!!」在网易云上还有 EXILE 的版本，
    只按曲名比会挑到别人。歌手只是加分项、不是门槛——翻唱、限定组合都可能有别的名义。
    """
    wanted = _normalise(title)
    if not wanted:
        return None
    wanted_must = [term for term in must if term]
    scored: list[tuple[int, int, int, dict[str, Any]]] = []
    for song in songs:
        name = _normalise(str(song.get("name") or ""))
        if not name:
            continue
        if name == wanted:
            rank = 0
        elif name.startswith(wanted):
            rank = 1
        elif wanted in name or name in wanted:
            # 我们要的是原版，候选却带「（某某Ver.）」：排在后面，让真正的原版先被挑中
            rank = 3 if (not _VER_SINGER.search(title) and _VER_SINGER.search(str(song.get("name") or ""))) else 2
        else:
            continue
        if not _VER_SINGER.search(title):
            # 我们要的是原版：曲名如果只在候选的括号里出现，那是另一首歌
            # （`アルストロメリア` vs `Migratory Echoes (アルストロメリア Ver.)`）
            outside = _normalise(_PARENS.sub("", str(song.get("name") or "")))
            if wanted not in outside:
                continue
        if _NOT_A_PERFORMANCE.search(str(song.get("name") or "")):
            continue
        if _NOT_A_PERFORMANCE.search(str(song.get("name") or "")):
            continue
        if wanted_must:
            # 曲名里点名了「某某Ver.」：演唱者或曲名得对得上那位，
            # 否则会把组合版当成独唱版（`With you（大崎甘奈Ver.）` 就吃过这个亏）
            text = _squeeze(f"{song.get('name') or ''} {' '.join(_artists_of(song))}")
            if not any(_squeeze(term) in text for term in wanted_must):
                continue
        distances = [_artist_distance(_artists_of(song), hint) for hint in hints]
        by_artist = min(distances) if distances else 99
        if by_artist != 0 and _trusted_album(song):
            # 歌手对不上但碟是企划自己的：`BEAST MODE` 挂在 Σ Desire 名下就是这样
            by_artist = 0
        scored.append((by_artist, rank, abs(len(name) - len(wanted)), song))
    return (_ranked(scored) or [None])[0]


def _other_copies(
    title: str, songs: list[dict[str, Any]], hints: Sequence[str], best: dict[str, Any]
) -> list[dict[str, Any]]:
    """同一首歌在别的碟上的版本（2023 Ver.、合集、演唱会）：一张没版权时留着换。"""
    wanted = _normalise(title)
    copies = []
    for song in songs:
        if song is best:
            continue
        name = _normalise(str(song.get("name") or ""))
        if not name or not (name == wanted or wanted in name or name in wanted):
            continue
        if min(_artist_distance(_artists_of(song), hint) for hint in hints) != 0 and not _trusted_album(song):
            continue
        copies.append(song)
    return copies[:3]


def _ranked(scored: list[tuple[int, int, int, dict[str, Any]]]) -> list[dict[str, Any]]:
    """排好序、只留下歌手对得上的那些。

    一个都对不上歌手就不猜：「Spread the Wings!!」在网易云有 EXILE 那版，
    「Feel Jewel Dream」有学マス那版——宁可说「没找到」，也别放错人的歌。
    """
    if not scored:
        return []
    scored.sort(key=lambda item: item[:3])
    if scored[0][0] != 0:
        return []
    return [song for _, _, _, song in scored]


def _squeeze(text: str) -> str:
    """去掉所有空白：网易云写「浅倉 透」，世界设定写「浅倉透」。"""
    return "".join(text.split())


def _artist_distance(artists: Sequence[str], hint: str) -> int:
    """歌手名里有没有 `hint`：命中 0，没命中 1。空白不算差别。"""
    folded = _squeeze(hint)
    return 0 if any(folded in _squeeze(artist) for artist in artists) else 1
