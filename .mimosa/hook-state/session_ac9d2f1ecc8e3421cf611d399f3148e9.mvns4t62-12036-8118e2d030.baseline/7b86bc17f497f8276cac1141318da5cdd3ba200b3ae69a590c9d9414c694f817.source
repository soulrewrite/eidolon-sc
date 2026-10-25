/** 她说过的每一句话的语音（GLOSSARY.md「消息语音」）：先问后端这句话在存储桶上的地址，
 * 再把地址交给一个 Audio 元素去放。同一句话永远是同一个地址，后端只在第一次有人听的时候合成，
 * 之后所有人拿到的都是桶上那份，浏览器也可以一直留着。 */

import { api, json } from "@/lib/api";

/** 要听的是哪句话：一条消息的第几段（`message`），还是她的一次搭话的第几段（`reach_out`）。
 * 两者分开存，标识符不是一个序列。 */
export type SpeechRef = { kind: "message" | "reach_out"; id: number; segment: number };

/** 这句话在哪听。第一次听要等后端合成，几秒；之后只是问一句地址。 */
export async function speechUrl(ref: SpeechRef): Promise<string> {
  const path =
    ref.kind === "message"
      ? `/api/messages/${ref.id}/speech?segment=${ref.segment}`
      : `/api/reach-outs/${ref.id}/speech?segment=${ref.segment}`;
  return (await json<{ url: string }>(await api(path))).url;
}

/** 这一句重新合成一遍，覆盖桶里那份，返回新的地址。
 * 合成每次都不一样，听到破音就重摇一次。 */
export async function respeak(ref: SpeechRef): Promise<string> {
  const path =
    ref.kind === "message"
      ? `/api/messages/${ref.id}/speech/again?segment=${ref.segment}`
      : `/api/reach-outs/${ref.id}/speech/again?segment=${ref.segment}`;
  return (await json<{ url: string }>(await api(path, { method: "POST" }))).url;
}

/** 消息语音开着没有，记在本机：默认开着，关掉以后气泡上不出现播放键，也不会有声音。
 * 这是每台设备自己的选择（和通话的音质那些不一样，那些跟着账号走）。 */
const SWITCH = "eidolon.messageSpeech";

/** 本机记着的开关。水合之前读不到 localStorage，调用处因此不能拿它做首屏渲染。 */
export function speechSwitchedOn(): boolean {
  try {
    return localStorage.getItem(SWITCH) !== "off";
  } catch {
    return true;
  }
}

/** 记住开关，下一次打开页面照这么来。 */
export function switchSpeech(on: boolean): void {
  try {
    if (on) localStorage.removeItem(SWITCH);
    else localStorage.setItem(SWITCH, "off");
  } catch {
    // 存不了就算了：这一次页面里照样按用户选的来。
  }
}
