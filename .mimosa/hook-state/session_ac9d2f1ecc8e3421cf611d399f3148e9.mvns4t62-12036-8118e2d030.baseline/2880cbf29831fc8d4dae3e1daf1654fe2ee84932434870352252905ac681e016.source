// 外观（设置「外观」）：现在只有「SCSP 头像」一个开关（GLOSSARY.md「SCSP 头像」）。只存在这台设备上，
// 在 localStorage 里按用户分开存（键为 eidolon.appearance.<用户 ID>）。读不到或数据坏了当作默认（关）；
// 存不进去（隐私模式等）时不抛错，改动只留在页面内存里。

import type { Character } from "@/lib/api";

export type Appearance = {
  /** 登录后的应用里，头像换成她们在 SCSP 里的那一套。 */
  scspAvatars: boolean;
};

// 默认给聊天用 SCSP 那一套（歌曲页用的是原来的立绘）；关掉开关就换回立绘。
// 2026-10-25 之前默认是关的，老设备存下的 `false` 用一次迁移改成 `true`。
export const DEFAULT_APPEARANCE: Appearance = { scspAvatars: true };

const MIGRATED_KEY = "eidolon.appearance.migrated";

function storageKey(userId: string): string {
  return `eidolon.appearance.${userId}`;
}

/** 这位用户在这台设备上的外观。 */
export function loadAppearance(userId: string): Appearance {
  try {
    const raw = localStorage.getItem(storageKey(userId));
    if (raw === null) return DEFAULT_APPEARANCE;
    const stored = JSON.parse(raw);
    const scspAvatars = stored?.scspAvatars === true;
    // 老设备存的是「关」，那会儿默认关；按新默认迁移一次，之后就听用户的
    if (!scspAvatars && localStorage.getItem(MIGRATED_KEY) === null) {
      try {
        localStorage.setItem(MIGRATED_KEY, "1");
        localStorage.setItem(storageKey(userId), JSON.stringify({ scspAvatars: true }));
      } catch {
        // 存不进去就算了，这次页面里按默认走
      }
      return DEFAULT_APPEARANCE;
    }
    return { scspAvatars };
  } catch {
    return DEFAULT_APPEARANCE;
  }
}

/** 存下这位用户的外观；存不进去时什么也不做。 */
export function keepAppearance(userId: string, appearance: Appearance): void {
  try {
    localStorage.setItem(storageKey(userId), JSON.stringify(appearance));
  } catch {
    // 存储不可用：这次存不下，改动只在这次页面里生效。
  }
}

/** 按外观换掉每位的头像：打开 SCSP 头像时用她的 SCSP 头像，她没有的照旧。 */
export function withAppearance(characters: Character[], appearance: Appearance): Character[] {
  if (!appearance.scspAvatars) return characters;
  return characters.map((c) => (c.scsp_avatar_url ? { ...c, avatar_url: c.scsp_avatar_url } : c));
}
