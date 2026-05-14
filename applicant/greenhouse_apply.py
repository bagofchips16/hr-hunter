"""
Greenhouse ATS auto-apply module.
Fills and submits application forms on boards.greenhouse.io.
"""

import logging
from pathlib import Path
from playwright.async_api import Page, TimeoutError as PwTimeout

logger = logging.getLogger("applicant.greenhouse")

# Greenhouse application form selectors
SELECTORS = {
    "apply_btn": 'a[href*="#app"], a:has-text("Apply"), button:has-text("Apply")',
    "first_name": '#first_name, input[name="job_application[first_name]"]',
    "last_name": '#last_name, input[name="job_application[last_name]"]',
    "email": '#email, input[name="job_application[email]"]',
    "phone": '#phone, input[name="job_application[phone]"]',
    "resume_input": 'input[type="file"][id*="resume"], input[type="file"]:first-of-type',
    "cover_letter_text": 'textarea[id*="cover_letter"], textarea[name*="cover_letter"]',
    "cover_letter_input": 'input[type="file"][id*="cover_letter"]',
    "linkedin": 'input[name*="linkedin"], input[id*="linkedin"], input[placeholder*="LinkedIn"]',
    "website": 'input[name*="website"], input[id*="website"], input[placeholder*="Website"]',
    "submit_btn": '#submit_app, button[type="submit"], input[type="submit"]',
}


async def detect_greenhouse(url: str) -> bool:
    """Check if URL is a Greenhouse job posting."""
    return "greenhouse.io" in url.lower()


async def extract_form_fields(page: Page) -> dict:
    """Navigate to apply form and extract available fields."""
    fields = {}

    # Click "Apply" button if present (some pages show job desc first)
    try:
        apply_btn = page.locator(SELECTORS["apply_btn"]).first
        if await apply_btn.is_visible(timeout=3000):
            await apply_btn.click()
            await page.wait_for_timeout(1500)
    except (PwTimeout, Exception):
        pass  # May already be on the form

    # Detect which fields are present
    for field_name, selector in SELECTORS.items():
        if field_name in ("apply_btn", "submit_btn"):
            continue
        try:
            el = page.locator(selector).first
            is_visible = await el.is_visible(timeout=1000)
            fields[field_name] = {
                "present": is_visible,
                "selector": selector,
            }
        except (PwTimeout, Exception):
            fields[field_name] = {"present": False, "selector": selector}

    # Detect custom questions
    custom_questions = []
    try:
        question_fields = page.locator(
            '.field:not(:has(#first_name)):not(:has(#last_name)):not(:has(#email)):not(:has(#phone)) '
            'label'
        )
        count = await question_fields.count()
        for i in range(min(count, 10)):
            label = await question_fields.nth(i).text_content()
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
    Fill the Greenhouse application form and optionally submit.
    
    Returns dict with status, fields_filled, screenshot_path, etc.
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
        # Click Apply button if needed
        try:
            apply_btn = page.locator(SELECTORS["apply_btn"]).first
            if await apply_btn.is_visible(timeout=3000):
                await apply_btn.click()
                await page.wait_for_timeout(1500)
        except (PwTimeout, Exception):
            pass

        # Fill standard fields
        await _fill_field(page, SELECTORS["first_name"], profile.get("first_name", ""), result)
        await _fill_field(page, SELECTORS["last_name"], profile.get("last_name", ""), result)
        await _fill_field(page, SELECTORS["email"], profile.get("email", ""), result)
        await _fill_field(page, SELECTORS["phone"], profile.get("phone", ""), result)

        # LinkedIn URL
        if profile.get("linkedin_url"):
            await _fill_field(page, SELECTORS["linkedin"], profile["linkedin_url"], result)

        # Website
        if profile.get("website"):
            await _fill_field(page, SELECTORS["website"], profile["website"], result)

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
                logger.warning(f"Could not upload resume: {e}")

        # Cover letter (try text area first, then file upload)
        if cover_letter:
            try:
                cl_text = page.locator(SELECTORS["cover_letter_text"]).first
                if await cl_text.is_visible(timeout=1000):
                    await cl_text.fill(cover_letter)
                    result["fields_filled"].append("cover_letter_text")
                    logger.info("Filled cover letter text")
            except (PwTimeout, Exception):
                result["fields_skipped"].append("cover_letter_text: not found")

        # Take pre-submit screenshot
        screenshot_path = Path("assets/screenshots")
        screenshot_path.mkdir(parents=True, exist_ok=True)
        ts = page.url.split("/")[-1][:20].replace("/", "_")
        ss_file = screenshot_path / f"greenhouse_{ts}_prefill.png"
        await page.screenshot(path=str(ss_file), full_page=True)
        result["screenshot"] = str(ss_file)

        if dry_run:
            result["status"] = "preview"
            logger.info("Dry run — form filled but NOT submitted")
        else:
            # Submit
            try:
                submit = page.locator(SELECTORS["submit_btn"]).first
                await submit.click()
                await page.wait_for_timeout(3000)

                # Check for success
                page_text = await page.content()
                if any(s in page_text.lower() for s in [
                    "thank you", "application submitted", "successfully",
                    "we've received", "confirmation"
                ]):
                    result["status"] = "submitted"
                    logger.info("Application submitted successfully!")
                else:
                    result["status"] = "submitted_unconfirmed"
                    logger.warning("Clicked submit but could not confirm success")

                # Post-submit screenshot
                ss_post = screenshot_path / f"greenhouse_{ts}_submitted.png"
                await page.screenshot(path=str(ss_post), full_page=True)
                result["screenshot"] = str(ss_post)

            except Exception as e:
                result["status"] = "submit_failed"
                result["error"] = str(e)
                logger.error(f"Submit failed: {e}")

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        logger.error(f"Greenhouse apply error: {e}")

    return result


async def _fill_field(page: Page, selector: str, value: str, result: dict):
    """Try to fill a form field. Track success/failure in result."""
    if not value:
        return
    field_name = selector.split(",")[0].strip("#").split("[")[0]
    try:
        el = page.locator(selector).first
        if await el.is_visible(timeout=1000):
            await el.fill(value)
            result["fields_filled"].append(field_name)
        else:
            result["fields_skipped"].append(f"{field_name}: not visible")
    except (PwTimeout, Exception) as e:
        result["fields_skipped"].append(f"{field_name}: {e}")
