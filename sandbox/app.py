"""
Redrob Hackathon — sandbox demo app (v3, Hero Landing UI).
"""

import json
import sys
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="Redrob Candidate Ranker — QuantumSolo",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Full dark navy background */
.stApp {
    background-color: #0D1B2A;
}

/* Hide default streamlit header */
header[data-testid="stHeader"] { background: transparent; }

/* ── HERO SECTION ── */
.hero-section {
    background: linear-gradient(135deg, #0D1B2A 0%, #1B2A4A 60%, #0D2137 100%);
    border-radius: 20px;
    padding: 60px 48px;
    margin-bottom: 40px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border: 1px solid rgba(255,255,255,0.07);
}
.hero-left { max-width: 55%; }
.hero-badge {
    display: inline-block;
    background: rgba(0,200,150,0.15);
    border: 1px solid rgba(0,200,150,0.4);
    border-radius: 20px;
    padding: 5px 16px;
    font-size: 0.78rem;
    color: #00C896;
    font-weight: 600;
    letter-spacing: 0.04em;
    margin-bottom: 18px;
}
.hero-h1 {
    font-size: 2.6rem;
    font-weight: 800;
    color: #FFFFFF;
    line-height: 1.2;
    margin: 0 0 16px 0;
}
.hero-h1 span { color: #00C896; }
.hero-sub {
    font-size: 1rem;
    color: #8FA8C8;
    line-height: 1.7;
    margin-bottom: 28px;
}
.hero-stats {
    display: flex;
    gap: 28px;
    margin-top: 8px;
}
.hero-stat-val { font-size: 1.4rem; font-weight: 700; color: #FFFFFF; }
.hero-stat-lbl { font-size: 0.75rem; color: #8FA8C8; margin-top: 2px; }

/* Preview card on the right */
.preview-card {
    background: #1B2A4A;
    border-radius: 16px;
    padding: 20px 24px;
    min-width: 260px;
    border: 1px solid rgba(255,255,255,0.1);
    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
}
.preview-card .preview-title {
    font-size: 0.75rem;
    font-weight: 700;
    color: #00C896;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 14px;
}
.preview-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
}
.preview-rank {
    width: 28px; height: 28px;
    border-radius: 50%;
    background: #0F3460;
    color: white;
    font-size: 0.75rem;
    font-weight: 700;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
}
.preview-rank.g { background: #D4A017; }
.preview-rank.s { background: #8D9DB6; }
.preview-rank.b { background: #A0522D; }
.preview-info { flex: 1; }
.preview-name { font-size: 0.82rem; font-weight: 600; color: #E2E8F0; }
.preview-co   { font-size: 0.72rem; color: #8FA8C8; }
.preview-score { font-size: 0.85rem; font-weight: 700; color: #00C896; }
.preview-bar-bg { background: rgba(255,255,255,0.08); border-radius: 4px; height: 4px; margin-top: 3px; }
.preview-bar-fill { height: 4px; border-radius: 4px; background: linear-gradient(90deg,#00C896,#0F3460); }

/* ── UPLOAD + RUN ── */
.section-label {
    font-size: 0.78rem;
    font-weight: 700;
    color: #00C896;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 8px;
}
.card {
    background: #1B2A4A;
    border-radius: 14px;
    padding: 24px 28px;
    border: 1px solid rgba(255,255,255,0.07);
    margin-bottom: 20px;
}

/* Streamlit file uploader label */
[data-testid="stFileUploader"] label { color: #8FA8C8 !important; }
[data-testid="stFileUploader"] { color: #E2E8F0; }

/* Streamlit info/success boxes */
[data-testid="stAlert"] { border-radius: 10px; }

/* CTA button */
div.stButton > button {
    background: linear-gradient(135deg, #00C896, #009B70);
    color: #0D1B2A;
    border: none;
    border-radius: 10px;
    padding: 14px 40px;
    font-size: 1rem;
    font-weight: 700;
    width: 100%;
    letter-spacing: 0.02em;
    transition: opacity 0.2s;
}
div.stButton > button:hover { opacity: 0.85; color: #0D1B2A; }

/* ── METRICS ── */
.metric-row { display: flex; gap: 16px; margin-bottom: 28px; }
.m-card {
    flex: 1;
    background: #1B2A4A;
    border-radius: 12px;
    padding: 18px 22px;
    border: 1px solid rgba(255,255,255,0.07);
}
.m-label { font-size: 0.73rem; color: #8FA8C8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
.m-value { font-size: 1.7rem; font-weight: 800; color: #FFFFFF; margin-top: 4px; }
.m-sub   { font-size: 0.72rem; color: #00C896; margin-top: 2px; }

/* ── PODIUM ── */
.podium-card {
    background: #1B2A4A;
    border-radius: 14px;
    padding: 20px 22px;
    border: 1px solid rgba(255,255,255,0.07);
    text-align: center;
}
.podium-medal { font-size: 2rem; margin-bottom: 8px; }
.podium-title { font-size: 0.9rem; font-weight: 700; color: #E2E8F0; }
.podium-co    { font-size: 0.78rem; color: #8FA8C8; margin-top: 4px; }
.podium-score { font-size: 1.3rem; font-weight: 800; color: #00C896; margin-top: 10px; }
.podium-bar-bg   { background: rgba(255,255,255,0.08); border-radius: 4px; height: 6px; margin-top: 8px; }
.podium-bar-fill { height: 6px; border-radius: 4px; background: linear-gradient(90deg,#00C896,#0F3460); }

/* ── CANDIDATE ROWS ── */
.cand-exp-title { color: #E2E8F0 !important; font-weight: 600; }
[data-testid="stExpander"] {
    background: #1B2A4A !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 10px !important;
    margin-bottom: 8px !important;
}
[data-testid="stExpander"] summary { color: #E2E8F0 !important; }

/* Download */
div.stDownloadButton > button {
    background: transparent;
    color: #00C896;
    border: 2px solid #00C896;
    border-radius: 10px;
    font-weight: 700;
    width: 100%;
}

/* ── FOOTER ── */
.footer {
    text-align: center;
    color: #4A6080;
    font-size: 0.75rem;
    margin-top: 48px;
    padding-top: 16px;
    border-top: 1px solid rgba(255,255,255,0.06);
}
.footer code { color: #00C896; background: rgba(0,200,150,0.1); padding: 2px 6px; border-radius: 4px; }

/* headings */
h2, h3 { color: #FFFFFF !important; }
p, li  { color: #8FA8C8; }
</style>
""", unsafe_allow_html=True)

# ── imports ────────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rank import score_candidates  # noqa: E402

DEFAULT_SAMPLE = Path(__file__).resolve().parent / "sample_candidates.json"

# ── HERO ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-section">
  <div class="hero-left">
    <div class="hero-badge">🏆 Redrob Hackathon · Track 1 · Data Challenge</div>
    <div class="hero-h1">Intelligent Candidate<br><span>Discovery & Ranking</span></div>
    <div class="hero-sub">
      Stop missing the right person. Our hybrid rule-based + TF-IDF semantic ranker
      scores 100,000 candidates in ~35 seconds — CPU only, no LLM calls, no network,
      fully explainable.
    </div>
    <div class="hero-stats">
      <div>
        <div class="hero-stat-val">100K</div>
        <div class="hero-stat-lbl">Candidates Ranked</div>
      </div>
      <div>
        <div class="hero-stat-val">~35s</div>
        <div class="hero-stat-lbl">Runtime (CPU)</div>
      </div>
      <div>
        <div class="hero-stat-val">6</div>
        <div class="hero-stat-lbl">Scoring Signals</div>
      </div>
      <div>
        <div class="hero-stat-val">0</div>
        <div class="hero-stat-lbl">API Calls</div>
      </div>
    </div>
  </div>
  <div class="preview-card">
    <div class="preview-title">🎯 Live Rankings Preview</div>
    <div class="preview-row">
      <div class="preview-rank g">1</div>
      <div class="preview-info">
        <div class="preview-name">Staff ML Engineer</div>
        <div class="preview-co">Yellow.ai · 8.6 yrs</div>
        <div class="preview-bar-bg"><div class="preview-bar-fill" style="width:78%"></div></div>
      </div>
      <div class="preview-score">0.78</div>
    </div>
    <div class="preview-row">
      <div class="preview-rank s">2</div>
      <div class="preview-info">
        <div class="preview-name">Senior AI Engineer</div>
        <div class="preview-co">Netflix · 7.8 yrs</div>
        <div class="preview-bar-bg"><div class="preview-bar-fill" style="width:76%"></div></div>
      </div>
      <div class="preview-score">0.76</div>
    </div>
    <div class="preview-row">
      <div class="preview-rank b">3</div>
      <div class="preview-info">
        <div class="preview-name">Staff ML Engineer</div>
        <div class="preview-co">Paytm · 7.0 yrs</div>
        <div class="preview-bar-bg"><div class="preview-bar-fill" style="width:73%"></div></div>
      </div>
      <div class="preview-score">0.73</div>
    </div>
    <div style="text-align:center;margin-top:14px;font-size:0.72rem;color:#4A6080">
      Run the ranker below to see your full results
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── UPLOAD ────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-label">📂 Step 1 — Load Candidates</div>', unsafe_allow_html=True)
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

# ── RUN ───────────────────────────────────────────────────────────────────────
st.markdown('<br><div class="section-label">⚙️ Step 2 — Run the Ranker</div>', unsafe_allow_html=True)
run = st.button("🚀 Check Candidate Rankings", type="primary")

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

    # metrics
    st.markdown('<br><div class="section-label">📊 Results Summary</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="m-card"><div class="m-label">Ranked</div><div class="m-value">{len(scored)}</div><div class="m-sub">candidates</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="m-card"><div class="m-label">Time</div><div class="m-value">{elapsed:.2f}s</div><div class="m-sub">CPU only</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="m-card"><div class="m-label">Top Score</div><div class="m-value">{scored[0]["score"]:.4f}</div><div class="m-sub">best match</div></div>', unsafe_allow_html=True)
    with c4:
        avg10 = sum(s["score"] for s in scored[:10]) / min(10, len(scored))
        st.markdown(f'<div class="m-card"><div class="m-label">Avg Top 10</div><div class="m-value">{avg10:.4f}</div><div class="m-sub">score</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # podium
    st.markdown('<div class="section-label">🏅 Top 3 Candidates</div>', unsafe_allow_html=True)
    icons = ["🥇","🥈","🥉"]
    cols = st.columns(3)
    for i, col in enumerate(cols):
        if i < len(scored):
            s = scored[i]
            with col:
                st.markdown(f"""
                <div class="podium-card">
                  <div class="podium-medal">{icons[i]}</div>
                  <div class="podium-title">{s['title']}</div>
                  <div class="podium-co">{s['company']} · {s['years']} yrs</div>
                  <div class="podium-score">{s['score']:.4f}</div>
                  <div class="podium-bar-bg"><div class="podium-bar-fill" style="width:{s['score']*100:.1f}%"></div></div>
                  <div style="font-size:0.7rem;color:#4A6080;margin-top:6px">{s['candidate_id']}</div>
                </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # full list
    st.markdown('<div class="section-label">📋 All Ranked Candidates</div>', unsafe_allow_html=True)
    for s in scored:
        icon = icons[s['rank']-1] if s['rank'] <= 3 else f"#{s['rank']}"
        with st.expander(f"{icon}  {s['title']}  ·  {s['company']}  ·  Score: {s['score']:.4f}"):
            st.markdown(f"""
            <div style="font-size:0.88rem;color:#8FA8C8;line-height:1.7">
              <b style="color:#E2E8F0">Candidate ID:</b> {s['candidate_id']}<br>
              <b style="color:#E2E8F0">Experience:</b> {s['years']} years<br>
              <b style="color:#E2E8F0">Score:</b> <span style="color:#00C896;font-weight:700">{s['score']:.4f}</span>
              <div style="background:rgba(255,255,255,0.06);border-radius:4px;height:6px;margin:8px 0 12px 0">
                <div style="width:{s['score']*100:.1f}%;height:6px;border-radius:4px;background:linear-gradient(90deg,#00C896,#0F3460)"></div>
              </div>
              <b style="color:#E2E8F0">Reasoning:</b><br>{s['reasoning']}
            </div>""", unsafe_allow_html=True)

    # download
    st.markdown("<br>", unsafe_allow_html=True)
    csv_rows = ["candidate_id,rank,score,reasoning"]
    for s in scored:
        r = s["reasoning"].replace('"', '""')
        csv_rows.append(f'{s["candidate_id"]},{s["rank"]},{s["score"]:.4f},"{r}"')
    st.download_button("⬇️ Download Ranked CSV", data="\n".join(csv_rows),
                       file_name="sandbox_ranking.csv", mime="text/csv")

# ── FOOTER ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="footer">
  Team QuantumSolo · Redrob Hackathon 2025 · Hybrid Rule-Based + TF-IDF Semantic Ranker<br>
  Full run: <code>python rank.py --candidates candidates.jsonl --out submission.csv</code>
</div>
""", unsafe_allow_html=True)