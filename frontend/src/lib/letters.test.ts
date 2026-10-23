import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { sealCharacterOf } from "@/lib/letters";

const toml = readFileSync(resolve(__dirname, "../../../characters/characters.toml"), "utf8");
const ids = [...toml.matchAll(/^id = "([a-z]+)"/gm)].map((match) => match[1]);

function seal(id: string) {
  return sealCharacterOf({ character_id: id, character_name: "x", character_name_zh: null });
}

describe("信封上的那一个字", () => {
  it("每个角色都登记了，一个不落", () => {
    expect(ids.length).toBe(29);
    const missing = ids.filter((id) => sealCharacterOf({
      character_id: id,
      character_name: "x",
      character_name_zh: null,
    }) === "x"); // 走到日文名兜底说明没登记
    expect(missing).toEqual([]);
  });

  it("按角色取，不按名字末字取", () => {
    // 末字规则会得到 美 / 花 / 希 / 子，都不是原作那枚印
    expect(seal("mamimi")).toBe("摩");
    expect(seal("tenka")).toBe("甜");
    expect(seal("haruki")).toBe("羊");
    expect(seal("chiyoko")).toBe("巧");
  });

  it("各组合都取对了", () => {
    expect(["mano", "hiori", "meguru"].map(seal)).toEqual(["真", "灯", "巡"]);
    expect(["kogane", "mamimi", "sakuya", "yuika", "kiriko"].map(seal)).toEqual([
      "鐘", "摩", "咲", "結", "霧",
    ]);
    expect(["kaho", "chiyoko", "juri", "rinze", "natsuha"].map(seal)).toEqual([
      "穂", "巧", "樹", "凛", "夏",
    ]);
    expect(["amana", "tenka", "chiyuki"].map(seal)).toEqual(["甘", "甜", "千"]);
    expect(["asahi", "fuyuko", "mei"].map(seal)).toEqual(["朝", "冬", "愛"]);
    expect(["toru", "madoka", "koito", "hinana"].map(seal)).toEqual(["透", "円", "糸", "雛"]);
    expect(["nichika", "mikoto"].map(seal)).toEqual(["日", "美"]);
    expect(["luca", "hana", "haruki"].map(seal)).toEqual(["路", "羽", "羊"]);
    expect(seal("hazuki")).toBe("葉");
  });

  it("没登记的角色退回名字末字，再退日文名首字", () => {
    expect(
      sealCharacterOf({ character_id: "someone", character_name: "新しい", character_name_zh: "新的" }),
    ).toBe("的");
    expect(
      sealCharacterOf({ character_id: "someone", character_name: "あたら", character_name_zh: null }),
    ).toBe("あ");
  });
});
