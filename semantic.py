"""
semantic.py — TF-IDF semantic similarity for the Redrob hybrid ranker.

WHY THIS EXISTS
---------------
The JD warns about a specific trap: "A Tier-5 candidate may not use the words
'RAG' or 'Pinecone' in their profile, but if their career history shows they
built a recommendation system at a product company, they're a fit."  Pure
keyword lookup (rank.py's skills table) misses this — a candidate whose
career_history talks about "built a real-time item retrieval service over
dense vectors" is describing the same work as "FAISS / vector search" without
using those words. TF-IDF over free-text fields catches the shared vocabulary
(retrieval, dense, ranking, similarity, vectors) even when exact terms differ.

WHY TF-IDF AND NOT NEURAL EMBEDDINGS
--------------------------------------
The submission spec is explicit: 5-minute CPU budget, 16GB RAM, no GPU, no
network, ≤5GB intermediate disk, must reproduce cleanly in a sandboxed Docker
container.  sentence-transformers + torch is a 2-3 GB dependency chain that
fails under these constraints.  TF-IDF + cosine similarity is scikit-learn
only (already a standard data-science dependency), fits in memory for 100K
candidates, and runs in seconds.  True zero-shared-vocabulary paraphrase
(zero word-root overlap) is the one case TF-IDF misses; that case is rare
in practice for domain-specific ML text, and the remaining signals in rank.py
(skills corroboration, title, company) partially compensate.

INTEGRATION WITH rank.py
--------------------------
1. Call build_tfidf_index(candidates) once, BEFORE the scoring loop.
   This fits all candidates' free text and returns (vectorizer, matrix).

2. Inside the scoring loop, call semantic_score(candidate_idx, index)
   to get a [0,1] similarity score for that candidate.

3. Blend it into fit_score with a small weight (0.10 recommended) so it
   acts as a tiebreaker / paraphrase-finder without overriding the
   stronger pillar signals.

DISK / MEMORY FOOTPRINT
------------------------
TF-IDF on ~100K candidates × ~500 token average free text: sparse matrix
~40-80 MB in RAM (scipy sparse, not dense), negligible disk if not cached.
Fitting + transform: ~5-8 seconds on a single CPU core. Cosine similarity
for one query vector vs 100K: <1 second with sklearn or numpy dot product.
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


# ---------------------------------------------------------------------------
# JD reference narrative — written from the JD's own "how to read between the
# lines" section.  This is what we compute similarity against.  It's a
# hand-written description of the *ideal candidate's career narrative*, NOT
# a keyword list — so it picks up related vocabulary, not just exact matches.
# ---------------------------------------------------------------------------
JD_REFERENCE_NARRATIVE = """
Senior AI engineer with deep experience building production retrieval and
ranking systems. Expertise in semantic search, embedding models, vector
databases such as FAISS, Pinecone, Weaviate, Milvus, Qdrant, and hybrid
search combining dense retrieval with BM25 sparse signals. Strong background
in natural language processing, information retrieval, and recommendation
systems. Built and deployed large-scale retrieval pipelines serving millions
of queries, optimizing relevance metrics including NDCG, MRR, and MAP.
Experience with RAG architectures, LLM integration, sentence transformers,
and HuggingFace ecosystems. Python expert with hands-on work in PyTorch,
fine-tuning language models with LoRA, QLoRA, and PEFT. Has shipped ML
systems end-to-end from research prototype to production at a product
company or AI-native startup. Understands the difference between offline
evaluation and live performance. Led or co-led small founding-team ML
efforts, not just executed tasks in a large org. Comfortable with ambiguity,
able to own a problem from data collection through deployment and monitoring.
Not just a researcher — has actual deployed systems with real users and
latency constraints.
"""


def _candidate_text(candidate):
    """
    Build a single free-text string from all the narrative fields we want
    semantic similarity to cover.  We use:
      - profile.summary        (the candidate's own pitch)
      - career_history[].description (what they actually worked on)
      - skills[].name          (lightweight — already covered by rule-based,
                                but including here helps TF-IDF pick up
                                domain vocabulary without keyword matching)
    We deliberately omit job titles and company names — those are already
    scored deterministically in rank.py and don't need a second vote here.
    """
    parts = []

    summary = (candidate.get("profile") or {}).get("summary", "") or ""
    if summary:
        parts.append(summary)

    for h in candidate.get("career_history", []):
        desc = h.get("description", "") or ""
        if desc:
            parts.append(desc)

    skill_names = " ".join(
    (s.get("name", "") if isinstance(s, dict) else str(s))
    for s in candidate.get("skills", [])
    )
    if skill_names:
        parts.append(skill_names)

    return " ".join(parts)


def build_tfidf_index(candidates):
    """
    Fit a TF-IDF vectorizer on all candidate free-text fields plus the JD
    reference narrative, then return the (vectorizer, candidate_matrix,
    jd_vector) tuple needed for scoring.

    Parameters
    ----------
    candidates : list of parsed candidate dicts (all 100K)

    Returns
    -------
    vectorizer    : fitted TfidfVectorizer
    cand_matrix   : scipy sparse matrix, shape (N, vocab)
    jd_vector     : dense numpy array, shape (1, vocab)
    """
    texts = [_candidate_text(c) for c in candidates]

    # Include the JD narrative in the fit so its vocabulary is part of the
    # IDF calculation — without this, JD-specific terms get artificially high
    # IDF (rare in the candidate corpus) and distort similarity scores.
    fit_corpus = texts + [JD_REFERENCE_NARRATIVE]

    vectorizer = TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 2),       # unigrams + bigrams catch "vector search",
                                  # "learning to rank", "sentence transformers"
                                  # as single features
        min_df=2,                 # ignore terms that appear in only 1 doc
                                  # (typos, one-off candidate-specific tokens)
        max_df=0.85,              # ignore terms in >85% of docs (stop-words
                                  # and domain-universal filler)
        sublinear_tf=True,        # log(1+tf) — reduces dominance of high-freq
                                  # terms like "machine" or "learning" which
                                  # appear in almost every candidate but carry
                                  # little discriminative signal
        strip_accents="unicode",
        lowercase=True,
    )

    full_matrix = vectorizer.fit_transform(fit_corpus)

    # Split back: candidate rows (0..N-1), JD row (last)
    cand_matrix = full_matrix[:-1]
    jd_vector = full_matrix[-1]   # sparse row vector

    return vectorizer, cand_matrix, jd_vector


def semantic_scores(cand_matrix, jd_vector):
    """
    Compute cosine similarity of every candidate against the JD narrative.

    Parameters
    ----------
    cand_matrix : sparse matrix (N, vocab) from build_tfidf_index
    jd_vector   : sparse row vector (1, vocab) from build_tfidf_index

    Returns
    -------
    scores : numpy array of shape (N,), values in [0, 1]
    """
    # cosine_similarity returns shape (N, 1); flatten to (N,)
    sims = cosine_similarity(cand_matrix, jd_vector).flatten()
    return sims.astype(np.float32)