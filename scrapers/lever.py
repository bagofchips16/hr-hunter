"""Lever ATS scraper — adapted for HR roles."""

import logging
from datetime import datetime
from typing import Optional

from .base import BaseScraper, JobListing

logger = logging.getLogger("hr-hunter")

HR_TERMS = {"human resource", "hr", "people", "talent", "recruit", "hrbp",
            "compensation", "benefits", "learning", "development", "engagement",
            "workforce", "hris", "diversity", "inclusion", "employee relation"}


class LeverScraper(BaseScraper):
    SOURCE_NAME = "Lever"
    BASE_URL = "https://api.lever.co/v0/postings"

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
        url = f"{self.BASE_URL}/{slug}?mode=json"
        data = await self._safe_get_json(url)
        if not data or not isinstance(data, list):
            return []
        jobs = []
        for job in data:
            categories = job.get("categories", {})
            jobs.append({
                "title": job.get("text", ""),
                "location": categories.get("location", ""),
                "url": job.get("hostedUrl", ""),
                "created_at": job.get("createdAt"),
                "description": job.get("descriptionPlain", ""),
                "company": company_name,
                "team": categories.get("team", ""),
                "department": categories.get("department", ""),
            })
        return jobs

    def _filter_jobs(self, jobs: list[dict], queries: list[str], location: str) -> list[JobListing]:
        results = []
        for job in jobs:
            title_lower = job["title"].lower()
            if not any(t in title_lower for t in HR_TERMS):
                continue
            posted = None
            if job.get("created_at"):
                try:
                    posted = datetime.fromtimestamp(job["created_at"] / 1000)
                except (ValueError, TypeError, OSError):
                    pass
            listing = JobListing(
                title=job["title"],
                company=job["company"],
                location=job.get("location", ""),
                url=job.get("url", ""),
                source=self.SOURCE_NAME,
                posted_date=posted,
                description=job.get("description", "")[:2000],
                seniority=self._detect_seniority(title_lower),
                department=f"{job.get('team', '')} | {job.get('department', '')}",
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
        return "HR"
