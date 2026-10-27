#!/usr/bin/env python3
"""世界设定的一致性检查：`world.json` 自己跟自己对不对得上。

为什么需要它：`world.json` 是人手提交的数据文件，一次 import 会整份换掉。上次核对
（2026-10-27）就发现分类目录、出演者、曲目之间能出现对不上的地方，而这些问题不会报错，
只会在聊天里表现为「她提了一场自己没去的 live」。

从哪里跑：后端容器里（有依赖，也读得到 /characters）：

    docker exec eidolon-sc-backend-1 python /deploy/check-events.py

退出码：有错误是 1，只有提醒是 0——cron 里据此决定要不要吵醒部署者。

shinycolors.moe 的对照（第二个源）这次**没做**：站点对 curl 只回 1.2KB 的空壳，
要无头浏览器渲染，放到社区新闻的截图 worker 里一起做（PLAN-20261027-daily-and-news）。
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

STALE_DAYS = 45
"""世界设定比这更旧就提醒：她记不住太早以前的事，聊到大事件会答不上来。"""


def world_file() -> Path:
    characters = os.environ.get("EIDOLON_CHARACTERS_PATH")
    if characters:
        return Path(characters).parent / "world.json"
    return Path("/characters/world.json")


def main() -> int:
    path = world_file()
    try:
        world = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"找不到 {path}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as error:
        print(f"{path} 不是合法 JSON：{error}", file=sys.stderr)
        return 1

    idols = {idol["name"] for idol in world.get("idols", [])}
    songs = {song["id"]: song for song in world.get("songs", [])}
    catalogs = {release["catalog"] for release in world.get("releases", [])}
    errors: list[str] = []
    warnings: list[str] = []

    as_of = world.get("as_of")
    if as_of:
        age = (date.today() - date.fromisoformat(as_of)).days
        if age > STALE_DAYS:
            warnings.append(f"世界设定停在 {as_of}，已经 {age} 天没更新（world sync 跑一下）")

    for live in world.get("lives", []):
        for day in live.get("days", []):
            where = f"{live['name']} {day['date']}"
            for performer in day.get("performers", []):
                if performer not in idols:
                    errors.append(f"{where}：出演者「{performer}」不在偶像名单里")
            for absent in day.get("absent", []):
                # absent 的定义是「公告过、但本人当天缺席」——本来就不该在 performer 里
                if absent in day.get("performers", []):
                    errors.append(f"{where}：「{absent}」同时出现在出演和缺席名单里")

    for release in world.get("releases", []):
        for track in release.get("tracks", []):
            song_id = track.get("song")
            if song_id and song_id not in songs:
                errors.append(f"{release['catalog']} 的「{track['title']}」指向不存在的歌 {song_id}")

    for song in world.get("songs", []):
        for singer in song.get("singers", []):
            if singer not in idols:
                errors.append(f"歌「{song['title']}」的演唱者「{singer}」不在偶像名单里")
        for catalog in song.get("releases", []):
            if catalog not in catalogs:
                errors.append(f"歌「{song['title']}」挂在不存在碟 {catalog} 上")

    print(
        f"{path}（as_of {as_of}）：{len(idols)} 位偶像、{len(songs)} 首歌、"
        f"{len(catalogs)} 张碟、{len(world.get('lives', []))} 场演出"
    )
    for line in warnings:
        print(f"提醒：{line}")
    for line in errors[:40]:
        print(f"错误：{line}")
    if len(errors) > 40:
        print(f"……另有 {len(errors) - 40} 条错误没列出")
    print(f"结论：{len(errors)} 个错误、{len(warnings)} 条提醒")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
