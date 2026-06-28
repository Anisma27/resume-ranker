"""
Redrob Hackathon — sandbox demo app (v2, Clean Professional UI).
"""

import json
import sys
from pathlib import Path

import streamlit as st

# ── page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Redrob Ranker — QuantumSolo",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Google Font */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Background */
.stApp {
    background-color: #F8F9FB;
}

/* Top header banner */
.hero-banner {
    background: linear-gradient(135deg, #1A1A2E 0%, #16213E 60%, #0F3460 100%);
    border-radius: 16px;
    padding: 36px 40px;
    margin-bottom: 28px;
    color: white;
}
.hero-banner h1 {
    font-size: 2rem;
    font-weight: 700;
    margin: 0 0 6px 0;
    color: white;
}
.hero-banner p {
    font-size: 0.95rem;
    color: #A0AEC0;
    margin: 0;
}
.hero-badge {
    display: inline-block;
    background: rgba(255,255,255,0.12);
    border: 1px solid rgba(255,255,255,0.2);
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 0.78rem;
    color: #E2E8F0;
    margin-bottom: 14px;
}

/* Metric cards */
.metric-card {
    background: white;
    border-radius: 12px;
    padding: 20px 24px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    border-left: 4px solid #0F3460;
}
.metric-card .metric-label {
    font-size: 0.78rem;
    color: #718096;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 6px;
}
.metric-card .metric-value {
    font-size: 1.6rem;
    font-weight: 700;
    color: #1A202C;
}

/* Score bar */
.score-bar-wrap {
    background: #EDF2F7;
    border-radius: 6px;
    height: 8px;
    width: 100%;
    margin-top: 4px;
}
.score-bar-fill {
    height: 8px;
    border-radius: 6px;
    background: linear-gradient(90deg, #0F3460, #E94560);
}

/* Rank badge */
.rank-badge {
    display: inline-block;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: #0F3460;
    color: white;
    font-size: 0.8rem;
    font-weight: 700;
    text-align: center;
    line-height: 32px;
}
.rank-badge.gold   { background: #D4A017; }
.rank-badge.silver { background: #8D9DB6; }
.rank-badge.bronze { background: #A0522D; }

/* Section heading */
.section-heading {
    font-size: 1.05rem;
    font-weight: 700;
    color: #1A202C;
    margin: 28px 0 12px 0;
    padding-bottom: 8px;
    border-bottom: 2px solid #E2E8F0;
}

/* Upload zone */
.upload-card {
    background: white;
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.07);
    margin-bottom: 20px;
}

/* Run button override */
div.stButton > button {
    background: linear-gradient(135deg, #0F3460, #E94560);
    color: white;
    border: none;
    border-radius: 10px;
    padding: 12px 36px;
    font-size: 1rem;
    font-weight: 600;
    width: 100%;
    transition: opacity 0.2s;
}
div.stButton > button:hover {
    opacity: 0.88;
    color: white;
}

/* Download button */
div.stDownloadButton > button {
    background: white;
    color: #0F3460;
    border: 2px solid #0F3460;
    border-radius: 10px;
    font-weight: 600;
    width: 100%;
}

/* Candidate row card */
.cand-card {
    background: white;
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.07);
    border-left: 3px solid #0F3460;
}
.cand-card.top3 {
    border-left: 3px solid #E94560;
    background: #FFF8F9;
}
.cand-title { font-weight: 600; color: #1A202C; font-size: 0.95rem; }
.cand-meta  { font-size: 0.82rem; color: #718096; margin-top: 2px; }
.cand-score { font-size: 1.1rem; font-weight: 700; color: #0F3460; }

/* Footer */
.footer {
    text-align: center;
    color: #A0AEC0;
    font-size: 0.78rem;
    margin-top: 40px;
    padding-top: 16px;
    border-top: 1px solid #E2E8F0;
}
</style>
""", unsafe_allow_html=True)

# ── imports ────────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rank import score_candidates  # noqa: E402

DEFAULT_SAMPLE = Path(__file__).resolve().parent / "sample_candidates.json"

# ── hero banner ────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-banner">
    <div class="hero-badge">🏆 Redrob Hackathon · Track 1 · Data Challenge</div>
    <h1>🎯 Intelligent Candidate Ranker</h1>
    <p>Team QuantumSolo &nbsp;·&nbsp; Hybrid Rule-Based + TF-IDF Semantic Scoring &nbsp;·&nbsp;
       CPU-only · No LLM calls · No network · ~35s for 100K candidates</p>
</div>
""", unsafe_allow_html=True)

# ── upload section ─────────────────────────────────────────────────────────────
st.markdown('<div class="section-heading">📂 Candidate Data</div>', unsafe_allow_html=True)

with st.container():
    uploaded = st.file_uploader(
        "Upload a candidate sample (.json array or .jsonl) — max ~100 candidates for the sandbox",
        type=["json", "jsonl"],
    )

def load_candidates(f):
    content = f.read().decode("utf-8").strip()
    if content.startswith("["):
        return json.loads(content)
    return [json.loads(line) for line in content.splitlines() if line.strip()]

if uploaded:
    candidates = load_candidates(uploaded)
    st.success(f"✅ Loaded **{len(candidates)}** candidates from your upload.")
else:
    with open(DEFAULT_SAMPLE, "r", encoding="utf-8") as f:
        candidates = json.load(f)
    st.info(f"ℹ️ Using bundled sample · **{len(candidates)} candidates** · Upload your own file to override.")

# ── run button ─────────────────────────────────────────────────────────────────
st.markdown('<div class="section-heading">⚙️ Run Ranker</div>', unsafe_allow_html=True)
run = st.button("🚀 Run Ranker", type="primary")

if run:
    import time
    with st.spinner("Building TF-IDF index and scoring candidates…"):
        start = time.time()
        results = score_candidates(candidates)
        elapsed = time.time() - start

    scored = []
    for rank_i, (cid, score, reasoning) in enumerate(results, start=1):
        cand = next((c for c in candidates if c["candidate_id"] == cid), {})
        profile = cand.get("profile", {})
        scored.append({
            "rank": rank_i,
            "candidate_id": cid,
            "title": profile.get("current_title", "—"),
            "company": profile.get("current_company", "—"),
            "years": profile.get("years_of_experience", "—"),
            "score": round(score, 4),
            "reasoning": reasoning,
        })

    # ── summary metrics ────────────────────────────────────────────────────────
    st.markdown('<div class="section-heading">📊 Summary</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Candidates Ranked</div>
            <div class="metric-value">{len(scored)}</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Time Taken</div>
            <div class="metric-value">{elapsed:.2f}s</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Top Score</div>
            <div class="metric-value">{scored[0]['score']:.4f}</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Avg Score (Top 10)</div>
            <div class="metric-value">{sum(s['score'] for s in scored[:10])/min(10,len(scored)):.4f}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── top 3 podium ──────────────────────────────────────────────────────────
    st.markdown('<div class="section-heading">🏅 Top 3 Candidates</div>', unsafe_allow_html=True)
    medals = ["gold", "silver", "bronze"]
    medal_icons = ["🥇", "🥈", "🥉"]
    cols = st.columns(3)
    for i, col in enumerate(cols):
        if i < len(scored):
            s = scored[i]
            with col:
                st.markdown(f"""
                <div class="cand-card top3">
                    <div style="margin-bottom:8px">{medal_icons[i]} <span class="rank-badge {medals[i]}">{s['rank']}</span></div>
                    <div class="cand-title">{s['title']}</div>
                    <div class="cand-meta">{s['company']} · {s['years']} yrs</div>
                    <div class="cand-score" style="margin-top:10px">{s['score']:.4f}</div>
                    <div class="score-bar-wrap"><div class="score-bar-fill" style="width:{s['score']*100:.1f}%"></div></div>
                </div>""", unsafe_allow_html=True)

    # ── ranked list ───────────────────────────────────────────────────────────
    st.markdown('<div class="section-heading">📋 All Ranked Candidates</div>', unsafe_allow_html=True)
    for s in scored:
        badge_class = medals[s['rank']-1] if s['rank'] <= 3 else ""
        card_class  = "cand-card top3" if s['rank'] <= 3 else "cand-card"
        with st.expander(f"#{s['rank']}  {s['title']}  ·  {s['company']}  ·  Score: {s['score']:.4f}"):
            st.markdown(f"""
            <div style="font-size:0.88rem;color:#4A5568;line-height:1.6">
                <b>Candidate ID:</b> {s['candidate_id']}<br>
                <b>Experience:</b> {s['years']} years<br>
                <b>Score:</b> {s['score']:.4f}
                <div class="score-bar-wrap" style="margin:6px 0 10px 0">
                    <div class="score-bar-fill" style="width:{s['score']*100:.1f}%"></div>
                </div>
                <b>Reasoning:</b><br>{s['reasoning']}
            </div>""", unsafe_allow_html=True)

    # ── download ──────────────────────────────────────────────────────────────
    st.markdown('<div class="section-heading">⬇️ Download Results</div>', unsafe_allow_html=True)
    csv_rows = ["candidate_id,rank,score,reasoning"]
    for s in scored:
        r = s["reasoning"].replace('"', '""')
        csv_rows.append(f'{s["candidate_id"]},{s["rank"]},{s["score"]:.4f},"{r}"')
    csv_text = "\n".join(csv_rows)
    st.download_button("⬇️ Download Ranked CSV", data=csv_text,
                       file_name="sandbox_ranking.csv", mime="text/csv")

# ── footer ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="footer">
    Team QuantumSolo · Redrob Hackathon 2025 · 
    Full run: <code>python rank.py --candidates candidates.jsonl --out submission.csv</code>
</div>
""", unsafe_allow_html=True)