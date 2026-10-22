# 续・闪耀色彩（eidolon-sc-tsuzuku）

> fork 自 [Sallyn0225/eidolon-sc](https://github.com/Sallyn0225/eidolon-sc)，署名 `soulrewrite`，全年龄。

## 为什么要一个 fork

上游不接 PR，玩法由维护者按自己的喜好做。这个 fork 想要的只有一件事：**她像一个记得你的人。**

- 不想打电话也能听她说 → 消息语音
- 有些话当面说不出口 → 晚上写一封信，放在公告里
- 换一段对话不该等于失忆 → 新对话接上上一段的末尾，情绪跟着接上
- 一个人不会永远等你先开口 → 搭话更密、能连说几句
- 另外把上游的成就系统和七草はづき搬了进来

## 登记信息（社区玩法仓库）

开登记 issue 时照抄这张表：

| 项 | 值 |
| --- | --- |
| 仓库地址 | `https://github.com/soulrewrite/eidolon-sc-tsuzuku` |
| 项目名 | 续・闪耀色彩（eidolon-sc-tsuzuku） |
| 署名 | soulrewrite |
| 内容分级 | 全年龄 |
| 玩法简介 | 在 Eidolon-SC 上补上「她记得你」的那一面：消息语音、晚上写的信、跨对话的记忆与情绪衔接、更主动的搭话，外加成就系统和新角色七草はづき。 |

**登记前只有本人在 GitHub 上能做的两件事**：

1. `Settings → General → Repository name` 改成 `eidolon-sc-tsuzuku`（上游要求与 `eidolon-sc` 区分开，旧地址会自动跳转）
2. 仓库设为 **Public**。它不是 GitHub fork network 里的那种 fork（是独立仓库推上去的），所以 Private → Public 一个开关就行；
   如果是 fork，本来就只能是公开的

**公开前自查**：

- [x] 没有密钥、令牌、密码——仓库里从来没有过，真实值只在部署机的 `.env`
- [x] 当前文件里没有服务器地址、域名、桶名、家目录（2026-10-22 清过一遍）
- [x] 没有剧情库、音色、立绘素材（ADR-0003；`characters/` 里只有上游也提交的头像与背景）
- [x] `LICENSE` 仍是 AGPL-3.0-or-later，README 顶部写明了是 fork
- [ ] **git 历史里还留着**旧版本文档提过的域名和桶名（`e0397b8a`、`9506d3c`），**决定不清**：
      清了要重写所有提交哈希、部署的镜像 tag 得重新对齐，不值当；
      这两个名字也进不去服务器（域名只在自己的 tailnet 里解析，桶名只读不写）

---

## 远端与基线

[Sallyn0225/eidolon-sc](https://github.com/Sallyn0225/eidolon-sc) 的 fork，只服务自己的一台服务器
（Tailscale 内网，不是公网；地址不写在这里）。上游的改动照常从 `upstream` 拉；这里动过什么，
都按下面的编号记着，方便以后合并时知道要解哪些冲突。

- **远端**：`origin` = `https://github.com/soulrewrite/eidolon-sc.git`（CI 从这里构建镜像），
  `upstream` = `https://github.com/Sallyn0225/eidolon-sc.git`
- **基线**：上游 `4b869539`（2026-10-20，`feat/daily-tasks` 的 merge，当时的生产版本）。
  此后只做**定向移植**，没有整块 merge 过上游。
- **已移植的上游提交**：`44a3657e`（成就系统）、`7eb50984`（叶月）。其余（通话上限、性能、发布流程）都还没进来。
  详见「一、新增功能」里标着「上游移植」的两节。

## 部署需要的外联

这台机器实际连的服务，`.env` 里逐项可改。

| 用途 | 服务 | 关键环境变量 | 备注 |
| --- | --- | --- | --- |
| 对话模型 | DeepSeek `deepseek-flash` | `CHAT_LLM_BASE_URL` / `CHAT_LLM_MODEL` / `CHAT_LLM_API_KEY` | `https://api.deepseek.com` |
| 判断模型（好感度、情绪、照片） | Jev @ OpenRouter | `JUDGE_PROVIDER=jev`、`JEV_API_KEY` | 没有它就没有好感度、没有照片判断 |
| 语音合成 TTS | Fish Audio `s2.1-pro-free` | `FISH_AUDIO_API_KEY` / `FISH_AUDIO_MODEL` | **必须走代理**，直连不通 |
| 语音识别 STT | 阿里云百炼 | `STT_PROVIDER=bailian`、`DASHSCOPE_API_KEY` | 通话时用 |
| 向量 + 重排 | 硅基流动 | `EMBEDDING_PROVIDER=siliconflow`、`EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B`、`RERANK_MODEL=Qwen/Qwen3-Reranker-0.6B`、`SILICONFLOW_API_KEY` | 剧情检索、记忆检索 |
| 生图 | **TensorArt**（用 NovelAI 形态的客户端说话） | `NOVELAI_API_FORMAT=tensorart`、`NOVELAI_BASE_URL=https://openapi.tensor.art/openworks/v1`、`NOVELAI_MODEL=anime_lab_wai_illustrious` | **必须走代理**；变量名沿用 `NOVELAI_*`，因为客户端就是照着 NovelAI 那套写的，只有 `api_format` 决定打哪个服务 |
| 立绘 / 语音存储 | 对象存储（S3 兼容） | `EIDOLON_STAND_S3_*`、`EIDOLON_STAND_ASSETS_URL` | 桶名、区域、密钥都在部署者的 `.env` 里 |
| 登录 | GitHub OAuth | `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | 走 GitHub 必须直连（走代理 403） |
| 代理 | 本机 SOCKS5（mihomo） | `EIDOLON_PROXY_URL`、`EIDOLON_PROXY_SERVICES=tts,image` | **只有 TTS 和生图走代理**；国内 API 直连快得多 |

其余与部署有关的：

- 限额全部关掉：`EIDOLON_TURNS_PER_HOUR=0`、`EIDOLON_CALLS_PER_HOUR=0`、`EIDOLON_PHOTOS_PER_HOUR=0`（0 = 不限）
- 搭话开着：`EIDOLON_REACH_OUTS=1`；间隔见「5」
- 域名用 Tailscale 签发的证书，**只在 tailnet 内可达**，不是公网
- 拉镜像**走代理**：实测同一层直连 0 B/s（卡死）、走代理 7.5 MB/s，`pull + up -d` 13 秒完成。
  代价是机场挂了 `docker pull` 会全线 EOF —— 那时候把 `docker.service.d/proxy.conf` 临时移走即可

---

# 一、新增功能

上游没有的，或者从上游单独搬进来的。按加入顺序编号。

## 1. 消息语音（上游没有）

文字对话里每句日语前面有个播放键，点一下她把这句说出来，不用打电话。

| 文件 | 改动 |
| --- | --- |
| `backend/src/eidolon/message_speech.py` | **新文件**。`MessageSpeech`：内容寻址（voice_id + 说出来的话 + 模型 + 读音表 → sha256）→ 桶里 `message-speech/`；没有就调 Fish Audio 合成再放进去 |
| `backend/src/eidolon/s3.py` | `Bucket.exists()`（HEAD，404 不算错）；`_send()` 多一个 `allowed` 状态码白名单 |
| `backend/src/eidolon/store.py` | `message_segments()` / `reach_out_segments()`：按 id 取她说的话，限本人可见 |
| `backend/src/eidolon/assembly.py` | `Backend.message_speech`；缺桶或 Fish key 时为 `None`，功能整体关闭 |
| `backend/src/eidolon/app.py` | 挂路由；回合里 `SegmentComplete` 一到就预合成 |
| `frontend/src/lib/messageSpeech.ts` | **新文件**。取地址 + localStorage 开关 |
| `frontend/src/components/conversations/useSpeechPlayer.ts` | **新文件**。一个页面一个 `Audio`，同时只放一句 |
| `frontend/src/components/conversations/ConversationView.tsx` | 气泡里的播放键 `SpeechKey`、页首的音符开关 |
| `frontend/src/theme/icons.ts`、`i18n/zh.ts`、`GLOSSARY.md`、`docs/configuration.md` | 图标、文案、词条、配置文档 |

接口：

- `GET /api/messages/{id}/speech?segment=n` → `{"url": "…"}`
- `GET /api/reach-outs/{id}/speech?segment=n` → 同上

只有对话的主人能问，别人（包括管理者）一律 404；合成不出来 503。合成走部署者的 key，不计限额。

## 2. 信（上游没有）

亲近以上的角色，晚上给你写一封信，放在**公告**里。

**谁写、什么时候**（`backend/src/eidolon/letters.py`）

- 只有 `TIERS = ("close", "intimate")`；冷却 `GAP_DAYS = (3, 7)` 天（每封抽一次）
- **每人每天最多一封**，不论是谁写的（亲近的有好几位，一人一封会像刷屏）
- 普通信在生产者的 `EVENING = (18:00, 22:00)` 里抽一分钟；抽签用 sha256，同一天多次 tick 不会变
- 特殊日子**当天就来**、不等晚上：制作人生日、第一次说话之后每满 30 天

**写什么**（`engine.letter`）

- 与搭话同一套提示词骨架：人设、世界设定、最新记忆、最近对话（含上一段的末尾）
- 结尾换成 `LETTER_RULES`：这是信，有称呼有落款；写平时当面说不出口的话；引一件具体的事；四到六段
- 产出仍是 `<ja>…</ja><zh>…</zh>`，和消息同一种结构，逐句双语

**怎么读**

- `GET /api/letters`（最新在前）、`POST /api/letters/{id}/read`
- 公告弹窗里多一段「信」；点开是一张信纸：她的通话背景压暗去色透在下面，衬线体，
  日文在上字幕在下，末尾落款，打开即已读

**还没做**：约定检测（「下周带你去吃那家店」）；信里带照片、随信附礼物。

## 3. 新对话接上一段（上游没有，改了上游行为）

上游是「一段对话只读自己那段记录」（`test_conversations_are_kept_apart` 就守着这条），跨对话只靠散点记忆，
于是「新建对话」在体感上等于失忆。

本 fork：新的一段对话**第一轮**把同角色上一段的最后 `RECAP_TURNS = 4` 轮接进历史。

- `store.conversation_before()` 找上一段；`engine._reply` 拼在历史前面
- **检索不读它**（`history` 保持原样），只有聊天模型和判断模型（好感度、照片、情绪）读
  —— 上一段的原话塞进 embedding 查询会把搜索带偏
- 只接第一轮（不烧上下文），只接**同一个角色**的（有测试守着）

### 3.1 搭话也接得上

这一段她说过的还不到 4 轮时，搭话的提示词也带上上一段的末尾——否则规则叫她「先接着最近聊过的事」，
她手里却没有那件事，只能发一句空问候。检索用的 `last_turn_query` 跟着取上一段最后一句。

## 4. 搭话可以说满几句（改了上游行为）

上游是「搭过一次，用户不回就再也不说」。这里放开：

| 文件 | 改动 |
| --- | --- |
| `backend/src/eidolon/reach_outs.py` | `SILENCE`（一次沉默最多说几句：亲密 3、亲近/信任 2）、`FOLLOW_UP = 6`（后续每句间隔是档位间隔的六分之一）、`_count_since()`、`_birthday_waiting()` |
| `backend/src/eidolon/store.py` | `reach_outs_since()`；`add_reach_out()` 多 `since` 参数，只拒绝「同一时刻的另一次搭话」 |
| `backend/tests/test_reach_outs.py` | 「说满两句就停」；「等用户回答」的期望从 `(1,2,3)` 改成 `(2,3,3,3)` |
| `GLOSSARY.md` | 「搭话」补上连说和生日的规则 |

> **合并上游时要注意**：`Store.add_reach_out` 签名变了（多 `since`），上游改到这里要手工解。

## 5. 搭话间隔可调（上游是写死的）

上游 `reach_outs.INTERVALS` 写死（intimate 3–6h / close 8–16h / trust 20–36h），改要动代码连带改十几处测试。
本 fork 改成环境变量，没写到的档位保持上游值：

```
EIDOLON_REACH_OUT_INTERVALS=intimate:1-3,close:2-6,trust:3-10
```

随机位置（`place`）本来就有，改的只是范围。夜里 22:00–08:00 仍然不打扰。

## 6. 成就系统（**上游移植**，`44a3657e`）

上游那个提交的父提交正好是 `4b869539`（本 fork 的基线），所以是整包干净搬过来的。

- 8 组成就：每角色「聊天回合 / 通话时长 / 礼物 / 亲密度」，全角色「往来角色数 / 亲密角色数 / 相处天数 / 抽卡」
- 两张表 `achievement_progress`、`achievement_stages`，进度按历史数据回填
- 前端：礼物页成就墙、聊天里的解锁提示、分享卡
- **不调 LLM**，纯计数解锁

> 合并上游时要注意：全角色「往来过几位角色」最高档在叶月那一提交里从 28 改成了 29，两处都在。

## 7. 叶月：七草はづき（**上游移植**，`7eb50984`）

角色不再只限偶像：事务员七草はづき也是角色。

- `characters.toml` 整条配置（音色、印象色 `#c3d825`、`idol_id 91`、默认衣装【２８３プロの日常】、照片 tag、招呼）
- 头像、SCSP 头像、通话背景、人设 sheet、facts 与出处、读音「ななくさ はづき」
- `world.py` 启动校验认事务所职员（`world.json` 的 `office.staff` 本来就有她，不用重跑 world sync）
- 各处提示词「偶像」放宽为「偶像（或事务员）」；落地页分组（283プロ）与字体子集

**部署后要跑**：story sync（她出场的剧情改算她）、stand-sync（衣装 91）、`eidolon greeting upload`。
**角色文件是宿主机挂载的**（容器里的 `/characters`），改完要同步宿主机再重启，光换镜像不生效。

---

# 二、与上游的差异、小更新

## 2.1 镜像推到自己的 GHCR（部署基建）

| 文件 | 改动 |
| --- | --- |
| `.github/workflows/ci.yml` | `images: ghcr.io/sallyn0225/…` → `ghcr.io/soulrewrite/…` |
| `docker-compose.prod.yml` | 两个服务的 `image:` 同上 |
| `.github/dependabot.yml` | 忽略的依赖名同上 |

不改这三处，push 后 CI 会在推送那一步失败。

> 服务器上实际跑的是 `docker-compose.custom.yml`（不在仓库里，含 TURN secret），`image:` 也指向
> `ghcr.io/soulrewrite/…`。**改镜像地址时两边都要改。**

## 2.2 生图换成 TensorArt（上游默认 NovelAI）

上游的 `ImageFormat` 只有 `novelai`（默认）和 `openai` 两种，靠 `NOVELAI_*` 那组变量配置。
本 fork 加了第三种 `tensorart`，本部署用的就是它（`NOVELAI_API_FORMAT=tensorart`）：

| 文件 | 改动 |
| --- | --- |
| `backend/src/eidolon/config.py` | `ImageFormat` 多一个 `"tensorart"` |
| `backend/src/eidolon/image_generation.py` | `_tensorart`：`POST {base}/task` 建任务 → 每 3 秒 `POST {base}/task/query` → 从签名的 outputs 取图。认证是 `Echo-Access-Key` 头（不是 Bearer），还要带浏览器 UA，否则 Cloudflare 403 code 1010；INTEGER 输入要传原生数字，传字符串会 500。`TIME_LIMIT` 90 → 160 秒 |
| `backend/src/eidolon/photo_prompt.py` | `rating:general` → `rating:sensitive`；新增 `CHARM_TAGS`（beautiful detailed eyes / soft lighting / delicate features）；负面词去掉 `cleavage`，nude/underwear/see-through 仍然挡 |
| `backend/tests/test_image_service.py` | TensorArt 的建任务/轮询/取图用例 |
| `backend/tests/test_photos.py`、`test_photo_all_ages.py` | 提示词尾部同步 |

**这个接口只吃 4 个参数**（prompt / width / height / count）：`negative_prompt`、`seed`、`steps`、`cfg` 都传不进去。
要全参数得注册 TensorArt 的 Application 走 TAMS API（`ap-east-1.tensorart.cloud/v1/jobs`），skills key 调它会 `app not found`。

**必须走代理**：`openapi.tensor.art` 在国内被 DNS 污染，所以 `EIDOLON_PROXY_SERVICES=tts,image`。

## 2.3 播放键的按压反馈（视觉）

气泡里的播放键原来只有 hover 变色，按下去什么也没有，手机上更是毫无回应。

| 文件 | 改动 |
| --- | --- |
| `ConversationView.tsx`（`SpeechKey`、`headerKey`） | `motion-safe:active:scale-90` + `active:bg-accent`；正在放时整颗实心底 |
| `(landing)/landing.css` | `.lp-sound:active` 缩放 0.92 |

## 2.4 落地页的声音开关（视觉）

`frontend/src/app/(landing)/Spectrum.tsx`：「声音 开/关」的文字按钮 → 内联音符 SVG（`aria-pressed` 区分开关）；
`landing.css` 的 `.lp-sound` 改成图标按钮，关掉时变暗并划一道斜线。

**文案没动**，所以落地页字体子集不用重新生成。以后改这里的文案，要跑 `node scripts/landing-fonts.mts`，
否则 `fonts/coverage.test.ts` 会挂。

## 2.5 数据库备份（上游是 age + S3，这台没有桶）

上游的 `deploy/db-backup.sh` 走 age 加密 + S3 兼容桶（ADR-0012），这台机器没配桶，所以另写了一个简单的，
每天凌晨 4 点跑（服务器上装在部署用户的家目录，仓库里是 `deploy/db-backup-simple.sh`）：

```sh
0 4 * * * ~/eidolon-db-backup.sh                # 部署用户的 crontab
```

- 用容器里的 `sqlite3` **在线备份 API**（WAL 下直接 cp 会拿到不一致的快照）
- 备份前跑 `PRAGMA integrity_check`
- 存 `~/eidolon-backup/eidolon-YYYYMMDD-HHMM.db.gz`，**保留 14 天**（最新一份不删）
- 日志同目录 `backup.log`；退出码 0 成功、2 导出/检查失败、5 容器没跑
- 恢复：容器停掉，`gzip -dc ...db.gz > /data/eidolon.db`

## 2.6 部署：镜像按提交固定

`.env` 里一行 `EIDOLON_IMAGE_TAG=sha-xxxxxxx`，`docker-compose.custom.yml` 写成 `:${EIDOLON_IMAGE_TAG:-main}`，
所以跑的是**某一次具体提交**，不是会滚动的 `main`。查当前版本：

```sh
docker ps --format '{{.Names}} {{.Image}}'
```

每次 push 之后要改这一行：

```sh
git rev-parse --short=7 HEAD        # 新提交的短哈希，CI 打的标签是 sha-<7位>
# 编辑部署目录下的 .env 里的 EIDOLON_IMAGE_TAG
cd <部署目录> && sudo docker compose -f docker-compose.custom.yml pull && sudo docker compose -f docker-compose.custom.yml up -d
```

回滚：把这一行改回上一版的 sha 再 pull，不用重新构建。

## 2.7 怎么把上游的新东西合进来

```sh
git fetch upstream main
git log --oneline 4b869539..upstream/main      # 先看有什么
git diff --binary <提交>^ <提交> > /tmp/x.patch  # 只要一个提交时
git apply --3way /tmp/x.patch                  # 二进制文件（jpg/woff2）要 --binary 才能进
```

合并后：

1. 看上面的冲突点：`Store.add_reach_out` 的签名、成就的 28→29 档位
2. 重跑后端 `uv run ruff check && uv run pyright && uv run pytest`，
   前端 `npm run typecheck && npm test && sh scripts/check-discipline.sh`
3. 把本文开头的「已移植的上游提交」补上这一条
4. push 到 `origin main` → CI 构建 → 服务器改 `EIDOLON_IMAGE_TAG` 再 pull

**合并是最容易出问题的一步**，注意两件事：

- 整块 `git apply` 遇到二进制文件失败会**整体回滚**，要用 `git diff --binary`
- 新加的表要同时登记进 `database.USER_DATA`（否则删账号会漏数据，`test_database` 会拦）；
  连库只能走 `eidolon.database.connect`，不许自己 `sqlite3.connect`

## 2.8 部署侧的把口收在哪

自己的部署不靠「域名没人知道」来保护，靠这三层（都不在仓库里，换部署的人要自己配）：

| 面 | 做法 |
| --- | --- |
| 前端 | 只监听 `127.0.0.1:8080`（compose 里 `HOSTNAME`），公网摸不到，nginx 反代它 |
| HTTPS | nginx 只 `listen <tailscale IP>:443`，公网连 SNI 打了也连不上；证书由 `tailscale cert` 签发 |
| SSH | root 不许用密码登录（`PermitRootLogin prohibit-password`），普通账号保留密码 + fail2ban 挡爆破 |

## 2.9 这个 fork 不打算做的事

- 不追上游每一次提交。只在自己有需求时按上面步骤整块合。
- 不改上游的领域模型（回合、搭话、记忆、好感度这些概念），除非已经写进 `GLOSSARY.md`。
- 剧情库、音色、立绘素材不进仓库（上游 ADR-0003，这里照旧）。

---

# 三、已知问题 / 待办

- **信**：约定检测没做；信里还不能带照片
- **语音合成与生图都依赖机场**：机场挂了就都用不了（`EIDOLON_PROXY_SERVICES=tts,image`）。
  机场全挂时 `update-sub.sh` 会用家宽出口兜底拉订阅，但**实际流量没有兜底**
- **上游还差**：通话上限（`9e4f3e63`）、性能那几笔（索引、线程化、连接池）、发布流程。
  性能实测在这台机器上收益接近 0（索引目标查询 0.01ms），暂不跟
