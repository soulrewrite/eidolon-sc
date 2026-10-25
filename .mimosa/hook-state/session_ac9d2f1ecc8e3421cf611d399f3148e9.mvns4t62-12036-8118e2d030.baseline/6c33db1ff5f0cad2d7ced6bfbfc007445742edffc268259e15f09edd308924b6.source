// Her letters (GLOSSARY.md「信」, fork): what she would not say to the producer's face, left in
// the announcements one evening. Only a character he is close to writes them, one every few
// days, in the evening — or on a day that calls for it.

import { api, expectNoContent, json } from "@/lib/api";

/** One letter as the user reads it: her words, Japanese on the paper with the Chinese under
 * it, the call background showing through, and her autograph at the end. */
export type Letter = {
  id: string;
  character_id: string;
  character_name: string;
  character_name_zh: string | null;
  /** Her image colour: the ink, the rules and the icons take their hue from it. */
  color: string;
  /** Her call background, which the paper is made of; null when she has none. */
  background_url: string | null;
  /** Her autograph, drawn at the foot of the letter; null signs with her name in type. */
  signature_url: string | null;
  /** The card art her envelope is made of; null when she has no card to show. */
  envelope_url: string | null;
  /** Why she wrote: his birthday, the monthly return of the day they first spoke, or nothing
   * more than an evening. */
  trigger: "birthday" | "anniversary" | "everyday";
  delivered_at: string;
  segments: { ja: string; zh: string }[];
  read: boolean;
};

/**
 * 印章上按的那个字（fork）：按角色定，不按名字末字取。
 *
 * 末字规则会错一大半：田中 摩美美 的印是「摩」不是「美」，大崎 甜花 是「甜」不是「花」，
 * 郁田 阳希 是「羊」不是「希」，園田 智代子 是「巧」不是「子」。只有 巡 / 鐘 / 咲 / 穂 / 甘 /
 * 朝 / 透 / 円 / 糸 / 日 / 羽 这些碰巧对得上。
 */
const SEAL_CHARACTER: Record<string, string> = {
  // illumination STARS
  mano: "真",
  hiori: "灯",
  meguru: "巡",
  // L'Antica
  kogane: "鐘",
  mamimi: "摩",
  sakuya: "咲",
  yuika: "結",
  kiriko: "霧",
  // 放课后Climax Girls
  kaho: "穂",
  chiyoko: "巧",
  juri: "樹",
  rinze: "凛",
  natsuha: "夏",
  // ALSTROEMERIA
  amana: "甘",
  tenka: "甜",
  chiyuki: "千",
  // Straylight
  asahi: "朝",
  fuyuko: "冬",
  mei: "愛",
  // noctchill
  toru: "透",
  madoka: "円",
  koito: "糸",
  hinana: "雛",
  // SHHis
  nichika: "日",
  mikoto: "美",
  // CoMETIK
  luca: "路",
  hana: "羽",
  haruki: "羊",
  // 事务员
  hazuki: "葉",
};

/**
 * 她信封上按的那一个字。没登记的角色退回老规矩：中文名最后一个字，再退日文名第一个字
 * （以后加角色不会因为少一行配置就画不出来）。
 */
export function sealCharacterOf(
  letter: Pick<Letter, "character_id" | "character_name" | "character_name_zh">,
): string {
  const fixed = SEAL_CHARACTER[letter.character_id];
  if (fixed) return fixed;

  const zh = letter.character_name_zh?.trim();
  if (zh) return zh.slice(-1);
  return letter.character_name.trim().slice(0, 1);
}

/** How a letter is set, apart from the person it came from. */
export type LetterLook = {
  /** The face the body is set in: 明朝 reads sharp, ゴシック reads plain. */
  font: string;
  weight: number;
  tracking: string;
  /** How much of her colour the ink keeps, in percent — a pastel alone is unreadable. */
  ink: number;
  /** A line's height, which the paper's rules are spaced by. */
  row: number;
  /** The autograph's width in pixels, on a wide screen. */
  signature: number;
  /** Its tilt, in degrees: a signature is not typeset straight. */
  tilt: number;
};

const MINCHO =
  '"Yu Mincho", "Hiragino Mincho ProN", "Noto Serif JP", "Source Han Serif SC", serif';
const GOTHIC = 'var(--font-japanese), "Hiragino Kaku Gothic ProN", "Yu Gothic", sans-serif';

/** How each of them sets a letter: the face, the weight, the space between words, and how
 * much of her colour the ink keeps (a pastel alone is unreadable). 明朝 reads sharp and
 * old-fashioned; ゴシック reads plain, and wide tracking reads distant. */
const BY_PERSON: Record<string, Partial<LetterLook>> = {
  // illumination STARS
  mano: { font: GOTHIC, weight: 400, tracking: "0.04em", ink: 36, row: 34 },
  hiori: { font: MINCHO, weight: 500, tracking: "0.02em", ink: 34, row: 33 },
  meguru: { font: GOTHIC, weight: 500, tracking: "0.015em", ink: 34, row: 34 },
  // L'Antica
  kogane: { font: GOTHIC, weight: 500, tracking: "0.03em", ink: 34, row: 34 },
  mamimi: { font: GOTHIC, weight: 400, tracking: "0.05em", ink: 36, row: 35 },
  sakuya: { font: MINCHO, weight: 500, tracking: "0.02em", ink: 34, row: 33 },
  yuika: { font: GOTHIC, weight: 400, tracking: "0.04em", ink: 36, row: 34 },
  kiriko: { font: MINCHO, weight: 400, tracking: "0.06em", ink: 36, row: 34 },
  // 放課後クライマックスガールズ
  kaho: { font: GOTHIC, weight: 500, tracking: "0.02em", ink: 36, row: 34 },
  chiyoko: { font: GOTHIC, weight: 400, tracking: "0.04em", ink: 36, row: 34 },
  juri: { font: GOTHIC, weight: 500, tracking: "0.03em", ink: 34, row: 33 },
  rinze: { font: MINCHO, weight: 400, tracking: "0.07em", ink: 34, row: 35 },
  natsuha: { font: GOTHIC, weight: 500, tracking: "0.02em", ink: 36, row: 34 },
  // ALSTROEMERIA
  anna: { font: GOTHIC, weight: 400, tracking: "0.05em", ink: 38, row: 34 },
  tenka: { font: GOTHIC, weight: 400, tracking: "0.06em", ink: 38, row: 36 },
  chiyuki: { font: MINCHO, weight: 400, tracking: "0.04em", ink: 36, row: 34 },
  // Straylight
  asahi: { font: GOTHIC, weight: 500, tracking: "0.03em", ink: 32, row: 33 },
  fuyuko: { font: MINCHO, weight: 500, tracking: "0.01em", ink: 30, row: 33 },
  mei: { font: MINCHO, weight: 400, tracking: "0.05em", ink: 34, row: 34 },
  // noctchill
  toru: { font: GOTHIC, weight: 400, tracking: "0.11em", ink: 30, row: 36 },
  madoka: { font: GOTHIC, weight: 500, tracking: "0.02em", ink: 32, row: 33 },
  koito: { font: GOTHIC, weight: 400, tracking: "0.05em", ink: 34, row: 34 },
  hinana: { font: GOTHIC, weight: 500, tracking: "0.02em", ink: 36, row: 34 },
  // SHHis
  nichika: { font: GOTHIC, weight: 500, tracking: "0.015em", ink: 32, row: 33 },
  mikoto: { font: MINCHO, weight: 500, tracking: "0.03em", ink: 32, row: 33 },
  // CoMETIK
  ruka: { font: MINCHO, weight: 500, tracking: "0.03em", ink: 34, row: 33 },
  hana: { font: GOTHIC, weight: 400, tracking: "0.06em", ink: 40, row: 35 },
  haruki: { font: GOTHIC, weight: 500, tracking: "0.02em", ink: 34, row: 34 },
  // 事務員
  hazuki: { font: MINCHO, weight: 400, tracking: "0.05em", ink: 36, row: 34 },
};

const DEFAULT_LOOK: LetterLook = {
  font: GOTHIC,
  weight: 400,
  tracking: "0.03em",
  ink: 36,
  row: 34,
  signature: 120,
  tilt: -2,
};

/** How her letter is set: her own way if she has one. */
export function letterLookOf(characterId: string): LetterLook {
  return { ...DEFAULT_LOOK, ...BY_PERSON[characterId] };
}

const CUE = /\[[a-z][a-z ,'-]*\]\s*/g;
/** Voice cues ([shyly], [whispering]) are for speech, not for paper. */
export function plain(text: string): string {
  return text.replace(CUE, "").trim();
}

/** Her words as the paper shows them: the 呼びかけ, then the body — without the name she
 * used to sign off with, now that the autograph is printed instead. */
export function letterBody(
  segments: { ja: string; zh: string }[],
  names: (string | null | undefined)[],
): { ja: string; zh: string }[] {
  const said = segments.map((s) => ({ ja: plain(s.ja), zh: plain(s.zh) }));
  const bare = names.filter((n): n is string => !!n);
  while (said.length > 1 && bare.some((n) => said[said.length - 1].ja.replace(/。$/, "") === n)) {
    said.pop();
  }
  const last = said[said.length - 1];
  if (last) {
    for (const name of bare) {
      for (const mark of ["", "　", " "]) {
        const tail = mark + name;
        if (last.ja.endsWith(tail)) {
          last.ja = last.ja.slice(0, -tail.length).trimEnd();
          last.zh = last.zh.trimEnd();
        }
      }
    }
  }
  return said;
}


/** The 呼びかけ at the head of a letter, and the rest of that first paragraph when the model
 * wrote them together (「プロデューサーへ。お誕生日おめでとう。…」). */
export function splitGreeting(segment: { ja: string; zh: string } | undefined): {
  greeting: { ja: string; zh: string } | null;
  rest: { ja: string; zh: string } | null;
} {
  if (!segment) return { greeting: null, rest: null };
  const cut = segment.ja.indexOf("。");
  if (cut <= 0 || cut > 11 || !segment.ja.slice(0, cut).endsWith("へ")) {
    return { greeting: segment, rest: null };
  }
  // 中文那头同样只取到第一个句号，跟着日文的称呼走。
  const zhCut = segment.zh.indexOf("。");
  const zhHead = zhCut > 0 && zhCut <= 12 ? segment.zh.slice(0, zhCut + 1) : segment.zh;
  const zhRest = zhCut > 0 && zhCut <= 12 ? segment.zh.slice(zhCut + 1).trim() : "";
  return {
    greeting: { ja: segment.ja.slice(0, cut + 1), zh: zhHead },
    rest: { ja: segment.ja.slice(cut + 1).trim(), zh: zhRest },
  };
}

/** The day a letter came, as 2026年10月22日. */
export function letterDay(at: string): string {
  const d = new Date(at);
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`;
}

/** Her letters, the latest first. */
export async function listLetters(): Promise<Letter[]> {
  return (await json<{ letters: Letter[] }>(await api("/api/letters"))).letters;
}

/** Mark a letter read; it stays in the list, the dot gone. */
export async function markLetterRead(id: string): Promise<void> {
  expectNoContent(await api(`/api/letters/${encodeURIComponent(id)}/read`, { method: "POST" }));
}
