"""Google Careers scraper — adapted for HR roles."""

import json
import logging
import re
from datetime import datetime
from typing import Optional
from urllib.parse import quote_plus

from .base import BaseScraper, JobListing

logger = logging.getLogger("hr-hunter")

HR_TERMS = {"human resource", "hr", "people", "talent", "recruit", "hrbp",
            "compensation", "benefits", "learning", "development", "engagement",
            "workforce", "hris", "diversity", "inclusion", "employee relation"}


class GoogleCareersScraper(BaseScraper):
    SOURCE_NAME = "Google Careers"
    BASE_URL = "https://www.google.com/about/careers/applications/jobs/results/"
    RATE_LIMIT_DELAY = 2.0

    async def search(self, queries: list[str], location: str = "India") -> list[JobListing]:
        results = []
        seen = set()
        for query in queries:
            try:
                jobs = await self._search_query(query, location)
                for j in jobs:
                    if j.uid not in seen:
                        seen.add(j.uid)
                        results.append(j)
                await self._rate_limit()
            except Exception as e:
                logger.warning(f"[Google Careers] Error: {e}")
        return results

    async def _search_query(self, query: str, location: str) -> list[JobListing]:
        url = (
            f"{self.BASE_URL}?q={quote_plus(query)}"
            f"&target_level=MID&target_level=SENIOR"
            f"&location={quote_plus(location)}"
        )
        resp = await self._safe_get(url)
        if not resp:
            return []
        return self._parse_embedded_data(resp.text)

    def _parse_embedded_data(self, html: str) -> list[JobListing]:
        marker = "key: 'ds:1'"
        idx = html.find(marker)
        if idx < 0:
            marker = 'key: "ds:1"'
            idx = html.find(marker)
        if idx < 0:
            return []
        data_idx = html.find("data:", idx)
        if data_idx < 0:
            return []
        arr_start = html.find("[", data_idx)
        if arr_start < 0:
            return []
        raw = self._extract_balanced(html, arr_start)
        if not raw:
            return []
        raw = (raw.replace("\\u003c", "<").replace("\\u003e", ">")
               .replace("\\u0026", "&").replace("\\u003d", "="))
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return []
        jobs_list = data[0] if isinstance(data, list) and data else []
        results = []
        for job in jobs_list:
            try:
                listing = self._parse_job_entry(job)
                if listing:
                    results.append(listing)
            except (IndexError, TypeError):
                continue
        return results

    def _parse_job_entry(self, job: list) -> Optional[JobListing]:
        title = job[1] if len(job) > 1 else ""
        title_lower = title.lower()
        if not any(t in title_lower for t in HR_TERMS):
            return None
        company = job[7] if len(job) > 7 and job[7] else "Google"
        job_id = job[0] if len(job) > 0 else ""
        url = f"https://www.google.com/about/careers/applications/jobs/results/{job_id}"
        location = ""
        if len(job) > 9 and isinstance(job[9], list):
            locs = []
            for loc_entry in job[9]:
                if isinstance(loc_entry, list) and loc_entry:
                    locs.append(str(loc_entry[0]))
            location = "; ".join(locs)
        description = ""
        for field_idx in [10, 3, 4]:
            if len(job) > field_idx and isinstance(job[field_idx], list):
                for item in job[field_idx]:
                    if isinstance(item, str) and len(item) > 50:
                        description += re.sub(r"<[^>]+>", " ", item) + " "
                        break
        posted = None
        if len(job) > 14 and isinstance(job[14], list) and job[14]:
            try:
                ts = int(job[14][0])
                posted = datetime.fromtimestamp(ts)
            except (ValueError, TypeError, OSError):
                pass
        return JobListing(
            title=title, company=company, location=location, url=url,
            source=self.SOURCE_NAME, posted_date=posted,
            description=description[:2000],
            seniority=self._detect_seniority(title_lower),
        )

    @staticmethod
    def _extract_balanced(text: str, start: int) -> Optional[str]:
        depth = 0
        i = start
        while i < len(text):
            c = text[i]
            if c == "[": depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0: return text[start:i+1]
            elif c == '"':
                i += 1
                while i < len(text) and text[i] != '"':
                    if text[i] == "\\": i += 1
                    i += 1
            i += 1
        return None

    def _detect_seniority(self, title: str) -> str:
        if any(k in title for k in ["senior", "sr.", "sr "]):
            return "Senior HR"
        if any(k in title for k in ["lead", "head", "director"]):
            return "HR Lead"
        if any(k in title for k in ["manager"]):
            return "HR Manager"
        return "HR"
