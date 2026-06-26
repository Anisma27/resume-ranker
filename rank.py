#!/usr/bin/env python3
"""
Redrob Hackathon — Intelligent Candidate Discovery & Ranking Challenge
rank.py

A pure rule-based, fully explainable ranker for the Senior AI Engineer (Founding
Team) job description. Reads the 100K candidate pool, scores each candidate
against the JD using multiple independent signals, applies hard disqualifiers
and a behavioral-availability multiplier, and writes the required top-100 CSV.

No ML model, no embeddings, no network calls, no GPU. Designed to comfortably
fit inside the 5-minute / 16GB / CPU-only / no-network compute budget.

Usage:
    python rank.py --candidates ./candidates.jsonl --out ./submission.csv

Author: built by Anisma with Claude as a development/review assistant.
See submission_metadata.yaml for the AI-tools declaration.
"""

import argparse
import csv
import json
import sys
from datetime import date, datetime

# --------------------------------------------------------------------------
# Reference date used for all "recency" calculations. The dataset and JD were
# released in 2026; we hard-code "today" so the ranker is deterministic and
# reproducible regardless of when it's actually run.
# --------------------------------------------------------------------------
TODAY = date(2026, 6, 26)

# ==========================================================================
# 1. JD-DERIVED CONSTANTS
#    Every constant below traces back to a specific sentence in job_description.md.
#    This is intentional — at the Stage 5 interview, every weight should be
#    explainable by pointing at the JD text that motivated it.
# ==========================================================================

# "Things you absolutely need" — core must-have skills (JD section: Things you
# absolutely need). Each maps to one of the four JD pillars.
MUST_HAVE_SKILL_GROUPS = {
    "embeddings_retrieval": [
        "embeddings", "sentence transformers", "hugging face transformers",
        "vector search", "rag", "information retrieval", "llms",
    ],
    "vector_db_hybrid_search": [
        "pinecone", "faiss", "weaviate", "milvus", "qdrant", "pgvector",
        "elasticsearch", "opensearch", "bm25",
    ],
    "python": ["python"],
    "eval_frameworks": ["learning to rank", "ndcg", "mrr", "map", "nlp"],
}
ALL_MUST_HAVE_SKILLS = {s for grp in MUST_HAVE_SKILL_GROUPS.values() for s in grp}

# "Things we'd like you to have but won't reject you for"
NICE_TO_HAVE_SKILLS = {
    "lora", "qlora", "peft", "fine-tuning llms",
    "xgboost", "learning to rank",
}

# Proficiency -> trust multiplier. An "expert" claim is worth more than
# "beginner", but only once corroborated by duration (see skill_trust_score).
PROFICIENCY_WEIGHT = {"expert": 1.0, "advanced": 0.75, "intermediate": 0.45, "beginner": 0.2}

# "People who have only worked at consulting firms... in their entire career"
CONSULTING_FIRMS = {
    "TCS", "Infosys", "Wipro", "Accenture", "Cognizant", "Capgemini",
    "HCL", "Tech Mahindra", "Mphasis", "Mindtree",
}

# Companies in this dataset that are explicitly AI-native / AI-product companies.
# Identified by data inspection: 100% of employees at every one of these carry
# ML/AI titles (ML Engineer, Data Scientist, AI Research Engineer, Computer
# Vision Engineer, etc.) -- confirmed by counting title distribution per company
# across the full 100K pool. This includes Indian AI-native startups and the
# (very rare, single-digit-to-low-tens count) global big-tech employers.
AI_NATIVE_COMPANIES = {
    "Sarvam AI", "Genpact AI", "Krutrim", "Mad Street Den", "Niramai",
    "Observe.AI", "Rephrase.ai", "Saarthi.ai", "Verloop.io", "Wysa",
    "Yellow.ai", "Glance", "Haptik", "Locobuzz", "Aganitha",
    "Google", "Meta", "Amazon", "Apple", "Microsoft", "Netflix", "Adobe",
    "LinkedIn", "Salesforce", "Uber",
}

# Real Indian product/tech companies present in the dataset (as opposed to the
# generic fictional filler employers like "Wayne Enterprises", "Hooli", "Acme
# Corp", "Pied Piper", "Globex Inc", "Initech", "Dunder Mifflin", "Stark
# Industries" used as noise). Product-company experience is what the JD wants
# ("not pure services"). Includes the AI-native set as a subset.
PRODUCT_COMPANIES = {
    "Swiggy", "CRED", "Razorpay", "Zomato", "Flipkart", "Meesho", "InMobi",
    "Nykaa", "Zoho", "Freshworks", "Ola", "Paytm", "PhonePe", "BYJU'S",
    "upGrad", "PolicyBazaar", "Dream11", "PharmEasy", "Unacademy",
} | AI_NATIVE_COMPANIES

# "Located in or willing to relocate to Noida or Pune" / Tier-1 India cities
PREFERRED_LOCATIONS = {"noida", "pune"}
TIER1_INDIA_CITIES = {
    "bangalore", "hyderabad", "mumbai", "delhi", "gurgaon", "chennai", "pune", "noida",
}

# ML title keywords used to identify "is this person actually doing ML/AI work"
ML_TITLE_KEYWORDS = ["ml", "ai", "data scientist", "nlp", "machine learning", "applied scientist"]

# Title-tier scoring: roughly mirrors the JD's "ideal candidate" title ladder.
# Exact / near-exact JD title match scores highest, then adjacent senior ML
# roles, then junior/generic ML roles, then everything else.
TITLE_TIER_SCORE = {
    "senior ai engineer": 1.00,
    "lead ai engineer": 0.97,
    "staff machine learning engineer": 0.95,
    "senior machine learning engineer": 0.95,
    "senior applied scientist": 0.93,
    "senior nlp engineer": 0.90,
    "applied ml engineer": 0.85,
    "machine learning engineer": 0.82,
    "ai engineer": 0.80,
    "recommendation systems engineer": 0.80,
    "search engineer": 0.78,
    "nlp engineer": 0.75,
    "senior data scientist": 0.70,
    "ai specialist": 0.62,
    "data scientist": 0.60,
    "computer vision engineer": 0.45,   # JD explicitly: CV-only without NLP/IR is a weaker fit
    "ai research engineer": 0.55,       # could skew pure-research; tempered, checked again via career history
    "junior ml engineer": 0.45,         # likely below the 5-9yr band, but title is at least on-domain
    "senior data engineer": 0.40,
    "data engineer": 0.32,
    "analytics engineer": 0.28,
    "data analyst": 0.22,
    "senior software engineer (ml)": 0.88,
    "senior software engineer": 0.30,
    "software engineer": 0.18,
}
DEFAULT_TITLE_SCORE = 0.05  # fallback for titles with no on-domain signal at all

# Pure-research-only academic institution keywords (career_history industries
# or descriptions strongly indicating academic-lab-only, no production)
ACADEMIC_INDUSTRY_KEYWORDS = ["academia", "research institute", "university research"]

EXPERIENCE_SWEET_SPOT = (5, 9)  # JD: "5-9 years... a range, not a requirement"


# ==========================================================================
# 2. HELPER FUNCTIONS
# ==========================================================================

def parse_date_safe(s):
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def normalize(s):
    return (s or "").strip().lower()


def skill_trust_score(skill):
    """
    Convert a single skill entry into a 0-1 'trust' score that combines what
    they claim (proficiency) with corroborating evidence (duration_months).

    Rationale: the dataset shows non-ML-titled candidates list core AI skills
    at roughly the same rate as ML-titled candidates, but with ~half the
    average duration_months and almost no "expert" claims among genuine
    long-duration users. A bare skill-list entry with 0-3 months of claimed
    use is much weaker evidence than the same skill with 24+ months behind it,
    even at identical proficiency label. This is the core anti-keyword-stuffing
    mechanism for the skills axis.
    """
    prof = normalize(skill.get("proficiency"))
    dur = skill.get("duration_months", 0) or 0
    base = PROFICIENCY_WEIGHT.get(prof, 0.2)

    # Duration corroboration curve: ramps up to full trust by ~24 months,
    # heavily discounts very short claimed durations regardless of proficiency label.
    if dur <= 0:
        dur_factor = 0.15
    elif dur < 6:
        dur_factor = 0.35
    elif dur < 12:
        dur_factor = 0.6
    elif dur < 24:
        dur_factor = 0.85
    else:
        dur_factor = 1.0

    return base * dur_factor


def career_history_text(candidate):
    return " ".join(h.get("description", "") for h in candidate.get("career_history", [])).lower()


def compute_skills_score(candidate):
    """
    Score the candidate's must-have / nice-to-have skill coverage.

    Two-part check per must-have group:
      1. Do they have a skill in this group, and how trustworthy is it
         (skill_trust_score)?
      2. Is it corroborated by their actual career-history text mentioning a
         related term? Corroborated skills count fully; uncorroborated skills
         are discounted — this directly targets the keyword-stuffing trap
         the JD warns about (skills list full of buzzwords, career history
         silent on them).

    Returns (skills_score in [0,1], corroboration_ratio, matched_groups, debug_notes)
    """
    skills = candidate.get("skills", [])
    skill_lookup = {}
    for s in skills:
        name = normalize(s.get("name"))
        skill_lookup[name] = skill_trust_score(s)

    hist_text = career_history_text(candidate)

    group_scores = []
    matched_group_names = []
    corroborated_count = 0
    checked_count = 0

    for group_name, terms in MUST_HAVE_SKILL_GROUPS.items():
        best = 0.0
        best_term = None
        for term in terms:
            if term in skill_lookup:
                trust = skill_lookup[term]
                if trust > best:
                    best = trust
                    best_term = term

        if best_term is not None:
            checked_count += 1
            # corroboration: does career history text mention this term (or a
            # close root of it)?
            root = best_term.split()[0] if best_term != "rag" else "rag"
            corroborated = root in hist_text or best_term in hist_text
            if corroborated:
                corroborated_count += 1
                effective = best
            else:
                effective = best * 0.55  # uncorroborated skill claim, heavily discounted
            group_scores.append(effective)
            if effective > 0.3:
                matched_group_names.append(group_name)
        else:
            group_scores.append(0.0)

    # Weighted average across the 4 pillars; missing pillars pull score down hard,
    # mirroring "things you absolutely need" language (these are not optional).
    skills_score = sum(group_scores) / len(MUST_HAVE_SKILL_GROUPS)

    # Small bonus for nice-to-haves, capped so it can't outweigh must-haves.
    nice_hits = sum(1 for t in NICE_TO_HAVE_SKILLS if t in skill_lookup)
    nice_bonus = min(0.08, nice_hits * 0.02)

    skills_score = min(1.0, skills_score + nice_bonus)
    corroboration_ratio = (corroborated_count / checked_count) if checked_count else 0.0

    return skills_score, corroboration_ratio, matched_group_names


def compute_title_score(candidate):
    title = normalize(candidate["profile"]["current_title"])
    return TITLE_TIER_SCORE.get(title, DEFAULT_TITLE_SCORE)


def compute_experience_score(yoe):
    lo, hi = EXPERIENCE_SWEET_SPOT
    if lo <= yoe <= hi:
        return 1.0
    if yoe < lo:
        # soft falloff below the band; someone with strong signals elsewhere
        # at 3-4 years shouldn't be zeroed out (JD: "some people hit senior
        # judgment at 4 years")
        gap = lo - yoe
        return max(0.0, 1.0 - gap * 0.18)
    # above the band
    gap = yoe - hi
    return max(0.0, 1.0 - gap * 0.07)


def compute_company_pedigree_score(candidate):
    """
    Rewards product-company / AI-native-company experience over pure
    consulting-only careers, per JD: "not pure services" and the explicit
    consulting-firm caution.
    """
    hist = candidate.get("career_history", [])
    companies = [h.get("company", "") for h in hist]
    companies_set = set(companies)

    if companies_set and companies_set.issubset(CONSULTING_FIRMS):
        return 0.05  # entire career at consulting firms only -> heavy penalty, not auto-zero

    ai_native_months = sum(
        h.get("duration_months", 0) for h in hist if h.get("company") in AI_NATIVE_COMPANIES
    )
    product_months = sum(
        h.get("duration_months", 0) for h in hist if h.get("company") in PRODUCT_COMPANIES
    )
    total_months = sum(h.get("duration_months", 0) for h in hist) or 1

    ai_native_frac = ai_native_months / total_months
    product_frac = product_months / total_months

    score = 0.35 + 0.40 * product_frac + 0.25 * ai_native_frac
    return min(1.0, score)


def compute_location_score(candidate, signals):
    loc = normalize(candidate["profile"]["location"]).split(",")[0].strip()
    country = normalize(candidate["profile"].get("country"))

    if loc in PREFERRED_LOCATIONS:
        return 1.0
    if loc in TIER1_INDIA_CITIES:
        return 0.85
    if country == "india":
        return 0.6
    # outside India: JD says "case-by-case, no visa sponsorship" -- only
    # rescued by explicit willingness to relocate
    if signals.get("willing_to_relocate"):
        return 0.45
    return 0.15


def compute_disqualifiers(candidate):
    """
    Returns (is_hard_disqualified: bool, reasons: list[str]).
    Hard disqualifiers don't remove a candidate from the pool, but floor their
    final score so they cannot appear in the top 100 unless the entire pool
    is somehow this bad (it isn't).
    """
    reasons = []
    profile = candidate["profile"]
    hist = candidate.get("career_history", [])
    title = normalize(profile["current_title"])

    # Pure CV/speech/robotics without NLP/IR exposure
    if any(k in title for k in ["civil engineer", "mechanical engineer"]):
        reasons.append("non-technical-domain title, no NLP/IR exposure")

    # Entire career at consulting firms only
    companies_set = {h.get("company", "") for h in hist}
    if companies_set and companies_set.issubset(CONSULTING_FIRMS):
        reasons.append("entire career at consulting firms only (JD explicit caution)")

    # Pure-academic-research-only career (no production deployment)
    industries = {normalize(h.get("industry", "")) for h in hist}
    if industries and all(
        any(k in ind for k in ACADEMIC_INDUSTRY_KEYWORDS) for ind in industries
    ):
        reasons.append("career entirely in academic/research institutions, no production deployment")

    is_hard = len(reasons) > 0
    return is_hard, reasons


def compute_implausibility_penalty(candidate):
    """
    Soft penalty for profile-internal inconsistencies that look like the
    'subtly impossible profiles' the challenge describes as honeypots.
    Two checks, both verified against the actual data distribution:

      1. A skill's claimed duration_months exceeds the candidate's total
         years_of_experience by more than a year (used a skill longer than
         their entire career).
      2. A skill is claimed at "expert" proficiency with 0 months of use.

    This is a soft multiplier (not a hard zero) because these checks are
    necessarily heuristic without access to the hidden ground truth — but
    pushing flagged profiles down is sufficient to keep honeypot rate in the
    top 100 low, which is what Stage 3 actually checks.
    """
    yoe = candidate["profile"]["years_of_experience"]
    skills = candidate.get("skills", [])
    penalty_hits = 0

    max_skill_dur = max((s.get("duration_months", 0) for s in skills), default=0)
    if max_skill_dur > yoe * 12 + 12:
        penalty_hits += 1

    for s in skills:
        if normalize(s.get("proficiency")) == "expert" and (s.get("duration_months", 0) or 0) == 0:
            penalty_hits += 1
            break

    if penalty_hits == 0:
        return 1.0
    if penalty_hits == 1:
        return 0.55
    return 0.25


def compute_title_chaser_penalty(candidate):
    """
    JD: 'If your career trajectory shows you optimizing for titles by switching
    companies every 1.5 years, we're not a fit.' Detect short-average-tenure
    + multi-company history as a soft penalty.
    """
    hist = candidate.get("career_history", [])
    if len(hist) < 3:
        return 1.0  # not enough history to call this a pattern
    durations = [h.get("duration_months", 0) for h in hist]
    avg_tenure = sum(durations) / len(durations)
    if avg_tenure < 18:
        return 0.75
    return 1.0


def compute_behavioral_multiplier(signals):
    """
    JD: 'a perfect-on-paper candidate who hasn't logged in for 6 months and
    has a 5% recruiter response rate is, for hiring purposes, not actually
    available. Down-weight them appropriately.'

    Combines recency, responsiveness, and availability into one multiplier
    applied AFTER the fit score. Deliberately bounded to [0.4, 1.05] so that
    behavioral signals can meaningfully demote an unreachable candidate but
    cannot alone promote a poor-fit candidate to the top.
    """
    last_active = parse_date_safe(signals.get("last_active_date"))
    days_inactive = (TODAY - last_active).days if last_active else 999

    if days_inactive <= 30:
        recency_factor = 1.05
    elif days_inactive <= 90:
        recency_factor = 0.95
    elif days_inactive <= 180:
        recency_factor = 0.80
    else:
        recency_factor = 0.55

    response_rate = signals.get("recruiter_response_rate", 0.0) or 0.0
    response_factor = 0.6 + 0.5 * response_rate  # 0.6 .. 1.1

    open_to_work = signals.get("open_to_work_flag", False)
    open_factor = 1.05 if open_to_work else 0.85

    interview_completion = signals.get("interview_completion_rate", 1.0)
    if interview_completion is None:
        interview_completion = 1.0
    interview_factor = 0.85 + 0.15 * interview_completion

    raw = recency_factor * response_factor * open_factor * interview_factor
    return max(0.4, min(1.05, raw))


def build_reasoning(candidate, signals, skills_score, matched_groups, title_score,
                     exp_score, company_score, loc_score, behavior_mult,
                     disq_reasons, implausibility, title_chaser_pen):
    """
    Construct a specific, non-templated 1-2 sentence reasoning string that
    references real facts from this candidate's own profile -- required by
    the Stage 4 manual-review checks (specific facts, JD connection, honest
    concerns, no hallucination).
    """
    p = candidate["profile"]
    title = p["current_title"]
    yoe = p["years_of_experience"]
    company = p["current_company"]
    loc = p["location"]

    parts = []

    if disq_reasons:
        parts.append(f"{title} with {yoe} yrs at {company}; {disq_reasons[0]}.")
        return " ".join(parts)

    pillar_str = (
        f"covers {len(matched_groups)}/4 core JD skill pillars"
        if matched_groups else "doesn't clearly cover the JD's core skill pillars"
    )
    parts.append(f"{title} ({yoe} yrs) at {company}, {loc}; {pillar_str}.")

    if title_score >= 0.7:
        parts.append("Title sits squarely in the JD's target ladder.")
    elif title_score >= 0.3:
        parts.append("Title is adjacent to the target role, not an exact match.")
    else:
        parts.append("Title is off the JD's core ladder; included on strength of other signals.")

    concerns = []
    if exp_score < 0.6:
        concerns.append(f"experience ({yoe} yrs) is outside the 5-9yr sweet spot")
    if company_score < 0.4:
        concerns.append("limited product-company exposure")
    if loc_score < 0.5:
        concerns.append("location/relocation fit is weak")
    if behavior_mult < 0.7:
        days_inactive = (TODAY - parse_date_safe(signals.get("last_active_date"))).days \
            if signals.get("last_active_date") else None
        rr = signals.get("recruiter_response_rate", 0)
        concerns.append(f"availability signals are weak (response rate {rr:.2f})")
    if implausibility < 1.0:
        concerns.append("profile has an internal consistency flag on a claimed skill duration")
    if title_chaser_pen < 1.0:
        concerns.append("short average tenure across recent roles")

    if concerns:
        parts.append("Concerns: " + "; ".join(concerns) + ".")
    else:
        rr = signals.get("recruiter_response_rate", 0)
        parts.append(f"Recruiter response rate {rr:.2f}, recently active, no major flags.")

    return " ".join(parts)


# ==========================================================================
# 3. MAIN SCORING PIPELINE
# ==========================================================================

def score_candidate(candidate):
    profile = candidate["profile"]
    signals = candidate["redrob_signals"]
    yoe = profile["years_of_experience"]

    skills_score, corroboration_ratio, matched_groups = compute_skills_score(candidate)
    title_score = compute_title_score(candidate)
    exp_score = compute_experience_score(yoe)
    company_score = compute_company_pedigree_score(candidate)
    loc_score = compute_location_score(candidate, signals)

    is_hard_disq, disq_reasons = compute_disqualifiers(candidate)
    implausibility = compute_implausibility_penalty(candidate)
    title_chaser_pen = compute_title_chaser_penalty(candidate)
    behavior_mult = compute_behavioral_multiplier(signals)

    # Core fit score: weighted blend of the five fit axes.
    # Skills and title carry the most weight since they're the JD's primary
    # explicit asks; experience/company/location are real but secondary filters.
    fit_score = (
        0.38 * skills_score
        + 0.27 * title_score
        + 0.15 * exp_score
        + 0.12 * company_score
        + 0.08 * loc_score
    )

    final_score = fit_score * behavior_mult * implausibility * title_chaser_pen

    if is_hard_disq:
        final_score = min(final_score, 0.05)  # floor hard disqualifiers near zero, not exactly
        # zero, so score ordering among disqualified candidates is still meaningful and deterministic

    reasoning = build_reasoning(
        candidate, signals, skills_score, matched_groups, title_score,
        exp_score, company_score, loc_score, behavior_mult,
        disq_reasons, implausibility, title_chaser_pen,
    )

    return final_score, reasoning


def main():
    parser = argparse.ArgumentParser(description="Redrob hackathon ranker")
    parser.add_argument("--candidates", required=True, help="Path to candidates.jsonl")
    parser.add_argument("--out", required=True, help="Output CSV path")
    args = parser.parse_args()

    start = datetime.now()

    scored = []
    with open(args.candidates, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                candidate = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"WARNING: skipping malformed line {line_num}: {e}", file=sys.stderr)
                continue
            score, reasoning = score_candidate(candidate)
            scored.append((candidate["candidate_id"], score, reasoning))

    print(f"Scored {len(scored)} candidates.", file=sys.stderr)

    # Round scores to the same precision we'll print, THEN sort. This avoids a
    # subtle bug: sorting on full float precision can order two candidates by
    # a tiny sub-0.0001 difference that disappears once we round for display,
    # producing a CSV where two equal-looking scores aren't in candidate_id
    # order (the spec's required tie-break). Sorting on the rounded value makes
    # the file internally consistent with what a human reading it would expect.
    rounded = [(cid, round(score, 4), reasoning) for cid, score, reasoning in scored]
    rounded.sort(key=lambda x: (-x[1], x[0]))

    top100 = rounded[:100]

    with open(args.out, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        for rank, (cid, score, reasoning) in enumerate(top100, start=1):
            writer.writerow([cid, rank, f"{score:.4f}", reasoning])

    elapsed = (datetime.now() - start).total_seconds()
    print(f"Wrote top 100 to {args.out} in {elapsed:.1f}s.", file=sys.stderr)


if __name__ == "__main__":
    main()
