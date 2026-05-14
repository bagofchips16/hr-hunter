"""Amazon Jobs scraper — adapted for HR roles."""

import logging
from datetime import datetime
from typing import Optional
from urllib.parse import quote_plus

from .base import BaseScraper, JobListing

logger = logging.getLogger("hr-hunter")

HR_TERMS = {"human resource", "hr", "people", "talent", "recruit", "hrbp",
            "compensation", "benefits", "learning", "development", "engagement",
            "workforce", "hris", "diversity", "inclusion", "employee relation"}


class AmazonJobsScraper(BaseScraper):
    SOURCE_NAME = "Amazon Jobs"
    BASE_URL = "https://www.amazon.jobs/en/search.json"
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
                logger.warning(f"[Amazon Jobs] Error: {e}")
        return results

    async def _search_query(self, query: str, location: str) -> list[JobListing]:
        params = {
            "base_query": query,
            "loc_query": location,
            "country": "IND",
            "category[]": "human-resources",
            "sort": "recent",
            "result_limit": 20,
        }
        url = f"{self.BASE_URL}?{'&'.join(f'{k}={quote_plus(str(v))}' for k, v in params.items())}"
        data = await self._safe_get_json(url)
        if not data:
            return []
        results = []
        for job in data.get("jobs", []):
            title = job.get("title", "")
            title_lower = title.lower()
            if not any(t in title_lower for t in HR_TERMS):
                continue
            description = job.get("description", "") or job.get("basic_qualifications", "")
            loc = job.get("normalized_location", "") or job.get("city", "")
            job_id = job.get("id_icims", "") or job.get("id", "")
            posted = None
            if job.get("posted_date"):
                try:
                    posted = datetime.strptime(job["posted_date"], "%B %d, %Y")
                except (ValueError, TypeError):
                    try:
                        posted = datetime.fromisoformat(job["posted_date"])
                    except (ValueError, TypeError):
                        pass
            listing = JobListing(
                title=title, company="Amazon", location=loc,
                url=f"https://www.amazon.jobs/en/jobs/{job_id}",
                source=self.SOURCE_NAME, posted_date=posted,
                description=description[:2000],
                seniority=self._detect_seniority(title_lower),
            )
            results.append(listing)
        return results

    def _detect_seniority(self, title: str) -> str:
        if any(k in title for k in ["senior", "sr.", "sr "]):
            return "Senior HR"
        if any(k in title for k in ["lead", "head", "director"]):
            return "HR Lead"
        if any(k in title for k in ["manager"]):
            return "HR Manager"
        return "HR"
