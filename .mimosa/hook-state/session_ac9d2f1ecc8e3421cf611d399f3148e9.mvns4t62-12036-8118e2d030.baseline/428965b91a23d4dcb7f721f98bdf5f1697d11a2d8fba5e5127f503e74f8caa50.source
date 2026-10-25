import { afterEach, describe, expect, it, vi } from "vitest";

import type { Character } from "@/lib/api";
import { DEFAULT_APPEARANCE, keepAppearance, loadAppearance, withAppearance } from "@/lib/appearance";

/** 这个浏览器的 localStorage，放在内存里。 */
function storage(initial: Record<string, string> = {}) {
  const items = new Map(Object.entries(initial));
  vi.stubGlobal("localStorage", {
    getItem: (key: string) => items.get(key) ?? null,
    setItem: (key: string, value: string) => void items.set(key, value),
  });
  return items;
}

afterEach(() => vi.unstubAllGlobals());

const character = (id: string, scsp: boolean) =>
  ({
    id,
    avatar_url: `/api/characters/${id}/avatar`,
    scsp_avatar_url: scsp ? `/api/characters/${id}/scsp-avatar` : null,
  }) as Character;

describe("外观存在这台设备上、按用户分开", () => {
  it("没存过时聊天用 SCSP 头像（歌曲页用的是另一套）", () => {
    storage();
    expect(loadAppearance("u1")).toEqual(DEFAULT_APPEARANCE);
    expect(DEFAULT_APPEARANCE.scspAvatars).toBe(true);
  });

  it("老设备存下的「关」迁移一次成「开」，之后听用户的", () => {
    const items = storage({ "eidolon.appearance.u1": '{"scspAvatars":false}' });
    expect(loadAppearance("u1")).toEqual({ scspAvatars: true });
    expect(items.get("eidolon.appearance.u1")).toBe('{"scspAvatars":true}');

    // 用户之后自己关掉，就不该再被迁移拉回开
    keepAppearance("u1", { scspAvatars: false });
    expect(loadAppearance("u1")).toEqual({ scspAvatars: false });
  });

  it("存下的读得回来，别的用户读不到", () => {
    storage();
    keepAppearance("u1", { scspAvatars: true });
    expect(loadAppearance("u1")).toEqual({ scspAvatars: true });
    expect(loadAppearance("u2")).toEqual(DEFAULT_APPEARANCE);
  });

  it("数据坏了当作默认", () => {
    storage({ "eidolon.appearance.u1": "{oops", "eidolon.appearance.u2": '{"scspAvatars":"yes"}' });
    expect(loadAppearance("u1")).toEqual(DEFAULT_APPEARANCE);
    expect(loadAppearance("u2")).toEqual(DEFAULT_APPEARANCE);
  });

  it("存不进去时不抛错", () => {
    vi.stubGlobal("localStorage", {
      setItem: () => {
        throw new Error("QuotaExceededError");
      },
    });
    expect(() => keepAppearance("u1", { scspAvatars: true })).not.toThrow();
  });
});

describe("按外观换头像", () => {
  const all = [character("mano", true), character("kogane", false)];

  it("关着时头像照旧", () => {
    expect(withAppearance(all, { scspAvatars: false })).toBe(all);
  });

  it("打开时换成她的 SCSP 头像，她没有的照旧", () => {
    expect(withAppearance(all, { scspAvatars: true }).map((c) => c.avatar_url)).toEqual([
      "/api/characters/mano/scsp-avatar",
      "/api/characters/kogane/avatar",
    ]);
  });
});
