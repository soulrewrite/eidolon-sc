"use client";

// 外壳持有的歌曲播放器（fork）：切页面不停，点语音或开始通话才停。
//
// 页面上的列表只负责「放哪一首」，真正的 <audio> 在这里——它挂在导航外壳上，
// 从对话换到礼物、设置，这个组件都不会卸载。

import { usePathname } from "next/navigation";
import { useEffect, useRef, useSyncExternalStore } from "react";

import { useDirectory } from "@/components/conversations/ConversationDirectory";
import { copy } from "@/i18n";
import { streamUrl } from "@/lib/music";
import { musicPlayback } from "@/lib/musicPlayer";
import { CloseIcon, MusicIcon } from "@/theme/icons";

const nothing = () => null;

export function MusicPlayer() {
  const playing = useSyncExternalStore(musicPlayback.subscribe, musicPlayback.get, nothing);
  const { call } = useDirectory();
  const pathname = usePathname();
  const audio = useRef<HTMLAudioElement | null>(null);

  // 开始通话就停下来：通话要占着麦克风和音频，歌还在响就全糊在一起了
  useEffect(() => {
    if (call !== null) musicPlayback.stop();
  }, [call]);

  useEffect(() => {
    const element = audio.current;
    if (!element) return;
    if (playing === null) {
      element.pause();
      element.removeAttribute("src");
      element.load();
      return;
    }
    element.src = streamUrl(playing.neteaseId);
    // 自动播放可能被浏览器拦（没点过页面），拦了就照实停掉，不留一个空转的状态
    void element.play().catch(() => musicPlayback.stop());
  }, [playing]);

  if (playing === null) return null;

  return (
    <>
      {/* 真正出声的元素：不显示，只负责放 */}
      {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
      <audio ref={audio} preload="none" />
      {/* 不在歌曲页时给一条窄条：能听见在放什么，也能停 */}
      {pathname !== "/music" && (
        <div className="pointer-events-none fixed inset-x-0 bottom-14 z-30 flex justify-center px-3 md:bottom-4">
          <div className="pointer-events-auto flex max-w-md items-center gap-2 rounded-full border bg-background/95 px-3 py-1.5 shadow-sm backdrop-blur">
            <MusicIcon aria-hidden className="size-4 shrink-0 text-muted-foreground" />
            <span className="min-w-0 flex-1 truncate text-meta">{playing.title}</span>
            <button
              type="button"
              aria-label={copy.music.stop}
              className="rounded-full p-1 text-muted-foreground hover:text-foreground"
              onClick={() => musicPlayback.stop()}
            >
              <CloseIcon className="size-4" />
            </button>
          </div>
        </div>
      )}
    </>
  );
}
