"""
Scoring & Analysis Engine for HR roles.
Scores each job listing against the candidate profile.
"""

import re
from datetime import datetime, timezone
from config import CANDIDATE_PROFILE, ALUMNI_COMPANIES, TC_ESTIMATES, SEARCH_CONFIG


# ─── Keyword Weight Maps ─────────────────────────────────────────────

TITLE_KEYWORDS = {
    # Core HR roles (highest weight)
    "hr business partner": 10, "hrbp": 10, "human resources business partner": 10,
    "talent acquisition": 9, "talent management": 9,
    "employee relations": 8, "people operations": 8, "people ops": 8,
    "compensation": 8, "benefits": 7, "total rewards": 9,
    "learning & development": 8, "l&d": 8, "training": 6,
    "organizational development": 8, "org development": 8, "od": 6,
    "hr analytics": 9, "people analytics": 9, "workforce analytics": 9,
    "hris": 8, "hr technology": 8, "hr tech": 8,
    "diversity": 7, "inclusion": 7, "dei": 8,
    "workforce planning": 7, "succession planning": 7,
    "change management": 7, "employee engagement": 7,
    "performance management": 7, "culture": 6,
    # Level signals
    "senior": 5, "lead": 6, "principal": 7, "head": 8,
    "director": 7, "manager": 4, "associate": 3,
    # Base HR signal
    "human resources": 4, "hr ": 4, "people": 3,
}

DESCRIPTION_KEYWORDS = {
    # Core HR competencies
    "hr business partner": 9, "hrbp": 9, "business partnering": 8,
    "talent acquisition": 8, "recruiting": 7, "sourcing": 6,
    "employee relations": 8, "labor relations": 7, "grievance": 6,
    "compensation": 7, "benefits administration": 7, "payroll": 5,
    "total rewards": 8, "salary benchmarking": 7, "equity": 5,
    "learning and development": 7, "training program": 6, "capability building": 7,
    "organizational development": 7, "org design": 7,
    "performance management": 7, "appraisal": 5, "goal setting": 5,
    "succession planning": 7, "workforce planning": 7, "headcount": 5,
    "hr analytics": 8, "people analytics": 8, "hr data": 6,
    "hris": 7, "workday": 7, "successfactors": 7, "bamboohr": 5,
    "darwinbox": 6, "oracle hcm": 6,
    "diversity and inclusion": 7, "dei": 7, "belonging": 5,
    "employee engagement": 7, "retention": 6, "attrition": 5,
    "change management": 7, "transformation": 5,
    "culture": 5, "employer branding": 6, "evp": 6,
    "compliance": 6, "labor law": 6, "statutory": 5,
    "onboarding": 5, "offboarding": 4,
    "stakeholder": 4, "cross-functional": 4,
    "hr policy": 5, "policy framework": 5,
    "leadership development": 7, "coaching": 5, "mentoring": 4,
    "talent review": 6, "calibration": 5,
}

# Titles that are NOT HR — hard reject
NOT_HR_TITLES = [
    "software engineer", "sde", "frontend", "backend", "full stack",
    "data engineer", "data scientist", "ml engineer", "devops",
    "product manager", "product owner", "product lead",
    "marketing manager", "brand manager", "content writer",
    "sales", "business development", "account manager",
    "finance manager", "accounting", "auditor", "controller",
    "supply chain", "logistics", "procurement", "warehouse",
    "designer", "ux designer", "ui designer", "graphic",
    "legal counsel", "paralegal", "lawyer",
    "customer success", "customer support", "support engineer",
    "qa engineer", "test engineer", "sre",
    "network engineer", "security engineer", "cloud engineer",
    "solutions architect", "technical architect",
]

# Must contain at least one of these to be considered an HR role
HR_TITLE_SIGNALS = [
    "human resource", "hr ", " hr", "hrbp",
    "talent acquisition", "talent management",
    "people operations", "people ops", "people partner",
    "people analytics", "people strategy",
    "employee relations", "employee engagement",
    "compensation", "benefits", "total rewards",
    "learning & development", "learning and development", "l&d",
    "organizational development", "org development",
    "workforce", "hris", "hr tech",
    "head of people", "chief people", "chief hr",
    "hr manager", "hr director", "hr lead", "hr business",
    "recruiter", "recruiting", "staffing",
    "diversity", "inclusion", "dei",
]


def _is_hr_role(title: str) -> bool:
    """Strict filter: return True only if this is an HR role."""
    t = title.lower()
    for bad in NOT_HR_TITLES:
        if bad in t:
            return False
    for sig in HR_TITLE_SIGNALS:
        if sig in t:
            return True
    return False


COMPANY_TIERS = {
    "tier1_bigtech": ["google", "meta", "amazon", "apple", "microsoft"],
    "tier1_unicorn": ["flipkart", "swiggy", "zomato", "razorpay", "cred",
                       "meesho", "phonepe", "groww", "zepto"],
    "tier2_consulting": ["deloitte", "mckinsey", "bcg", "bain", "ey", "pwc",
                          "kpmg", "accenture"],
    "tier2_tech": ["stripe", "databricks", "snowflake", "salesforce",
                    "adobe", "linkedin", "uber", "netflix", "spotify"],
    "tier3_conglomerate": ["reliance", "tata", "mahindra", "aditya birla",
                            "godrej", "infosys", "tcs", "wipro", "hcl"],
}


def score_job(job) -> dict:
    """Compute a multi-dimensional fit score for a job listing."""
    exp_score, exp_note = _score_experience(job.description)

    scores = {
        "title_score": _score_title(job.title),
        "description_score": _score_description(job.description),
        "company_score": _score_company(job.company),
        "seniority_score": _score_seniority(job.seniority, job.title),
        "location_score": _score_location(job.location),
        "recency_score": _score_recency(job.posted_date),
        "experience_score": exp_score,
    }

    weights = {
        "title_score": 0.22,
        "description_score": 0.18,
        "company_score": 0.15,
        "seniority_score": 0.08,
        "location_score": 0.12,
        "recency_score": 0.10,
        "experience_score": 0.15,
    }

    raw_score = sum(scores[k] * weights[k] for k in weights)
    fit_score = min(100, max(0, int(raw_score)))

    if fit_score >= 85:
        priority = "P0"
        signal = "Elite"
    elif fit_score >= 70:
        priority = "P1"
        signal = "High"
    elif fit_score >= 55:
        priority = "P2"
        signal = "High"
    else:
        priority = "P3"
        signal = "Medium"

    visa_note = _assess_visa(job)

    return {
        "fit_score": fit_score,
        "priority": priority,
        "signal_strength": signal,
        "match_reason": _generate_match_reason(job, scores),
        "referral_advantage": _assess_referral(job.company),
        "hiring_pain_point": _predict_pain_point(job),
        "speed_to_hire": _predict_speed(job, fit_score),
        "estimated_tc": _estimate_tc(job),
        "interview_loop": _predict_interview_loop(job),
        "inmail_draft": _generate_inmail(job),
        "visa_note": visa_note,
        "experience_note": exp_note,
        "sub_scores": scores,
    }


def _score_title(title: str) -> int:
    title_lower = title.lower()
    if not _is_hr_role(title):
        return 0
    score = 0
    for keyword, weight in TITLE_KEYWORDS.items():
        if keyword in title_lower:
            score += weight
    return max(15, min(100, score * 4))


def _score_description(description: str) -> int:
    if not description:
        return 40
    desc_lower = description.lower()
    score = 0
    for keyword, weight in DESCRIPTION_KEYWORDS.items():
        if keyword in desc_lower:
            score += weight
    return min(100, score * 3)


def _score_company(company: str) -> int:
    comp_lower = company.lower().strip()
    for name in COMPANY_TIERS["tier1_bigtech"]:
        if name in comp_lower:
            return 95
    for name in COMPANY_TIERS["tier1_unicorn"]:
        if name in comp_lower:
            return 90
    for name in COMPANY_TIERS["tier2_consulting"]:
        if name in comp_lower:
            return 80
    for name in COMPANY_TIERS["tier2_tech"]:
        if name in comp_lower:
            return 85
    for name in COMPANY_TIERS["tier3_conglomerate"]:
        if name in comp_lower:
            return 65
    return 50


def _score_seniority(seniority: str, title: str) -> int:
    level = seniority.lower() if seniority else title.lower()
    if any(k in level for k in ["senior", "sr.", "sr "]):
        return 95
    if any(k in level for k in ["lead", "head"]):
        return 90
    if any(k in level for k in ["manager"]):
        return 85
    if any(k in level for k in ["director", "vp"]):
        return 60
    if any(k in level for k in ["associate", "junior", "executive"]):
        return 50
    return 65


CANDIDATE_YOE = 5

def _score_experience(description: str) -> tuple:
    if not description:
        return 70, "No experience requirement mentioned"
    desc_lower = description.lower()
    patterns = [
        r'(\d+)\s*\+?\s*(?:years?|yrs?)(?:\s+of)?\s+(?:of\s+)?(?:relevant\s+|professional\s+|hands[- ]on\s+|hr\s+)?(?:experience|exp)',
        r'(?:minimum|at\s+least|min\.?)\s*(?:of\s+)?(\d+)\s*\+?\s*(?:years?|yrs?)',
        r'(\d+)\s*[-–]\s*\d+\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience|exp)',
        r'(\d+)\s*\+?\s*(?:years?|yrs?)\s+(?:in|of|working)',
    ]
    required_yoe = None
    for pattern in patterns:
        matches = re.findall(pattern, desc_lower)
        if matches:
            nums = [int(m) for m in matches if m.isdigit()]
            if nums:
                required_yoe = max(nums)
                break
    if required_yoe is None:
        return 70, "No specific YOE requirement found"
    diff = CANDIDATE_YOE - required_yoe
    if diff >= 2:
        return 90, f"✅ Strong fit — asks {required_yoe}+ yrs, you have {CANDIDATE_YOE}"
    elif diff >= 0:
        return 100, f"✅ Perfect match — asks {required_yoe}+ yrs, you have {CANDIDATE_YOE}"
    elif diff >= -2:
        return 65, f"⚠️ Stretch — asks {required_yoe}+ yrs, you have {CANDIDATE_YOE} (apply anyway)"
    elif diff >= -4:
        return 30, f"🔴 Underqualified — asks {required_yoe}+ yrs, you have {CANDIDATE_YOE}"
    else:
        return 10, f"🔴 Too senior — asks {required_yoe}+ yrs, you have {CANDIDATE_YOE}"


def _score_location(location: str) -> int:
    if not location:
        return 50
    loc_lower = location.lower()
    india_signals = ["india", "bangalore", "bengaluru", "hyderabad", "mumbai",
                     "delhi", "gurgaon", "gurugram", "noida", "pune", "chennai",
                     "kolkata", "ahmedabad", "jaipur"]
    if any(s in loc_lower for s in india_signals):
        return 100
    if any(s in loc_lower for s in ["remote", "global", "anywhere", "flexible"]):
        return 95
    if any(s in loc_lower for s in ["singapore", "dubai", "london"]):
        return 75
    if any(s in loc_lower for s in ["united states", "usa", "new york", "san francisco"]):
        return 70
    return 55


def _assess_visa(job) -> str:
    loc_lower = (job.location or "").lower()
    desc_lower = (job.description or "").lower()
    comp_lower = job.company.lower()
    india_signals = ["india", "bangalore", "bengaluru", "hyderabad", "mumbai",
                     "delhi", "gurgaon", "gurugram", "noida", "pune", "chennai",
                     "kolkata", "ahmedabad", "jaipur"]
    if any(s in loc_lower for s in india_signals):
        return "N/A — India-based role"
    visa_negative = ["no visa sponsorship", "must be authorized", "must have right to work",
                     "will not sponsor", "no sponsorship", "authorized to work"]
    visa_positive = ["visa sponsorship", "sponsor visa", "relocation support",
                     "relocation assistance", "relocation package"]
    for neg in visa_negative:
        if neg in desc_lower:
            return "⚠️ UNLIKELY — JD indicates no visa sponsorship"
    for pos in visa_positive:
        if pos in desc_lower:
            return "✅ LIKELY — JD mentions visa/relocation support"
    big_sponsors = ["google", "meta", "amazon", "apple", "microsoft",
                    "deloitte", "ey", "pwc", "kpmg", "accenture"]
    for name in big_sponsors:
        if name in comp_lower:
            return "✅ LIKELY — Large company, typically sponsors visas"
    if "remote" in loc_lower:
        return "🌍 CHECK — Remote role, confirm if open to India-based remote"
    return "❓ UNKNOWN — Ask recruiter about visa sponsorship early"


def _score_recency(posted_date) -> int:
    if not posted_date:
        return 50
    now = datetime.now(timezone.utc) if posted_date.tzinfo else datetime.now()
    delta = now - posted_date
    hours = delta.total_seconds() / 3600
    if hours <= 24: return 100
    if hours <= 48: return 85
    if hours <= 72: return 70
    if hours <= 168: return 50
    return 30


def _generate_match_reason(job, scores: dict) -> str:
    reasons = []
    title_lower = job.title.lower()
    desc_lower = (job.description or "").lower()

    if "business partner" in title_lower or "hrbp" in title_lower:
        reasons.append("HR Business Partner role — direct match with strategic HR partnering experience")
    if "talent acquisition" in title_lower or "recruiting" in title_lower:
        reasons.append("Talent Acquisition leadership — experience building and scaling hiring pipelines")
    if "compensation" in title_lower or "total rewards" in title_lower or "benefits" in title_lower:
        reasons.append("Comp & Ben focus — experience with compensation frameworks and benchmarking")
    if "learning" in title_lower or "l&d" in title_lower or "development" in title_lower:
        reasons.append("L&D / OD role — experience designing training and capability building programs")
    if "analytics" in title_lower or "hris" in title_lower:
        reasons.append("HR Tech / Analytics — data-driven HR approach with HRIS experience")
    if "employee relations" in title_lower:
        reasons.append("ER expertise — handling employee grievances, investigations, and policy compliance")
    if "diversity" in title_lower or "inclusion" in title_lower or "dei" in title_lower:
        reasons.append("DEI focus — experience building inclusive workplace programs")
    if "head" in title_lower or "director" in title_lower:
        reasons.append("HR leadership role — ready for next-level strategic HR ownership")

    comp_lower = job.company.lower()
    for name in COMPANY_TIERS["tier1_bigtech"]:
        if name in comp_lower:
            reasons.append("Big Tech — structured HR practices, strong career growth")
            break
    for name in COMPANY_TIERS["tier1_unicorn"]:
        if name in comp_lower:
            reasons.append("High-growth startup — fast-paced, impactful HR work")
            break

    if not reasons:
        reasons.append("HR role with transferable skills from 5yr corporate HR background")

    return " | ".join(reasons[:3])


def _assess_referral(company: str) -> str:
    comp_lower = company.lower().strip()
    for name in ALUMNI_COMPANIES:
        if name in comp_lower:
            return f"HIGH — {company} has strong alumni network. Referral path likely exists."
    return f"MODERATE — Check LinkedIn for connections at {company}."


def _predict_pain_point(job) -> str:
    title_lower = job.title.lower()
    desc_lower = (job.description or "").lower()
    combined = f"{title_lower} {desc_lower}"
    pain_points = [
        ("talent acquisition", "Filling critical roles fast in a competitive talent market"),
        ("recruiting", "Scaling hiring pipeline while maintaining quality of hire"),
        ("hrbp", "Aligning HR strategy with business goals during rapid growth"),
        ("business partner", "Driving organizational effectiveness through strategic HR interventions"),
        ("compensation", "Designing competitive comp structures to attract and retain top talent"),
        ("total rewards", "Building compelling total rewards packages to reduce attrition"),
        ("learning", "Upskilling workforce to meet evolving business and technology needs"),
        ("development", "Building leadership pipeline and succession readiness"),
        ("analytics", "Leveraging HR data to drive evidence-based people decisions"),
        ("hris", "Implementing / optimizing HRIS to streamline HR operations"),
        ("employee relations", "Managing complex employee situations while protecting the organization"),
        ("engagement", "Improving employee engagement scores and reducing voluntary attrition"),
        ("diversity", "Building a diverse and inclusive workforce to drive innovation"),
        ("retention", "Reducing attrition of high-performers in competitive market"),
        ("culture", "Building and scaling company culture through hypergrowth"),
        ("change", "Leading organizational change management during transformation"),
        ("compliance", "Ensuring HR compliance across multiple jurisdictions"),
        ("onboarding", "Creating seamless onboarding experience to improve new hire retention"),
    ]
    for keyword, pain in pain_points:
        if keyword in combined:
            return pain
    return "Hiring experienced HR professional to drive people strategy and operations"


def _predict_speed(job, fit_score: int) -> str:
    comp_lower = job.company.lower()
    for name in COMPANY_TIERS["tier1_unicorn"]:
        if name in comp_lower:
            return "HIGH — Startup, likely fast-tracking HR hires"
    for name in COMPANY_TIERS["tier1_bigtech"]:
        if name in comp_lower:
            return "MEDIUM — Big tech, structured loop (3-5 weeks typical)"
    for name in COMPANY_TIERS["tier2_consulting"]:
        if name in comp_lower:
            return "MEDIUM — Consulting firm, thorough process"
    return "MEDIUM — Standard hiring timeline"


def _estimate_tc(job) -> str:
    comp_lower = job.company.lower().strip()
    seniority = job.seniority or "HR Manager"
    for company_key, levels in TC_ESTIMATES.items():
        if company_key in comp_lower:
            for level_key in ["HR Director", "Senior HRBP", "HR Manager"]:
                if level_key.lower() in seniority.lower():
                    return levels.get(level_key, levels.get("Senior HRBP", "40-60L"))
            return levels.get("Senior HRBP", "40-60L")
    for name in COMPANY_TIERS["tier1_bigtech"]:
        if name in comp_lower:
            return TC_ESTIMATES["default_bigtech"].get("Senior HRBP", "50-70L")
    for name in COMPANY_TIERS["tier1_unicorn"]:
        if name in comp_lower:
            return TC_ESTIMATES["default_startup"].get("Senior HRBP", "40-60L")
    return TC_ESTIMATES["default_startup"].get("HR Manager", "25-40L")


def _predict_interview_loop(job) -> list[str]:
    comp_lower = job.company.lower()
    if "google" in comp_lower:
        return [
            "Recruiter Screen → Role fit + leveling",
            "HRBP Case Study → Strategic HR scenario",
            "Cross-functional → Stakeholder management + influence",
            "Googleyness & Leadership → Culture fit + leadership signals",
            "Hiring Committee Review",
        ]
    if "amazon" in comp_lower:
        return [
            "Recruiter Screen → Role overview + leadership principles",
            "Phone Screen → STAR stories (Customer Obsession, Ownership)",
            "Loop Day (4-5 rounds) → HR case study, Leadership, Bar Raiser",
        ]
    for name in COMPANY_TIERS["tier1_unicorn"]:
        if name in comp_lower:
            return [
                "Recruiter Screen → Background + motivation",
                "Hiring Manager → HR vision + domain expertise",
                "Case Study → HR scenario solving",
                "Culture Fit → Values alignment",
            ]
    return [
        "Recruiter Screen → Background fit + level calibration",
        "Hiring Manager → HR expertise + strategic thinking",
        "Stakeholder Round → Cross-functional collaboration",
        "Final / Leadership → Culture + strategic alignment",
    ]


def _generate_inmail(job) -> str:
    comp = job.company
    title_lower = job.title.lower()

    if "business partner" in title_lower or "hrbp" in title_lower:
        hook = "strategic HR business partnering"
        proof = "partnered with business leaders at Reliance to drive people strategy across 500+ employees"
        value = "aligning HR initiatives with business outcomes"
    elif "talent acquisition" in title_lower or "recruiting" in title_lower:
        hook = "talent acquisition leadership"
        proof = "built and scaled hiring pipelines at Reliance, managing end-to-end recruitment across functions"
        value = "building high-performing teams through strategic talent sourcing"
    elif "compensation" in title_lower or "benefits" in title_lower or "total rewards" in title_lower:
        hook = "compensation and benefits strategy"
        proof = "designed and implemented compensation frameworks at Reliance, driving pay equity and competitiveness"
        value = "building total rewards programs that attract and retain top talent"
    elif "learning" in title_lower or "l&d" in title_lower:
        hook = "learning and development"
        proof = "designed capability building programs at Reliance, impacting 500+ employees across functions"
        value = "building learning ecosystems that drive business performance"
    elif "analytics" in title_lower or "hris" in title_lower:
        hook = "HR analytics and technology"
        proof = "leveraged HR data and HRIS tools at Reliance to drive evidence-based people decisions"
        value = "turning HR data into actionable business insights"
    elif "head" in title_lower or "director" in title_lower:
        hook = "HR leadership"
        proof = "5 years at Reliance leading HR initiatives across talent, engagement, and organizational development"
        value = "driving strategic people agenda that enables business growth"
    else:
        hook = "HR management"
        proof = "5 years at Reliance driving HR strategy across business partnering, talent, and employee engagement"
        value = "building people-first organizations that deliver business results"

    inmail = (
        f"Hi — I'm reaching out about the {job.title} role at {comp}. "
        f"I've spent 5 years at Reliance focused on {hook}, where I {proof}. "
        f"My core strength is {value}. "
        f"I'd welcome a conversation about how my experience maps to "
        f"what you're building. Happy to share specifics on impact and approach."
    )
    words = inmail.split()
    if len(words) > 155:
        inmail = " ".join(words[:150]) + "..."
    return inmail


def analyze_jobs(jobs: list) -> list:
    """Score and rank a list of JobListings. Returns sorted list."""
    for job in jobs:
        analysis = score_job(job)
        job.fit_score = analysis["fit_score"]
        job.priority = analysis["priority"]
        job.signal_strength = analysis["signal_strength"]
        job.match_reason = analysis["match_reason"]
        job.referral_advantage = analysis["referral_advantage"]
        job.hiring_pain_point = analysis["hiring_pain_point"]
        job.speed_to_hire = analysis["speed_to_hire"]
        job.estimated_tc = analysis["estimated_tc"]
        job.interview_loop = analysis["interview_loop"]
        job.inmail_draft = analysis["inmail_draft"]
        job.visa_note = analysis["visa_note"]
        job.experience_note = analysis["experience_note"]

    india_signals = ["india", "bangalore", "bengaluru", "hyderabad", "mumbai",
                     "delhi", "gurgaon", "gurugram", "noida", "pune", "chennai",
                     "kolkata", "ahmedabad", "jaipur"]

    def _is_india(j):
        loc = (j.location or "").lower()
        return any(s in loc for s in india_signals)

    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    jobs.sort(key=lambda j: (
        0 if _is_india(j) else 1,
        priority_order.get(j.priority, 9),
        -j.fit_score,
    ))
    return jobs
