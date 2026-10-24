# 续・闪耀色彩

> 一个《偶像大师 闪耀色彩》的 AI 分身：文字 + 语音通话，28 位偶像加一位事务员。
> 非官方同人，AGPL-3.0-or-later。

| | |
| --- | --- |
| 仓库 | `soulrewrite/eidolon-sc-tsuzuku` |
| 上游 | [Sallyn0225/eidolon-sc](https://github.com/Sallyn0225/eidolon-sc)（不接 PR，所以单开一条线） |
| 基线 | 上游 `4b869539`；此后只做**定向移植**，没有整块 merge |
| 已移植 | `44a3657e` 成就系统 · `7eb50984` 七草はづき |
| 角色 | 28 位偶像 + 七草はづき（事务员） |
| 部署 | 单机自托管，Tailscale 内网可达，不对公网 |

## 只为一件事：她像一个记得你的人

| 你想要的 | 上游 | 这里 |
| --- | --- | --- |
| 不打电话也能听她说 | — | 消息语音：每句旁边的播放键 |
| 有些话当面说不出口 | — | 晚上写一封信，放在公告里 |
| 换一段对话不该等于失忆 | 一段对话只读自己那段 | 新对话接上上一段的末尾 |
| 她不会永远等你先开口 | 不回就不再说话 | 一次沉默可以说满几句 |
| — | — | 另外移植了成就系统和新角色 |

## 功能一览

| # | 功能 | 来源 | 入口 | 关键位置 |
| --- | --- | --- | --- | --- |
| 1 | 消息语音 | 自研 | 气泡播放键 / 页首音符 | `message_speech.py`、`useSpeechPlayer.ts` |
| 2 | 信 | 自研 | 公告 → 信 | `letters.py`、`LetterSheet.tsx` |
| 3 | 跨对话接续 | 自研（改上游行为） | 新建对话的第一轮 | `engine._reply`、`store.conversation_before` |
| 4 | 搭话连说 | 自研（改上游行为） | 自动 | `reach_outs.py` |
| 5 | 搭话间隔可调 | 自研 | `.env` | `EIDOLON_REACH_OUT_INTERVALS` |
| 6 | 成就系统 | 移植 `44a3657e` | 礼物页 / 聊天 | `achievements` |
| 7 | 七草はづき | 移植 `7eb50984` | 落地页 283プロ | `characters.toml` |
| 8 | 歌曲与专辑 | 自研 | 底部导航「歌曲」 | `music.py`、`lib/music.ts`、`MusicPage.tsx` |

## 几个不显然的点

- **消息语音**：内容寻址（voice_id + 文本 + 模型 + 读音表 → sha256）落到桶里 `message-speech/`；只有对话的主人能取，别人（含管理者）一律 404；合成走部署者的 key，不计限额。
- **信**：只有亲近以上会写；**每人每天最多一封**（否则几个亲近角色像刷屏）；普通信在 18:00–22:00 里抽一分钟，生日和每满 30 天当天就来。
- **跨对话接续**：只接**同一个角色**上一段的最后 4 轮，且只接第一轮。**检索不读它**——上一段原话塞进 embedding 查询会把搜索带偏。
- **搭话**：一次沉默最多说 3 句（亲近 / 信任 2 句），后续每句间隔是档位间隔的 1/6；22:00–08:00 不打扰。
- **成就**：纯计数解锁，不调 LLM。
- **歌曲**：曲目和专辑来自世界设定（`world.json`），**音频不经过我们**——点开才去网易云查这首歌，拿到 id 后放官方外链播放器；查到的结果缓存进 `music-cache.json`，查不到就照实说。

## 与上游的差异

| 项 | 我们的做法 | 为什么 |
| --- | --- | --- |
| 镜像 | 推到自己的 GHCR（`ci.yml`、`compose.prod.yml`、`dependabot.yml` 三处都要改） | 上游镜像在对方名下 |
| 生图 | 多一种 `ImageFormat`：`tensorart`（仍沿用 `NOVELAI_*` 变量名） | 这个接口只吃 prompt / width / height / count，其余参数传不进去；必须走代理 |
| 播放键 | 按下缩放 + 实心底 | 原来只有 hover，手机上毫无反馈 |
| 落地页声音 | 文字按钮换成内联音符 SVG | 视觉统一 |
| 备份 | 每天 04:00 在线备份到 `~/eidolon-backup/`，保留 14 天 | 这台没有 S3 桶，用不了上游的 age + 桶方案 |
| 部署 | 镜像按**提交**固定，不用滚动的 `main` | 回滚只需改一行 |

**CI 的两个坑**（2026-10 踩过）：GitHub 会**自动禁用 fork 的工作流**（要在 Actions 页点绿色按钮解除）；账号里的 `$0` 预算也会把 Actions / Packages 一并 block。另外 CI 只打 `sha-*` 标签，**没有 `main`**，部署必须写具体哈希。

## 部署需要的外联

`.env` 里逐项可改；只有 TTS 和生图走代理。

| 用途 | 服务 | 关键变量 |
| --- | --- | --- |
| 对话模型 | DeepSeek `deepseek-flash` | `CHAT_LLM_*` |
| 判断（好感度 / 情绪 / 照片） | Jev @ OpenRouter | `JUDGE_PROVIDER=jev`、`JEV_API_KEY` |
| 语音合成 | Fish Audio `s2.1-pro-free`（**走代理**） | `FISH_AUDIO_*` |
| 语音识别 | 阿里云百炼 | `STT_PROVIDER=bailian`、`DASHSCOPE_API_KEY` |
| 向量 + 重排 | 硅基流动 | `EMBEDDING_*`、`RERANK_MODEL`、`SILICONFLOW_API_KEY` |
| 生图 | TensorArt（**走代理**） | `NOVELAI_API_FORMAT=tensorart`、`NOVELAI_*` |
| 立绘 / 语音存储 | S3 兼容对象存储 | `EIDOLON_STAND_S3_*`、`EIDOLON_STAND_ASSETS_URL` |
| 登录 | GitHub OAuth（**必须直连**，走代理 403） | `GITHUB_CLIENT_*` |
| 代理 | 本机 SOCKS5 | `EIDOLON_PROXY_URL`、`EIDOLON_PROXY_SERVICES=tts,image` |

限额全关（`0` = 不限）：`EIDOLON_TURNS_PER_HOUR` / `EIDOLON_CALLS_PER_HOUR` / `EIDOLON_PHOTOS_PER_HOUR`。

**部署侧的把口**（都不在仓库里，换部署的人要自己配）：前端只监听 `127.0.0.1:8080`；nginx 只 `listen <tailscale IP>:443`，证书由 `tailscale cert` 签发；SSH 禁 root 密码登录 + fail2ban。

## 合并上游

```sh
git fetch upstream main
git log --oneline 4b869539..upstream/main
git diff --binary <提交>^ <提交> > /tmp/x.patch   # 二进制文件（jpg/woff2）必须 --binary
git apply --3way /tmp/x.patch
```

合并后必查：

1. **冲突点**：`Store.add_reach_out` 多了一个 `since` 参数；成就里「往来过几位角色」最高档在叶月那次从 28 改成 29
2. 新表要登记进 `database.USER_DATA`（否则删账号漏数据，`test_database` 会拦）；连库只能走 `eidolon.database.connect`
3. 后端 `uv run ruff check && uv run pyright && uv run pytest`；前端 `npm run typecheck && npm test && sh scripts/check-discipline.sh`
4. 补上本文开头的「已移植」

> 整块 `git apply` 遇到二进制文件会**整体回滚**，所以一定带 `--binary`。

## 已知问题 / 不打算做的事

- **信**：约定检测（「下周带你去吃那家店」）还没做；信里也不能带照片。
- **TTS 与生图都依赖机场**：机场挂了两个都用不了；订阅有家宽兜底，**实际流量没有**。
- **上游还差**：通话上限 `9e4f3e63`、性能那几笔（索引 / 线程化 / 连接池）、发布流程。性能实测在这台机器上收益接近 0，暂不跟。
- **不追上游每一次提交**；不改上游的领域模型（回合、搭话、记忆、好感度），除非先写进 `GLOSSARY.md`；剧情库、音色、立绘素材不进仓库（ADR-0003）。

## 登记信息（社区玩法仓库）

| 项 | 值 |
| --- | --- |
| 仓库地址 | `https://github.com/soulrewrite/eidolon-sc-tsuzuku` |
| 项目名 | 续・闪耀色彩（eidolon-sc-tsuzuku） |
| 署名 | soulrewrite |
| 内容分级 | 全年龄 |
| 玩法简介 | 在 Eidolon-SC 上补上「她记得你」的那一面：消息语音、晚上写的信、跨对话的记忆与情绪衔接、更主动的搭话，外加成就系统和新角色七草はづき。 |

**登记前只有本人能做的两件事**

1. `Settings → General → Repository name` 改成 `eidolon-sc-tsuzuku`（旧地址自动跳转）
2. 仓库设为 **Public**（独立仓库推上去的，不是 GitHub fork network 里的 fork，一个开关即可）

**公开前自查**

- [x] 没有密钥、令牌、密码——真实值只在部署机的 `.env`
- [x] 没有服务器地址、域名、桶名、家目录
- [x] 没有剧情库、音色、立绘素材（ADR-0003；`characters/` 里只有上游也提交的头像与背景）
- [x] `LICENSE` 仍是 AGPL-3.0-or-later，README 顶部写明是 fork
- [ ] **git 历史里还留着**旧版本文档提过的域名和桶名（`e0397b8a`、`9506d3c`），**决定不清**：清了要重写所有提交哈希、镜像 tag 得重新对齐，不值当；这两个名字也进不去服务器
