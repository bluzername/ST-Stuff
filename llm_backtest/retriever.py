from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import List, Tuple
import math
import re

from .docstore import Document


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[A-Za-z0-9_$%\.\-]+", text.lower())


@dataclass
class Retrieved:
    doc: Document
    score: float


def retrieve(docs: List[Document], query: str, as_of: datetime, top_k: int = 10) -> List[Retrieved]:
    """Very simple TF-IDF-ish scorer without external deps.

    - Filters docs by published_at <= as_of
    - Scores by sum( tf(term, doc) * idf(term) ) for query terms
    - Returns top_k
    """
    terms = _tokenize(query)
    if not terms:
        return []

    # Build doc-term counts and df for quick scoring
    filtered: List[Tuple[Document, Counter]] = []
    df: Counter = Counter()
    for d in docs:
        if d.published_dt() > as_of:
            continue
        toks = _tokenize(d.title + " \n " + d.text[:5000])  # cap per doc
        c = Counter(toks)
        if not c:
            continue
        filtered.append((d, c))
        seen = set(toks)
        for t in set(terms) & seen:
            df[t] += 1

    N = max(1, len(filtered))
    results: List[Retrieved] = []
    for d, c in filtered:
        score = 0.0
        for t in terms:
            tf = c.get(t, 0)
            if tf == 0:
                continue
            idf = math.log((N + 1) / (1 + df.get(t, 0))) + 1.0
            score += tf * idf
        if score > 0:
            results.append(Retrieved(doc=d, score=score))

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:top_k]

