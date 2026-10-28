"use client";

// 信（fork）：统计页的一节，样子照着「收藏的语音」——按角色分组、可折叠，顶部能按时间筛选，
// 点一行就摊开同一张信纸（`LetterSheet`）。信本来只躺在公告弹窗里，翻旧的很不方便。

import { useEffect, useMemo, useState } from "react";
import { ChevronDownIcon } from "lucide-react";

import { MarkedAvatar } from "@/components/app/MarkedAvatar";
import { LetterSheet } from "@/components/app/LetterSheet";
import { copy } from "@/i18n";
import type { Character } from "@/lib/api";
import { groupLetters, listLetters, markLetterRead, type Letter } from "@/lib/letters";
import { cn } from "@/lib/utils";

const t = copy.settings.stats.letters;

/** 顶部的日期筛选：全部、近 7 天、近 30 天。 */
type Range = "all" | "week" | "month";

const RANGES: Range[] = ["all", "week", "month"];
const DAYS: Record<Range, number | null> = { all: null, week: 7, month: 30 };

export function LetterArchive({ characters }: { characters: Character[] }) {
  const [letters, setLetters] = useState<Letter[] | null>(null);
  const [range, setRange] = useState<Range>("all");
  const [open, setOpen] = useState<Set<string>>(() => new Set());
  const [reading, setReading] = useState<Letter | null>(null);

  useEffect(() => {
    let cancelled = false;
    void listLetters().then(
      (all) => !cancelled && setLetters(all),
      () => !cancelled && setLetters([]),
    );
    return () => {
      cancelled = true;
    };
  }, []);

  // 默认只展开最近那一封所在的组，其余收起来。
  useEffect(() => {
    if (!letters?.length) return;
    setOpen((current) => {
      if (current.size > 0) return current;
      const newest = [...letters].sort(
        (a, b) => Date.parse(b.delivered_at) - Date.parse(a.delivered_at),
      )[0];
      return newest ? new Set([newest.character_id]) : current;
    });
  }, [letters]);

  const filtered = useMemo(() => {
    if (!letters) return [];
    const days = DAYS[range];
    if (days === null) return letters;
    const since = Date.now() - days * 86_400_000;
    return letters.filter((letter) => Date.parse(letter.delivered_at) >= since);
  }, [letters, range]);

  const grouped = useMemo(() => groupLetters(filtered, characters), [filtered, characters]);

  if (letters === null) return null;

  const shift = (characterId: string) =>
    setOpen((current) => {
      const next = new Set(current);
      if (next.has(characterId)) next.delete(characterId);
      else next.add(characterId);
      return next;
    });

  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-header">{t.title}</h2>
        {letters.length > 0 && (
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
      {letters.length === 0 ? (
        <p className="text-meta text-muted-foreground">{t.hint}</p>
      ) : filtered.length === 0 ? (
        <p className="text-meta text-muted-foreground">{t.emptyRange}</p>
      ) : (
        <div className="flex flex-col gap-2">
          {grouped.map(({ key, character, letters: hers }) => {
            const name = character?.name ?? hers[0]?.character_name ?? "";
            const expanded = open.has(key);
            return (
              <div key={key} className="flex flex-col gap-1">
                <button
                  type="button"
                  aria-expanded={expanded}
                  aria-label={t.expand(name, hers.length)}
                  className="flex items-center gap-2 rounded-md px-1 py-1 text-left hover:bg-accent/50"
                  onClick={() => shift(key)}
                >
                  <MarkedAvatar name={name} src={character?.avatar_url ?? null} size="sm" />
                  <span className="text-body">{name}</span>
                  <span className="text-meta text-muted-foreground tabular-nums">
                    {t.count(hers.length)}
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
                    {hers.map((letter) => (
                      <li key={letter.id}>
                        <button
                          type="button"
                          className="flex w-full items-center gap-2 rounded-md px-1 py-1 text-left text-body hover:bg-accent/50"
                          onClick={() => {
                            setReading(letter);
                            if (!letter.read) void markLetterRead(letter.id).catch(() => {});
                          }}
                        >
                          <span aria-hidden className="font-serif" style={{ color: letter.color }}>
                            ✉
                          </span>
                          <span className="tabular-nums text-meta text-muted-foreground">
                            {new Date(letter.delivered_at).toLocaleDateString("zh-CN")}
                          </span>
                          <span className="text-meta text-muted-foreground">
                            {letter.trigger === "birthday"
                              ? copy.conversationList.letterForBirthday
                              : letter.trigger === "anniversary"
                                ? copy.conversationList.letterForAnniversary
                                : ""}
                          </span>
                          {!letter.read && <span className="text-meta text-muted-foreground">{t.unread}</span>}
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
      <LetterSheet
        letter={reading}
        onClose={() => setReading(null)}
        onRead={(letter) =>
          setLetters((current) =>
            current?.map((one) => (one.id === letter.id ? { ...one, read: true } : one)) ?? current,
          )
        }
      />
    </section>
  );
}
