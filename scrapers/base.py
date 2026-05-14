"""Base scraper interface and common utilities."""

import asyncio
import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

import httpx

logger = logging.getLogger("hr-hunter")


@dataclass
class JobListing:
    """Standardized job listing from any source."""
    title: str
    company: str
    location: str
    url: str
    source: str
    posted_date: Optional[datetime] = None
    description: str = ""
    seniority: str = ""
    department: str = ""
    # Analysis fields (populated by scoring engine)
    fit_score: int = 0
    priority: str = ""
    signal_strength: str = ""
    match_reason: str = ""
    referral_advantage: str = ""
    hiring_pain_point: str = ""
    speed_to_hire: str = ""
    estimated_tc: str = ""
    interview_loop: list = field(default_factory=list)
    inmail_draft: str = ""
    visa_note: str = ""
    experience_note: str = ""

    @property
    def uid(self) -> str:
        raw = f"{self.company}|{self.title}|{self.url}"
        return hashlib.md5(raw.encode()).hexdigest()

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.posted_date:
            d["posted_date"] = self.posted_date.isoformat()
        return d


class BaseScraper(ABC):
    """Abstract base for all job scrapers."""

    SOURCE_NAME: str = "unknown"
    BASE_URL: str = ""
    RATE_LIMIT_DELAY: float = 1.5

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/json",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

    async def close(self):
        await self.client.aclose()

    @abstractmethod
    async def search(self, queries: list[str], location: str = "India") -> list[JobListing]:
        ...

    async def _rate_limit(self):
        await asyncio.sleep(self.RATE_LIMIT_DELAY)

    async def _safe_get(self, url: str, **kwargs) -> Optional[httpx.Response]:
        try:
            resp = await self.client.get(url, **kwargs)
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as e:
            logger.warning(f"[{self.SOURCE_NAME}] HTTP {e.response.status_code} for {url}")
        except httpx.RequestError as e:
            logger.warning(f"[{self.SOURCE_NAME}] Request error: {e}")
        return None

    async def _safe_get_json(self, url: str, **kwargs) -> Optional[dict]:
        resp = await self._safe_get(url, **kwargs)
        if resp:
            try:
                return resp.json()
            except Exception:
                logger.warning(f"[{self.SOURCE_NAME}] Failed to parse JSON from {url}")
        return None
