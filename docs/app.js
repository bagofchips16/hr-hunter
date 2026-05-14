/* ─── HR Hunter — Static Public Dashboard ─── */

const REPO = 'bagofchips16/hr-hunter';

let allJobs = [];
let currentData = null;
let activeFilter = 'all';
let searchQuery = '';

document.addEventListener('DOMContentLoaded', () => {
    loadData();
    setupEventListeners();
});

function setupEventListeners() {
    document.querySelectorAll('.filter-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            activeFilter = chip.dataset.filter;
            renderJobs();
        });
    });
    let debounceTimer;
    document.getElementById('searchInput').addEventListener('input', (e) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            searchQuery = e.target.value.toLowerCase().trim();
            renderJobs();
        }, 200);
    });
}

async function loadData() {
    try {
        const resp = await fetch('data.json?t=' + Date.now());
        const data = await resp.json();
        currentData = data;
        allJobs = data.jobs || [];
        renderDashboard(data);
        setStatus('ready');
        const ts = data.daily_run_at || data.metadata?.timestamp;
        if (ts) {
            const d = new Date(ts);
            const ago = timeSince(d);
            document.getElementById('lastUpdated').textContent = 'Updated ' + ago;
        }
    } catch (err) {
        document.getElementById('jobsGrid').innerHTML = `
            <div class="empty-state">
                <h2>Could not load data</h2>
                <p>Check back later — data is refreshed automatically every 6 hours.</p>
            </div>`;
        setStatus('error');
    }
}

function timeSince(date) {
    const seconds = Math.floor((new Date() - date) / 1000);
    if (seconds < 60) return 'just now';
    const mins = Math.floor(seconds / 60);
    if (mins < 60) return mins + 'm ago';
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return hrs + 'h ago';
    const days = Math.floor(hrs / 24);
    return days + 'd ago';
}

// ─── Trigger GitHub Actions scrape ──────────────────────────────────
async function triggerRefresh() {
    const btn = document.getElementById('refreshBtn');
    btn.disabled = true;
    btn.innerHTML = '⏳ Refreshing...';
    setStatus('loading');

    const oldTimestamp = currentData?.daily_run_at;

    // Try triggering a live scrape via GitHub Actions API
    const pat = localStorage.getItem('hr_hunter_pat');
    if (pat) {
        try {
            const resp = await fetch(`https://api.github.com/repos/${REPO}/dispatches`, {
                method: 'POST',
                headers: {
                    'Accept': 'application/vnd.github+json',
                    'Authorization': 'Bearer ' + pat,
                },
                body: JSON.stringify({ event_type: 'scrape' }),
            });
            if (resp.status === 204 || resp.ok) {
                btn.innerHTML = '⏳ Scraping live...';
                document.getElementById('lastUpdated').textContent = 'Scrape running — fresh data in ~3 min...';
                pollForNewData(oldTimestamp);
                return;
            }
        } catch (e) { /* fall through */ }
    }

    // Re-fetch latest data (cache-bust)
    await loadData();
    resetRefreshBtn();
}

async function pollForNewData(oldTimestamp) {
    let attempts = 0;
    const maxAttempts = 36; // 6 minutes (every 10s)

    const poll = setInterval(async () => {
        attempts++;
        try {
            const resp = await fetch('data.json?t=' + Date.now());
            const data = await resp.json();
            if (data.daily_run_at !== oldTimestamp) {
                clearInterval(poll);
                currentData = data;
                allJobs = data.jobs || [];
                renderDashboard(data);
                setStatus('ready');
                resetRefreshBtn();
                document.getElementById('lastUpdated').textContent = 'Updated just now';
                return;
            }
        } catch (e) { /* retry */ }
        if (attempts >= maxAttempts) {
            clearInterval(poll);
            setStatus('ready');
            resetRefreshBtn();
        }
    }, 10000);
}

function resetRefreshBtn() {
    const btn = document.getElementById('refreshBtn');
    btn.innerHTML = '🔄 Search Now';
    btn.disabled = false;
}

function renderDashboard(data) {
    renderStats(data.metadata);
    renderJobs();
    renderInsights(data.market_insights);
}

function renderStats(meta) {
    animateNumber('statScraped', meta.total_scraped || 0);
    animateNumber('statMatched', meta.above_threshold || 0);
    animateNumber('statDisplayed', meta.displayed || 0);
    const sources = Object.keys(meta.source_stats || {}).length;
    document.getElementById('statSources').textContent = sources;
    const companies = new Set(allJobs.map(j => j.company)).size;
    document.getElementById('statCompanies').textContent = companies;
}

function animateNumber(id, target) {
    const el = document.getElementById(id);
    const start = parseInt(el.textContent) || 0;
    if (start === target) { el.textContent = target; return; }
    const duration = 600;
    const startTime = performance.now();
    function tick(now) {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        el.textContent = Math.round(start + (target - start) * eased);
        if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
}

function renderJobs() {
    const container = document.getElementById('jobsGrid');
    if (!allJobs.length) {
        container.innerHTML = `<div class="empty-state"><h2>No openings loaded</h2></div>`;
        return;
    }

    let jobs = [...allJobs];

    // Text search
    if (searchQuery) {
        jobs = jobs.filter(j => {
            const text = `${j.title} ${j.company} ${j.location} ${j.source} ${j.match_reason}`.toLowerCase();
            return text.includes(searchQuery);
        });
    }

    // Filters
    const indiaTerms = ['india', 'bangalore', 'bengaluru', 'hyderabad', 'mumbai',
        'delhi', 'gurgaon', 'gurugram', 'noida', 'pune', 'chennai', 'kolkata', 'ahmedabad', 'kochi', 'jaipur'];
    const hrbpTerms = ['hrbp', 'business partner', 'talent acquisition', 'recruiting', 'recruiter', 'ta lead'];
    const compTerms = ['compensation', 'benefits', 'comp &', 'total rewards', 'payroll', 'workday compensation'];
    const ldTerms = ['learning', 'development', 'l&d', 'training', 'organisational development', 'organizational development'];
    const analyticsTerms = ['analytics', 'hris', 'people data', 'workforce', 'workday'];

    if (activeFilter !== 'all') {
        if (activeFilter === 'p1') jobs = jobs.filter(j => j.priority === 'P1');
        else if (activeFilter === 'p2') jobs = jobs.filter(j => j.priority === 'P2');
        else if (activeFilter === 'hrbp') jobs = jobs.filter(j => {
            const t = (j.title + ' ' + (j.match_reason || '')).toLowerCase();
            return hrbpTerms.some(k => t.includes(k));
        });
        else if (activeFilter === 'comp') jobs = jobs.filter(j => {
            const t = (j.title + ' ' + (j.match_reason || '')).toLowerCase();
            return compTerms.some(k => t.includes(k));
        });
        else if (activeFilter === 'ld') jobs = jobs.filter(j => {
            const t = (j.title + ' ' + (j.match_reason || '')).toLowerCase();
            return ldTerms.some(k => t.includes(k));
        });
        else if (activeFilter === 'analytics') jobs = jobs.filter(j => {
            const t = (j.title + ' ' + (j.match_reason || '')).toLowerCase();
            return analyticsTerms.some(k => t.includes(k));
        });
        else if (activeFilter === 'india') {
            jobs = jobs.filter(j => indiaTerms.some(t => (j.location || '').toLowerCase().includes(t)));
        }
        else if (activeFilter === 'abroad') {
            jobs = jobs.filter(j => {
                const loc = (j.location || '').toLowerCase();
                return !indiaTerms.some(t => loc.includes(t));
            });
        }
    }

    document.getElementById('jobCount').textContent = `Showing ${jobs.length} of ${allJobs.length} openings`;

    if (!jobs.length) {
        container.innerHTML = `<div class="empty-state"><h2>No roles match this filter</h2><p>Try a different filter or search term.</p></div>`;
        return;
    }

    container.innerHTML = jobs.map((job, idx) => renderJobCard(job, idx)).join('');
}

function renderJobCard(job, idx) {
    const priorityClass = (job.priority || 'p3').toLowerCase();
    const scoreClass = job.fit_score >= 85 ? 'elite' : job.fit_score >= 70 ? 'high' : 'medium';
    const postedDate = job.posted_date
        ? new Date(job.posted_date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
        : 'Recent';

    const interviewSteps = (job.interview_loop || []).map(s => `<li>${escapeHtml(s)}</li>`).join('');

    return `
    <div class="job-card ${priorityClass}" id="job-${idx}" style="animation: fadeSlideIn 0.3s ease ${Math.min(idx * 0.03, 1)}s both;">
        <div class="job-header">
            <div class="job-header-left">
                <div class="job-title">
                    <a href="${escapeHtml(job.url)}" target="_blank" rel="noopener noreferrer">
                        ${escapeHtml(job.title)}
                    </a>
                </div>
                <div class="job-company">${escapeHtml(job.company)}</div>
                <div class="job-meta">
                    <span class="job-meta-item">📍 ${escapeHtml(job.location || 'Not specified')}</span>
                    <span class="job-meta-item">📅 ${postedDate}</span>
                    <span class="job-meta-item">💰 ${escapeHtml(job.estimated_tc || 'N/A')}</span>
                </div>
                <div class="job-badges" style="margin-top:10px;">
                    <span class="badge badge-${priorityClass}">${escapeHtml(job.priority)}</span>
                    <span class="badge badge-source">${escapeHtml(job.source)}</span>
                    <span class="badge" style="background:rgba(16,185,129,0.15);color:#10b981;">
                        ${escapeHtml(job.seniority || 'HR')}
                    </span>
                    ${renderVisaBadge(job.visa_note)}
                </div>
            </div>
            <div class="fit-score ${scoreClass}">
                ${job.fit_score}
                <div class="label">FIT</div>
            </div>
        </div>

        <div class="detail-section" style="margin-top:12px;">
            <h4>Why This Role</h4>
            <p>${escapeHtml(job.match_reason)}</p>
        </div>

        <button class="expand-btn" onclick="toggleExpand(this)">▼ Show Details</button>

        <a href="${escapeHtml(job.url)}" target="_blank" rel="noopener noreferrer"
           class="apply-btn apply-external">↗ Apply</a>

        <div class="job-details">
            <div class="detail-section">
                <h4>About This Role</h4>
                <p>${escapeHtml(job.hiring_pain_point)}</p>
            </div>
            <div class="detail-section">
                <h4>Interview Process</h4>
                <ul>${interviewSteps || '<li>Standard interview process</li>'}</ul>
            </div>
        </div>
    </div>`;
}

function toggleExpand(btn) {
    const card = btn.closest('.job-card');
    card.classList.toggle('expanded');
    btn.textContent = card.classList.contains('expanded') ? '▲ Hide Details' : '▼ Show Details';
}

function renderInsights(insights) {
    const panel = document.getElementById('insightsPanel');
    if (!insights) { panel.style.display = 'none'; return; }
    panel.style.display = 'block';
    document.getElementById('insightsTrends').innerHTML =
        (insights.trends || []).map(t => `<li class="trend-item">${escapeHtml(t)}</li>`).join('') || '<li>No data</li>';
    document.getElementById('insightsHirers').innerHTML =
        (insights.aggressive_hirers || []).map(h => `<li class="hirer-item">${escapeHtml(h.company)}: <strong>${h.open_roles}</strong> roles</li>`).join('') || '<li>No data</li>';
    document.getElementById('insightsPatterns').innerHTML =
        (insights.jd_patterns || []).map(p => `<li class="pattern-item">"${escapeHtml(p.keyword)}" — ${p.frequency}×</li>`).join('') || '<li>No data</li>';
}

function renderVisaBadge(visaNote) {
    if (!visaNote || visaNote.includes('N/A')) return '';
    if (visaNote.includes('LIKELY'))
        return `<span class="badge" style="background:rgba(16,185,129,0.15);color:#10b981;">🛂 Visa Likely</span>`;
    if (visaNote.includes('CHECK'))
        return `<span class="badge" style="background:rgba(245,158,11,0.15);color:#f59e0b;">🌍 Check Visa</span>`;
    return `<span class="badge" style="background:rgba(107,114,128,0.15);color:#9ca3af;">❓ Visa Unknown</span>`;
}

function setStatus(state) {
    const badge = document.getElementById('statusBadge');
    badge.className = 'status-badge';
    const map = {
        ready: ['status-ready', '● Live'],
        loading: ['status-loading', '● Loading...'],
        error: ['status-error', '● Error']
    };
    const [cls, text] = map[state] || map.error;
    badge.classList.add(cls);
    badge.textContent = text;
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
