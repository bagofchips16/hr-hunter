# HR Hunter

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/bagofchips16/hr-hunter)

Automated HR & People role tracker. Scrapes jobs from Greenhouse, Lever, Ashby, LinkedIn, Google Careers, and Amazon Jobs — scores and ranks them for HR professionals.

## Features

- **6 job sources**: Greenhouse boards, Lever, Ashby, LinkedIn, Google Careers, Amazon Jobs
- **Smart scoring**: Fit scores based on experience, seniority, location, and HR specialization
- **Priority tiers**: P0 (Urgent), P1 (Strong), P2 (Good), P3 (Okay)
- **Live dashboard**: FastAPI-powered UI with filters, market insights, and one-click apply links
- **Daily auto-run**: Windows Task Scheduler integration for hands-free daily scans
- **Semi-auto apply**: Playwright-based application for Greenhouse and Lever ATS

## Quick Start

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Run a scan and start the dashboard
python daily_run.py
```

Dashboard opens at **http://127.0.0.1:8081**

## Daily Auto-Run

Run `setup_daily_task.bat` as Administrator to register a Windows Task Scheduler task that scans at 8:30 AM daily.

## Project Structure

```
hr-hunter/
├── app.py              # FastAPI web server + dashboard
├── config.py           # HR profile, search queries, company boards
├── scoring.py          # Job scoring, fit calculation, match reasons
├── orchestrator.py     # Scraper coordination + result aggregation
├── daily_run.py        # Headless daily scan + server launch
├── scrapers/
│   ├── base.py         # Base scraper with retry logic
│   ├── greenhouse.py   # Greenhouse ATS scraper
│   ├── lever.py        # Lever ATS scraper
│   ├── ashby.py        # Ashby ATS scraper
│   ├── linkedin.py     # LinkedIn Jobs scraper
│   ├── google_careers.py # Google Careers scraper
│   └── amazon.py       # Amazon Jobs scraper
├── applicant/          # Semi-auto apply module
├── templates/          # HTML dashboard
├── static/             # CSS + JS
└── assets/             # Profile + daily results
```
