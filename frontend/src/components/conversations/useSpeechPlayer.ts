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
 */
export function useSpeechPlayer(): SpeechPlay {
  const [asking, setAsking] = useState<string | null>(null);
  const [playing, setPlaying] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const audio = useRef<HTMLAudioElement | null>(null);
  const failing = useRef<number | null>(null);

  // 离开页面时别留一个还在响的元素；`audio` 是这一页自己的，不是全站的。
  useEffect(() => {
    return () => {
      audio.current?.pause();
      audio.current = null;
      if (failing.current !== null) window.clearTimeout(failing.current);
    };
  }, []);

  const stop = useCallback(() => {
    audio.current?.pause();
    setPlaying(null);
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
      setAsking(key);
      void (async () => {
        try {
          const url = await speechUrl(ref);
          if (!audio.current) audio.current = new Audio();
          const element = audio.current;
          element.src = url;
          element.onended = () => setPlaying((now) => (now === key ? null : now));
          await element.play();
          setAsking((now) => (now === key ? null : now));
          setPlaying(key);
        } catch {
          setAsking((now) => (now === key ? null : now));
          setFailed(key);
          if (failing.current !== null) window.clearTimeout(failing.current);
          failing.current = window.setTimeout(() => setFailed((now) => (now === key ? null : now)), 2000);
        }
      })();
    },
    [asking, playing, stop],
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
  const again = useCallback((ref: SpeechRef) => {
    const key = keyOf(ref);
    audio.current?.pause();
    setPlaying(null);
    setFailed(null);
    setAsking(key);
    void (async () => {
      try {
        const url = await respeak(ref);
        if (!audio.current) audio.current = new Audio();
        const element = audio.current;
        element.src = `${url}?r=${Date.now()}`;
        element.onended = () => setPlaying((now) => (now === key ? null : now));
        await element.play();
        setAsking((now) => (now === key ? null : now));
        setPlaying(key);
      } catch {
        setAsking((now) => (now === key ? null : now));
        setFailed(key);
        if (failing.current !== null) window.clearTimeout(failing.current);
        failing.current = window.setTimeout(() => setFailed((now) => (now === key ? null : now)), 2000);
      }
    })();
  }, []);

  return { state, toggle, again };
}
