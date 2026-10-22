"""Her letters' envelopes: the card art that sits behind one (fork).

A letter picks the newest produce card she had when she wrote — SSR/UR first, then the
plain ones — and keeps its art in the data volume, where `/api/letters/{id}/envelope`
serves it from. Downloading once per card is enough: the art of a card never changes.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import httpx

from eidolon.mirror import STATIC_URL, Mirror

log = logging.getLogger(__name__)

_CARD_ART = f"{STATIC_URL}/images/content/idols/card"
"""Where a produce card's art is filed on the CDN, by its `enzaId`."""


class Envelopes:
    """The card art behind her letters, kept as one file per card in `directory`."""

    def __init__(self, directory: Path, mirror: Mirror | None = None) -> None:
        self._directory = directory
        self._mirror = mirror or Mirror()

    def path(self, enza_id: str) -> Path:
        return self._directory / f"{enza_id}.jpg"

    async def for_idol(self, idol_id: int | None, now: datetime) -> str | None:
        """The `enzaId` of the card whose art her letter should carry, its art fetched if this
        is the first letter to use it; None when she has no card to show, or the mirror
        cannot be reached (the letter is still written, without an envelope)."""
        if idol_id is None:
            return None
        try:
            cards = await self._mirror.cards(idol_id)
        except Exception:
            log.warning("no cards for idol %s", idol_id, exc_info=True)
            return None
        today = now.date().isoformat()
        candidates = [
            card
            for card in cards
            if card.enza_id
            and card.type.startswith("P_")
            and (not card.release_date or card.release_date <= today)
        ]
        if not candidates:
            return None
        # 优先 SSR/UR，其次按发售日——她写信那天手上最新的那张。
        candidates.sort(
            key=lambda card: (
                1 if ("SSR" in card.type or "UR" in card.type) else 0,
                card.release_date,
            ),
            reverse=True,
        )
        enza_id = candidates[0].enza_id
        if self.path(enza_id).exists():
            return enza_id
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=10)) as client:
                response = await client.get(f"{_CARD_ART}/{enza_id}.jpg")
                response.raise_for_status()
        except Exception:
            log.warning("card art for %s could not be fetched", enza_id, exc_info=True)
            return None
        self._directory.mkdir(parents=True, exist_ok=True)
        self.path(enza_id).write_bytes(response.content)
        log.info("kept the card art %s for her letters", enza_id)
        return enza_id
