// 收藏的语音（fork）：她说的一句，收进统计页，随时回听。
// 服务端收藏时会把那一份音频复制出来，所以之后给这句「重新生成」、或者删掉整段对话，
// 收藏里听到的还是当初那一版。

import { api, json } from "@/lib/api";
import type { SpeechRef } from "@/lib/messageSpeech";

/** 一条收藏：谁的、她说了什么、哪里能听到。 */
export type VoiceFavorite = {
  id: number;
  character_id: string;
  character_name: string | null;
  color: string | null;
  ja: string;
  zh: string;
  url: string;
  created_at: string;
};

/** 收藏这一句；同一句再收藏还是同一条。 */
export async function favoriteVoice(ref: SpeechRef): Promise<VoiceFavorite> {
  return json(
    await api("/api/voice-favorites", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(ref),
    }),
  );
}

/** 取消一条收藏，连带服务端存的那份音频一起删掉。 */
export async function unfavoriteVoice(id: number): Promise<void> {
  await api(`/api/voice-favorites/${encodeURIComponent(String(id))}`, { method: "DELETE" });
}

/** 所有收藏，新的在前。 */
export async function voiceFavorites(): Promise<VoiceFavorite[]> {
  return json(await api("/api/voice-favorites"));
}
