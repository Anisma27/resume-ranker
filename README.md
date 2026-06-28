# Redrob Hackathon — Intelligent Candidate Discovery & Ranking Challenge
**Team:** QuantumSolo · **Track:** Data Challenge (Track 1)

A hybrid rule-based + TF-IDF semantic candidate ranker built for Redrob's "Senior AI Engineer — Founding Team" job description. No LLM calls, no GPU, no network. Designed to satisfy the hackathon's compute constraints with large margin, and fully defensible in a design-review interview — every scoring weight traces back to a specific sentence in the job description.

---

## What changed in v2

v1 was pure rule-based (five structured-field signals). v2 adds a **sixth signal: TF-IDF semantic similarity** over candidate free text (profile summary + career history descriptions + skill names) against a hand-written JD reference narrative.

This directly addresses the JD's stated trap: *"A Tier-5 candidate may not use the words 'RAG' or 'Pinecone' in their profile, but if their career history shows they built a recommendation system at a product company, they're a fit."* TF-IDF catches shared vocabulary (retrieval, dense, ranking, similarity, vectors) even when exact terms differ — without violating any compute constraint.

---

## Why TF-IDF and not neural embeddings

The compute budget is 5 minutes, 16GB RAM, CPU-only, no network, for 100,000 candidates. `sentence-transformers + torch` is a 2-3GB dependency chain that fails under these constraints. TF-IDF + cosine similarity is `scikit-learn` only, fits in memory for 100K candidates, and runs in seconds. The one case TF-IDF misses (true zero-shared-vocabulary paraphrase) is rare in domain-specific ML text, and the remaining rule-based signals partially compensate.

---

## Results on the released data

| Metric | v2 result | Budget |
|---|---|---|
| Runtime (100K candidates) | ~37 seconds | 300 seconds |
| Peak memory | ~3 GB | 16 GB |
| Network calls during ranking | zero | zero allowed |
| GPU usage | zero | zero allowed |
| Honeypots in top 100 | zero | < 10% threshold |
| Validates against `validate_submission.py` | ✅ passes | required |

---

## How it works

`rank.py` scores every candidate against **six independent signals**, applies hard disqualifiers and soft penalties, then multiplies by a behavioral-availability factor from Redrob platform signals.

### Signal 1 — Skills score (weight 0.342)
The JD lists four "things you absolutely need": embeddings/retrieval, vector DB / hybrid search, Python, and ranking-evaluation experience. For each pillar, the ranker finds the candidate's best matching skill and computes a **trust score** combining claimed proficiency with `duration_months` — a skill claimed for 0–3 months counts far less than the same skill claimed for 24+ months, regardless of the proficiency label.

Each matched skill is also checked for **corroboration** — does the candidate's career-history text mention the same technology? An uncorroborated skill claim is discounted by ~45%. This directly targets keyword stuffing: in the data, non-ML-titled candidates list buzzword skills almost as often as genuine ML candidates, but with roughly half the average duration.

### Signal 2 — Title score (weight 0.243)
A lookup table scores each of the dataset's 47 distinct job titles against the JD's stated title ladder. Senior/Staff/Lead AI/ML Engineer roles score highest; adjacent roles like Search Engineer or Data Scientist score in the middle; off-domain titles score near zero.

### Signal 3 — Experience score (weight 0.135)
A band-based score centered on the JD's 5–9 year sweet spot, with a gentle asymmetric falloff outside it (the JD says some people hit senior judgment earlier, so under-band candidates aren't penalized as hard as far-over-band ones).

### Signal 4 — Company pedigree score (weight 0.108)
Rewards time spent at real product companies and AI-native companies (Sarvam AI, Krutrim, Yellow.ai, Google, Meta, etc.) over fictional filler employers (Wayne Enterprises, Hooli, Acme Corp) or pure consulting-firm careers, which the JD explicitly flags as a weak fit.

### Signal 5 — Location score (weight 0.072)
Exact match on Pune/Noida scores highest, other Tier-1 Indian cities next, rest of India next, international only if the candidate has flagged willingness to relocate.

### Signal 6 — Semantic similarity score (weight 0.10) ⭐ new in v2
TF-IDF vectorizer fitted over all 100K candidates' free text (profile summary + career history descriptions + skill names) plus a hand-written JD reference narrative. Cosine similarity against the JD narrative is pre-computed once for all candidates in ~5–8 seconds, then used as a per-candidate lookup during scoring. Catches genuine fit expressed in different vocabulary — the "recommendation system" candidate who never wrote "RAG" or "Pinecone".

### Hard disqualifiers
Floor (not zero, but effectively out of top-100 range) candidates whose entire career is at consulting firms only, whose career is entirely in academic/research institutions, or whose title is in a clearly unrelated domain — per the JD's explicit "things we do NOT want" section.

### Implausibility / honeypot penalty
A soft multiplier for profile-internal inconsistencies: a skill's claimed duration exceeding total years of experience, or "expert" proficiency with zero months of use. Empirically tuned to flag ~85 candidates — matching the challenge's stated ~80 honeypot count.

### Behavioral availability multiplier
Combines `last_active_date` recency, `recruiter_response_rate`, `open_to_work_flag`, and `interview_completion_rate` into one bounded multiplier (0.4–1.05), applied after the fit score. Implements the JD's explicit instruction: *"a perfect-on-paper candidate who hasn't logged in for 6 months and has a 5% recruiter response rate is, for hiring purposes, not actually available."*

### Reasoning generation
Each row's reasoning field is built per-candidate from the actual scoring components — real title, real years of experience, real company, real response rate, real concerns — not a template with the name swapped in. Stage 4 manual review checks for hallucination and templated reasoning.

---

## Repository structure

```
.
├── rank.py                      # main ranker — rule-based + semantic scoring
├── semantic.py                  # TF-IDF semantic similarity module (v2)
├── requirements.txt             # scikit-learn, numpy only
├── submission_metadata.yaml     # team info, AI tools declaration
├── .gitignore                   # excludes dataset and output files
├── sandbox/
│   ├── app.py                   # Streamlit demo app
│   ├── requirements.txt         # streamlit + scikit-learn + numpy
│   └── sample_candidates.json   # 50 candidates for the sandbox demo
└── README.md                    # this file
```

---

## Reproducing the submission

```bash
pip install -r requirements.txt
python rank.py --candidates ./candidates.jsonl --out ./submission.csv
```

To validate:
```bash
python validate_submission.py submission.csv
```

Runtime: ~37 seconds · Peak memory: ~3GB · Zero network calls · Zero GPU.

---

## Sandbox demo

Live at: https://resume-ranker-drvmmvus2dccc6qjbb4e4h.streamlit.app/

Upload any `.json` or `.jsonl` sample (max ~100 candidates) or use the bundled 50-candidate sample to see the ranker run end-to-end in the browser.

---

## AI tools used

Declared in `submission_metadata.yaml`. Claude was used as a development and data-analysis assistant — to explore the dataset's actual distributions (title frequencies, skill-duration patterns, company tiers, honeypot-style inconsistencies) before any scoring logic was written, and to help structure and review `rank.py` and `semantic.py`. No candidate data was sent to any external API during the ranking step itself — all scoring runs locally with zero network access, per the compute constraints. Scoring weights, thresholds, and design decisions were derived from reading the job description and inspecting actual dataset distributions — not invented or copied from elsewhere.
