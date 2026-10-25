"""预合成（`MessageSpeech.warm`）与点播放（`url_of`）必须算到同一个地址。

点播放时用的是入库的 `ja`（带 delivery cue，`[happily] お花` 这样），预合成时用的是
流式事件 `SpeechDelta`（`[happily]お花`，cue 后面没有那个空格）。两者只有经过
`voiced()` 之后才逐字一致 —— 那时候哈希才对得上。用 `SegmentDelta`（给人看的那份，
cue 已经没了）就会算出另一个地址，合成出来的东西点播放时找不到，等于白花一次。
"""

from eidolon.delivery_cues import voiced
from eidolon.reply_format import ReplyParser, SpeechDelta

REPLY = (
    "<ja>[happily] お花、ちゃんと飾れたよー。</ja><zh>花好好摆上了哦。</zh>"
    "<ja>[gently] でも、ちょっと大きすぎたかも。</ja><zh>不过好像有点太大了。</zh>"
    "<ja>ありがとう。</ja><zh>谢谢你。</zh>"
)


def test_the_text_prewarmed_is_the_text_a_click_asks_for():
    parser = ReplyParser()
    spoken: dict[int, str] = {}
    for char in REPLY:
        for event in parser.feed(char):
            if isinstance(event, SpeechDelta):
                spoken[event.segment] = spoken.get(event.segment, "") + event.text
    parser.finish()

    assert len(parser.complete) == 3
    for index, segment in enumerate(parser.complete):
        # 入库的 `ja` 带着 cue 后面那个空格，念的那份没有；`voiced()` 抹平这一处。
        assert voiced(segment.ja) == spoken[index], index
