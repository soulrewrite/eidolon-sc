import { beforeEach, describe, expect, it, vi } from "vitest";

import { musicPlayback } from "@/lib/musicPlayer";

describe("跨页面的歌曲播放状态", () => {
  beforeEach(() => {
    musicPlayback.stop();
  });

  it("一开始什么都没在放", () => {
    expect(musicPlayback.get()).toBeNull();
  });

  it("放一首之后，谁读都能读到同一首（页面换了也读得到）", () => {
    musicPlayback.play("虹になれ", "2020881825");
    expect(musicPlayback.get()).toEqual({ title: "虹になれ", neteaseId: "2020881825" });
  });

  it("已经在放同一首时不重复通知", () => {
    const listener = vi.fn();
    const unsubscribe = musicPlayback.subscribe(listener);
    musicPlayback.play("虹になれ", "1");
    musicPlayback.play("虹になれ", "1");
    expect(listener).toHaveBeenCalledTimes(1);
    unsubscribe();
  });

  it("换一首会通知", () => {
    const listener = vi.fn();
    const unsubscribe = musicPlayback.subscribe(listener);
    musicPlayback.play("虹になれ", "1");
    musicPlayback.play("ヒカリのdestination", "2");
    expect(listener).toHaveBeenCalledTimes(2);
    expect(musicPlayback.get()?.title).toBe("ヒカリのdestination");
    unsubscribe();
  });

  it("停下之后回到没有，且没人订阅了就不再管", () => {
    musicPlayback.play("虹になれ", "1");
    musicPlayback.stop();
    expect(musicPlayback.get()).toBeNull();

    const listener = vi.fn();
    const unsubscribe = musicPlayback.subscribe(listener);
    unsubscribe();
    musicPlayback.play("虹になれ", "1");
    expect(listener).not.toHaveBeenCalled();
  });
});
