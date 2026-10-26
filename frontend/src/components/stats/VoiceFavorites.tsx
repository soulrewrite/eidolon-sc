"use client";

// 收藏的语音（fork）：统计页的一节。按角色分组、可折叠，顶部能按时间筛选；
// 点一下放，右侧可以取消收藏。音频是服务端收藏时复制出来的那一份，
// 和聊天里「重新生成」无关，删掉对话也还在。

import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDownIcon } from "lucide-react";

import { MarkedAvatar } from "@/components/app/MarkedAvatar";
import { copy } from "@/i18n";
import { Ja } from "@/theme/Ja";
import type { Character } from "@/lib/api";
import { CloseIcon, FavoriteIcon, PlayIcon, SpeechPauseIcon } from "@/theme/icons";
import type { VoiceFavorite } from "@/lib/voiceFavorites";
import { cn } from "@/lib/utils";

const t = copy.settings.stats.favorites;

/** 顶部的日期筛选：全部、近 7 天、近 30 天。 */
type Range = "all" | "week" | "month";

const RANGES: Range[] = ["all", "week", "month"];
const DAYS: Record<Range, number | null> = { all: null, week: 7, month: 30 };

/** 按角色分组：角色顺序照偶像表（`characters` 的顺序），组内新的在前。 */
function groups(
  favorites: VoiceFavorite[], characters: Character[]
): { key: string; character: Character | undefined; lines: VoiceFavorite[] }[] {
  const byId = new Map(characters.map((c) => [c.id, c]));
  const grouped = new Map<string, VoiceFavorite[]>();
  for (const favorite of favorites) {
    const lines = grouped.get(favorite.character_id) ?? [];
    lines.push(favorite);
    grouped.set(favorite.character_id, lines);
  }
  return [...grouped.entries()]
    .sort(([a], [b]) => {
      const left = byId.get(a)?.idol_id ?? Number.MAX_SAFE_INTEGER;
      const right = byId.get(b)?.idol_id ?? Number.MAX_SAFE_INTEGER;
      return left - right;
    })
    .map(([id, lines]) => ({ key: id, character: byId.get(id), lines }));
}

export function VoiceFavorites({
  favorites,
  characters,
  onRemove,
}: {
  favorites: VoiceFavorite[];
  characters: Character[];
  onRemove: (id: number) => void;
}) {
  const [range, setRange] = useState<Range>("all");
  const [playing, setPlaying] = useState<number | null>(null);
  const audio = useRef<HTMLAudioElement | null>(null);
  // 默认只展开最近收藏的那一组：其余收起来，一屏就能看到都有谁。
  const [open, setOpen] = useState<Set<string>>(() => new Set());

  // 一页只有一个音频元素：放另一句就停下上一句；离开页面不留一个还在响的。
  useEffect(() => {
    return () => {
      audio.current?.pause();
      audio.current = null;
    };
  }, []);

  useEffect(() => {
    setOpen((current) => {
      if (current.size > 0) return current;
      const newest = [...favorites].sort(
        (a, b) => Date.parse(b.created_at) - Date.parse(a.created_at),
      )[0];
      return newest ? new Set([newest.character_id]) : current;
    });
  }, [favorites]);

  const filtered = useMemo(() => {
    const days = DAYS[range];
    if (days === null) return favorites;
    const since = Date.now() - days * 86_400_000;
    return favorites.filter((favorite) => Date.parse(favorite.created_at) >= since);
  }, [favorites, range]);

  const grouped = useMemo(() => groups(filtered, characters), [filtered, characters]);

  const toggle = (favorite: VoiceFavorite) => {
    if (playing === favorite.id) {
      audio.current?.pause();
      setPlaying(null);
      return;
    }
    if (!audio.current) audio.current = new Audio();
    const element = audio.current;
    element.src = favorite.url;
    element.onended = () => setPlaying(null);
    element.play().then(
      () => setPlaying(favorite.id),
      () => setPlaying(null),
    );
  };

  const shift = (characterId: string) => {
    setOpen((current) => {
      const next = new Set(current);
      if (next.has(characterId)) next.delete(characterId);
      else next.add(characterId);
      return next;
    });
  };

  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-header">{t.title}</h2>
        {favorites.length > 0 && (
          <div className="flex items-center gap-1" role="group" aria-label={t.rangeLabel}>
            {RANGES.map((option) => (
              <button
                key={option}
                type="button"
                aria-pressed={range === option}
                className={cn(
                  "rounded-full px-2.5 py-1 text-meta transition-colors",
                  range === option
                    ? "bg-foreground text-background"
                    : "bg-muted text-muted-foreground hover:bg-accent hover:text-foreground",
                )}
                onClick={() => setRange(option)}
              >
                {t.ranges[option]}
              </button>
            ))}
            <span className="ml-1 text-meta text-muted-foreground tabular-nums">
              {t.count(filtered.length)}
            </span>
          </div>
        )}
      </div>
      {favorites.length === 0 ? (
        <p className="text-meta text-muted-foreground">{t.hint}</p>
      ) : filtered.length === 0 ? (
        <p className="text-meta text-muted-foreground">{t.emptyRange}</p>
      ) : (
        <div className="flex flex-col gap-2">
          {grouped.map(({ key, character, lines }) => {
            const name = character?.name ?? lines[0].character_name ?? "";
            const expanded = open.has(key);
            return (
              <div key={key} className="flex flex-col gap-1">
                <button
                  type="button"
                  aria-expanded={expanded}
                  aria-label={t.expand(name, lines.length)}
                  className="flex items-center gap-2 rounded-md px-1 py-1 text-left hover:bg-accent/50"
                  onClick={() => shift(key)}
                >
                  <MarkedAvatar name={name} src={character?.avatar_url ?? null} size="sm" />
                  <span className="text-body">{name}</span>
                  <span className="text-meta text-muted-foreground tabular-nums">
                    {t.count(lines.length)}
                  </span>
                  <ChevronDownIcon
                    aria-hidden
                    className={cn(
                      "ml-auto size-4 text-muted-foreground transition-transform duration-200",
                      expanded && "rotate-180",
                    )}
                  />
                </button>
                {expanded && (
                  <ul className="flex flex-col gap-1">
                    {lines.map((line) => (
                      <li
                        key={line.id}
                        className="flex items-start gap-2 rounded-md px-1 py-1 hover:bg-accent/50"
                      >
                        <button
                          type="button"
                          className={cn(
                            "mt-px flex size-6 shrink-0 items-center justify-center rounded-md text-muted-foreground",
                            "transition-colors hover:bg-accent hover:text-foreground",
                            playing === line.id && "bg-accent text-foreground",
                          )}
                          aria-label={playing === line.id ? t.stop : t.play}
                          aria-pressed={playing === line.id}
                          onClick={() => toggle(line)}
                        >
                          {playing === line.id ? (
                            <SpeechPauseIcon aria-hidden className="size-3.5 fill-current" />
                          ) : (
                            <PlayIcon aria-hidden className="size-3.5" />
                          )}
                        </button>
                        <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                          <span className="text-japanese-line">
                            <Ja>{line.ja}</Ja>
                          </span>
                          {line.zh && (
                            <span className="text-subtitle text-muted-foreground">{line.zh}</span>
                          )}
                        </span>
                        <button
                          type="button"
                          className="mt-px flex size-6 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                          aria-label={t.remove}
                          onClick={() => onRemove(line.id)}
                        >
                          <CloseIcon aria-hidden className="size-3.5" />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            );
          })}
        </div>
      )}
      {favorites.length > 0 && (
        <p className="flex items-center gap-1 text-meta text-muted-foreground">
          <FavoriteIcon aria-hidden className="size-3" />
          {t.hint}
        </p>
      )}
    </section>
  );
}
