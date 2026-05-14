"""
Application Engine — orchestrates the semi-auto apply flow.
Manages browser lifecycle, routes to correct ATS module, tracks applications.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

from .greenhouse_apply import detect_greenhouse, fill_and_submit as greenhouse_submit
from .lever_apply import detect_lever, fill_and_submit as lever_submit
from .cover_letter import generate_cover_letter

logger = logging.getLogger("applicant.engine")

BASE_DIR = Path(__file__).resolve().parent.parent
PROFILE_PATH = BASE_DIR / "assets" / "profile.json"
RESUME_PATH = BASE_DIR / "assets" / "resume.pdf"
LOG_PATH = BASE_DIR / "assets" / "applications_log.json"


class ApplicationEngine:
    """Semi-auto application engine with preview → confirm → submit flow."""

    def __init__(self):
        self.profile = self._load_profile()
        self._pw = None
        self._browser = None

    def _load_profile(self) -> dict:
        if PROFILE_PATH.exists():
            with open(PROFILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    async def _ensure_browser(self):
        if not self._browser:
            self._pw = await async_playwright().start()
            self._browser = await self._pw.chromium.launch(headless=True)

    async def close(self):
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._pw:
            await self._pw.stop()
            self._pw = None

    def detect_ats(self, url: str) -> str:
        """Detect which ATS a job URL belongs to."""
        url_lower = url.lower()
        if "greenhouse.io" in url_lower:
            return "greenhouse"
        if "lever.co" in url_lower:
            return "lever"
        return "unsupported"

    async def preview(self, job: dict) -> dict:
        """
        Generate a preview of what will be filled in the application.
        Does NOT open a browser — just computes the data.
        """
        url = job.get("url", "")
        ats = self.detect_ats(url)

        cover_letter = generate_cover_letter(self.profile, job)
        resume_exists = RESUME_PATH.exists()

        preview_data = {
            "ats_type": ats,
            "url": url,
            "company": job.get("company", ""),
            "title": job.get("title", ""),
            "supported": ats != "unsupported",
            "fields": {
                "first_name": self.profile.get("first_name", ""),
                "last_name": self.profile.get("last_name", ""),
                "full_name": self.profile.get("full_name", ""),
                "email": self.profile.get("email", ""),
                "phone": self.profile.get("phone", ""),
                "linkedin_url": self.profile.get("linkedin_url", ""),
                "current_company": self.profile.get("current_company", ""),
            },
            "cover_letter": cover_letter,
            "resume_ready": resume_exists,
            "resume_path": str(RESUME_PATH) if resume_exists else None,
        }

        return preview_data

    async def apply(self, job: dict, cover_letter: str = None, dry_run: bool = True) -> dict:
        """
        Fill and optionally submit an application.
        
        Args:
            job: Job listing dict
            cover_letter: Override cover letter (or auto-generate)
            dry_run: If True, fill form but don't click submit
        """
        url = job.get("url", "")
        ats = self.detect_ats(url)

        if ats == "unsupported":
            return {
                "status": "unsupported",
                "error": f"Auto-apply not supported for this URL: {url}",
                "ats_type": ats,
            }

        if not cover_letter:
            cover_letter = generate_cover_letter(self.profile, job)

        resume_path = str(RESUME_PATH) if RESUME_PATH.exists() else ""

        await self._ensure_browser()
        page = await self._browser.new_page()

        try:
            logger.info(f"Navigating to {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)

            if ats == "greenhouse":
                result = await greenhouse_submit(
                    page, self.profile, cover_letter, resume_path, dry_run=dry_run
                )
            elif ats == "lever":
                result = await lever_submit(
                    page, self.profile, cover_letter, resume_path, dry_run=dry_run
                )
            else:
                result = {"status": "error", "error": "Unknown ATS"}

            result["ats_type"] = ats
            result["url"] = url
            result["company"] = job.get("company", "")
            result["title"] = job.get("title", "")
            result["cover_letter"] = cover_letter
            result["applied_at"] = datetime.now().isoformat()

            # Log the application
            self._log_application(result)

            return result

        except Exception as e:
            logger.error(f"Apply error: {e}")
            return {
                "status": "error",
                "error": str(e),
                "ats_type": ats,
                "url": url,
            }
        finally:
            await page.close()

    def _log_application(self, result: dict):
        """Append application result to log file."""
        log = []
        if LOG_PATH.exists():
            try:
                with open(LOG_PATH, "r", encoding="utf-8") as f:
                    log = json.load(f)
            except (json.JSONDecodeError, Exception):
                log = []

        log.append({
            "url": result.get("url"),
            "company": result.get("company"),
            "title": result.get("title"),
            "ats": result.get("ats_type"),
            "status": result.get("status"),
            "fields_filled": result.get("fields_filled", []),
            "fields_skipped": result.get("fields_skipped", []),
            "applied_at": result.get("applied_at"),
            "screenshot": result.get("screenshot"),
        })

        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(log, f, indent=2, default=str)

    def get_application_log(self) -> list:
        """Return all logged applications."""
        if LOG_PATH.exists():
            try:
                with open(LOG_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, Exception):
                return []
        return []

    def get_applied_urls(self) -> set:
        """Return set of URLs already applied to."""
        log = self.get_application_log()
        return {entry.get("url", "") for entry in log if entry.get("url")}

    def mark_applied(self, url: str, title: str = "", company: str = "") -> dict:
        """Manually mark a job as applied (for jobs applied outside the tool)."""
        entry = {
            "url": url,
            "company": company,
            "title": title,
            "ats": "manual",
            "status": "applied_externally",
            "fields_filled": [],
            "fields_skipped": [],
            "applied_at": datetime.now().isoformat(),
            "screenshot": None,
        }
        self._log_application(entry)
        return entry
