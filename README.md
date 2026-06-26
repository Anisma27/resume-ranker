# Redrob Hackathon — Intelligent Candidate Discovery & Ranking Challenge

**Team:** QuantumSolo
**Track:** Data Challenge (Track 1)

A pure rule-based, fully explainable candidate ranker built for Redrob's
"Senior AI Engineer — Founding Team" job description. No ML model, no
embeddings, no LLM calls, no GPU. Designed from the ground up to satisfy the
hackathon's compute constraints with large margin, and to be fully defensible
in a design-review interview — every scoring weight traces back to a specific
sentence in the job description.

## Why rule-based, not embeddings/LLM-based

The compute budget is 5 minutes, 16GB RAM, CPU-only, no network, for 100,000
candidates. That budget rules out per-candidate LLM calls outright (the spec
says so explicitly) and makes embeddings unnecessary complexity for a problem
that's actually about *structured reasoning over structured fields* — title
ladder, skill corroboration, experience band, company pedigree, location fit,
behavioral availability — not about free-text semantic similarity. A
transparent scoring function over these fields is both faster and easier to
defend than a black-box model, and it directly targets the specific traps the
challenge describes (keyword stuffing, honeypots, behavioral twins).

## Results on the released data

- **Runtime:** ~9.3 seconds for all 100,000 candidates (budget: 300s)
- **Peak memory:** ~78 MB (budget: 16 GB)
- **Network calls during ranking:** zero
- **GPU usage:** zero
- Validated against `validate_submission.py` from the official bundle: passes.
- Manually verified: zero honeypot-pattern candidates and zero
  consulting-only-career candidates appear in the top 100.

## How it works

`rank.py` scores every candidate against five independent fit axes, applies
hard disqualifiers and soft penalties for implausible/inconsistent profiles,
then multiplies by a behavioral-availability factor derived from Redrob
platform signals.

### 1. Skills score (weight 0.38)
The JD lists four "things you absolutely need": embeddings/retrieval,
vector DB / hybrid search, Python, and ranking-evaluation experience. For each
pillar, the ranker finds the candidate's best matching skill and computes a
**trust score** combining their claimed proficiency with `duration_months` —
a skill claimed for 0–3 months counts far less than the same skill claimed for
24+ months, regardless of the proficiency label. This directly targets the
keyword-stuffing trap: in the released data, non-ML-titled candidates list
these buzzword skills almost as often as genuine ML candidates, but with
roughly half the average duration and a fraction of the "expert" claims.

On top of that, each matched skill is checked for **corroboration** — does
the candidate's actual career-history text mention the same technology? An
uncorroborated skill claim (present in the skills list, absent from any job
description) is discounted by ~45%.

### 2. Title score (weight 0.27)
A lookup table scores each of the dataset's 47 distinct job titles against
the JD's stated title ladder (Senior/Staff/Lead AI/ML Engineer roles score
highest; adjacent roles like Search Engineer or Data Scientist score in the
middle; off-domain titles like Business Analyst score near zero).

### 3. Experience score (weight 0.15)
A band-based score centered on the JD's 5–9 year sweet spot, with a gentle
asymmetric falloff outside it (the JD explicitly says some people hit
"senior" judgment earlier, so under-band candidates aren't penalized as hard
as far-over-band ones).

### 4. Company pedigree score (weight 0.12)
Rewards time spent at real product companies and AI-native companies
(identified by inspecting the dataset — every employee at companies like
Sarvam AI, Krutrim, Yellow.ai, or the rare global big-tech employers carries
an ML/AI title) over the dataset's fictional filler employers (Wayne
Enterprises, Hooli, Acme Corp, etc., used as generic noise) or pure
consulting-firm careers, which the JD explicitly flags as a weak fit.

### 5. Location score (weight 0.08)
Exact match on Pune/Noida scores highest, other Tier-1 Indian cities the JD
names as acceptable next, other India next, international only if the
candidate has flagged willingness to relocate.

### Hard disqualifiers
Floor (not zero, but effectively out of top-100 range) candidates whose
entire career is at consulting firms only, whose entire career is in
academic/research institutions with no production deployment, or whose
current title is in a clearly unrelated technical domain (civil/mechanical
engineering) per the JD's explicit "things we do NOT want" section.

### Implausibility / honeypot penalty
A soft multiplier (not a hard cutoff, since this is necessarily heuristic
without the hidden ground truth) for profile-internal inconsistencies: a
skill's claimed duration exceeding the candidate's total years of experience,
or "expert" proficiency claimed with zero months of use. Verified empirically
against the data that these are rare, genuinely strange patterns rather than
common noise.

### Behavioral availability multiplier
Combines `last_active_date` recency, `recruiter_response_rate`,
`open_to_work_flag`, and `interview_completion_rate` into one bounded
multiplier (0.4–1.05), applied after the fit score. This implements the JD's
explicit instruction: "a perfect-on-paper candidate who hasn't logged in for
6 months and has a 5% recruiter response rate is, for hiring purposes, not
actually available."

### Reasoning generation
Each row's `reasoning` field is built per-candidate from the actual scoring
components that fired for that candidate (real title, real years of
experience, real company, real response rate, real concerns) — not a
template with the name swapped in. This is intentional: Stage 4 manual review
checks for hallucination and templated reasoning.

## Repository structure

```
.
├── rank.py                        # the ranker (single file, stdlib only)
├── requirements.txt                # no external dependencies
├── submission_metadata.yaml        # filled-in metadata for this submission
├── sandbox/
│   ├── app.py                      # minimal Streamlit app for the sandbox demo
│   └── sample_candidates.json      # small sample for the sandbox to run against
└── README.md                       # this file
```

## Reproducing the submission

Single command, no setup beyond stdlib Python 3.9+:

```bash
python rank.py --candidates ./candidates.jsonl --out ./submission.csv
```

No `pip install` is required — the ranker uses only the Python standard
library (`json`, `csv`, `argparse`, `datetime`). This was a deliberate choice
to eliminate any dependency-related reproduction risk at Stage 3.

To validate the output against the official spec before submitting:

```bash
python validate_submission.py team_quantumsolo.csv
```

(copy `validate_submission.py` from the original hackathon bundle into this
repo, or run it from wherever you extracted the bundle.)

## Compute environment this was tested on

See `submission_metadata.yaml` for the exact declared environment. Summary:
plain CPU machine, Python 3.x standard library only, no GPU, no network
during the ranking step, ~9 seconds and ~80MB peak memory for the full
100,000-candidate pool — both multiple orders of magnitude under budget.

## AI tools used

Declared in `submission_metadata.yaml`. In summary: Claude was used as a
development and data-analysis assistant — to explore the released dataset's
actual distributions (title frequencies, skill-duration patterns, company
tiers, honeypot-style inconsistencies) before any scoring logic was written,
and to help structure and review the resulting `rank.py`. No candidate data
was sent to any external API as part of the ranking step itself; all of that
runs locally with zero network access, per the compute constraints. The
scoring weights, thresholds, and design decisions were derived from
reading the job description and inspecting the actual dataset distributions
shown above — not invented or copied from elsewhere.
