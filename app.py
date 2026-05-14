"""
FastAPI Backend for HR Hunter.
Serves the web dashboard and provides SSE streaming for real-time search progress.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from orchestrator import run_all_scrapers
from applicant.engine import ApplicationEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("hr-hunter")

app = FastAPI(title="HR Hunter", version="1.0.0")

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

_cache = {"data": None, "timestamp": None, "loading": False}

_daily_results_file = BASE_DIR / "assets" / "daily_results.json"
if _daily_results_file.exists():
    try:
        _daily = json.loads(_daily_results_file.read_text(encoding="utf-8"))
        _cache["data"] = {
            "jobs": _daily.get("jobs", []),
            "metadata": _daily.get("metadata", {}),
            "market_insights": _daily.get("market_insights", {}),
        }
        _cache["timestamp"] = _daily.get("daily_run_at") or _daily.get("metadata", {}).get("timestamp")
        logger.info(f"Loaded {len(_cache['data']['jobs'])} jobs from daily results")
    except Exception as e:
        logger.warning(f"Could not load daily results: {e}")

_applicant = ApplicationEngine()


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html")


@app.get("/api/search/stream")
async def search_jobs_stream():
    if _cache["loading"]:
        async def already_running():
            yield f"data: {json.dumps({'event': 'error', 'message': 'Search already in progress'})}\n\n"
        return StreamingResponse(already_running(), media_type="text/event-stream")

    _cache["loading"] = True

    async def event_stream():
        queue = asyncio.Queue()

        async def on_progress(event_data: dict):
            await queue.put(event_data)

        async def run_search():
            try:
                results = await run_all_scrapers(on_progress=on_progress)
                _cache["data"] = results
                _cache["timestamp"] = datetime.now().isoformat()
                await queue.put({"event": "result", "data": results})
            except Exception as e:
                logger.error(f"Search failed: {e}")
                await queue.put({"event": "error", "message": str(e)})
            finally:
                _cache["loading"] = False
                await queue.put(None)

        task = asyncio.create_task(run_search())

        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield f"data: {json.dumps(event, default=str)}\n\n"
        except asyncio.CancelledError:
            task.cancel()
            _cache["loading"] = False

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/search")
async def search_jobs():
    if _cache["loading"]:
        return JSONResponse({"status": "loading", "message": "Search already in progress..."})
    _cache["loading"] = True
    try:
        results = await run_all_scrapers()
        _cache["data"] = results
        _cache["timestamp"] = datetime.now().isoformat()
        return JSONResponse({"status": "success", **results})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
    finally:
        _cache["loading"] = False


@app.get("/api/cached")
async def get_cached():
    if _cache["data"]:
        return JSONResponse({"status": "success", "cached_at": _cache["timestamp"], **_cache["data"]})
    return JSONResponse({"status": "empty", "message": "No cached results. Run a search first."})


@app.get("/api/status")
async def get_status():
    return JSONResponse({
        "loading": _cache["loading"],
        "has_cache": _cache["data"] is not None,
        "cached_at": _cache["timestamp"],
    })


@app.post("/api/apply/preview")
async def apply_preview(request: Request):
    body = await request.json()
    job = body.get("job")
    if not job or not job.get("url"):
        return JSONResponse({"status": "error", "message": "Job URL required"}, status_code=400)
    try:
        preview = await _applicant.preview(job)
        return JSONResponse({"status": "success", **preview})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/apply/submit")
async def apply_submit(request: Request):
    body = await request.json()
    job = body.get("job")
    cover_letter = body.get("cover_letter")
    dry_run = body.get("dry_run", True)
    if not job or not job.get("url"):
        return JSONResponse({"status": "error", "message": "Job URL required"}, status_code=400)
    try:
        result = await _applicant.apply(job, cover_letter=cover_letter, dry_run=dry_run)
        return JSONResponse({"status": "success", **result})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/api/apply/log")
async def apply_log():
    log = _applicant.get_application_log()
    return JSONResponse({"status": "success", "applications": log, "total": len(log)})


@app.post("/api/apply/mark")
async def mark_applied(request: Request):
    body = await request.json()
    url = body.get("url")
    if not url:
        return JSONResponse({"status": "error", "message": "URL required"}, status_code=400)
    entry = _applicant.mark_applied(url=url, title=body.get("title", ""), company=body.get("company", ""))
    return JSONResponse({"status": "success", "entry": entry})


if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8081))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
