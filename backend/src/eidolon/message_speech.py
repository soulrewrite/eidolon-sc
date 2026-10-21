"""The speech of a reply's segments (GLOSSARY.md「消息语音」): what she said in a text
turn, voiced on demand, so that the browser can play it a segment at a time without a
call.

A segment is voiced once in her voice, delivery cues and all, over Fish Audio's HTTP API
as mp3 — the same way a greeting is (`greetings`) — and put in the stands' bucket under
`message-speech/<id>-<hash>.mp3`. The hash is of what she says in the segment, of her
voice, of the model that voices it and of the readings it uses, as a greeting's hash is:
so the server knows where it is without asking the bucket, a segment whose words, voice
or readings changed is at an address no browser has cached, and one the bucket already
has is never voiced again. Every user who asks hears the same audio.

Voicing happens as the user asks, never in advance: the first listener of a segment
waits for it to be voiced, a few seconds; everyone from then on is sent straight to the
bucket, whose copy any browser may keep forever. It is the deployer's key that voices, as
`.env` has it (`FISH_AUDIO_API_KEY`, `FISH_AUDIO_MODEL`), through the proxy or direct as
the proxy settings have it for the tts service. Nothing is recorded of it and it counts
against no one's limit, as with greetings (a user's own key is not used: bringing one to
a text turn does not bring it to listening).
"""

import asyncio
import hashlib
import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import httpx
from fastapi import FastAPI, HTTPException

from eidolon.characters import Character
from eidolon.config import FishAudioModel
from eidolon.delivery_cues import spoken_by, voiced
from eidolon.greetings import FishAudioSettings
from eidolon.proxy import ProxyRoutes
from eidolon.readings import Reading, pronunciation_dictionary
from eidolon.s3 import Bucket, S3Error, S3Settings
from eidolon.sessions import UserId
from eidolon.store import Store

log = logging.getLogger(__name__)

DIRECTORY = "message-speech"
"""Where in the stands' bucket the segments' speech is put."""

SPEECH_CACHE = "public, max-age=31536000, immutable"
"""A segment's speech never changes at its address: new words, a new voice, a new model
or new readings are a new one."""

FISH_TTS_HTTP_URL = "https://api.fish.audio/v1/tts"
_TIMEOUT = httpx.Timeout(60, connect=10)
"""A segment is a few seconds of audio, voiced in a few seconds more."""

_HASH_LENGTH = 12

VOICE_ATTEMPTS = 3
"""How many times a segment is tried before it is given up on. A proxy dropping one
connection is common enough (a node going away mid-handshake) that the next attempt a
moment later usually goes through; a service refusing outright is not retried by it."""

VOICE_RETRY = 0.8
"""How long to wait before trying again, in seconds."""

WARM_SEGMENTS = 2
"""How many segments may be voiced ahead of anyone asking for them at once: one that has
just been said while the previous one is still being voiced. Not more, so that a service
with a handful of concurrent requests to give is not taken up by one reply."""

NOT_FOUND = "这条消息没有语音"

UNAVAILABLE = "这句语音暂时合成不出来，稍后再试"


@dataclass(frozen=True)
class _Spoken:
    """Where a segment's speech is, and what to say in her voice if the bucket does not
    have it yet."""

    path: str
    said: str
    voice_id: str


def speech_path(character: Character, said: str, model: FishAudioModel,
                readings: Sequence[Reading]) -> str | None:
    """Where the segment `said` in her voice is in the bucket; None without a voice to
    say it in. The same words in the same voice, model and readings are always at the
    same address; any change is a new one."""
    if not character.voice_id.strip():
        return None
    seeded = f"{character.voice_id}\n{model}\n{said}"
    seeded += "".join(f"\n{r.written}\t{r.phonemes}" for r in readings)
    digest = hashlib.sha256(seeded.encode()).hexdigest()
    return f"{DIRECTORY}/{character.id}-{digest[:_HASH_LENGTH]}.mp3"


class MessageSpeech:
    """The speech of every reply's segments, voiced on the deployer's key and put in the
    stands' bucket of `settings`, through the proxy or direct as `routes` has it for the
    tts service, with `readings` as every segment's pronunciation dictionary."""

    def __init__(
        self,
        characters: Mapping[str, Character],
        readings: Sequence[Reading],
        fish: FishAudioSettings,
        settings: S3Settings,
        routes: ProxyRoutes,
        assets_url: str,
    ) -> None:
        self._characters = characters
        self._readings = readings
        self._dictionary = pronunciation_dictionary(readings)
        self._fish = fish
        self._routes = routes
        self._bucket = Bucket(settings)
        self._assets_url = assets_url.rstrip("/")
        # A segment just said is voiced while the next one is being written, two at a time
        # at most: a user sending several replies in a row must not have them pile up on the
        # service.
        self._warming = asyncio.Semaphore(WARM_SEGMENTS)

    async def aclose(self) -> None:
        await self._bucket.aclose()

    async def url_of(self, character_id: str, ja: str) -> str | None:
        """Where the segment's speech is heard from: the bucket's address of it, voiced
        and put first if the bucket does not have it yet; None if she has no voice to say
        it in, or it cannot be voiced or put (said why in the log)."""
        spoken = self._spoken(character_id, ja)
        if spoken is None:
            return None
        try:
            if not await self._bucket.exists(spoken.path):
                audio = await self._voice(spoken.said, spoken.voice_id)
                await self._bucket.put(spoken.path, audio, "audio/mpeg", SPEECH_CACHE)
        except (S3Error, _CouldNotVoice):
            log.warning("the speech of a segment could not be put", exc_info=True)
            return None
        return f"{self._assets_url}/{spoken.path}"

    async def warm(self, character_id: str, ja: str) -> None:
        """Voice a segment of a reply as it is said, before anyone asks for it: by the time
        the user has read it and decided to listen, it is in the bucket and the click plays
        at once. One that cannot be voiced is left to when it is asked for, which tries
        afresh anyway."""
        async with self._warming:
            await self.url_of(character_id, ja)

    async def again(self, character_id: str, ja: str) -> str | None:
        """Voice the segment afresh and overwrite what the bucket has, for a take that came
        out broken: Fish Audio answers a little differently every time, so the same words
        can come out again. `None` if she has no voice for it, or it cannot be voiced or
        put — the bucket keeping the take it had."""
        spoken = self._spoken(character_id, ja)
        if spoken is None:
            return None
        async with self._warming:
            try:
                audio = await self._voice(spoken.said, spoken.voice_id)
                await self._bucket.put(spoken.path, audio, "audio/mpeg", SPEECH_CACHE)
            except (S3Error, _CouldNotVoice):
                log.warning("the speech of a segment could not be voiced again", exc_info=True)
                return None
        return f"{self._assets_url}/{spoken.path}"

    def _spoken(self, character_id: str, ja: str) -> _Spoken | None:
        character = self._characters.get(character_id)
        if character is None:
            return None
        said = spoken_by(voiced(ja), self._fish.model)
        if not said:
            return None
        path = speech_path(character, said, self._fish.model, self._readings)
        if path is None:
            return None
        return _Spoken(path, said, character.voice_id)

    async def _voice(self, said: str, voice_id: str) -> bytes:
        """`said` in her voice as mp3, over the proxy or direct as the settings have it
        for the tts service. Tried `VOICE_ATTEMPTS` times: the proxy losing a connection
        is momentary, and the next one usually goes through."""
        for attempt in range(1, VOICE_ATTEMPTS + 1):
            try:
                return await self._voice_once(said, voice_id)
            except _CouldNotVoice as e:
                if not e.retryable or attempt == VOICE_ATTEMPTS:
                    raise
                log.info("语音合成第 %d 次没成，等一下再试", attempt)
                await asyncio.sleep(VOICE_RETRY)
        raise AssertionError("unreachable")

    async def _voice_once(self, said: str, voice_id: str) -> bytes:
        """`said` in her voice as mp3, once."""
        body: dict[str, object] = {"text": said, "reference_id": voice_id, "format": "mp3"}
        if self._dictionary is not None:
            body["pronunciation_dictionary"] = self._dictionary
        client = self._routes.client("tts", _TIMEOUT)
        try:
            response = await client.post(
                FISH_TTS_HTTP_URL,
                headers={"Authorization": f"Bearer {self._fish.api_key}", "model": self._fish.model},
                json=body,
            )
        except httpx.HTTPError as e:
            raise _CouldNotVoice(f"连不上语音合成：{e!r}") from None
        finally:
            await client.aclose()
        if response.is_error:
            raise _CouldNotVoice(
                f"语音合成没能合成：{response.status_code} {response.text[:200]}",
                retryable=response.status_code >= 500,
            )
        if not response.content:
            raise _CouldNotVoice("语音合成没有返回音频")
        return response.content


class _CouldNotVoice(RuntimeError):
    """A segment could not be voiced: the service unreachable, refusing, or silent.

    `retryable` says whether trying again at once is worth it: a connection lost on the
    way, or the service's own 5xx, may well go through the next time; a key refused or a
    request it will not take will not."""

    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


def add_message_speech_routes(
    app: FastAPI, store: Store, speech: MessageSpeech
) -> None:
    """`/api/messages/{id}/speech?segment={n}`: where segment `n` of her reply is heard
    from, as `{"url": ...}` in the bucket, voiced first if the bucket does not have it
    yet. Only the user whose conversation the reply is in is told of it; to anyone else,
    admins too, there is no such message (404). A segment that never made it (the reply
    cut short), one of her replies whose character has no voice, and one that cannot be
    voiced or put are all 503 with what to say about it, the browser falling back to
    text. `POST .../speech/again?segment={n}` voices it afresh, overwriting what the
    bucket has: Fish Audio answers a little differently every time, so a take that came
    out broken can be had again."""

    @app.get("/api/messages/{message_id}/speech")
    async def message_speech(message_id: int, user_id: UserId, segment: int = 0) -> dict:
        found = store.message_segments(message_id, user_id)
        if found is None:
            raise HTTPException(404, NOT_FOUND)
        return await _where(found, segment)

    @app.get("/api/reach-outs/{reach_out_id}/speech")
    async def reach_out_speech(reach_out_id: int, user_id: UserId, segment: int = 0) -> dict:
        found = store.reach_out_segments(reach_out_id, user_id)
        if found is None:
            raise HTTPException(404, NOT_FOUND)
        return await _where(found, segment)

    @app.post("/api/messages/{message_id}/speech/again")
    async def message_speech_again(
        message_id: int, user_id: UserId, segment: int = 0
    ) -> dict:
        """这一句重新合成一遍，覆盖桶里那份（`MessageSpeech.again`）：合成是随机的，
        听出破音就来一次。"""
        found = store.message_segments(message_id, user_id)
        if found is None:
            raise HTTPException(404, NOT_FOUND)
        return await _again(found, segment)

    @app.post("/api/reach-outs/{reach_out_id}/speech/again")
    async def reach_out_speech_again(
        reach_out_id: int, user_id: UserId, segment: int = 0
    ) -> dict:
        found = store.reach_out_segments(reach_out_id, user_id)
        if found is None:
            raise HTTPException(404, NOT_FOUND)
        return await _again(found, segment)

    async def _again(found: tuple[str, str], segment: int) -> dict:
        """What segment `segment` of `found` now sounds like, voiced afresh."""
        character_id, segments_json = found
        segments = json.loads(segments_json or "[]")
        if not 0 <= segment < len(segments):
            raise HTTPException(404, NOT_FOUND)
        ja = segments[segment].get("ja") or ""
        if not ja.strip():
            raise HTTPException(404, NOT_FOUND)
        url = await speech.again(character_id, ja)
        if url is None:
            raise HTTPException(503, UNAVAILABLE)
        return {"url": url}

    async def _where(found: tuple[str, str], segment: int) -> dict:
        """Where segment `segment` of what she said, `found`, is heard from."""
        character_id, segments_json = found
        segments = json.loads(segments_json or "[]")
        if not 0 <= segment < len(segments):
            raise HTTPException(404, NOT_FOUND)
        ja = segments[segment].get("ja") or ""
        if not ja.strip():
            raise HTTPException(404, NOT_FOUND)
        url = await speech.url_of(character_id, ja)
        if url is None:
            raise HTTPException(503, UNAVAILABLE)
        return {"url": url}
