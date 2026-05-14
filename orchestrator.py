"""
Job Scraping Orchestrator for HR roles.
Runs all scrapers concurrently, deduplicates, and scores results.
"""

import asyncio
import logging
from datetime import datetime
from typing import Callable, Optional

from scrapers.greenhouse import GreenhouseScraper
from scrapers.lever import LeverScraper
from scrapers.ashby import AshbyScraper
from scrapers.linkedin import LinkedInScraper
from scrapers.google_careers import GoogleCareersScraper
from scrapers.amazon import AmazonJobsScraper
from scoring import analyze_jobs
from config import (
    SEARCH_QUERIES, GREENHOUSE_BOARDS, LEVER_BOARDS, ASHBY_BOARDS,
    SEARCH_CONFIG, CANDIDATE_PROFILE,
)
from applicant.engine import ApplicationEngine

logger = logging.getLogger("hr-hunter")

_applied_engine = ApplicationEngine()


async def run_all_scrapers(on_progress: Optional[Callable] = None) -> dict:
    start_time = datetime.now()

    scrapers = [
        ("Greenhouse", GreenhouseScraper(GREENHOUSE_BOARDS)),
        ("Lever", LeverScraper(LEVER_BOARDS)),
        ("Ashby", AshbyScraper(ASHBY_BOARDS)),
        ("LinkedIn", LinkedInScraper()),
        ("Google Careers", GoogleCareersScraper()),
        ("Amazon Jobs", AmazonJobsScraper()),
    ]

    total_scrapers = len(scrapers)
    completed_count = 0
    all_jobs = []
    source_stats = {}
    errors = []

    async def _emit(event_type: str, data: dict):
        if on_progress:
            await on_progress({"event": event_type, **data})

    await _emit("start", {
        "total_sources": total_scrapers,
        "sources": [name for name, _ in scrapers],
    })

    for name, _ in scrapers:
        await _emit("source_status", {"source": name, "status": "pending", "found": 0})

    async def _run_and_report(name: str, scraper) -> list:
        nonlocal completed_count
        await _emit("source_status", {"source": name, "status": "scanning", "found": 0})
        try:
            jobs = await scraper.search(SEARCH_QUERIES, "India")
            completed_count += 1
            source_stats[name] = {"found": len(jobs), "error": None}
            await _emit("source_status", {
                "source": name, "status": "done", "found": len(jobs),
                "progress": completed_count, "total": total_scrapers,
            })
            return jobs
        except Exception as e:
            completed_count += 1
            err_msg = str(e)[:100]
            errors.append(f"{name}: {err_msg}")
            source_stats[name] = {"found": 0, "error": err_msg}
            await _emit("source_status", {
                "source": name, "status": "error", "found": 0, "error": err_msg,
                "progress": completed_count, "total": total_scrapers,
            })
            logger.error(f"[Orchestrator] {name} failed: {e}")
            return []

    tasks = [_run_and_report(name, scraper) for name, scraper in scrapers]
    results = await asyncio.gather(*tasks)

    for job_list in results:
        all_jobs.extend(job_list)

    for _, scraper in scrapers:
        await scraper.close()

    await _emit("phase", {"phase": "dedup", "message": "Deduplicating results..."})
    seen = set()
    unique_jobs = []
    for job in all_jobs:
        if job.uid not in seen:
            seen.add(job.uid)
            unique_jobs.append(job)

    applied_urls = _applied_engine.get_applied_urls()
    if applied_urls:
        before = len(unique_jobs)
        unique_jobs = [j for j in unique_jobs if j.url not in applied_urls]
        skipped = before - len(unique_jobs)
        if skipped:
            logger.info(f"Filtered out {skipped} already-applied jobs")

    await _emit("phase", {"phase": "scoring", "message": f"Scoring {len(unique_jobs)} roles..."})
    scored_jobs = analyze_jobs(unique_jobs)

    min_score = SEARCH_CONFIG.get("min_fit_score", 40)
    filtered_jobs = [j for j in scored_jobs if j.fit_score >= min_score]
    display_jobs = filtered_jobs

    elapsed = (datetime.now() - start_time).total_seconds()
    insights = _generate_market_insights(scored_jobs)

    result = {
        "jobs": [j.to_dict() for j in display_jobs],
        "metadata": {
            "total_scraped": len(all_jobs),
            "unique": len(unique_jobs),
            "above_threshold": len(filtered_jobs),
            "displayed": len(display_jobs),
            "elapsed_seconds": round(elapsed, 1),
            "source_stats": source_stats,
            "errors": errors,
            "timestamp": datetime.now().isoformat(),
            "min_fit_score": min_score,
        },
        "market_insights": insights,
    }

    await _emit("complete", {
        "elapsed": round(elapsed, 1),
        "total_scraped": len(all_jobs),
        "displayed": len(display_jobs),
    })

    return result


def _generate_market_insights(jobs: list) -> dict:
    if not jobs:
        return {"trends": ["Insufficient data"], "aggressive_hirers": [], "jd_patterns": []}

    company_counts = {}
    for job in jobs:
        comp = job.company.strip()
        company_counts[comp] = company_counts.get(comp, 0) + 1
    aggressive_hirers = sorted(company_counts.items(), key=lambda x: -x[1])[:5]

    keyword_freq = {}
    keywords_to_track = [
        "hrbp", "business partner", "talent acquisition", "recruiting",
        "compensation", "benefits", "total rewards", "learning",
        "development", "analytics", "hris", "workday", "employee relations",
        "diversity", "inclusion", "engagement", "retention",
        "performance management", "succession planning", "change management",
    ]
    for job in jobs:
        combined = f"{job.title} {job.description}".lower()
        for kw in keywords_to_track:
            if kw in combined:
                keyword_freq[kw] = keyword_freq.get(kw, 0) + 1

    top_patterns = sorted(keyword_freq.items(), key=lambda x: -x[1])[:8]

    trends = []
    if keyword_freq.get("hrbp", 0) + keyword_freq.get("business partner", 0) > 5:
        trends.append("Strong demand for HR Business Partners across sectors")
    if keyword_freq.get("talent acquisition", 0) + keyword_freq.get("recruiting", 0) > 5:
        trends.append("Active hiring for TA leadership — companies scaling teams")
    if keyword_freq.get("analytics", 0) + keyword_freq.get("hris", 0) > 3:
        trends.append("Growing demand for HR Analytics / HRIS — data-driven HR is trending")
    if keyword_freq.get("diversity", 0) + keyword_freq.get("inclusion", 0) > 2:
        trends.append("DEI roles on the rise — companies investing in inclusive workplaces")
    if not trends:
        trends.append("Steady HR hiring across industries")

    return {
        "trends": trends,
        "aggressive_hirers": [{"company": c, "open_roles": n} for c, n in aggressive_hirers],
        "jd_patterns": [{"keyword": kw, "frequency": freq} for kw, freq in top_patterns],
    }
