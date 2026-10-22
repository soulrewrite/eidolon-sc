"use client";

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogTitle } from "@/components/ui/dialog";
import { useIsMobile } from "@/hooks/use-mobile";
import { copy } from "@/i18n";
import {
  letterBody,
  letterDay,
  letterLookOf,
  splitGreeting,
  type Letter,
  type LetterLook,
} from "@/lib/letters";
import { cn } from "@/lib/utils";
import { Ja } from "@/theme/Ja";

const t = copy.conversationList;

/** Why she wrote, when it is not just an evening. */
function reasonOf(letter: Letter): string | null {
  if (letter.trigger === "birthday") return t.letterForBirthday;
  if (letter.trigger === "anniversary") return t.letterForAnniversary;
  return null;
}

/** Her colour mixed into dark ink: a pastel on its own cannot be read. */
function ink(color: string, percent: number): string {
  return `color-mix(in srgb, ${color} ${percent}%, #2f2620)`;
}

/**
 * A sheet of her paper: her call background under a wash of paper colour, ruled, with a margin
 * line down the left. `row` is both the line height and the rule spacing, so the words sit on
 * the rules.
 */
function Sheet({
  letter,
  look,
  row,
  compact,
  children,
  cardUrl,
  wash = 0.55,
}: {
  letter: Letter;
  look: LetterLook;
  row: number;
  compact: boolean;
  children: React.ReactNode;
  /** 她的卡面，压在纸的右上角（信封用的那张）；null 时不放。 */
  cardUrl?: string | null;
  /** How much paper colour covers her background; the less, the more of her shows. */
  wash?: number;
}) {
  return (
    <div
      className="relative overflow-hidden rounded-[12px] sm:min-w-0 sm:flex-1 sm:rounded-[3px]"
      style={{
        padding: compact ? "22px 16px 18px 34px" : "30px 34px 22px 54px",
        // 纸压在桌上：内圈一道极淡的暗线是纸的厚度，外面那层投影是纸离桌面的那点距离。
        boxShadow: compact
          ? "0 1px 0 rgba(255, 255, 255, .55) inset, 0 0 0 1px rgba(122, 98, 64, .12) inset, 0 16px 30px -18px rgba(0, 0, 0, .6)"
          : "0 1px 0 rgba(255, 255, 255, .55) inset, 0 0 0 1px rgba(122, 98, 64, .13) inset, 0 34px 64px -30px rgba(0, 0, 0, .7)",
        color: ink(letter.color, look.ink),
        fontFamily: look.font,
        fontWeight: look.weight,
        letterSpacing: look.tracking,
        // 纸是半透的，她的背景会透上来；字靠这圈柔光从背景里浮出来。
        textShadow: "0 1px 2px rgba(255, 255, 255, .85), 0 0 2px rgba(255, 255, 255, .6)",
        // 横线按这个间距画，正文行高也是它——字才压得在线上。
        "--row": `${row}px`,
      } as React.CSSProperties}
    >
      {letter.background_url && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={letter.background_url}
          alt=""
          aria-hidden
          className="absolute inset-0 size-full object-cover"
          style={{ opacity: 0.74, filter: "saturate(.72) contrast(.9)" }}
        />
      )}
      <div aria-hidden className="absolute inset-0" style={{ background: `rgba(252, 248, 238, ${wash})` }} />
      {/* 纸纤维：两层几乎看不见的斜纹，只在近处让纸不像一块平涂的色块。 */}
      <div
        aria-hidden
        className="absolute inset-0"
        style={{
          backgroundImage:
            "repeating-linear-gradient(94deg, rgba(122, 98, 64, .035) 0 1px, transparent 1px 4px), repeating-linear-gradient(2deg, rgba(122, 98, 64, .022) 0 1px, transparent 1px 7px)",
        }}
      />
      <div
        aria-hidden
        className="absolute inset-0"
        style={{
          backgroundImage:
            "repeating-linear-gradient(to bottom, transparent 0, transparent calc(var(--row) - 1px), rgba(122, 99, 71, .2) calc(var(--row) - 1px), rgba(122, 99, 71, .2) var(--row))",
          backgroundPosition: compact ? "0 22px" : "0 30px",
          backgroundSize: "100% var(--row)",
        }}
      />
      {/* 左侧那条竖线 */}
      <div
        aria-hidden
        className="absolute inset-y-0 w-px opacity-50"
        style={{
          left: compact ? 24 : 40,
          background: `color-mix(in srgb, ${letter.color} 60%, rgba(150,52,52,.55))`,
        }}
      />
      <div className="relative" style={cardUrl ? { paddingRight: compact ? 0 : 128 } : undefined}>
        {children}
      </div>
      {cardUrl && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={cardUrl}
          alt=""
          aria-hidden
          className="absolute top-6 right-6 hidden object-cover sm:block"
          style={{
            width: 104,
            height: 146,
            borderRadius: 3,
            boxShadow: "0 6px 16px -8px rgba(0, 0, 0, .5), 0 0 0 1px rgba(255, 255, 255, .6)",
          }}
        />
      )}
    </div>
  );
}


/**
 * The envelope a letter arrives in (fork): her card art behind it, blurred, and a cream
 * envelope sealed in her colour. 「拆开」 opens the letter; the paper is behind it.
 */
function EnvelopeView({
  letter,
  art,
  onOpen,
}: {
  letter: Letter;
  art: string;
  onOpen: () => void;
}) {
  return (
    <div className="absolute inset-0 z-[5] flex flex-col items-center justify-center gap-7 overflow-hidden">
      <div
        aria-hidden
        className="absolute inset-0"
        style={{
          backgroundImage: `url(${art})`,
          backgroundSize: "cover",
          backgroundPosition: "center",
          filter: "blur(28px) saturate(.88) brightness(.72)",
          transform: "scale(1.1)",
        }}
      />
      <div
        aria-hidden
        className="absolute inset-0"
        style={{ background: "linear-gradient(180deg, rgba(20, 16, 14, .5), rgba(20, 16, 14, .7))" }}
      />
      <div
        className="relative shrink-0"
        style={{
          width: "min(86vw, 460px)",
          aspectRatio: "460 / 310",
          borderRadius: 7,
          background: "linear-gradient(180deg, #f8f4ea, #eee6d5)",
          boxShadow:
            "0 34px 70px -28px rgba(0, 0, 0, .8), 0 0 0 1px rgba(120, 96, 64, .2) inset",
        }}
      >
        {/* 上翻盖 */}
        <div
          aria-hidden
          className="absolute inset-0"
          style={{
            clipPath: "polygon(0 0, 100% 0, 50% 55%)",
            background: "linear-gradient(180deg, #fffdf7 0%, #f8f2e4 72%, #efe7d5 100%)",
          }}
        />
        {/* 两道折痕 */}
        <svg viewBox="0 0 460 310" preserveAspectRatio="none" className="absolute inset-0 size-full" aria-hidden>
          <path d="M0 0 L230 170 L460 0" fill="none" stroke="rgba(120, 96, 64, .22)" strokeWidth="1" />
        </svg>
        {/* 蜡封：她的颜色 */}
        <div
          className="absolute top-[53%] left-1/2 flex size-[76px] -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full font-serif text-[26px]"
          style={{
            background: `radial-gradient(circle at 34% 28%, #fff6b8, ${letter.color} 52%, #b39600 100%)`,
            color: "#3a2f00",
            boxShadow: "0 4px 10px rgba(0, 0, 0, .4), 0 0 0 2px rgba(255, 255, 255, .28) inset",
          }}
        >
          ✉
        </div>
        {/* 地址线 */}
        <div className="absolute bottom-9 left-9 flex flex-col gap-2.5" aria-hidden>
          {[168, 132, 96].map((width) => (
            <div key={width} style={{ height: 1, width, background: "rgba(90, 70, 45, .3)" }} />
          ))}
        </div>
        <div className="absolute right-9 bottom-7 font-serif text-[15px] tracking-wide" style={{ color: "#43331f" }}>
          {letter.character_name} より
        </div>
      </div>
      <button
        type="button"
        onClick={onOpen}
        className="relative rounded-full bg-black/45 px-8 py-3 text-sm text-white backdrop-blur-sm transition-colors hover:bg-black/55"
      >
        {t.letterOpen}
      </button>
    </div>
  );
}

/**
 * One of her letters (GLOSSARY.md「信」, fork): her call background under the paper, Japanese
 * set on the rules, the Chinese on a second sheet of the same paper, her autograph at the foot.
 * The face, the ink and the leading follow who wrote it — 明朝 for the ones with an edge,
 * wide-tracked ゴシック for the ones who leave space between words.
 *
 * On a phone the paper fills the screen and everything steps down a size; the rules keep lining
 * up with the words. Opening one marks it read.
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
  const compact = useIsMobile();
  const [opened, setOpened] = useState(false);
  const sealed = Boolean(letter?.envelope_url) && !opened;
  const look = letter ? letterLookOf(letter.character_id) : null;
  const row = look ? (compact ? Math.round(look.row * 0.9) : look.row) : 34;
  const body = letter
    ? letterBody(letter.segments, [letter.character_name, letter.character_name_zh])
    : [];
  // 模型有时把「プロデューサーへ。」和正文写在同一段里，拆开再排。
  const { greeting, rest: tail } = splitGreeting(body[0]);
  const rest = [...(tail && tail.ja ? [tail] : []), ...body.slice(1)];

  useEffect(() => {
    setOpened(false);
  }, [letter?.id]);

  useEffect(() => {
    if (letter && !letter.read) onRead(letter);
    // 只在换了一封信时记一次；同一个对象重渲染不再调。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [letter?.id]);

  return (
    <Dialog open={letter !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        showCloseButton={false}
        // 桌面：她的通话背景铺满弹层，只压一点暗，纸是米白实底压在上面（DESIGN.md「The Letter Desk Rule」）。
        // 背景挂在滚动容器自己身上（background-attachment 默认 scroll），滚动正文时不会跟着跑。
        // 手机上纸铺满整屏，这张图看不见，行为不变。
        style={
          letter?.background_url
            ? {
                backgroundImage: `linear-gradient(180deg, rgba(20, 16, 14, .18), rgba(20, 16, 14, .34)), url(${letter.background_url})`,
                backgroundSize: "cover, cover",
                backgroundPosition: "center, center",
              }
            : undefined
        }
        className={cn(
          "no-scrollbar gap-0 overflow-y-auto p-0",
          // 手机：整屏。四边贴住，别用 100vw——它把滚动条那点宽度也算进去，会横向溢出。
          "max-sm:inset-0 max-sm:top-0 max-sm:left-0 max-sm:h-auto max-sm:w-auto",
          "max-sm:max-w-none max-sm:translate-x-0 max-sm:translate-y-0 max-sm:rounded-none",
          "max-sm:bg-transparent max-sm:ring-0",
          // 桌面：一张压暗的桌上放两张纸。底色是自己的场景色（深色模式按 The Night Edge Rule 高一档），
          // 纸的颜色、边和投影都在 Sheet 里，这里只管桌面和桌上的字。
          "sm:max-h-[calc(100dvh-2rem)] sm:max-w-4xl sm:rounded-xl sm:bg-letter-scene sm:text-letter-scene-ink",
          // 打开时像把纸展开：从上面压开一点，同时淡入。
          "motion-safe:data-[state=open]:animate-letter-unfold",
          // 信封那一层是绝对定位的，纸还没渲染时弹窗没有内容高度，得自己撑开。
          sealed && "h-[min(88dvh,780px)] sm:h-[min(86dvh,720px)] sm:max-h-none",
        )}
      >
        {letter && sealed && letter.envelope_url && (
          <EnvelopeView letter={letter} art={letter.envelope_url} onOpen={() => setOpened(true)} />
        )}
        {letter && look && greeting && !sealed && (
          // 两张纸等高：中文那页通常短一截，多出来的横线就当还没写到的信纸，桌面不会空一块。
          // 手机也留一圈边：她的背景在纸外露出一点，纸是圆角的。
          <div className="relative flex flex-col gap-3 p-4 sm:flex-row sm:items-stretch sm:gap-6 sm:p-6">
            <Sheet letter={letter} look={look} row={row} compact={compact} cardUrl={letter.envelope_url}>
              <div
                className="flex items-baseline justify-end gap-2 tabular-nums"
                style={{
                  lineHeight: "var(--row)",
                  fontSize: compact ? 11.5 : 12.5,
                  letterSpacing: ".07em",
                  color: ink(letter.color, 26),
                }}
              >
                {reasonOf(letter) && (
                  <span
                    className="rounded-full px-2 text-[10px] tracking-normal"
                    style={{
                      borderWidth: 1,
                      borderStyle: "solid",
                      borderColor: `color-mix(in srgb, ${letter.color} 45%, transparent)`,
                      color: ink(letter.color, 40),
                    }}
                  >
                    {reasonOf(letter)}
                  </span>
                )}
                <span>{letterDay(letter.delivered_at)}</span>
              </div>
              <DialogTitle
                className="text-start font-normal"
                style={{ lineHeight: "var(--row)", fontSize: compact ? 14 : 15 }}
              >
                <Ja>{greeting.ja}</Ja>
              </DialogTitle>
              <div style={{ marginTop: "var(--row)" }}>
                {rest.map((segment, i) => (
                  <p
                    key={i}
                    className={compact ? "m-0" : "m-0 text-justify"}
                    style={{
                      lineHeight: "var(--row)",
                      fontSize: compact ? 14 : 15,
                      textIndent: "2em",
                    }}
                  >
                    <Ja>{segment.ja}</Ja>
                  </p>
                ))}
              </div>
              <div className="flex justify-end" style={{ marginTop: "calc(var(--row) * .6)" }}>
                {letter.signature_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={letter.signature_url}
                    alt={`${letter.character_name} 的签名`}
                    className="h-auto opacity-95 mix-blend-multiply [filter:saturate(.7)_contrast(1.02)_brightness(.92)]"
                    style={{
                      width: compact ? Math.round(look.signature * 0.74) : look.signature,
                      transform: `rotate(${look.tilt}deg)`,
                    }}
                  />
                ) : (
                  <p className="font-serif text-body">
                    {letter.character_name_zh ?? letter.character_name}
                  </p>
                )}
              </div>
            </Sheet>

            <Sheet letter={letter} look={look} row={row} compact={compact} wash={0.64}>
              <p
                className="text-right"
                style={{
                  lineHeight: "var(--row)",
                  fontSize: 11,
                  letterSpacing: ".18em",
                  color: "#94826e",
                }}
              >
                {t.letterChinese}
              </p>
              {body.map((segment, i) => (
                <p
                  key={i}
                  className={compact ? "m-0" : "m-0 text-justify"}
                  style={{
                    lineHeight: "var(--row)",
                    fontSize: compact ? 13 : 13.5,
                    letterSpacing: ".02em",
                    textIndent: i === 0 ? 0 : "2em",
                    fontFamily: '"Noto Sans SC", system-ui, sans-serif',
                    fontWeight: 400,
                  }}
                >
                  {segment.zh}
                </p>
              ))}
            </Sheet>
          </div>
        )}

        <DialogFooter
          className={cn(
            "sticky bottom-0 z-10 flex-row justify-end gap-2 bg-transparent p-2 sm:p-3",
            // 信封时弹窗里只有这一行在流里，粘不住底，直接钉在底部。
            sealed && "absolute inset-x-0 bottom-0",
          )}
        >
          <Button
            variant="ghost"
            onClick={onClose}
            // 深色半透明胶囊：桌面压在她们的背景上、手机压在纸上都一样能读。
            className="rounded-full bg-black/35 px-5 text-white backdrop-blur-sm hover:bg-black/45 hover:text-white"
          >
            {copy.common.close}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** A letter in the announcements list: her envelope in her colour, the day, a dot unread. */
export function LetterRow({
  letter,
  onClick,
  compact,
}: {
  letter: Letter;
  onClick: () => void;
  /** A narrower row, for the dialog on a phone. */
  compact?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "group flex w-full items-center gap-3 rounded-[min(var(--radius-md),10px)] px-2 text-left",
        "transition-[background-color,transform] hover:bg-accent active:scale-[.99]",
        compact ? "py-1.5" : "py-2",
      )}
    >
      <span
        aria-hidden
        className="font-serif text-body transition-transform group-hover:-rotate-6"
        // 信封用她的印象色，压一点黑，浅色也看得见。
        style={{ color: ink(letter.color, 55) }}
      >
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
      {!letter.read && (
        <span aria-hidden className="size-1.5 shrink-0 rounded-full" style={{ background: letter.color }} />
      )}
    </button>
  );
}
