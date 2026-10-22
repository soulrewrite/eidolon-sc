// Her letters (GLOSSARY.md「信」, fork): what she would not say to the producer's face, left in
// the announcements one evening. Only a character he is close to writes them, one every few
// days, in the evening — or on a day that calls for it.

import { api, expectNoContent, json } from "@/lib/api";

/** One letter as the user reads it: her words, in Japanese with the Chinese subtitle under
 * each line, and the paper it came on (her call background, when she has one). */
export type Letter = {
  id: string;
  character_id: string;
  character_name: string;
  character_name_zh: string | null;
  /** Her call background, which the letter is written on; null when she has none. */
  background_url: string | null;
  /** Why she wrote: his birthday, the monthly return of the day they first spoke, or nothing
   * more than an evening. */
  trigger: "birthday" | "anniversary" | "everyday";
  delivered_at: string;
  segments: { ja: string; zh: string }[];
  read: boolean;
};

/** Her letters, the latest first. */
export async function listLetters(): Promise<Letter[]> {
  return (await json<{ letters: Letter[] }>(await api("/api/letters"))).letters;
}

/** Mark a letter read; it stays in the list, the dot gone. */
export async function markLetterRead(id: string): Promise<void> {
  expectNoContent(await api(`/api/letters/${encodeURIComponent(id)}/read`, { method: "POST" }));
}
