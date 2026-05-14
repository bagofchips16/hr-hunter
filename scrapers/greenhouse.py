"""Greenhouse ATS scraper — adapted for HR roles."""

import logging
from datetime import datetime
from typing import Optional

from .base import BaseScraper, JobListing

logger = logging.getLogger("hr-hunter")

HR_TERMS = {"human resource", "hr", "people", "talent", "recruit", "hrbp",
            "compensation", "benefits", "learning", "development", "engagement",
            "workforce", "hris", "diversity", "inclusion", "employee relation"}


class GreenhouseScraper(BaseScraper):
    SOURCE_NAME = "Greenhouse"
    BASE_URL = "https://boards-api.greenhouse.io/v1/boards"

    def __init__(self, boards: dict[str, str]):
        super().__init__()
        self.boards = boards

    async def search(self, queries: list[str], location: str = "India") -> list[JobListing]:
        results = []
        for slug, company_name in self.boards.items():
            jobs = await self._fetch_board(slug, company_name)
            if jobs:
                filtered = self._filter_jobs(jobs, queries, location)
                results.extend(filtered)
        return results

    async def _fetch_board(self, slug: str, company_name: str) -> list[dict]:
        url = f"{self.BASE_URL}/{slug}/jobs?content=true"
        data = await self._safe_get_json(url)
        if not data or "jobs" not in data:
            return []
        jobs = []
        for job in data["jobs"]:
            jobs.append({
                "id": job.get("id"),
                "title": job.get("title", ""),
                "location": job.get("location", {}).get("name", ""),
                "url": job.get("absolute_url", ""),
                "updated_at": job.get("updated_at", ""),
                "content": job.get("content", ""),
                "company": company_name,
                "departments": [d.get("name", "") for d in job.get("departments", [])],
            })
        return jobs

    def _filter_jobs(self, jobs: list[dict], queries: list[str], location: str) -> list[JobListing]:
        results = []
        for job in jobs:
            title_lower = job["title"].lower()
            if not any(t in title_lower for t in HR_TERMS):
                continue
            posted = None
            if job.get("updated_at"):
                try:
                    posted = datetime.fromisoformat(job["updated_at"].replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass
            listing = JobListing(
                title=job["title"],
                company=job["company"],
                location=job.get("location", ""),
                url=job.get("url", ""),
                source=self.SOURCE_NAME,
                posted_date=posted,
                description=job.get("content", "")[:2000],
                seniority=self._detect_seniority(title_lower),
                department=" | ".join(job.get("departments", [])),
            )
            results.append(listing)
        return results

    def _detect_seniority(self, title: str) -> str:
        title = title.lower()
        if any(k in title for k in ["senior", "sr.", "sr "]):
            return "Senior HR"
        if any(k in title for k in ["lead", "head", "director"]):
            return "HR Lead"
        if any(k in title for k in ["manager"]):
            return "HR Manager"
        if any(k in title for k in ["associate", "executive", "junior"]):
            return "HR Associate"
        return "HR"
