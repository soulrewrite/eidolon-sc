"""曲库与网易云查找（FORK.md「歌曲」）。不起服务，只测纯逻辑。"""

from datetime import date
from typing import cast

import httpx

import pytest

from eidolon.music import (  # pyright: ignore[reportPrivateUsage]
    MusicLibrary,
    _best_match,
    _keywords,
    _normalise,
)
from eidolon.world import Idol, Release, Song, Track, World


def library(tmp_path) -> MusicLibrary:
    """两位偶像、两张碟、三首歌，网易云缓存落在 tmp。"""
    world = World(
        as_of=date(2026, 9, 28),
        office="283プロダクション",
        staff=(),
        units=(),
        idols=(
            Idol(
                name="櫻木真乃",
                reading="さくらぎ まの",
                unit="illumination STARS",
                cv="関根瞳",
                sources=(),
            ),
        ),
        releases=(
            Release(
                catalog="LACM-14781",
                title="BRILLI@NT WING 01",
                date=date(2018, 6, 6),
                tracks=(Track("Spread the Wings!!", "Spread the Wings!!"), Track("Off Vocal", None)),
                sources=("https://example.invalid/1",),
            ),
            Release(
                catalog="LACM-14782",
                title="BRILLI@NT WING 02",
                date=date(2018, 7, 4),
                tracks=(Track("虹になれ", "虹になれ"),),
                sources=("https://example.invalid/2",),
            ),
        ),
        songs=(
            Song(
                id="Spread the Wings!!",
                title="Spread the Wings!!",
                singers=("櫻木真乃", "風野灯織"),
                special_unit=None,
                releases=("LACM-14781",),
                sources=(),
            ),
            Song(
                id="虹になれ",
                title="虹になれ",
                singers=("櫻木真乃",),
                special_unit=None,
                releases=("LACM-14782",),
                sources=(),
            ),
            Song(
                id="FELICE（櫻木真乃Ver.）",
                title="FELICE（櫻木真乃Ver.）",
                singers=("櫻木真乃",),
                special_unit=None,
                releases=(),
                sources=(),
            ),
            Song(
                id="ヒカリのdestination",
                title="ヒカリのdestination",
                singers=("風野灯織",),
                special_unit=None,
                releases=(),
                sources=(),
            ),
        ),
    )
    return MusicLibrary(world, path=tmp_path / "cache.json")


def test_her_songs_are_only_hers(tmp_path):
    music = library(tmp_path)
    # 顺序照世界设定里的曲目顺序，FELICE 的独唱版排在最后
    assert [song.title for song in music.songs("櫻木真乃")] == [
        "Spread the Wings!!",
        "虹になれ",
        "FELICE（櫻木真乃Ver.）",
    ]
    assert [song.title for song in music.songs("風野灯織")] == [
        "Spread the Wings!!",
        "ヒカリのdestination",
    ]


def test_every_song_when_no_singer_is_named(tmp_path):
    assert len(library(tmp_path).songs()) == 4


def test_singers_are_those_with_songs_in_world_order(tmp_path):
    assert library(tmp_path).singer_names() == ["櫻木真乃", "風野灯織"]


def test_an_unknown_singer_has_nothing(tmp_path):
    assert library(tmp_path).songs("七草はづき") == []


def test_albums_newest_first_and_tracks_kept(tmp_path):
    albums = library(tmp_path).albums()
    assert [album.catalog for album in albums] == ["LACM-14782", "LACM-14781"]
    assert albums[1].tracks == ("Spread the Wings!!", "Off Vocal")
    # 曲目里不是歌的（off vocal）不进 songs
    assert albums[1].songs == ("Spread the Wings!!",)


def test_no_world_no_songs(tmp_path):
    assert MusicLibrary(None, path=tmp_path / "c.json").is_empty


@pytest.mark.parametrize(
    ("wanted", "listed", "taken"),
    [
        ("Spread the Wings!!", "Spread the Wings!!", True),       # 一模一样
        ("Spread the Wings!!", "Spread the Wings", True),        # 标点不同
        ("ヒカリのdestination", "ヒカリのdestination (2023 Ver.)", True),  # 版本后缀
        ("虹になれ", "虹色のなれ", False),                        # 只是碰巧包含几个字
    ],
)
def test_which_listing_counts_as_the_same_song(wanted: str, listed: str, taken: bool):
    songs = [{"id": 1, "name": listed, "ar": [{"name": "シャイニーカラーズ"}]}]
    assert (_best_match(wanted, songs) is not None) is taken


def test_a_same_title_by_someone_else_loses():
    """「Spread the Wings!!」在网易云上还有 EXILE 那一版，只按曲名会比到别人。"""
    songs = [
        {"id": 1, "name": "Spread The Wings", "ar": [{"name": "PSYCHIC FEVER from EXILE TRIBE"}]},
        {"id": 2, "name": "Spread the Wings!! (2023 Ver.)", "ar": [{"name": "シャイニーカラーズ"}]},
    ]
    assert (_best_match("Spread the Wings!!", songs) or {})["id"] == 2


class FakeNetease:
    """假 httpx client：`get` 直接回准备好的 JSON。"""

    def __init__(self, payload: dict) -> None:
        self.status_code = 200
        self._payload = payload

    async def get(self, *_: object, **__: object) -> object:
        return self

    def json(self) -> dict:
        return self._payload


def test_a_common_title_is_searched_with_her_group(tmp_path):
    """`Sparkle` 这种词单搜会被别人的同名歌淹掉，带上组合名才排得上来。"""
    keywords = _keywords("Sparkle", ["イルミネーションスターズ"])
    assert keywords[0] == "Sparkle"
    assert "Sparkle イルミネーションスターズ" in keywords


class DjClient:
    """假 client：单曲搜不到，节目的详情里有。"""

    status_code = 200

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def get(self, url: str, params: dict | None = None, **_: object) -> object:
        self.calls.append(url)
        if "program/detail" in url:
            self._payload = {"program": {"name": "With you（大崎甘奈Ver.）", "mainTrackId": 2686388735}}
        else:
            self._payload = {"result": {"songs": []}}
        return self

    def json(self) -> dict:
        return self._payload


async def test_a_song_only_in_a_radio_program_is_found(tmp_path):
    """没单独上架的歌常常只在电台节目里：「With you（大崎甘奈Ver.）」就是这样。"""
    music = library(tmp_path)
    music._programs = ["3074027043"]  # pyright: ignore[reportPrivateUsage]
    client = DjClient()
    found = await music.lookup(cast("httpx.AsyncClient", client), "With you（大崎甘奈Ver.）")
    assert found is not None
    assert found["id"] == "2686388735"
    assert found["via"] == "dj"


async def test_an_encrypted_result_is_not_taken_as_missing(tmp_path):
    """`search/get/web` 现在回 `{"result":"35b174…"}`：那是“没问到”，不能缓存成“没有这首”。"""
    music = library(tmp_path)
    encrypted = FakeNetease({"result": "35b1748964af8a7c1d883e3a6f3c773b"})
    assert await music.lookup(cast("httpx.AsyncClient", encrypted), "虹になれ") is None

    # 下次问成了，就该拿到——缓存里不能留着“没有”
    hit = FakeNetease(
        {"result": {"songs": [{"id": 7, "name": "虹になれ", "ar": [{"name": "シャイニーカラーズ"}]}]}}
    )
    found = await music.lookup(cast("httpx.AsyncClient", hit), "虹になれ")
    assert found is not None and found["id"] == "7"


def test_a_version_suffix_is_dropped_for_a_second_search():
    """带全角括号的长串网易云搜不好，去掉括号里的版本说明再搜一次。"""
    assert _keywords("FELICE（櫻木真乃Ver.）") == ["FELICE（櫻木真乃Ver.）", "FELICE"]
    assert _keywords("虹になれ") == ["虹になれ"]


async def test_a_solo_version_credited_to_her_cv_is_found(tmp_path):
    """`FELICE（櫻木真乃Ver.）` 在网易云的歌手是 **関根瞳**（声优），不是组合也不是角色名。"""
    music = library(tmp_path)
    hit = FakeNetease(
        {
            "result": {
                "songs": [
                    {"id": 42, "name": "FELICE（櫻木真乃Ver.）", "ar": [{"name": "関根瞳"}]},
                ]
            }
        }
    )
    found = await music.lookup(cast("httpx.AsyncClient", hit), "FELICE（櫻木真乃Ver.）")
    assert found is not None and found["id"] == "42"


def test_normalising_ignores_case_and_punctuation():
    assert _normalise("Spread the Wings!!") == _normalise("spread the wings")


def test_a_found_song_is_remembered_without_asking_again(tmp_path):
    """查过的写进缓存：同一个曲名不会再问网易云一次。"""
    music = library(tmp_path)
    music._found = {"虹になれ": {"id": "123", "name": "虹になれ"}}  # pyright: ignore[reportPrivateUsage]
    music._save_cache()  # pyright: ignore[reportPrivateUsage]

    again = library(tmp_path)
    assert again.cached("虹になれ") == {"id": "123", "name": "虹になれ"}


def test_a_song_netease_does_not_have_is_remembered_as_missing(tmp_path):
    music = library(tmp_path)
    music._found = {"どこにもない": None}  # pyright: ignore[reportPrivateUsage]
    music._save_cache()  # pyright: ignore[reportPrivateUsage]

    again = library(tmp_path)
    assert "どこにもない" in again._found  # pyright: ignore[reportPrivateUsage]
    assert again.cached("どこにもない") is None
