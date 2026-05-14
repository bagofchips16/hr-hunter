"""
Lever ATS auto-apply module.
Fills and submits application forms on jobs.lever.co.
"""

import logging
from pathlib import Path
from playwright.async_api import Page, TimeoutError as PwTimeout

logger = logging.getLogger("applicant.lever")

# Lever application form selectors
SELECTORS = {
    "apply_btn": 'a.postings-btn[href*="apply"], a:has-text("Apply"), .apply-button',
    "full_name": 'input[name="name"], input[placeholder*="Full name"]',
    "email": 'input[name="email"], input[type="email"]',
    "phone": 'input[name="phone"], input[type="tel"]',
    "org": 'input[name="org"], input[placeholder*="Current company"]',
    "resume_input": 'input[type="file"][name="resume"]',
    "urls_linkedin": '.application-additional input[name="urls[LinkedIn]"], input[placeholder*="LinkedIn"]',
    "urls_github": '.application-additional input[name="urls[GitHub]"], input[placeholder*="GitHub"]',
    "urls_portfolio": '.application-additional input[name="urls[Portfolio]"], input[placeholder*="Portfolio"]',
    "urls_other": '.application-additional input[name="urls[Other]"]',
    "cover_letter_text": 'textarea[name="comments"]',
    "submit_btn": 'button[type="submit"]:has-text("Submit"), button.postings-btn[type="submit"]',
}


async def detect_lever(url: str) -> bool:
    """Check if URL is a Lever job posting."""
    return "lever.co" in url.lower()


async def extract_form_fields(page: Page) -> dict:
    """Navigate to apply form and extract available fields."""
    fields = {}

    # Navigate to /apply if not already there
    current_url = page.url
    if "/apply" not in current_url:
        try:
            apply_btn = page.locator(SELECTORS["apply_btn"]).first
            if await apply_btn.is_visible(timeout=3000):
                await apply_btn.click()
                await page.wait_for_timeout(1500)
        except (PwTimeout, Exception):
            # Try direct navigation to /apply
            if not current_url.endswith("/apply"):
                await page.goto(current_url.rstrip("/") + "/apply")
                await page.wait_for_timeout(1500)

    for field_name, selector in SELECTORS.items():
        if field_name in ("apply_btn", "submit_btn"):
            continue
        try:
            el = page.locator(selector).first
            is_visible = await el.is_visible(timeout=1000)
            fields[field_name] = {"present": is_visible, "selector": selector}
        except (PwTimeout, Exception):
            fields[field_name] = {"present": False, "selector": selector}

    # Detect custom questions (Lever uses .application-question)
    custom_questions = []
    try:
        questions = page.locator(".application-question label, .custom-question label")
        count = await questions.count()
        for i in range(min(count, 10)):
            label = await questions.nth(i).text_content()
            if label and label.strip():
                custom_questions.append(label.strip())
    except Exception:
        pass

    fields["custom_questions"] = custom_questions
    return fields


async def fill_and_submit(
    page: Page,
    profile: dict,
    cover_letter: str,
    resume_path: str,
    dry_run: bool = True,
) -> dict:
    """
    Fill the Lever application form and optionally submit.
    """
    result = {
        "status": "pending",
        "fields_filled": [],
        "fields_skipped": [],
        "custom_questions_found": [],
        "screenshot": None,
        "error": None,
    }

    try:
        # Navigate to /apply
        current_url = page.url
        if "/apply" not in current_url:
            try:
                apply_btn = page.locator(SELECTORS["apply_btn"]).first
                if await apply_btn.is_visible(timeout=3000):
                    await apply_btn.click()
                    await page.wait_for_timeout(1500)
            except (PwTimeout, Exception):
                if not current_url.endswith("/apply"):
                    await page.goto(current_url.rstrip("/") + "/apply")
                    await page.wait_for_timeout(1500)

        # Fill standard fields
        full_name = profile.get("full_name", f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip())
        await _fill_field(page, SELECTORS["full_name"], full_name, result)
        await _fill_field(page, SELECTORS["email"], profile.get("email", ""), result)
        await _fill_field(page, SELECTORS["phone"], profile.get("phone", ""), result)
        await _fill_field(page, SELECTORS["org"], profile.get("current_company", ""), result)

        # URLs
        if profile.get("linkedin_url"):
            await _fill_field(page, SELECTORS["urls_linkedin"], profile["linkedin_url"], result)
        if profile.get("github"):
            await _fill_field(page, SELECTORS["urls_github"], profile["github"], result)
        if profile.get("website"):
            await _fill_field(page, SELECTORS["urls_portfolio"], profile["website"], result)

        # Resume upload
        resume = Path(resume_path)
        if resume.exists():
            try:
                file_input = page.locator(SELECTORS["resume_input"]).first
                if await file_input.count() > 0:
                    await file_input.set_input_files(str(resume))
                    result["fields_filled"].append("resume")
                    logger.info("Uploaded resume")
            except Exception as e:
                result["fields_skipped"].append(f"resume: {e}")

        # Cover letter / additional info
        if cover_letter:
            try:
                cl_text = page.locator(SELECTORS["cover_letter_text"]).first
                if await cl_text.is_visible(timeout=1000):
                    await cl_text.fill(cover_letter)
                    result["fields_filled"].append("cover_letter")
                    logger.info("Filled cover letter")
            except (PwTimeout, Exception):
                result["fields_skipped"].append("cover_letter: not found")

        # Screenshot before submit
        screenshot_path = Path("assets/screenshots")
        screenshot_path.mkdir(parents=True, exist_ok=True)
        ts = page.url.split("/")[-2][:20] if "/apply" in page.url else "lever"
        ss_file = screenshot_path / f"lever_{ts}_prefill.png"
        await page.screenshot(path=str(ss_file), full_page=True)
        result["screenshot"] = str(ss_file)

        if dry_run:
            result["status"] = "preview"
            logger.info("Dry run — form filled but NOT submitted")
        else:
            try:
                submit = page.locator(SELECTORS["submit_btn"]).first
                await submit.click()
                await page.wait_for_timeout(3000)

                page_text = await page.content()
                if any(s in page_text.lower() for s in [
                    "thank you", "application submitted", "successfully",
                    "we received", "confirmation"
                ]):
                    result["status"] = "submitted"
                    logger.info("Application submitted successfully!")
                else:
                    result["status"] = "submitted_unconfirmed"

                ss_post = screenshot_path / f"lever_{ts}_submitted.png"
                await page.screenshot(path=str(ss_post), full_page=True)
                result["screenshot"] = str(ss_post)

            except Exception as e:
                result["status"] = "submit_failed"
                result["error"] = str(e)
                logger.error(f"Submit failed: {e}")

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        logger.error(f"Lever apply error: {e}")

    return result


async def _fill_field(page: Page, selector: str, value: str, result: dict):
    if not value:
        return
    field_name = selector.split(",")[0].strip().split("[")[0].split(".")[-1]
    try:
        el = page.locator(selector).first
        if await el.is_visible(timeout=1000):
            await el.fill(value)
            result["fields_filled"].append(field_name)
        else:
            result["fields_skipped"].append(f"{field_name}: not visible")
    except (PwTimeout, Exception) as e:
        result["fields_skipped"].append(f"{field_name}: {e}")
