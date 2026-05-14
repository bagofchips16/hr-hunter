"""LinkedIn Jobs scraper — adapted for HR roles."""

import logging
import re
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote_plus

from .base import BaseScraper, JobListing

logger = logging.getLogger("hr-hunter")

HR_TERMS = {"human resource", "hr", "people", "talent", "recruit", "hrbp",
            "compensation", "benefits", "learning", "development", "engagement",
            "workforce", "hris", "diversity", "inclusion", "employee relation"}


class LinkedInScraper(BaseScraper):
    SOURCE_NAME = "LinkedIn"
    BASE_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    RATE_LIMIT_DELAY = 1.5

    async def search(self, queries: list[str], location: str = "India") -> list[JobListing]:
        results = []
        seen_urls = set()
        broad_locations = [location, "Remote"]

        for query in queries:
            for loc in broad_locations:
                try:
                    jobs = await self._search_query(query, loc)
                    for job in jobs:
                        if job.url not in seen_urls:
                            seen_urls.add(job.url)
                            results.append(job)
                    await self._rate_limit()
                except Exception as e:
                    logger.warning(f"[LinkedIn] Error searching '{query}' in '{loc}': {e}")
        return results

    async def _search_query(self, query: str, location: str) -> list[JobListing]:
        params = {
            "keywords": query,
            "location": location,
            "f_TPR": "r259200",
            "f_E": "4",
            "start": "0",
            "sortBy": "DD",
        }
        url = f"{self.BASE_URL}?{'&'.join(f'{k}={quote_plus(str(v))}' for k, v in params.items())}"
        resp = await self._safe_get(url)
        if not resp:
            return []
        return self._parse_html(resp.text)

    def _parse_html(self, html: str) -> list[JobListing]:
        results = []
        title_pattern = re.compile(r'<h3[^>]*class="base-search-card__title[^"]*"[^>]*>\s*(.*?)\s*</h3>', re.DOTALL)
        company_pattern = re.compile(r'<h4[^>]*class="base-search-card__subtitle[^"]*"[^>]*>\s*<a[^>]*>\s*(.*?)\s*</a>', re.DOTALL)
        location_pattern = re.compile(r'<span class="job-search-card__location">\s*(.*?)\s*</span>', re.DOTALL)
        link_pattern = re.compile(r'<a[^>]*class="base-card__full-link[^"]*"[^>]*href="([^"]*)"', re.DOTALL)
        time_pattern = re.compile(r'<time[^>]*datetime="([^"]*)"', re.DOTALL)

        titles = title_pattern.findall(html)
        companies = company_pattern.findall(html)
        locations = location_pattern.findall(html)
        links = link_pattern.findall(html)
        times = time_pattern.findall(html)

        for i in range(min(len(titles), len(links))):
            title = self._clean_html(titles[i]) if i < len(titles) else ""
            company = self._clean_html(companies[i]) if i < len(companies) else ""
            loc = self._clean_html(locations[i]) if i < len(locations) else ""
            url = links[i].split("?")[0] if i < len(links) else ""
            posted = None
            if i < len(times):
                try:
                    posted = datetime.fromisoformat(times[i])
                except (ValueError, TypeError):
                    pass
            if not title or not url:
                continue
            title_lower = title.lower()
            if not any(t in title_lower for t in HR_TERMS):
                continue
            listing = JobListing(
                title=title,
                company=company,
                location=loc,
                url=url,
                source=self.SOURCE_NAME,
                posted_date=posted,
                seniority=self._detect_seniority(title_lower),
            )
            results.append(listing)
        return results

    def _clean_html(self, text: str) -> str:
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _detect_seniority(self, title: str) -> str:
        if any(k in title for k in ["senior", "sr.", "sr "]):
            return "Senior HR"
        if any(k in title for k in ["lead", "head", "director"]):
            return "HR Lead"
        if any(k in title for k in ["manager"]):
            return "HR Manager"
        return "HR"
