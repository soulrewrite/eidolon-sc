"""社区消息（`community_news.py`）：抓 Lantis、去重、挑一条、窗口。

不起服务：只测解析和挑选，网络那一段用手写的 HTML 片段。
"""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo
from typing import cast

from eidolon.clock import Clock
from eidolon.store import Store
from eidolon.community_news import (
    SC_WEIGHT,
    CommunityNews,
    about,
    parse_lantis,
    parse_release_details,
)

PAGE = """
<div class="release_box info">
  <a href="https://shinycolors.lantis.jp/releaseinfo/lacz-10374/">
    <img src="https://shinycolors.lantis.jp/x/wp-content/uploads/2026/09/LACZ-10374.jpg">
  </a>
  <a href="https://twitter.com/share" data-url="https://shinycolors.lantis.jp/releaseinfo/lacz-10374/"
     data-text="THE IDOLM@STER SHINY COLORS SOLO COLLECTION 283 PRODUCTION Solo Live Collection">
     Tweet
  </a>
  <span>2026.09.26</span>
</div>
<div class="release_box info">
  <a href="https://shinycolors.lantis.jp/releaseinfo/lacm-24636/">
    <img src="https://shinycolors.lantis.jp/x/wp-content/uploads/2025/03/LACM-24636.jpg">
  </a>
  <a href="https://twitter.com/share" data-url="https://shinycolors.lantis.jp/releaseinfo/lacm-24636/"
     data-text="THE IDOLM@STER MILLION THE@TER Real Mind Shakes">
     Tweet
  </a>
  <span>2025.03.26</span>
</div>
"""


def test_a_release_page_becomes_candidates():
    found = parse_lantis(PAGE)
    assert len(found) == 2
    first = found[0]
    assert first.url.endswith("/releaseinfo/lacz-10374/")
    assert "SHINY COLORS" in first.title
    assert first.published == date(2026, 9, 26)
    assert first.weight == SC_WEIGHT


def test_another_brand_weighs_less():
    found = parse_lantis(PAGE)
    million = found[1]
    assert million.weight == 1
    assert million.published == date(2025, 3, 26)


def clock_at(day: date, hour: int, minute: int = 0) -> Clock:
    """按**东京时间**造一个时刻（窗口是按用户时区判的）。"""
    moment = datetime(day.year, day.month, day.day, hour, minute, tzinfo=ZoneInfo("Asia/Tokyo"))
    return lambda: moment.astimezone(UTC)


class NoStore:
    """只需要 `current_conversations` 的替身；挑消息的测试不走推送。"""

    def current_conversations(self):  # noqa: ANN201
        return []


def test_the_same_release_is_only_kept_once(tmp_path):
    day = date(2026, 10, 27)
    news = CommunityNews(tmp_path / "n.db", cast("Store", NoStore()), clock_at(day, 12, 30))
    news._remember(parse_lantis(PAGE))  # pyright: ignore[reportPrivateUsage]
    news._remember(parse_lantis(PAGE))  # pyright: ignore[reportPrivateUsage]
    candidate = news.next_to_push()
    assert candidate is not None
    news.mark_pushed(candidate)
    assert news.next_to_push() is not None  # 还有第二条
    second = news.next_to_push()
    assert second is not None and second.url != candidate.url
    assert news.pushed_today("Asia/Tokyo") == 1  # 已推过一条（钟停在当天 12:30）
    news.close()


def test_the_higher_weight_goes_first(tmp_path):
    day = date(2026, 10, 27)
    news = CommunityNews(tmp_path / "n.db", cast("Store", NoStore()), clock_at(day, 12, 30))
    news._remember(parse_lantis(PAGE))  # pyright: ignore[reportPrivateUsage]
    candidate = news.next_to_push()
    assert candidate is not None and candidate.weight == SC_WEIGHT
    news.close()


def test_the_windows_are_lunch_and_evening(tmp_path):
    day = date(2026, 10, 27)
    for hour, expected in ((9, False), (12, True), (13, True), (14, False), (19, True), (20, True), (22, False)):
        news = CommunityNews(tmp_path / f"w{hour}.db", cast("Store", NoStore()), clock_at(day, hour))
        assert news.window_now("Asia/Tokyo") is expected, hour
        news.close()


def test_an_old_release_can_be_skipped(tmp_path):
    day = date(2026, 10, 27)
    news = CommunityNews(tmp_path / "n.db", cast("Store", NoStore()), clock_at(day, 12, 30))
    news._remember(parse_lantis(PAGE))  # pyright: ignore[reportPrivateUsage]
    # 只要最近 7 天内发布的：两条都太旧
    old = news.next_to_push(since=datetime(2026, 10, 20, tzinfo=UTC))
    assert old is None
    news.close()


DETAIL = """
<p>2026.09.26 RELEASE THE IDOLM@STER SHINY COLORS SOLO COLLECTION</p>
<p>アーティスト：シャイニーカラーズ 杜野凛世（CV.丸岡和佳奈）、大崎甘奈（CV.黒木ほの香）
発売日：2026/9/26 品番：LACZ-10374 価格：2,640円</p>
<p>1.クローバー (杜野凛世Ver.) 2.クローバー (大崎甘奈Ver.) 3.SOLAR WAY (郁田はるきVer.)
『THE IDOLM@STER SHINY COLORS SOLO COLLECTION』の会場にて販売されます。</p>
"""


def test_a_release_page_tells_whose_album_it_is():
    """她得知道这张碟是谁的——不然聊起来像不认识自己事务所的人。"""
    artist, tracks = parse_release_details(DETAIL)
    assert artist is not None and "杜野凛世" in artist
    assert len(tracks) == 3
    assert tracks[0] == "クローバー (杜野凛世Ver.)"


def test_what_she_is_told_names_the_artist_and_the_tracks():
    from eidolon.community_news import Candidate

    told = about(
        Candidate(
            url="https://example.test/x",
            title="SOLO COLLECTION",
            source="lantis",
            published=date(2026, 9, 26),
            weight=SC_WEIGHT,
            artist="シャイニーカラーズ 杜野凛世",
            tracks=("クローバー", "SOLAR WAY"),
        )
    )
    assert "シャイニーカラーズ 杜野凛世" in told
    assert "クローバー" in told
    assert "2026-09-26" in told
