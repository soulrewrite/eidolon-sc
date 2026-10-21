"""Image generation (GLOSSARY.md「生图」): one picture from a prompt, checked and made into what
a photo is kept as.

An image service is reached in the format whoever configured it chose (`ImageFormat`),
never found out. In NovelAI's own: `POST {base_url}/ai/generate-image` with a bearer
token, answering with a ZIP of the picture, at NovelAI or a relay passing requests on as
they are; every request asks for one picture of 832×1216 at 23 steps, scale 7 with Euler
Ancestral, from a random seed, in the shape of V4's prompts and later. In OpenAI's image
format: `POST {base_url}/images/generations`, the address up to `/v1`, asking at the top
level for one picture of that size with the negative prompt, as base64 (`b64_json`, with
a `data:` prefix or without); one answered with a URL instead is downloaded on the same
client, in the same time. In TensorArt's OpenAPI (「Tensor skills」): `POST {base_url}/task` naming one of its
tools (`anime_lab_wai_illustrious` and the like, `settings.model`) with the prompt and the
size, answered with a task's id, then `POST {base_url}/task/query` every `TENSORART_POLL`
seconds until the task is `FINISH`, then the picture downloaded from the address it gives
(one that expires within the hour, so it is taken at once). Its tools take neither a
negative prompt nor a seed nor the steps: what `ImagePrompt.negative` says is not sent.

An answer in any other shape, a chat completion's among them,
is not a picture. None of it is anyone's to set. What comes back is checked: exactly one
picture, 832×1216. It is kept as WebP, its size as it is, every bit of metadata dropped,
the prompt the PNG carries among it. Only the server calls the service; browsers never do.

A request is billed in pictures (`billing`): one where the service answered with a picture,
of the size asked for or not, none where it answered with an error, or not in time. A
change to an image service is tried by generating one picture (`try_image_service`), which
is billed for nothing and recorded nowhere.
"""

import asyncio
import base64
import binascii
import io
import random
import zipfile
from dataclasses import dataclass
from typing import Literal

import httpx
from PIL import Image, UnidentifiedImageError

from eidolon.billing import bill
from eidolon.config import ImageSettings
from eidolon.photo_prompt import ImagePrompt, check_prompt

WIDTH, HEIGHT = 832, 1216
STEPS = 23
SCALE = 7
SAMPLER = "k_euler_ancestral"
WEBP_QUALITY = 85
MAX_SEED = 4294967295 - 7
"""The largest seed NovelAI takes."""

TIME_LIMIT = 160
"""The longest a photo may take in all, in seconds, waiting its turn included. A queue of
TensorArt's free tier at its busiest runs past a minute before the picture is begun."""
GENERATION_TIMEOUT = httpx.Timeout(TIME_LIMIT, connect=10)

Failure = Literal["timeout", "service_error", "bad_image"]
"""Why a picture could not be had: the service took too long, answered with an error or
could not be reached, or answered with what is not one picture of the size asked for."""

TENSORART_POLL = 3
"""How often, in seconds, TensorArt is asked how a task is coming along."""

TENSORART_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
"""What TensorArt's OpenAPI is asked with: the Cloudflare in front of it refuses a request
without a browser's own (403, code 1010)."""


class ImageFailed(Exception):
    def __init__(self, reason: Failure, detail: str) -> None:
        super().__init__(f"{reason}: {detail}")
        self.reason: Failure = reason
        self.detail = detail


def _bad_image(why: str) -> ImageFailed:
    """The service answered with what is not one picture of the size asked for: what is
    recorded as an answer that could not be read (`activity.error_kind`)."""
    return ImageFailed("bad_image", f"生图服务的返回无法解析（{why}）")


@dataclass(frozen=True)
class GeneratedImage:
    webp: bytes


def generation_request(model: str, prompt: ImagePrompt, seed: int) -> dict:
    """The body NovelAI's `/ai/generate-image` is sent for `prompt` with `model`."""
    return {
        "input": prompt.positive,
        "model": model,
        "action": "generate",
        "parameters": {
            "params_version": 3,
            "width": WIDTH,
            "height": HEIGHT,
            "scale": SCALE,
            "sampler": SAMPLER,
            "steps": STEPS,
            "n_samples": 1,
            "ucPreset": 3,  # none: the negative prompt is written out in full
            "qualityToggle": False,  # the quality tags are written out too
            "seed": seed,
            "noise_schedule": "karras",
            "cfg_rescale": 0,
            "negative_prompt": prompt.negative,
            "v4_prompt": {
                "caption": {"base_caption": prompt.positive, "char_captions": []},
                "use_coords": False,
                "use_order": True,
            },
            "v4_negative_prompt": {
                "caption": {"base_caption": prompt.negative, "char_captions": []},
                "legacy_uc": False,
            },
        },
    }


class ImageGenerator:
    """Generates pictures at the image service `settings` name, over `client`; whoever
    made the client closes it."""

    def __init__(self, settings: ImageSettings, client: httpx.AsyncClient) -> None:
        self.settings = settings
        self._client = client

    async def generate(self, prompt: ImagePrompt, until: float) -> GeneratedImage:
        """One picture for `prompt`, as kept, had by `until` (the running loop's time) at
        the latest. Raises ImageFailed saying why there is none. Tells what it is billed
        for (`billing`): one picture once the service answered with any, none before."""
        bill("images", 0)
        try:
            async with asyncio.timeout_at(until):
                if self.settings.api_format == "openai":
                    picture = await self._openai(prompt)
                elif self.settings.api_format == "tensorart":
                    picture = await self._tensorart(prompt)
                else:
                    picture = await self._novelai(prompt)
        except (TimeoutError, httpx.TimeoutException) as e:
            raise ImageFailed("timeout", f"生图服务没有及时回应：{e!r}") from e
        except httpx.HTTPError as e:
            raise ImageFailed("service_error", f"无法连接生图服务：{e!r}") from e
        return GeneratedImage(kept_as_webp(picture))

    async def _novelai(self, prompt: ImagePrompt) -> bytes:
        body = generation_request(
            self.settings.model, prompt, random.SystemRandom().randint(0, MAX_SEED)
        )
        res = await self._client.post(
            f"{self.settings.base_url}/ai/generate-image", json=body, headers=self._auth()
        )
        _check_status(res)
        pictures = files_in(res.content)
        if pictures:
            bill("images", 1)
        if len(pictures) != 1:
            raise _bad_image(f"ZIP 里有 {len(pictures)} 个文件")
        return pictures[0]

    async def _openai(self, prompt: ImagePrompt) -> bytes:
        res = await self._client.post(
            f"{self.settings.base_url}/images/generations",
            json=openai_request(self.settings.model, prompt),
            headers=self._auth(),
        )
        _check_status(res)
        try:
            answer = res.json()
        except ValueError:
            raise _bad_image("不是 JSON") from None
        data = answer.get("data") if isinstance(answer, dict) else None
        if not isinstance(data, list) or not all(isinstance(d, dict) for d in data):
            raise _bad_image("不是 OpenAI 图像格式的返回")
        if not data:
            raise _bad_image("返回了 0 张图")
        picture = await self._picture(data[0])
        bill("images", 1)
        if len(data) != 1:
            raise _bad_image(f"返回了 {len(data)} 张图")
        return picture

    async def _tensorart(self, prompt: ImagePrompt) -> bytes:
        """Over TensorArt's OpenAPI: a task with one of its tools, `settings.model`, then
        asking how it is coming along until it is done, then the picture itself from the
        address it answers with. Its tools take the prompt and the size alone — no
        negative prompt, no seed, no steps — so `prompt.negative` is not sent."""
        task_id = await self._tensorart_task(prompt)
        url = await self._tensorart_wait(task_id)
        picture = await self._client.get(url)
        _check_status(picture)
        bill("images", 1)
        return picture.content

    async def _tensorart_task(self, prompt: ImagePrompt) -> str:
        """Start one picture for `prompt`; its task's id."""
        res = await self._client.post(
            f"{self.settings.base_url}/task",
            json={
                "toolName": self.settings.model,
                "inputs": [
                    {"type": "STRING", "value": prompt.positive},
                    # Numbers, not the strings the definition writes them as: sent as
                    # strings the service answers 500 saying the width is null.
                    {"type": "INTEGER", "value": WIDTH},
                    {"type": "INTEGER", "value": HEIGHT},
                    {"type": "INTEGER", "value": 1},
                ],
            },
            headers=self._tensorart_auth(),
        )
        _check_status(res)
        try:
            body = res.json()
            task = body["data"]["task"]
            task_id = task["id"]
        except (ValueError, KeyError, TypeError):
            raise _bad_image(f"不是 TensorArt 建任务的返回：{res.text[:200]}") from None
        return str(task_id)

    async def _tensorart_wait(self, task_id: str) -> str:
        """Where the picture of `task_id` is, once the service is done with it; asked for
        every `TENSORART_POLL` seconds, as long as the turn is given."""
        while True:
            await asyncio.sleep(TENSORART_POLL)
            res = await self._client.post(
                f"{self.settings.base_url}/task/query",
                json={"taskIds": [task_id]},
                headers=self._tensorart_auth(),
            )
            _check_status(res)
            try:
                task = res.json()["data"]["tasks"][0]
                status = task["status"]
            except (ValueError, KeyError, IndexError, TypeError):
                raise _bad_image(f"不是 TensorArt 查任务的返回：{res.text[:200]}") from None
            if status == "FINISH":
                outputs = task.get("outputs") or []
                if not outputs:
                    raise _bad_image("任务说完成了，却没有图")
                return str(outputs[0]["value"])
            if status in ("EXCEPTION", "CANCELED"):
                raise ImageFailed("service_error", f"TensorArt 的任务 {status}：{task}")

    def _tensorart_auth(self) -> dict[str, str]:
        """TensorArt 的 key 放在 `Echo-Access-Key` 里（不是 Bearer）；它前面的
        Cloudflare 又不认没有 User-Agent 的请求（回 403 code 1010），所以一个浏览器的
        User-Agent 一并带上。"""
        return {
            "Echo-Access-Key": self.settings.api_key,
            "User-Agent": TENSORART_USER_AGENT,
        }

    async def _picture(self, item: dict) -> bytes:
        """The picture one item of OpenAI's image format's `data` gives: decoded, or
        downloaded on the same client."""
        if isinstance(encoded := item.get("b64_json"), str):
            return _decoded(encoded)
        if isinstance(url := item.get("url"), str):
            downloaded = await self._client.get(url)
            _check_status(downloaded)
            return downloaded.content
        raise _bad_image("返回里没有 b64_json，也没有 url")

    def _auth(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.settings.api_key}"}


def openai_request(model: str, prompt: ImagePrompt) -> dict:
    """The body OpenAI's image format, `/images/generations`, is sent for `prompt` with
    `model`: what it asks for at the top level, as relays read it."""
    return {
        "model": model,
        "prompt": prompt.positive,
        "negative_prompt": prompt.negative,
        "size": f"{WIDTH}x{HEIGHT}",
        "n": 1,
        "response_format": "b64_json",
    }


async def try_image_service(generator: ImageGenerator) -> None:
    """Generate one picture, from a fixed prompt in the art style of `generator`'s settings,
    as a change to an image service is tried; raises ImageFailed saying why there is none.
    Billed for nothing and recorded nowhere: no `billing` is open for it, nor is it timed
    into the activity log."""
    until = asyncio.get_running_loop().time() + TIME_LIMIT
    await generator.generate(check_prompt(generator.settings.style), until)


def _check_status(res: httpx.Response) -> None:
    if res.status_code >= 400:
        raise ImageFailed("service_error", f"生图服务返回 {res.status_code}: {res.text[:300]}")


def _decoded(encoded: str) -> bytes:
    """The picture base64 `encoded`, with a `data:` URL's prefix or without."""
    if encoded.startswith("data:"):
        encoded = encoded.partition(",")[2]
    try:
        return base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise _bad_image("b64_json 不是 base64") from None


def files_in(archive: bytes) -> list[bytes]:
    """The files in the ZIP `archive`. Raises ImageFailed if it is not a ZIP."""
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
            return [zipped.read(n) for n in zipped.namelist() if not n.endswith("/")]
    except (zipfile.BadZipFile, OSError) as e:
        raise _bad_image(f"不是 ZIP：{e}") from None


def kept_as_webp(picture: bytes) -> bytes:
    """`picture` as a photo is kept: WebP, nothing but its pixels. Raises ImageFailed unless
    it is a picture of `WIDTH`×`HEIGHT`."""
    try:
        with Image.open(io.BytesIO(picture)) as opened:
            opened.load()
            size = opened.size
            if size != (WIDTH, HEIGHT):
                raise _bad_image(f"{size[0]}×{size[1]}，不是 {WIDTH}×{HEIGHT}")
            # Made anew from its pixels alone, so nothing of what came with it is written.
            pixels = opened.convert("RGB")
            bare = Image.frombytes("RGB", size, pixels.tobytes())
    except (UnidentifiedImageError, OSError, ValueError) as e:
        raise _bad_image(f"不是图片：{e}") from None
    out = io.BytesIO()
    bare.save(out, "WEBP", quality=WEBP_QUALITY)
    return out.getvalue()
