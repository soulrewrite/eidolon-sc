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
  /** Why she wrote: his birthday, the monthly return of the day they first spoke, or nothing
   * more than an evening. */
  trigger: "birthday" | "anniversary" | "everyday";
  delivered_at: string;
  segments: { ja: string; zh: string }[];
  read: boolean;
};

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
