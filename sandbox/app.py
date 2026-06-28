"""
Redrob Hackathon — sandbox demo app.

A minimal Streamlit UI that runs rank.py's scoring logic on a small uploaded
(or pre-loaded) sample of candidates and shows the resulting ranked CSV.

This satisfies the hackathon's Section 10.5 sandbox requirement: a hosted
environment where organizers can verify the ranker runs end-to-end on a
small sample. The full 100K-candidate run happens locally / at Stage 3 —
this app is just a reachable, reproducible sanity check.

Deploy: push this repo to GitHub, then deploy on Streamlit Cloud pointing at
sandbox/app.py as the entry point. Free tier is fine.
"""

import json
import sys
from pathlib import Path

import streamlit as st

# Make rank.py and semantic.py (one directory up) importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rank import score_candidates  # noqa: E402

st.set_page_config(page_title="Redrob Ranker — Sandbox", layout="wide")

st.title("Redrob Hackathon — Candidate Ranker Sandbox")
st.caption(
    "Team QuantumSolo · Hybrid rule-based + TF-IDF semantic ranker, CPU, no network. "
    "Upload a small candidate sample (JSON list or JSONL) or use the bundled "
    "sample to see the ranker run end-to-end."
)

DEFAULT_SAMPLE = Path(__file__).resolve().parent / "sample_candidates.json"


def load_candidates(uploaded_file):
    content = uploaded_file.read().decode("utf-8")
    content_stripped = content.strip()
    if content_stripped.startswith("["):
        return json.loads(content_stripped)
    return [json.loads(line) for line in content_stripped.splitlines() if line.strip()]


uploaded = st.file_uploader(
    "Upload a candidate sample (.json array or .jsonl), max ~100 candidates",
    type=["json", "jsonl"],
)

if uploaded is not None:
    candidates = load_candidates(uploaded)
    st.success(f"Loaded {len(candidates)} candidates from upload.")
else:
    with open(DEFAULT_SAMPLE, "r", encoding="utf-8") as f:
        candidates = json.load(f)
    st.info(f"Using bundled sample ({len(candidates)} candidates). Upload your own file to override.")

if st.button("Run ranker", type="primary"):
    import time

    start = time.time()

    with st.spinner("Building TF-IDF index and scoring candidates..."):
        results = score_candidates(candidates)

    elapsed = time.time() - start

    scored = []
    for cid, score, reasoning in results:
        # find the matching candidate for display fields
        c = next(x for x in candidates if x["candidate_id"] == cid)
        scored.append({
            "candidate_id": cid,
            "title": c["profile"]["current_title"],
            "years_of_experience": c["profile"]["years_of_experience"],
            "company": c["profile"]["current_company"],
            "score": round(score, 4),
            "reasoning": reasoning,
        })

    scored.sort(key=lambda x: (-x["score"], x["candidate_id"]))

    st.success(f"Ranked {len(scored)} candidates in {elapsed:.2f}s (CPU, no network).")
    st.dataframe(scored, use_container_width=True)

    csv_rows = ["candidate_id,rank,score,reasoning"]
    for i, row in enumerate(scored, start=1):
        reasoning_escaped = row["reasoning"].replace('"', '""')
        csv_rows.append(f'{row["candidate_id"]},{i},{row["score"]:.4f},"{reasoning_escaped}"')
    csv_text = "\n".join(csv_rows)

    st.download_button(
        "Download ranked CSV",
        data=csv_text,
        file_name="sandbox_ranking.csv",
        mime="text/csv",
    )

st.divider()
st.caption(
    "Full code: rank.py + semantic.py at the repo root. The full 100,000-candidate "
    "submission was produced locally with: "
    "`python rank.py --candidates ./candidates.jsonl --out ./submission.csv` "
    "— ~37 seconds, ~3GB peak memory, zero network calls."
)