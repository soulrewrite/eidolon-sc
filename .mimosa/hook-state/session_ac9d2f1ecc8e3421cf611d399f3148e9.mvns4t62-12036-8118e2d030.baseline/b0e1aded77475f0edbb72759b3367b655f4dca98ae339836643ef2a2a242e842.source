"use client";

// 歌曲的播放状态（fork，FORK.md「歌曲」）：一套全局的，切页面不停。
//
// 页面自己持有一个 <audio> 的话，一换页就卸载、音乐就断了。所以状态放在这里，
// 真正的 <audio> 由外壳（NavShell 里的 MusicPlayer）持有，永远不卸载：
// 只有点她的消息语音、或者开始通话，才把它停下来。

/** 现在在放哪一首；null 是没在放。
 *
 * `at` / `duration` 是给页面显示进度用的（秒，`duration` 未知时是 0）；
 * `unplayable` 是那条音频取不到（多半是网易云没版权）——放着也没声，页面要照实说。
 */
export type Playing = {
  title: string;
  neteaseId: string;
  at: number;
  duration: number;
  unplayable: boolean;
} | null;

let current: Playing = null;
const listeners = new Set<() => void>();

function emit(): void {
  for (const listener of listeners) listener();
}

export const musicPlayback = {
  subscribe(listener: () => void): () => void {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  },
  /** 给 `useSyncExternalStore` 的取快照：手机上首屏（还没跑脚本）当作没在放。 */
  get(): Playing {
    return current;
  },
  /** 放这一首；已经在放同一首、又没出过错，就不重来。 */
  play(title: string, neteaseId: string): void {
    if (current?.neteaseId === neteaseId && !current.unplayable) return;
    current = { title, neteaseId, at: 0, duration: 0, unplayable: false };
    emit();
  },
  /** 播放器报到哪里了。按秒去通知，免得一秒画几十次。 */
  tick(at: number, duration: number): void {
    if (current === null) return;
    const second = Math.floor(at);
    if (current.at === second && current.duration === Math.floor(duration)) return;
    current = { ...current, at: second, duration: Math.floor(duration) };
    emit();
  },
  /** 那条音频取不到（多半是没版权）：留住状态让页面说明白，但不再出声。 */
  markUnplayable(): void {
    if (current === null || current.unplayable) return;
    current = { ...current, unplayable: true };
    emit();
  },
  /** 停下来。她的语音开口、通话接通，都会调这个。 */
  stop(): void {
    if (current === null) return;
    current = null;
    emit();
  },
};
