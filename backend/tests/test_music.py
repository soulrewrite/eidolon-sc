"""曲库与网易云查找（FORK.md「歌曲」）。不起服务，只测纯逻辑。"""

from datetime import date

import pytest

from eidolon.music import MusicLibrary, _best_match, _normalise  # pyright: ignore[reportPrivateUsage]
from eidolon.world import Release, Song, Track, World


def library(tmp_path) -> MusicLibrary:
    """两位偶像、两张碟、三首歌，网易云缓存落在 tmp。"""
    world = World(
        as_of=date(2026, 9, 28),
        office="283プロダクション",
        staff=(),
        units=(),
        idols=(),
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
    assert [song.title for song in music.songs("櫻木真乃")] == ["Spread the Wings!!", "虹になれ"]
    assert [song.title for song in music.songs("風野灯織")] == [
        "Spread the Wings!!",
        "ヒカリのdestination",
    ]


def test_every_song_when_no_singer_is_named(tmp_path):
    assert len(library(tmp_path).songs()) == 3


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
    songs = [{"id": 1, "name": listed}]
    assert (_best_match(wanted, songs) is not None) is taken


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
