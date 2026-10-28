import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { announced, groupLetters, heldBack, sealCharacterOf, type Letter } from "@/lib/letters";

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


function letter(id: string, characterId: string, deliveredAt: string): Letter {
  return {
    id,
    character_id: characterId,
    character_name: characterId,
    character_name_zh: null,
    color: "#fff",
    background_url: null,
    signature_url: null,
    envelope_url: null,
    trigger: "everyday",
    delivered_at: deliveredAt,
    segments: [],
    read: false,
  };
}

describe("公告里只放最新的几封", () => {
  const all = [
    letter("a", "mano", "2026-10-27T10:00:00Z"),
    letter("b", "meguru", "2026-10-26T10:00:00Z"),
    letter("c", "hiori", "2026-10-25T10:00:00Z"),
    letter("d", "mano", "2026-10-24T10:00:00Z"),
  ];

  it("放最新三封，新的在前", () => {
    expect(announced(all).map((one) => one.id)).toEqual(["a", "b", "c"]);
  });

  it("剩下几封说得清", () => {
    expect(heldBack(all)).toBe(1);
    expect(heldBack(all.slice(0, 2))).toBe(0);
    expect(heldBack([])).toBe(0);
  });
});

describe("统计页里的信按角色分组", () => {
  const all = [
    letter("a", "mano", "2026-10-27T10:00:00Z"),
    letter("b", "meguru", "2026-10-26T10:00:00Z"),
    letter("c", "mano", "2026-10-24T10:00:00Z"),
  ];
  const characters = [
    { id: "meguru", idol_id: 3 },
    { id: "mano", idol_id: 1 },
  ] as Parameters<typeof groupLetters>[1];

  it("组内新的在前，组按偶像表的顺序", () => {
    const grouped = groupLetters(all, characters);
    expect(grouped.map((group) => group.key)).toEqual(["mano", "meguru"]);
    expect(grouped[0].letters.map((one) => one.id)).toEqual(["a", "c"]);
  });
});
