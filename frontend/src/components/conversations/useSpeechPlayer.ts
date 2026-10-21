"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { speechUrl, respeak, type SpeechRef } from "@/lib/messageSpeech";

/** 一句话在这台页面上的处境：没在放、正在问地址或合成（`asking`）、在放、这次没放出来（`failed`）。 */
export type SpeechPlay = {
  /** 现在是什么样子，一句话一条。 */
  state: (ref: SpeechRef) => "idle" | "asking" | "playing" | "failed";
  /** 放这句话；正在放同一句就停下来。 */
  toggle: (ref: SpeechRef) => void;
  /** 这一句重新合成一遍再放：合成每次都不一样，听着破音就重摇一次。 */
  again: (ref: SpeechRef) => void;
};

/** 同一个地址的一串字符，用来认出一句话。 */
function keyOf(ref: SpeechRef): string {
  return `${ref.kind}:${ref.id}:${ref.segment}`;
}

/**
 * 消息语音的播放器（GLOSSARY.md「消息语音」）：点一下气泡上那句话前面的音符，她就把这句说出来。
 *
 * 一个页面只有一个 Audio 元素：同时只放一句，点另一句就把上一句停下。第一句要先等后端合成（几秒），
 * 这期间那一条显示转圈；放不出来的那条闪一下「放不出来」，不留着，也不影响别的句子。
 * 放完、停下、离开这一页（或者这一页换了对话）都把音频收起来，不留一个还在响的元素在后台。
 *
 * 已经问到的地址记在这一页里（`known`）：同一句再点一次不再问后端，直接从浏览器缓存里放，
 * 也就不该再转一次圈。桶上的语音是 `immutable` 的，地址不变内容就不变，缓存这份是安全的。
 */
export function useSpeechPlayer(): SpeechPlay {
  const [asking, setAsking] = useState<string | null>(null);
  const [playing, setPlaying] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const audio = useRef<HTMLAudioElement | null>(null);
  /** 这一页已经问到过的地址，一句话一条。 */
  const known = useRef(new Map<string, string>());
  /** 音频元素现在装的是哪个地址，免得同一句再点一次又去设一遍 src（那会重新拉一遍）。 */
  const loaded = useRef<string | null>(null);
  const failing = useRef<number | null>(null);

  // 离开页面时别留一个还在响的元素；`audio` 是这一页自己的，不是全站的。
  useEffect(() => {
    return () => {
      audio.current?.pause();
      audio.current = null;
      loaded.current = null;
      known.current.clear();
      if (failing.current !== null) window.clearTimeout(failing.current);
    };
  }, []);

  const stop = useCallback(() => {
    audio.current?.pause();
    setPlaying(null);
  }, []);

  const fail = useCallback((key: string) => {
    setAsking((now) => (now === key ? null : now));
    setFailed(key);
    if (failing.current !== null) window.clearTimeout(failing.current);
    failing.current = window.setTimeout(() => setFailed((now) => (now === key ? null : now)), 2000);
  }, []);

  /** 把 `url` 放起来；地址变了才换源（重摇就是换地址），同一句重放只是从头再放。 */
  const play = useCallback(async (key: string, url: string) => {
    if (!audio.current) audio.current = new Audio();
    const element = audio.current;
    if (loaded.current !== url) {
      element.src = url;
      loaded.current = url;
    }
    element.currentTime = 0;
    element.onended = () => setPlaying((now) => (now === key ? null : now));
    await element.play();
    setPlaying(key);
  }, []);

  const toggle = useCallback(
    (ref: SpeechRef) => {
      const key = keyOf(ref);
      if (playing === key) {
        stop();
        return;
      }
      // 正等着同一句：再点一下就是不等了。
      if (asking === key) {
        setAsking(null);
        return;
      }
      audio.current?.pause();
      setPlaying(null);
      setFailed(null);
      // 这一句问过了：不再问后端，也不转圈。
      const asked = known.current.get(key);
      if (asked !== undefined) {
        void play(key, asked).catch(() => {
          known.current.delete(key);
          fail(key);
        });
        return;
      }
      setAsking(key);
      void (async () => {
        try {
          const url = await speechUrl(ref);
          known.current.set(key, url);
          await play(key, url);
          setAsking((now) => (now === key ? null : now));
        } catch {
          fail(key);
        }
      })();
    },
    [asking, playing, stop, play, fail],
  );

  const state = useCallback(
    (ref: SpeechRef) => {
      const key = keyOf(ref);
      if (playing === key) return "playing" as const;
      if (asking === key) return "asking" as const;
      if (failed === key) return "failed" as const;
      return "idle" as const;
    },
    [asking, playing, failed],
  );

  // 重新合成并放。地址和原来一样（同一句话同一个地址），桶上那份被覆盖了，
  // 所以带一个时间戳绕开浏览器和 CDN 的缓存 —— 它们把这份当成 immutable 存着。
  const again = useCallback(
    (ref: SpeechRef) => {
      const key = keyOf(ref);
      audio.current?.pause();
      setPlaying(null);
      setFailed(null);
      setAsking(key);
      void (async () => {
        try {
          const url = `${await respeak(ref)}?r=${Date.now()}`;
          known.current.set(key, url);
          await play(key, url);
          setAsking((now) => (now === key ? null : now));
        } catch {
          fail(key);
        }
      })();
    },
    [play, fail],
  );

  return { state, toggle, again };
}
