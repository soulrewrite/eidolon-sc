"use client";

// 收藏的语音（fork）：统计页的一节。按角色分组，点一下放，右侧可以取消收藏。
// 音频是服务端收藏时复制出来的那一份，和聊天里「重新生成」无关，删掉对话也还在。

import { useEffect, useRef, useState } from "react";

import { MarkedAvatar } from "@/components/app/MarkedAvatar";
import { Button } from "@/components/ui/button";
import { copy } from "@/i18n";
import { Ja } from "@/theme/Ja";
import type { Character } from "@/lib/api";
import { CloseIcon, FavoriteIcon, PlayIcon, SpeechPauseIcon } from "@/theme/icons";
import type { VoiceFavorite } from "@/lib/voiceFavorites";
import { cn } from "@/lib/utils";

const t = copy.settings.stats.favorites;

/** 按角色分组：角色顺序照偶像表（`characters` 的顺序），组内新的在前。 */
function groups(
  favorites: VoiceFavorite[], characters: Character[]
): { character: Character | undefined; lines: VoiceFavorite[] }[] {
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
    .map(([id, lines]) => ({ character: byId.get(id), lines }));
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
  const [playing, setPlaying] = useState<number | null>(null);
  const audio = useRef<HTMLAudioElement | null>(null);

  // 一页只有一个音频元素：放另一句就停下上一句；离开页面不留一个还在响的。
  useEffect(() => {
    return () => {
      audio.current?.pause();
      audio.current = null;
    };
  }, []);

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

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-header">{t.title}</h2>
      {favorites.length === 0 ? (
        <p className="text-meta text-muted-foreground">{t.hint}</p>
      ) : (
        <div className="flex flex-col gap-4">
          {groups(favorites, characters).map(({ character, lines }) => (
            <div key={character?.id ?? lines[0].character_id} className="flex flex-col gap-2">
              <div className="flex items-center gap-2">
                <MarkedAvatar
                  name={character?.name ?? lines[0].character_name ?? ""}
                  src={character?.avatar_url ?? null}
                  size="sm"
                />
                <span className="text-body">{character?.name ?? lines[0].character_name}</span>
                <span className="text-meta text-muted-foreground">{t.count(lines.length)}</span>
              </div>
              <ul className="flex flex-col gap-1">
                {lines.map((line) => (
                  <li key={line.id} className="flex items-start gap-2 rounded-md px-1 py-1 hover:bg-accent/50">
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      className={cn(
                        "mt-px shrink-0 text-muted-foreground",
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
                    </Button>
                    <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                      <span className="text-japanese-line">
                        <Ja>{line.ja}</Ja>
                      </span>
                      {line.zh && (
                        <span className="text-subtitle text-muted-foreground">{line.zh}</span>
                      )}
                    </span>
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      className="shrink-0 text-muted-foreground"
                      aria-label={t.remove}
                      onClick={() => onRemove(line.id)}
                    >
                      <CloseIcon aria-hidden className="size-3.5" />
                    </Button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
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
