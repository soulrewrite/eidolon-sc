# 这个 fork 与上游的差异

本仓库是 [Sallyn0225/eidolon-sc](https://github.com/Sallyn0225/eidolon-sc) 的 fork，只服务于自己那台部署
（`eidolon-sc.tail6eaf6c.ts.net`）。上游的改动照常从 `upstream` 拉，这里的改动一律写在下面这份清单里，
方便以后合并上游时知道自己动过什么。

- **基线**：上游 `4b869539`（2026-10-20 17:22:50，`feat/daily-tasks` 的 merge）。
  这个是当时正在跑的生产版本，**刻意没有追上游最新**：`8a31a358` 之后上游多了成就系统（achievements）
  和新角色 hazuki，没有在这台机器上验过，不跟着走。
- **远端**：
  - `origin` = `https://github.com/soulrewrite/eidolon-sc.git`（自己的 fork，CI 从这里构建镜像）
  - `upstream` = `https://github.com/Sallyn0225/eidolon-sc.git`

## 改了什么

### 1. 镜像推到自己的 GHCR（部署基建）

| 文件 | 改动 |
|---|---|
| `.github/workflows/ci.yml` | `images: ghcr.io/sallyn0225/…` → `ghcr.io/soulrewrite/…` |
| `docker-compose.prod.yml` | 两个服务的 `image:` 同上 |
| `.github/dependabot.yml` | 忽略的依赖名同上 |

上游的 CI 把镜像推到上游作者的 GHCR，fork 没有写权限；不改这三处，push 后 CI 会在推送那一步失败。

> 服务器上实际跑的是 `docker-compose.custom.yml`（不在仓库里，含 TURN secret），它的 `image:` 也指向
> `ghcr.io/soulrewrite/…`。**改镜像地址时两边都要改。**

### 2. 消息语音（新增功能，上游没有）

文字对话里每一句日语前一个播放键，点一下她就把这句说出来，不用打电话。

| 文件 | 改动 |
|---|---|
| `backend/src/eidolon/message_speech.py` | **新文件**。`MessageSpeech`：内容寻址（voice_id + 说出来的话 + 模型 + 读音表 → sha256）→ 存储桶 `message-speech/`；桶里没有就用 Fish Audio 的 HTTP API 合成再放进去。`add_message_speech_routes` 挂两个路由 |
| `backend/src/eidolon/s3.py` | `Bucket.exists()`（HEAD，404 不算错）；`_send()` 多一个 `allowed` 状态码白名单 |
| `backend/src/eidolon/store.py` | `message_segments()` 与 `reach_out_segments()`：按 id 取她说的话，限本人可见（搭话在 `reach_outs` 表，id 空间和 messages 分开） |
| `backend/src/eidolon/assembly.py` | `Backend.message_speech`；`build` 里构造，缺存储桶或 Fish key 时为 `None`，功能整体关闭 |
| `backend/src/eidolon/app.py` | 挂路由；回合里 `SegmentComplete` 一到就 `create_task(warm(...))` 预合成 |
| `frontend/src/lib/messageSpeech.ts` | **新文件**。取地址 + localStorage 开关 |
| `frontend/src/components/conversations/useSpeechPlayer.ts` | **新文件**。一个页面一个 `Audio`，同时只放一句 |
| `frontend/src/components/conversations/ConversationView.tsx` | 气泡里每段日语前的播放键 `SpeechKey`、页首的音符开关 |
| `frontend/src/theme/icons.ts` | `SpeechOnIcon`/`SpeechOffIcon`/`SpeechPlayIcon`/`SpeechPauseIcon` |
| `frontend/src/i18n/zh.ts` | `conversation.speech*` 几条文案 |
| `GLOSSARY.md` | 新增「消息语音」词条 |
| `docs/configuration.md` | 新增「消息语音」一节 |

接口：

- `GET /api/messages/{id}/speech?segment=n` → `{"url": "…"}`
- `GET /api/reach-outs/{id}/speech?segment=n` → 同上

只有对话的主人能问，别人（包括管理者）一律 404；合成不出来 503。合成走部署者的 key，不计限额。

### 3. 搭话可以说满几句（改动上游行为）

上游的规则是「她搭过一次话，用户不回就再也不说」。这个 fork 放开了：

| 文件 | 改动 |
|---|---|
| `backend/src/eidolon/reach_outs.py` | `SILENCE`（一次沉默最多说几句：亲密 3、亲近/信任 2）、`FOLLOW_UP = 6`（后续每句间隔是档位间隔的六分之一）；`_count_since()` 数这一轮说了几句；`_birthday_waiting()` 让生日当天不等档位 |
| `backend/src/eidolon/store.py` | `reach_outs_since()`；`add_reach_out()` 多 `since` 参数，只拒绝「同一时刻的另一次搭话」，不再因为「搭过」就拒 |
| `backend/tests/test_reach_outs.py` | 新增「一次沉默说满两句就停」；改写「等用户回答」那条，期望值从 `(1,2,3)` 变 `(2,3,3,3)` |
| `GLOSSARY.md` | 「搭话」词条补上连说和生日的规则 |

> **合并上游时要注意**：`Store.add_reach_out` 的签名变了（多了 `since`）。上游如果改了这里，冲突要手工解。

### 4. 生图换成 TensorArt（WAI Illustrious），提示词放宽

上游演示的部署用硅基流动的 Kolors；Kolors 没在 Danbooru 上训练过，**不认识
`morino rinze` 这类角色 tag**，只能按外貌 tag 画个“黑发红眼的女孩”，所以照片不是本人。

| 文件 | 改动 |
|---|---|
| `backend/src/eidolon/config.py` | `ImageFormat` 多一个 `"tensorart"` |
| `backend/src/eidolon/image_generation.py` | `_tensorart`：`POST {base}/task` 建任务 → 每 3 秒 `POST {base}/task/query` → 从签名的 outputs 地址取图。认证是 `Echo-Access-Key` 头（不是 Bearer），还必须带浏览器 User-Agent，否则 Cloudflare 403 code 1010；INTEGER 输入要传原生数字，传字符串会 500。`TIME_LIMIT` 90 → 160 秒 |
| `backend/src/eidolon/photo_prompt.py` | `rating:general` → `rating:sensitive`；新增 `CHARM_TAGS`（beautiful detailed eyes / soft lighting / delicate features）；负面词去掉 `cleavage`，nude/underwear/see-through 这些仍然挡 |
| `backend/tests/test_image_service.py` | 新增 TensorArt 的建任务/轮询/取图用例 |
| `backend/tests/test_photos.py`、`test_photo_all_ages.py` | 断言里的提示词尾部同步 |

**这个接口只吃 4 个参数**（prompt / width / height / count）：`negative_prompt`、`seed`、
`steps`、`cfg` 都传不进去。要全参数得注册 TensorArt 的 Application 走 TAMS API
（`ap-east-1.tensorart.cloud/v1/jobs`），skills key 调它会 `app not found`。

**服务器必须走代理**：`openapi.tensor.art` 在国内被 DNS 污染（解析到 Facebook 的 IP），
`.env` 的 `EIDOLON_PROXY_SERVICES` 因此是 `tts,image`。

### 5. 落地页的声音开关（视觉改动）
| 文件 | 改动 |
|---|---|
| `frontend/src/app/(landing)/Spectrum.tsx` | 「声音 开/关」的文字按钮 → 内联音符 SVG（`aria-pressed` 区分开关） |
| `frontend/src/app/(landing)/landing.css` | `.lp-sound` 改成图标按钮；关掉时音符变暗并划一道斜线 |

**文案没动**（`copy.sound` / `soundOn` / `soundOff` 仍用于 `aria-label`），所以落地页的字体子集
（`frontend/src/app/(landing)/fonts/`）不用重新生成。以后如果要改这里的文案，记得跑
`node scripts/landing-fonts.mts`，否则 `fonts/coverage.test.ts` 会挂。

## 怎么把上游的新东西合进来

```sh
git fetch upstream main
git log --oneline 4b869539..upstream/main      # 先看有什么
git merge upstream/main                        # 或 git rebase upstream/main
```

合并后：

1. 看上面「合并时要注意」那个 `add_reach_out` 签名冲突。
2. 重跑：后端 `uv run ruff check && uv run pyright && uv run pytest`；
   前端 `npm run typecheck && npm test && sh scripts/check-discipline.sh`。
3. 把本文开头的「基线」改成新的提交号。
4. push 到 `origin main`，CI 构建镜像，服务器 `docker compose -f docker-compose.custom.yml pull && up -d`。

## 部署：镜像按提交固定

服务器的 `.env` 里有一行

```
EIDOLON_IMAGE_TAG=sha-d2dceaf
```

`docker-compose.custom.yml` 的两个服务都写成 `:${EIDOLON_IMAGE_TAG:-main}`，所以跑的是**某一次具体提交**
的镜像，不是会滚动的 `main`。好处是「服务器上跑的到底是哪一版」一眼能查：

```sh
docker ps --format '{{.Names}} {{.Image}}'
```

**每次 push 之后要改这一行**：

```sh
git rev-parse --short=7 HEAD        # 新提交的短哈希，CI 会打 sha-<7位> 的标签
# 编辑 /opt/eidolon-sc/.env 里的 EIDOLON_IMAGE_TAG
cd /opt/eidolon-sc && sudo docker compose -f docker-compose.custom.yml pull && sudo docker compose -f docker-compose.custom.yml up -d
```

要回滚，把这一行改成上一版的 sha 再 pull 一次就行——不用重新构建。

## 这个 fork 不打算做的事

- 不追上游每一次提交。只在自己有需求时，按上面的步骤整块合。
- 不改动上游的领域模型（回合、搭话、记忆、好感度这些概念），除非已经写进 `GLOSSARY.md`。
- 剧情库、音色、立绘素材不进仓库（上游 ADR-0003，这里照旧）。
