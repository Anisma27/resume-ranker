#!/usr/bin/env python3
"""
Redrob Hackathon — Intelligent Candidate Discovery & Ranking Challenge
rank.py  (v2 — hybrid rule-based + TF-IDF semantic similarity)

Changes from v1:
  - Imports semantic.py to build a TF-IDF index over candidate free-text
    (profile.summary + career_history descriptions + skill names) and the
    JD reference narrative.
  - Adds a 6th scoring signal: semantic similarity (weight 0.10), blended
    into fit_score AFTER the five pillar scores.  The pillar weights are
    scaled down proportionally so they still sum to 1.0 with the new signal.
  - Everything else — rule-based signals, behavioral multiplier, honeypot
    detection, hard disqualifiers, tie-break ordering — is unchanged from v1.

Compute budget: 5 min / 16GB RAM / CPU-only / no-network.
Measured: ~37s wall-clock, ~3GB peak RAM on the full 100K pool.

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

from semantic import build_tfidf_index, semantic_scores

TODAY = date(2026, 6, 26)

# ==========================================================================
# JD-DERIVED CONSTANTS  (unchanged from v1 — see v1 comments for rationale)
# ==========================================================================

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

NICE_TO_HAVE_SKILLS = {
    "lora", "qlora", "peft", "fine-tuning llms",
    "xgboost", "learning to rank",
}

PROFICIENCY_WEIGHT = {"expert": 1.0, "advanced": 0.75, "intermediate": 0.45, "beginner": 0.2}

CONSULTING_FIRMS = {
    "TCS", "Infosys", "Wipro", "Accenture", "Cognizant", "Capgemini",
    "HCL", "Tech Mahindra", "Mphasis", "Mindtree",
}

AI_NATIVE_COMPANIES = {
    "Sarvam AI", "Genpact AI", "Krutrim", "Mad Street Den", "Niramai",
    "Observe.AI", "Rephrase.ai", "Saarthi.ai", "Verloop.io", "Wysa",
    "Yellow.ai", "Glance", "Haptik", "Locobuzz", "Aganitha",
    "Google", "Meta", "Amazon", "Apple", "Microsoft", "Netflix", "Adobe",
    "LinkedIn", "Salesforce", "Uber",
}

PRODUCT_COMPANIES = {
    "Swiggy", "CRED", "Razorpay", "Zomato", "Flipkart", "Meesho", "InMobi",
    "Nykaa", "Zoho", "Freshworks", "Ola", "Paytm", "PhonePe", "BYJU'S",
    "upGrad", "PolicyBazaar", "Dream11", "PharmEasy", "Unacademy",
} | AI_NATIVE_COMPANIES

PREFERRED_LOCATIONS = {"noida", "pune"}
TIER1_INDIA_CITIES = {
    "bangalore", "hyderabad", "mumbai", "delhi", "gurgaon", "chennai", "pune", "noida",
}

ML_TITLE_KEYWORDS = ["ml", "ai", "data scientist", "nlp", "machine learning", "applied scientist"]

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
    "computer vision engineer": 0.45,
    "ai research engineer": 0.55,
    "junior ml engineer": 0.45,
    "senior data engineer": 0.40,
    "data engineer": 0.32,
    "analytics engineer": 0.28,
    "data analyst": 0.22,
    "senior software engineer (ml)": 0.88,
    "senior software engineer": 0.30,
    "software engineer": 0.18,
}
DEFAULT_TITLE_SCORE = 0.05

ACADEMIC_INDUSTRY_KEYWORDS = ["academia", "research institute", "university research"]
EXPERIENCE_SWEET_SPOT = (5, 9)

# ==========================================================================
# v2 SCORING WEIGHTS
# Pillar weights from v1 (0.38/0.27/0.15/0.12/0.08) scaled to 0.90 total
# to make room for the new semantic signal at 0.10.  Relative proportions
# among the five pillars are preserved exactly.
# ==========================================================================
W_SKILLS    = 0.342   # was 0.38
W_TITLE     = 0.243   # was 0.27
W_EXP       = 0.135   # was 0.15
W_COMPANY   = 0.108   # was 0.12
W_LOCATION  = 0.072   # was 0.08
W_SEMANTIC  = 0.10    # new in v2


# ==========================================================================
# HELPER FUNCTIONS  (unchanged from v1)
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
    prof = normalize(skill.get("proficiency"))
    dur = skill.get("duration_months", 0) or 0
    base = PROFICIENCY_WEIGHT.get(prof, 0.2)

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
            root = best_term.split()[0] if best_term != "rag" else "rag"
            corroborated = root in hist_text or best_term in hist_text
            if corroborated:
                corroborated_count += 1
                effective = best
            else:
                effective = best * 0.55
            group_scores.append(effective)
            if effective > 0.3:
                matched_group_names.append(group_name)
        else:
            group_scores.append(0.0)

    skills_score = sum(group_scores) / len(MUST_HAVE_SKILL_GROUPS)
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
        gap = lo - yoe
        return max(0.0, 1.0 - gap * 0.18)
    gap = yoe - hi
    return max(0.0, 1.0 - gap * 0.07)


def compute_company_pedigree_score(candidate):
    hist = candidate.get("career_history", [])
    companies = [h.get("company", "") for h in hist]
    companies_set = set(companies)

    if companies_set and companies_set.issubset(CONSULTING_FIRMS):
        return 0.05

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
    if signals.get("willing_to_relocate"):
        return 0.45
    return 0.15


def compute_disqualifiers(candidate):
    reasons = []
    profile = candidate["profile"]
    hist = candidate.get("career_history", [])
    title = normalize(profile["current_title"])

    if any(k in title for k in ["civil engineer", "mechanical engineer"]):
        reasons.append("non-technical-domain title, no NLP/IR exposure")

    companies_set = {h.get("company", "") for h in hist}
    if companies_set and companies_set.issubset(CONSULTING_FIRMS):
        reasons.append("entire career at consulting firms only (JD explicit caution)")

    industries = {normalize(h.get("industry", "")) for h in hist}
    if industries and all(
        any(k in ind for k in ACADEMIC_INDUSTRY_KEYWORDS) for ind in industries
    ):
        reasons.append("career entirely in academic/research institutions, no production deployment")

    is_hard = len(reasons) > 0
    return is_hard, reasons


def compute_implausibility_penalty(candidate):
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
    hist = candidate.get("career_history", [])
    if len(hist) < 3:
        return 1.0
    durations = [h.get("duration_months", 0) for h in hist]
    avg_tenure = sum(durations) / len(durations)
    if avg_tenure < 18:
        return 0.75
    return 1.0


def compute_behavioral_multiplier(signals):
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
    response_factor = 0.6 + 0.5 * response_rate

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
                     disq_reasons, implausibility, title_chaser_pen, sem_score):
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

    # Mention semantic signal when it's meaningfully high — adds a fact the
    # recruiter can cross-check ("narrative shows retrieval/ranking work")
    if sem_score >= 0.20:
        parts.append(f"Career narrative shows strong semantic overlap with JD requirements (sim={sem_score:.2f}).")
    elif sem_score >= 0.10:
        parts.append(f"Career narrative has moderate JD vocabulary alignment (sim={sem_score:.2f}).")

    concerns = []
    if exp_score < 0.6:
        concerns.append(f"experience ({yoe} yrs) is outside the 5-9yr sweet spot")
    if company_score < 0.4:
        concerns.append("limited product-company exposure")
    if loc_score < 0.5:
        concerns.append("location/relocation fit is weak")
    if behavior_mult < 0.7:
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
# MAIN SCORING PIPELINE
# ==========================================================================

def score_candidates(candidates: list[dict]) -> list[tuple]:
    """
    Score all candidates. Returns list of (candidate_id, score, reasoning).

    Two-phase approach to stay within budget:
    1. Build TF-IDF index over all candidates (once, ~5-8s).
    2. Score loop: O(1) lookup into the pre-built similarity array per candidate.
    """
    print("Building TF-IDF index over candidate narratives...", file=sys.stderr)
    t0 = datetime.now()
    _, cand_matrix, jd_vector = build_tfidf_index(candidates)
    sem_sims = semantic_scores(cand_matrix, jd_vector)
    print(f"TF-IDF index built in {(datetime.now()-t0).total_seconds():.1f}s.", file=sys.stderr)

    results = []
    for idx, candidate in enumerate(candidates):
        profile = candidate["profile"]
        signals = candidate["redrob_signals"]
        yoe = profile["years_of_experience"]

        skills_score, corroboration_ratio, matched_groups = compute_skills_score(candidate)
        title_score = compute_title_score(candidate)
        exp_score = compute_experience_score(yoe)
        company_score = compute_company_pedigree_score(candidate)
        loc_score = compute_location_score(candidate, signals)
        sem_score = float(sem_sims[idx])

        is_hard_disq, disq_reasons = compute_disqualifiers(candidate)
        implausibility = compute_implausibility_penalty(candidate)
        title_chaser_pen = compute_title_chaser_penalty(candidate)
        behavior_mult = compute_behavioral_multiplier(signals)

        fit_score = (
            W_SKILLS    * skills_score
            + W_TITLE   * title_score
            + W_EXP     * exp_score
            + W_COMPANY * company_score
            + W_LOCATION * loc_score
            + W_SEMANTIC * sem_score
        )

        final_score = fit_score * behavior_mult * implausibility * title_chaser_pen

        if is_hard_disq:
            final_score = min(final_score, 0.05)

        reasoning = build_reasoning(
            candidate, signals, skills_score, matched_groups, title_score,
            exp_score, company_score, loc_score, behavior_mult,
            disq_reasons, implausibility, title_chaser_pen, sem_score,
        )

        results.append((candidate["candidate_id"], final_score, reasoning))

    return results


def main():
    parser = argparse.ArgumentParser(description="Redrob hackathon ranker v2")
    parser.add_argument("--candidates", required=True, help="Path to candidates.jsonl")
    parser.add_argument("--out", required=True, help="Output CSV path")
    args = parser.parse_args()

    start = datetime.now()

    print("Loading candidates...", file=sys.stderr)
    candidates = []
    with open(args.candidates, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                candidates.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"WARNING: skipping malformed line {line_num}: {e}", file=sys.stderr)

    print(f"Loaded {len(candidates)} candidates.", file=sys.stderr)

    scored = score_candidates(candidates)

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
