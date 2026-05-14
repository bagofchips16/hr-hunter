"""
Configuration for the HR Hunter tool.
Edit CANDIDATE_PROFILE and SEARCH_CONFIG to customize.
"""

from datetime import datetime, timedelta

# ─── Candidate Profile ───────────────────────────────────────────────
CANDIDATE_PROFILE = {
    "current_company": "Reliance",
    "years_experience": 5,
    "current_role": "HR Professional",
    "current_tc_lakhs": 30,
    "target_tc_lakhs": 40,
    "target_levels": ["Senior HR", "HR Manager", "HRBP", "Lead HR", "HR Business Partner"],
    "core_skills": [
        "HR Business Partnering", "Talent Acquisition", "Talent Management",
        "Employee Relations", "Performance Management", "Compensation & Benefits",
        "Learning & Development", "Organizational Development",
        "HR Analytics", "People Operations", "HRIS",
        "Workforce Planning", "Succession Planning", "Change Management",
        "Diversity & Inclusion", "Employee Engagement",
    ],
    "target_domains": [
        "HR Business Partner", "Talent Acquisition", "Total Rewards",
        "L&D", "OD", "People Analytics", "HR Tech", "HRIS",
        "Employee Relations", "Compensation & Benefits",
    ],
    "preferred_companies": [
        "Google", "Meta", "Amazon", "Apple", "Microsoft",
        "Flipkart", "Swiggy", "Zomato", "Razorpay", "CRED",
        "Meesho", "PhonePe", "Paytm", "Groww", "Zepto",
        "Infosys", "TCS", "Wipro", "HCL", "Tech Mahindra",
        "Reliance", "Tata", "Mahindra", "Aditya Birla", "Godrej",
        "Deloitte", "McKinsey", "BCG", "Bain", "EY", "PwC", "KPMG",
        "Stripe", "Databricks", "Snowflake", "Salesforce",
        "LinkedIn", "Uber", "Netflix", "Adobe", "Accenture",
    ],
    "locations": [
        # India
        "India", "Bangalore", "Bengaluru", "Hyderabad", "Mumbai",
        "Delhi", "Gurgaon", "Gurugram", "Noida", "Pune", "Chennai",
        "Kolkata", "Ahmedabad", "Jaipur",
        # Global / Remote
        "Remote", "Global", "Anywhere",
        # International
        "Singapore", "Dubai", "London", "New York",
    ],
    "visa_required_abroad": True,
}

# ─── Search Configuration ────────────────────────────────────────────
SEARCH_CONFIG = {
    "max_age_hours": 72,
    "max_results_per_source": 30,
    "min_fit_score": 40,
    "cutoff_date": datetime.now() - timedelta(hours=72),
}

# ─── Search Queries ──────────────────────────────────────────────────
SEARCH_QUERIES = [
    # Core HR roles
    "HR Business Partner",
    "Senior HR Manager",
    "Talent Acquisition Lead",
    "HR Manager",
    # Specialized HR
    "Compensation Benefits Manager",
    "Learning Development Manager",
    "People Analytics",
    "HRIS Manager",
    # Senior / Leadership
    "Head of HR",
    "HR Director",
]

# ─── Greenhouse Boards (company_slug -> display name) ────────────────
GREENHOUSE_BOARDS = {
    "databricks": "Databricks",
    "stripe": "Stripe",
    "discord": "Discord",
    "figma": "Figma",
    "pinterest": "Pinterest",
    "airbnb": "Airbnb",
    "lyft": "Lyft",
    "datadog": "Datadog",
    "anthropic": "Anthropic",
    "scaleai": "Scale AI",
}

# ─── Lever Boards ────────────────────────────────────────────────────
LEVER_BOARDS = {}

# ─── Ashby Boards ────────────────────────────────────────────────────
ASHBY_BOARDS = {
    "openai": "OpenAI",
}

# ─── Alumni-Heavy Companies (for referral scoring) ───────────────────
ALUMNI_COMPANIES = [
    "google", "meta", "amazon", "flipkart", "swiggy", "zomato",
    "razorpay", "cred", "meesho", "phonepe", "paytm", "groww",
    "infosys", "tcs", "wipro", "hcl", "deloitte", "ey", "pwc", "kpmg",
    "uber", "linkedin", "microsoft", "accenture",
]

# ─── TC Estimation (India, in Lakhs) ─────────────────────────────────
TC_ESTIMATES = {
    "google": {"HR Manager": "40-55L", "Senior HRBP": "55-75L", "HR Director": "80-120L"},
    "meta": {"HR Manager": "45-60L", "Senior HRBP": "60-80L", "HR Director": "85-130L"},
    "amazon": {"HR Manager": "35-50L", "Senior HRBP": "50-70L", "HR Director": "75-110L"},
    "flipkart": {"HR Manager": "30-45L", "Senior HRBP": "45-65L", "HR Director": "70-100L"},
    "default_bigtech": {"HR Manager": "35-50L", "Senior HRBP": "50-70L", "HR Director": "70-100L"},
    "default_startup": {"HR Manager": "25-40L", "Senior HRBP": "40-60L", "HR Director": "60-90L"},
    "default_consulting": {"HR Manager": "30-45L", "Senior HRBP": "45-65L", "HR Director": "65-95L"},
    "default_conglomerate": {"HR Manager": "20-35L", "Senior HRBP": "35-50L", "HR Director": "50-75L"},
}
