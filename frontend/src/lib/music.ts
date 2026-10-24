// 歌曲页（fork，FORK.md「歌曲」）：曲目与专辑来自世界设定，播放交给网易云的外链播放器——
// 音频始终在网易云那边，我这里只拼一个 iframe 地址。

import { api, json } from "@/lib/api";

/** 一首歌：谁唱的、在哪几张碟里。 */
export type Song = {
  id: string;
  title: string;
  singers: string[];
  releases: string[];
  special_unit: string | null;
};

/** 一张碟：曲目表里的 `songs` 是能点开播的那几首，`Off Vocal` 之类是 null，不在里面。 */
export type Album = {
  catalog: string;
  title: string;
  date: string;
  tracks: string[];
  songs: string[];
};

/** 网易云那边对上的那一首。 */
export type FoundSong = {
  id: string;
  name: string;
  artists: string[];
  album: string | null;
  duration: number | null;
};

export async function musicSongs(characterId?: string): Promise<{ songs: Song[]; singers: string[] }> {
  const query = characterId ? `?character_id=${encodeURIComponent(characterId)}` : "";
  return json(await api(`/api/music/songs${query}`));
}

export async function musicAlbums(): Promise<{ albums: Album[] }> {
  return json(await api("/api/music/albums"));
}

export async function musicLookup(title: string): Promise<FoundSong | null> {
  const found = await json(await api(`/api/music/lookup?title=${encodeURIComponent(title)}`));
  return (found as { found: FoundSong | null }).found;
}

/** 网易云的外链播放器。`type=2` 是单曲，`auto=1` 点开就放。 */
export function playerUrl(id: string): string {
  return `https://music.163.com/outchain/player?type=2&id=${encodeURIComponent(id)}&auto=1&height=66`;
}

/** 她在网易云的那首单曲页，播放器之外再给一条出口。 */
export function songPageUrl(id: string): string {
  return `https://music.163.com/song?id=${encodeURIComponent(id)}`;
}
