"""
Template-based cover letter generator.
Generates a tailored cover letter using job details and candidate profile.
No LLM required — uses pattern matching on job keywords.
"""


def generate_cover_letter(profile: dict, job: dict) -> str:
    """
    Generate a cover letter for a specific job application.
    
    Args:
        profile: Candidate profile from assets/profile.json
        job: Job listing dict with title, company, description, match_reason, etc.
    """
    name = profile.get("full_name", "Candidate")
    company = job.get("company", "your company")
    title = job.get("title", "Product Manager")
    desc = (job.get("description", "") or "").lower()
    match_reason = job.get("match_reason", "")

    # Detect domain focus from job description
    hooks = []
    if _has_any(desc, ["ai safety", "responsible ai", "trust & safety", "trust and safety",
                        "content moderation", "abuse", "integrity"]):
        hooks.append(
            "At Microsoft, I've led AI Safety and Trust & Safety initiatives involving "
            "content moderation systems processing over 100 million URLs daily. I've built "
            "abuse detection pipelines and partnered cross-functionally with ML, policy, and "
            "engineering teams to ship responsible AI products at scale."
        )
    elif _has_any(desc, ["llm", "large language model", "generative ai", "foundation model",
                          "model deployment", "model serving", "rlhf"]):
        hooks.append(
            "I've driven product strategy for LLM-powered features at Microsoft, working "
            "closely with research and engineering teams on model deployment, safety "
            "guardrails, and scalable serving infrastructure."
        )
    elif _has_any(desc, ["platform", "infrastructure", "developer", "api", "sdk"]):
        hooks.append(
            "At Microsoft, I've owned platform and infrastructure product areas, defining "
            "APIs and developer experiences that serve millions of users. I bring deep "
            "experience translating complex technical systems into clear product roadmaps."
        )
    elif _has_any(desc, ["growth", "engagement", "retention", "monetization", "payments"]):
        hooks.append(
            "I bring strong analytical skills and a data-driven approach to product growth, "
            "having shipped features at Microsoft that improved engagement metrics across "
            "products used by hundreds of millions."
        )
    else:
        hooks.append(
            "As a Product Manager at Microsoft with 5 years of experience, I've led "
            "cross-functional teams to deliver impactful products across AI, platform, "
            "and safety domains."
        )

    # Add a quantified impact line
    if _has_any(desc, ["scale", "100m", "billion", "large scale", "at scale"]):
        hooks.append(
            "I'm particularly drawn to scale challenges — my work in content moderation "
            "at Microsoft processes 100M+ URLs/day with <50ms latency requirements."
        )

    # Build the letter
    hook_text = " ".join(hooks)

    letter = f"""Dear Hiring Team at {company},

I'm writing to express my strong interest in the {title} role. {hook_text}

What excites me about {company} is the opportunity to apply my experience at the intersection of product strategy and technical execution. {match_reason}

Key highlights from my background:
• 5 years as a Product Manager at Microsoft, shipping AI and platform products at scale
• Deep expertise in AI Safety, Trust & Safety, and content moderation (100M+ URLs/day)
• Experience with LLMs, abuse detection systems, and responsible AI frameworks
• Strong cross-functional leadership across engineering, ML research, policy, and design

I'd love the opportunity to discuss how my experience aligns with your team's needs. I'm available for a conversation at your convenience.

Best regards,
{name}"""

    return letter.strip()


def _has_any(text: str, keywords: list) -> bool:
    return any(kw in text for kw in keywords)
