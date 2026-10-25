"use client";

// 歌曲页（fork）：上面一排她的头像，点一位就只看她唱过的歌；切到「专辑」按发售日看碟。
// 播放靠网易云的外链播放器，点一首才去查它在网易云是哪一首（查到就记住，不再问）。

import { useEffect, useMemo, useState, useSyncExternalStore } from "react";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { copy } from "@/i18n";
import { api, json, type Character } from "@/lib/api";
import {
  musicAlbums,
  musicLookup,
  musicSongs,
  type Album,
  type FoundSong,
  type Song,
} from "@/lib/music";
import { musicPlayback } from "@/lib/musicPlayer";
import { cn } from "@/lib/utils";
import { AlbumIcon, MusicIcon, PlayIcon } from "@/theme/icons";

const t = copy.music;

/** 秒数写成 0:07 / 5:12。 */
function clock(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}

type Tab = "songs" | "albums";

export function MusicPage() {
  const [characters, setCharacters] = useState<Character[] | null>(null);
  const [singers, setSingers] = useState<string[]>([]);
  const [songs, setSongs] = useState<Song[] | null>(null);
  const [albums, setAlbums] = useState<Album[] | null>(null);
  const [tab, setTab] = useState<Tab>("songs");
  const [picked, setPicked] = useState<string | null>(null);
  /** 点了但没查到的那一条：展开告诉用户「网易云没有这首」。 */
  const [nowPlaying, setNowPlaying] = useState<string | null>(null);
  // 在放哪一首由外壳的播放器说了算：离开这一页它还在放
  const now = useSyncExternalStore(musicPlayback.subscribe, musicPlayback.get, () => null);
  const [found, setFound] = useState<Record<string, FoundSong | null>>({});
  const [searching, setSearching] = useState<string | null>(null);
  const [openAlbum, setOpenAlbum] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    void (async () => {
      const [listed, shelf] = await Promise.all([
        json(await api("/api/characters")) as Promise<Character[]>,
        musicSongs(),
      ]);
      if (!alive) return;
      setCharacters(listed);
      setSingers(shelf.singers);
      setSongs(shelf.songs);
    })();
    return () => {
      alive = false;
    };
  }, []);

  // 只留有歌的那几位，按世界设定里的顺序（不是角色的顺序）
  const withSongs = useMemo(() => {
    if (!characters) return [];
    const byName = new Map(characters.map((character) => [character.name, character]));
    return singers.flatMap((name) => {
      const character = byName.get(name);
      return character ? [character] : [];
    });
  }, [characters, singers]);

  useEffect(() => {
    if (picked === null) return;
    let alive = true;
    void (async () => {
      const shelf = await musicSongs(picked);
      if (alive) setSongs(shelf.songs);
    })();
    return () => {
      alive = false;
    };
  }, [picked]);

  useEffect(() => {
    if (tab !== "albums" || albums !== null) return;
    void (async () => {
      const shelf = await musicAlbums();
      setAlbums(shelf.albums);
    })();
  }, [tab, albums]);

  /** 点一首：先查它在网易云是哪一首，再交给外壳的播放器（切页面也不停）。 */
  async function play(title: string) {
    if (now?.title === title) {
      musicPlayback.stop();
      return;
    }
    let hit = found[title];
    if (hit === undefined) {
      setSearching(title);
      try {
        hit = await musicLookup(title);
        setFound((before) => ({ ...before, [title]: hit }));
      } finally {
        setSearching(null);
      }
    }
    if (hit === null) {
      setNowPlaying(title);   // 没查到：展开那句「网易云没有这首」
      return;
    }
    musicPlayback.play(title, hit.id);
  }

  const current = picked === null ? null : withSongs.find((character) => character.id === picked) ?? null;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex shrink-0 flex-wrap items-center gap-3 border-b bg-background px-4 py-3">
        <MusicIcon aria-hidden className="size-5 text-muted-foreground" />
        <h1 className="text-title font-medium">{t.title}</h1>
        {current && (
          <span className="text-meta text-muted-foreground">{t.only(current.name_zh ?? current.name)}</span>
        )}
        <div className="ms-auto flex gap-1">
          <Button
            size="sm"
            variant={tab === "songs" ? "secondary" : "ghost"}
            onClick={() => setTab("songs")}
          >
            <MusicIcon data-icon="inline-start" />
            {t.songsTab}
          </Button>
          <Button
            size="sm"
            variant={tab === "albums" ? "secondary" : "ghost"}
            onClick={() => setTab("albums")}
          >
            <AlbumIcon data-icon="inline-start" />
            {t.albumsTab}
          </Button>
        </div>
      </header>

      {tab === "songs" && (
        <>
          <div className="flex shrink-0 gap-3 overflow-x-auto border-b px-4 py-3">
            <button
              type="button"
              aria-pressed={picked === null}
              onClick={() => setPicked(null)}
              className={cn(
                "flex shrink-0 flex-col items-center gap-1 rounded-lg px-2 py-1 text-meta",
                picked === null ? "bg-accent text-foreground" : "text-muted-foreground",
              )}
            >
              <span className="flex size-12 items-center justify-center rounded-full border bg-background">
                <MusicIcon className="size-5" />
              </span>
              {t.everyone}
            </button>
            {withSongs.map((character) => (
              <button
                key={character.id}
                type="button"
                aria-pressed={picked === character.id}
                onClick={() => setPicked(character.id)}
                className={cn(
                  "flex w-16 shrink-0 flex-col items-center gap-1 rounded-lg px-1 py-1 text-meta",
                  picked === character.id ? "bg-accent text-foreground" : "text-muted-foreground",
                )}
              >
                {character.scsp_avatar_url ?? character.avatar_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={(character.scsp_avatar_url ?? character.avatar_url) as string}
                    alt=""
                    className="size-12 rounded-full border object-cover"
                    style={{ borderColor: character.color }}
                  />
                ) : (
                  <span className="size-12 rounded-full border bg-muted" />
                )}
                <span className="w-full truncate text-center">{character.name_zh ?? character.name}</span>
              </button>
            ))}
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-6">
            {songs === null ? (
              <div className="flex h-full items-center justify-center">
                <Spinner className="size-6 text-muted-foreground" aria-label={t.loading} />
              </div>
            ) : songs.length === 0 ? (
              <p className="py-10 text-center text-body text-muted-foreground">{t.noSongs}</p>
            ) : (
              <ul className="divide-y">
                {songs.map((song) => (
                  <li key={song.id} className="py-2">
                    <div className="flex items-center gap-3">
                      <Button
                        size="icon-sm"
                        variant={now?.title === song.title ? "secondary" : "ghost"}
                        aria-label={now?.title === song.title ? t.stop : t.play(song.title)}
                        onClick={() => void play(song.title)}
                      >
                        <PlayIcon />
                      </Button>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-body font-medium">{song.title}</p>
                        <p className="truncate text-meta text-muted-foreground">
                          {song.singers.join(" · ")}
                          {song.special_unit ? ` · ${song.special_unit}` : ""}
                        </p>
                      </div>
                    </div>
                    {(now?.title === song.title || nowPlaying === song.title) && (
                      <div className="mt-2">
                        {searching === song.title ? (
                          <p className="text-meta text-muted-foreground">{t.searching}</p>
                        ) : now?.title === song.title && now.unplayable ? (
                          // 唯一要说明的情况：取不到那条音频（多半是网易云没版权）
                          <p className="text-meta text-muted-foreground">{t.cannotPlay}</p>
                        ) : now?.title === song.title ? (
                          <div className="ms-12 flex items-center gap-2">
                            <div className="h-1 min-w-0 flex-1 overflow-hidden rounded-full bg-muted">
                              <div
                                className="h-full bg-foreground/40"
                                style={{
                                  width:
                                    now.duration > 0
                                      ? `${Math.min(100, (now.at / now.duration) * 100)}%`
                                      : "0%",
                                }}
                              />
                            </div>
                            <span className="shrink-0 text-meta text-muted-foreground tabular-nums">
                              {clock(now.at)} / {now.duration > 0 ? clock(now.duration) : "…"}
                            </span>
                          </div>
                        ) : found[song.title] === null ? (
                          <p className="text-meta text-muted-foreground">{t.notOnNetease}</p>
                        ) : null}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}

      {tab === "albums" && (
        <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-6">
          {albums === null ? (
            <div className="flex h-full items-center justify-center">
              <Spinner className="size-6 text-muted-foreground" aria-label={t.loading} />
            </div>
          ) : (
            <ul className="divide-y">
              {albums.map((album) => (
                <li key={album.catalog} className="py-2">
                  <button
                    type="button"
                    className="flex w-full items-baseline gap-3 text-start"
                    onClick={() => setOpenAlbum(openAlbum === album.catalog ? null : album.catalog)}
                  >
                    <span className="text-meta text-muted-foreground tabular-nums">{album.date}</span>
                    <span className="min-w-0 flex-1 truncate text-body">{album.title}</span>
                    <span className="text-meta text-muted-foreground">{album.catalog}</span>
                  </button>
                  {openAlbum === album.catalog && (
                    <ol className="mt-2 ms-16 list-decimal space-y-1 text-meta text-muted-foreground">
                      {album.tracks.map((track, index) => (
                        <li key={`${album.catalog}-${index}`}>{track}</li>
                      ))}
                    </ol>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
