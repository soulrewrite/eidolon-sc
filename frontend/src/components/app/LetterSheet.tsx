"use client";

import { useEffect } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { copy } from "@/i18n";
import type { Letter } from "@/lib/letters";

import { Ja } from "@/theme/Ja";

const t = copy.conversationList;

/** The day a letter came, as 10月22日（木）. */
export function letterDay(at: string): string {
  const d = new Date(at);
  return `${d.getMonth() + 1}月${d.getDate()}日`;
}

/** Why she wrote, when it is not just an evening. */
function reasonOf(letter: Letter): string | null {
  if (letter.trigger === "birthday") return t.letterForBirthday;
  if (letter.trigger === "anniversary") return t.letterForAnniversary;
  return null;
}

/**
 * One of her letters (GLOSSARY.md「信」, fork), opened from the announcements: her call
 * background shows through, dimmed, and the words sit on a sheet of paper over it — Japanese
 * in the serif face the app keeps for her replies, the Chinese subtitle under each line, her
 * name signed at the end. Opening one marks it read.
 */
export function LetterSheet({
  letter,
  onClose,
  onRead,
}: {
  letter: Letter | null;
  onClose: () => void;
  onRead: (letter: Letter) => void;
}) {
  useEffect(() => {
    if (letter && !letter.read) onRead(letter);
    // 只在换了一封信时记一次；同一个对象重渲染不再调。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [letter?.id]);

  return (
    <Dialog open={letter !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        showCloseButton={false}
        className="max-h-[calc(100dvh-2rem)] overflow-hidden p-0 sm:max-w-lg"
      >
        {letter && (
          <div className="relative flex max-h-[calc(100dvh-2rem)] flex-col">
            {letter.background_url && (
              // 她的通话背景透出来，压暗、去色，好让字压得住。
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={letter.background_url}
                alt=""
                aria-hidden
                className="absolute inset-0 size-full object-cover opacity-25 saturate-50"
              />
            )}
            <div className="relative flex max-h-[calc(100dvh-2rem)] flex-col">
              <DialogHeader className="px-6 pt-6 pb-2">
                <p className="flex items-center gap-2 text-meta text-muted-foreground tabular-nums">
                  {letterDay(letter.delivered_at)}
                  {reasonOf(letter) && <Badge variant="secondary">{reasonOf(letter)}</Badge>}
                </p>
                <DialogTitle className="font-serif text-title">
                  <Ja>{letter.segments[0]?.ja ?? ""}</Ja>
                </DialogTitle>
              </DialogHeader>
              <div className="min-h-0 flex-1 overflow-y-auto px-6 pb-2">
                <div className="flex flex-col gap-4 font-serif">
                  {letter.segments.slice(1).map((segment, i) => (
                    <div key={i} className="flex flex-col gap-1">
                      <p className="text-japanese-line leading-relaxed">
                        <Ja>{segment.ja}</Ja>
                      </p>
                      {segment.zh && (
                        <p className="text-subtitle text-muted-foreground">{segment.zh}</p>
                      )}
                    </div>
                  ))}
                </div>
                <p className="mt-6 text-right font-serif text-body text-muted-foreground">
                  {letter.character_name_zh ?? letter.character_name}
                </p>
              </div>
              <DialogFooter className="flex-row justify-end px-6 pt-2 pb-6">
                <Button variant="ghost" onClick={onClose}>
                  {copy.common.close}
                </Button>
              </DialogFooter>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

/** A letter in the announcements list: a line of paper with her name and the day, and a dot
 * while it is unread. */
export function LetterRow({
  letter,
  onClick,
}: {
  letter: Letter;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex w-full items-center gap-3 rounded-[min(var(--radius-md),10px)] px-2 py-2 text-left",
        "transition-colors hover:bg-accent",
      )}
    >
      <span aria-hidden className="font-serif text-body text-muted-foreground">
        ✉
      </span>
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="flex items-center gap-2 text-body">
          <span className="truncate font-serif">{letter.character_name}</span>
          {reasonOf(letter) && <Badge variant="outline">{reasonOf(letter)}</Badge>}
        </span>
        <span className="text-meta text-muted-foreground tabular-nums">
          {letterDay(letter.delivered_at)}
        </span>
      </span>
      {!letter.read && <span aria-hidden className="size-1.5 shrink-0 rounded-full bg-foreground" />}
    </button>
  );
}
