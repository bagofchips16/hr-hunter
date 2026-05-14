"""
HR Hunter — Daily auto-run script.
Runs all scrapers headlessly, saves results to assets/daily_results.json,
then starts the web server in the background.
"""

import asyncio
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(str(BASE_DIR / "assets" / "daily_run.log"), mode="a", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("hr-hunter")


async def main():
    logger.info("=" * 60)
    logger.info(f"HR Hunter daily run starting at {datetime.now()}")

    from orchestrator import run_all_scrapers

    results = await run_all_scrapers()
    results["daily_run_at"] = datetime.now().isoformat()

    out_path = BASE_DIR / "assets" / "daily_results.json"
    out_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")

    meta = results.get("metadata", {})
    logger.info(
        f"Done — scraped={meta.get('total_scraped',0)}, "
        f"displayed={meta.get('displayed',0)}, "
        f"companies={len(set(j.get('company','') for j in results.get('jobs',[])))}"
    )

    # Start server in background
    import platform
    python = sys.executable
    flags = 0
    if platform.system() == "Windows":
        flags = subprocess.CREATE_NO_WINDOW
    subprocess.Popen(
        [python, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", "8081"],
        cwd=str(BASE_DIR),
        creationflags=flags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    logger.info("Server started on http://127.0.0.1:8081")


if __name__ == "__main__":
    asyncio.run(main())
