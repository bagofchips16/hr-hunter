/* ─── Job Hunter Dashboard JavaScript (v2 — SSE Streaming) ─── */

const API = {
    stream: '/api/search/stream',
    cached: '/api/cached',
    applyPreview: '/api/apply/preview',
    applySubmit: '/api/apply/submit',
    applyLog: '/api/apply/log',
    applyMark: '/api/apply/mark',
};

let currentData = null;
let activeFilter = 'all';
let appliedUrls = new Set();

// ─── Initialize ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    loadAppliedUrls();
    loadCachedResults();
    setupEventListeners();
});

function setupEventListeners() {
    document.getElementById('searchBtn').addEventListener('click', runSearch);
    document.querySelectorAll('.filter-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            activeFilter = chip.dataset.filter;
            renderJobs();
        });
    });
}

// ─── SSE Streaming Search ────────────────────────────────────────────
function runSearch() {
    const btn = document.getElementById('searchBtn');
    btn.disabled = true;
    setStatus('loading');
    showProgressPanel();

    const evtSource = new EventSource(API.stream);

    evtSource.onmessage = function(e) {
        try {
            const msg = JSON.parse(e.data);
            handleStreamEvent(msg, evtSource);
        } catch (err) {
            console.error('SSE parse error:', err);
        }
    };

    evtSource.onerror = function() {
        evtSource.close();
        btn.disabled = false;
        if (!currentData) {
            setStatus('error');
            updatePhase('Connection lost. Click Search to retry.');
        }
    };

    window._currentSearch = evtSource;
}

function handleStreamEvent(msg, evtSource) {
    switch (msg.event) {
        case 'start':
            initSourceTracker(msg.sources);
            updatePhase('Scanning ' + msg.total_sources + ' sources...');
            break;

        case 'source_status':
            updateSourceStatus(msg.source, msg.status, msg.found, msg.progress, msg.total);
            break;

        case 'phase':
            updatePhase(msg.message);
            break;

        case 'complete':
            updatePhase(`Done! ${msg.total_scraped} scraped → ${msg.displayed} displayed in ${msg.elapsed}s`);
            document.getElementById('progressBar').style.width = '100%';
            break;

        case 'result':
            currentData = msg.data;
            renderDashboard(msg.data);
            setStatus('ready');
            document.getElementById('searchBtn').disabled = false;
            if (evtSource) evtSource.close();
            setTimeout(hideProgressPanel, 2000);
            break;

        case 'error':
            setStatus('error');
            document.getElementById('searchBtn').disabled = false;
            updatePhase('Error: ' + (msg.message || 'Search failed'));
            if (evtSource) evtSource.close();
            setTimeout(hideProgressPanel, 4000);
            break;
    }
}

// ─── Progress Panel ──────────────────────────────────────────────────
function showProgressPanel() {
    const panel = document.getElementById('progressPanel');
    panel.style.display = 'block';
    document.getElementById('progressPhase').textContent = 'Connecting...';
    document.getElementById('progressBar').style.width = '0%';
    document.getElementById('progressPct').textContent = '';
    document.getElementById('sourceTracker').innerHTML = '';
}

function hideProgressPanel() {
    const panel = document.getElementById('progressPanel');
    panel.style.opacity = '0';
    setTimeout(() => {
        panel.style.display = 'none';
        panel.style.opacity = '1';
    }, 400);
}

function initSourceTracker(sources) {
    const container = document.getElementById('sourceTracker');
    container.innerHTML = sources.map(name => `
        <div class="source-item pending" id="src-${slugify(name)}">
            <span class="source-icon">⏳</span>
            <span class="source-name">${escapeHtml(name)}</span>
            <span class="source-count" id="src-count-${slugify(name)}"></span>
        </div>
    `).join('');
}

function updateSourceStatus(source, status, found, progress, total) {
    const slug = slugify(source);
    const el = document.getElementById(`src-${slug}`);
    if (!el) return;

    const icon = el.querySelector('.source-icon');
    const count = el.querySelector('.source-count');

    el.className = 'source-item ' + status;

    if (status === 'scanning') {
        icon.textContent = '🔄';
        count.textContent = 'scanning...';
        count.style.color = '#f59e0b';
    } else if (status === 'done') {
        icon.textContent = found > 0 ? '✅' : '⬜';
        count.textContent = found > 0 ? `${found} found` : '0 found';
        count.style.color = found > 0 ? '#10b981' : '#6b7280';
    } else if (status === 'error') {
        icon.textContent = '❌';
        count.textContent = 'failed';
        count.style.color = '#ef4444';
    }

    if (progress && total) {
        const pct = Math.round((progress / total) * 90); // reserve 10% for scoring
        document.getElementById('progressBar').style.width = pct + '%';
        document.getElementById('progressPct').textContent = `${progress}/${total} sources`;
    }
}

function updatePhase(message) {
    document.getElementById('progressPhase').textContent = message;
}

// ─── Cached Results ──────────────────────────────────────────────────
async function loadCachedResults() {
    try {
        const resp = await fetch(API.cached);
        const data = await resp.json();
        if (data.status === 'success') {
            currentData = data;
            renderDashboard(data);
            setStatus('ready');
        }
    } catch (err) { /* empty state shown */ }
}

// ─── Render ──────────────────────────────────────────────────────────
function renderDashboard(data) {
    renderStats(data.metadata);
    renderJobs();
    renderInsights(data.market_insights);
}

function renderStats(meta) {
    animateNumber('statScraped', meta.total_scraped || 0);
    animateNumber('statMatched', meta.above_threshold || 0);
    animateNumber('statDisplayed', meta.displayed || 0);
    document.getElementById('statTime').textContent = (meta.elapsed_seconds || 0) + 's';
    document.getElementById('statSources').textContent =
        Object.keys(meta.source_stats || {}).length;
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
    if (!currentData || !currentData.jobs || currentData.jobs.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <h2>No jobs loaded</h2>
                <p>Click "Search Now" to scan all job boards for HR roles.</p>
            </div>`;
        return;
    }

    let jobs = [...currentData.jobs];

    if (activeFilter !== 'all') {
        if (activeFilter === 'p0') jobs = jobs.filter(j => j.priority === 'P0');
        else if (activeFilter === 'p1') jobs = jobs.filter(j => j.priority === 'P1');
        else if (activeFilter === 'p2') jobs = jobs.filter(j => j.priority === 'P2');
        else if (activeFilter === 'hr') jobs = jobs.filter(j =>
            j.seniority === 'HR' || j.seniority === 'HR Associate');
        else if (activeFilter === 'senior-hr') jobs = jobs.filter(j =>
            j.seniority === 'Senior HR' || j.seniority === 'HR Lead' || j.seniority === 'HR Manager');
        else if (activeFilter === 'hrbp') {
            const aiTerms = ['hrbp', 'business partner', 'talent acquisition', 'recruiting',
                             'ta ', 'talent partner', 'recruiter'];
            jobs = jobs.filter(j => {
                const combined = (j.title + ' ' + (j.description || '')).toLowerCase();
                return aiTerms.some(t => combined.includes(t));
            });
        }
        else if (activeFilter === 'india') {
            const india = ['india', 'bangalore', 'bengaluru', 'hyderabad', 'mumbai',
                           'delhi', 'gurgaon', 'gurugram', 'noida', 'pune', 'chennai'];
            jobs = jobs.filter(j => india.some(t => (j.location||'').toLowerCase().includes(t)));
        }
        else if (activeFilter === 'abroad') {
            const india = ['india', 'bangalore', 'bengaluru', 'hyderabad', 'mumbai',
                           'delhi', 'gurgaon', 'gurugram', 'noida', 'pune', 'chennai'];
            jobs = jobs.filter(j => {
                const loc = (j.location||'').toLowerCase();
                return !india.some(t => loc.includes(t)) || loc.includes('remote') || loc.includes('global');
            });
        }
        else if (activeFilter === 'visa') {
            jobs = jobs.filter(j => (j.visa_note || '').includes('LIKELY'));
        }
    }

    if (jobs.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <h2>No roles match this filter</h2>
                <p>Try a different filter or run a fresh search.</p>
            </div>`;
        return;
    }

    container.innerHTML = jobs.map((job, idx) => renderJobCard(job, idx)).join('');
}

function renderJobCard(job, idx) {
    const priorityClass = (job.priority || 'p3').toLowerCase();
    const scoreClass = job.fit_score >= 85 ? 'elite' : job.fit_score >= 70 ? 'high' : 'medium';
    const signalBadge = job.signal_strength === 'Elite' ? 'badge-elite' : 'badge-high';
    const postedDate = job.posted_date
        ? new Date(job.posted_date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
        : 'Recent';

    const interviewSteps = (job.interview_loop || []).map(s => `<li>${escapeHtml(s)}</li>`).join('');

    return `
    <div class="job-card ${priorityClass}" id="job-${idx}" style="animation: fadeSlideIn 0.3s ease ${idx * 0.05}s both;">
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
                    <span class="job-meta-item">⚡ ${escapeHtml(job.speed_to_hire || 'N/A')}</span>
                </div>
                <div class="job-badges" style="margin-top:10px;">
                    <span class="badge badge-${priorityClass}">${escapeHtml(job.priority)}</span>
                    <span class="badge ${signalBadge}">${escapeHtml(job.signal_strength)}</span>
                    <span class="badge badge-source">${escapeHtml(job.source)}</span>
                    <span class="badge" style="background:rgba(16,185,129,0.15);color:#10b981;">
                        ${escapeHtml(job.seniority || 'HR')}
                    </span>
                    ${renderVisaBadge(job.visa_note)}
                    ${renderExpBadge(job.experience_note)}
                </div>
            </div>
            <div class="fit-score ${scoreClass}">
                ${job.fit_score}
                <div class="label">FIT</div>
            </div>
        </div>

        <div class="detail-section" style="margin-top:12px;">
            <h4>Why This Matches</h4>
            <p>${escapeHtml(job.match_reason)}</p>
        </div>

        <button class="expand-btn" onclick="toggleExpand(${idx})">▼ Show Full Analysis</button>

        ${renderApplyButton(job, idx)}
        ${renderMarkAppliedButton(job, idx)}

        <div class="job-details">
            <div class="detail-section">
                <h4>Hiring Manager Pain Point</h4>
                <p>${escapeHtml(job.hiring_pain_point)}</p>
            </div>
            <div class="detail-section">
                <h4>Referral Advantage</h4>
                <p>${escapeHtml(job.referral_advantage)}</p>
            </div>
            <div class="detail-section">
                <h4>🛂 Visa Sponsorship</h4>
                <p>${escapeHtml(job.visa_note || 'Unknown')}</p>
            </div>
            <div class="detail-section">
                <h4>📊 Experience Match</h4>
                <p>${escapeHtml(job.experience_note || 'Unknown')}</p>
            </div>
            <div class="detail-section">
                <h4>Predicted Interview Loop</h4>
                <ul>${interviewSteps}</ul>
            </div>
            <div class="detail-section">
                <h4>Hiring Manager InMail Draft</h4>
                <div class="inmail-box">
                    <button class="copy-btn" onclick="copyInmail(${idx}, event)">Copy</button>
                    ${escapeHtml(job.inmail_draft)}
                </div>
            </div>
        </div>
    </div>`;
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

// ─── Actions ─────────────────────────────────────────────────────────
function toggleExpand(idx) {
    const card = document.getElementById(`job-${idx}`);
    const btn = card.querySelector('.expand-btn');
    card.classList.toggle('expanded');
    btn.textContent = card.classList.contains('expanded') ? '▲ Hide Analysis' : '▼ Show Full Analysis';
}

function copyInmail(idx, event) {
    event.stopPropagation();
    const job = currentData.jobs[idx];
    if (job && job.inmail_draft) {
        navigator.clipboard.writeText(job.inmail_draft).then(() => {
            event.target.textContent = 'Copied!';
            setTimeout(() => event.target.textContent = 'Copy', 2000);
        });
    }
}

// ─── Applied Tracking ────────────────────────────────────────────────
async function loadAppliedUrls() {
    try {
        const resp = await fetch(API.applyLog);
        const data = await resp.json();
        if (data.applications) {
            appliedUrls = new Set(data.applications.map(a => a.url).filter(Boolean));
        }
    } catch (err) { /* ignore */ }
}

function renderMarkAppliedButton(job, idx) {
    if (appliedUrls.has(job.url)) {
        return `<span class="applied-badge">✅ Applied</span>`;
    }
    return `<button class="apply-btn apply-mark" onclick="markAsApplied(${idx}, this)">
                ✓ Mark as Applied
            </button>`;
}

async function markAsApplied(idx, btn) {
    const job = currentData.jobs[idx];
    if (!job) return;
    btn.disabled = true;
    btn.textContent = 'Saving...';
    try {
        await fetch(API.applyMark, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: job.url, title: job.title, company: job.company }),
        });
        appliedUrls.add(job.url);
        btn.outerHTML = `<span class="applied-badge">✅ Applied</span>`;
    } catch (err) {
        btn.disabled = false;
        btn.textContent = '✓ Mark as Applied';
    }
}

// ─── Auto-Apply ──────────────────────────────────────────────────────
function renderApplyButton(job, idx) {
    const url = (job.url || '').toLowerCase();
    const supported = url.includes('greenhouse.io') || url.includes('lever.co');
    if (!supported) {
        return `<a href="${escapeHtml(job.url)}" target="_blank" rel="noopener noreferrer"
                   class="apply-btn apply-external">↗ Apply on Site</a>`;
    }
    return `<button class="apply-btn apply-auto" onclick="openApplyModal(${idx})">
                🚀 Quick Apply
            </button>`;
}

async function openApplyModal(idx) {
    const job = currentData.jobs[idx];
    if (!job) return;

    const modal = document.getElementById('applyModal');
    const body = document.getElementById('applyModalBody');
    modal.style.display = 'flex';

    body.innerHTML = `
        <div class="apply-loading">
            <div class="spinner"></div>
            <p>Generating application preview for <strong>${escapeHtml(job.title)}</strong> at <strong>${escapeHtml(job.company)}</strong>...</p>
        </div>`;

    try {
        const resp = await fetch(API.applyPreview, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ job }),
        });
        const data = await resp.json();

        if (data.status !== 'success') {
            body.innerHTML = `<div class="apply-error">Error: ${escapeHtml(data.message || 'Unknown error')}</div>`;
            return;
        }

        body.innerHTML = renderApplyPreview(data, job, idx);

    } catch (err) {
        body.innerHTML = `<div class="apply-error">Failed to connect: ${escapeHtml(err.message)}</div>`;
    }
}

function renderApplyPreview(data, job, idx) {
    const atsLabel = data.ats_type === 'greenhouse' ? '🌿 Greenhouse' : '🏗️ Lever';
    const resumeStatus = data.resume_ready
        ? '✅ Resume ready'
        : '⚠️ No resume found — add your PDF to assets/resume.pdf';

    return `
    <div class="apply-preview">
        <div class="apply-job-header">
            <h3>${escapeHtml(job.title)}</h3>
            <div class="apply-company">${escapeHtml(job.company)} · ${atsLabel}</div>
        </div>

        <div class="apply-section">
            <h4>📋 Fields to Fill</h4>
            <div class="apply-fields">
                <div class="apply-field"><label>Name</label><span>${escapeHtml(data.fields.full_name || data.fields.first_name + ' ' + data.fields.last_name)}</span></div>
                <div class="apply-field"><label>Email</label><span>${escapeHtml(data.fields.email)}</span></div>
                <div class="apply-field"><label>Phone</label><span>${escapeHtml(data.fields.phone)}</span></div>
                <div class="apply-field"><label>LinkedIn</label><span>${escapeHtml(data.fields.linkedin_url)}</span></div>
                <div class="apply-field"><label>Resume</label><span>${resumeStatus}</span></div>
            </div>
        </div>

        <div class="apply-section">
            <h4>✉️ Cover Letter</h4>
            <textarea id="applyCoverLetter" class="apply-cover-letter" rows="12">${escapeHtml(data.cover_letter)}</textarea>
        </div>

        <div class="apply-actions">
            <button class="btn btn-secondary" onclick="closeApplyModal()">Cancel</button>
            <button class="btn btn-primary apply-dryrun" onclick="submitApplication(${idx}, true)">
                👁️ Dry Run (Fill Only)
            </button>
            <button class="btn btn-danger apply-submit-real" onclick="submitApplication(${idx}, false)">
                🚀 Fill & Submit
            </button>
        </div>

        <div class="apply-note">
            <strong>Dry Run</strong> fills the form without submitting — you get a screenshot to verify.
            <strong>Fill & Submit</strong> fills AND clicks submit. Use with caution.
        </div>
    </div>`;
}

async function submitApplication(idx, dryRun) {
    const job = currentData.jobs[idx];
    const coverLetter = document.getElementById('applyCoverLetter')?.value || '';
    const body = document.getElementById('applyModalBody');

    const actionLabel = dryRun ? 'Filling form (dry run)' : 'Filling & submitting';
    body.innerHTML = `
        <div class="apply-loading">
            <div class="spinner"></div>
            <p>${actionLabel} for <strong>${escapeHtml(job.title)}</strong> at <strong>${escapeHtml(job.company)}</strong>...</p>
            <p class="apply-sublabel">This opens a headless browser — takes 10-20 seconds...</p>
        </div>`;

    try {
        const resp = await fetch(API.applySubmit, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ job, cover_letter: coverLetter, dry_run: dryRun }),
        });
        const data = await resp.json();

        body.innerHTML = renderApplyResult(data, job);

    } catch (err) {
        body.innerHTML = `<div class="apply-error">Failed: ${escapeHtml(err.message)}</div>`;
    }
}

function renderApplyResult(data, job) {
    const statusMap = {
        'preview': { icon: '👁️', label: 'Form Filled (Dry Run)', cls: 'result-preview' },
        'submitted': { icon: '✅', label: 'Application Submitted!', cls: 'result-success' },
        'submitted_unconfirmed': { icon: '⚠️', label: 'Submitted (Unconfirmed)', cls: 'result-warning' },
        'submit_failed': { icon: '❌', label: 'Submit Failed', cls: 'result-error' },
        'error': { icon: '❌', label: 'Error', cls: 'result-error' },
        'unsupported': { icon: '🚫', label: 'Not Supported', cls: 'result-error' },
    };
    const info = statusMap[data.status] || statusMap['error'];

    const filledHtml = (data.fields_filled || []).map(f =>
        `<span class="field-tag filled">${escapeHtml(f)}</span>`
    ).join('');
    const skippedHtml = (data.fields_skipped || []).map(f =>
        `<span class="field-tag skipped">${escapeHtml(f)}</span>`
    ).join('');

    const screenshotHtml = data.screenshot
        ? `<div class="apply-section"><h4>📸 Screenshot</h4><p class="apply-sublabel">Saved to: ${escapeHtml(data.screenshot)}</p></div>`
        : '';

    return `
    <div class="apply-result ${info.cls}">
        <div class="result-header">
            <span class="result-icon">${info.icon}</span>
            <div>
                <h3>${info.label}</h3>
                <div class="apply-company">${escapeHtml(job.title)} at ${escapeHtml(job.company)}</div>
            </div>
        </div>

        ${data.error ? `<div class="apply-error-detail">${escapeHtml(data.error)}</div>` : ''}

        <div class="apply-section">
            <h4>Fields Filled</h4>
            <div class="field-tags">${filledHtml || '<span class="apply-sublabel">None</span>'}</div>
        </div>

        ${skippedHtml ? `
        <div class="apply-section">
            <h4>Fields Skipped</h4>
            <div class="field-tags">${skippedHtml}</div>
        </div>` : ''}

        ${screenshotHtml}

        <div class="apply-actions">
            <button class="btn btn-secondary" onclick="closeApplyModal()">Close</button>
        </div>
    </div>`;
}

function closeApplyModal() {
    document.getElementById('applyModal').style.display = 'none';
}

// Close modal on backdrop click
document.addEventListener('click', (e) => {
    if (e.target.id === 'applyModal') closeApplyModal();
});

// ─── Helpers ─────────────────────────────────────────────────────────
function renderVisaBadge(visaNote) {
    if (!visaNote || visaNote.includes('N/A')) return '';
    if (visaNote.includes('LIKELY'))
        return `<span class="badge" style="background:rgba(16,185,129,0.15);color:#10b981;">🛂 Visa Likely</span>`;
    if (visaNote.includes('UNLIKELY'))
        return `<span class="badge" style="background:rgba(239,68,68,0.15);color:#ef4444;">⚠️ No Visa</span>`;
    if (visaNote.includes('CHECK'))
        return `<span class="badge" style="background:rgba(245,158,11,0.15);color:#f59e0b;">🌍 Check Visa</span>`;
    return `<span class="badge" style="background:rgba(107,114,128,0.15);color:#9ca3af;">❓ Visa Unknown</span>`;
}

function renderExpBadge(expNote) {
    if (!expNote) return '';
    if (expNote.includes('Perfect match'))
        return `<span class="badge" style="background:rgba(16,185,129,0.15);color:#10b981;">✅ Exp Match</span>`;
    if (expNote.includes('Strong fit'))
        return `<span class="badge" style="background:rgba(16,185,129,0.15);color:#10b981;">✅ Exp Fit</span>`;
    if (expNote.includes('Stretch'))
        return `<span class="badge" style="background:rgba(245,158,11,0.15);color:#f59e0b;">⚠️ Exp Stretch</span>`;
    if (expNote.includes('Underqualified') || expNote.includes('Too senior'))
        return `<span class="badge" style="background:rgba(239,68,68,0.15);color:#ef4444;">🔴 Exp Gap</span>`;
    return '';
}

function setStatus(state) {
    const badge = document.getElementById('statusBadge');
    badge.className = 'status-badge';
    const map = { ready: ['status-ready', '● Ready'], loading: ['status-loading', '● Searching...'], error: ['status-error', '● Error'] };
    const [cls, text] = map[state] || map.error;
    badge.classList.add(cls);
    badge.textContent = text;
}

function slugify(str) { return str.toLowerCase().replace(/[^a-z0-9]+/g, '-'); }

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
