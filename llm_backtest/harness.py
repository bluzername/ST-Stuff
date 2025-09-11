from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Optional
import os
import json
import textwrap

from .config import LLMConfig
from .retriever import Retrieved
from .sources.wayback import fetch_wayback
from .docstore import DocStore


@dataclass
class Decision:
    ticker: str
    action: str  # BUY/SELL/HOLD
    confidence: float
    citations: List[str]
    rationale: str


class LLMClient:
    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg

    def generate(self, prompt: str, context: List[Retrieved]) -> str:
        # If disabled, return an empty decisions payload
        if not self.cfg.enabled:
            return json.dumps({"decisions": []})

        if self.cfg.provider == "openrouter":
            return self._call_openrouter(prompt, context)
        raise RuntimeError(f"Unsupported LLM provider: {self.cfg.provider}")

    def _call_openrouter(self, prompt: str, context: List[Retrieved]) -> str:
        # Build messages and pass compact context as a system note
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            # Fail soft: behave like disabled
            return json.dumps({"decisions": []})

        # Compact context: include top few docs with URL, published_at, snippet
        def mk_snippet(r: Retrieved) -> str:
            txt = r.doc.text[:1200]
            return f"- [{r.doc.published_at}] {r.doc.url} | {r.doc.title}\n{txt}"

        ctx_docs = context[:6]
        ctx_text = "\n\n".join(mk_snippet(r) for r in ctx_docs)
        system = (
            "You are an investment research analyst operating in a time-frozen mode. "
            "Use ONLY the provided documents (they are all published at or before the cutoff). "
            "Do not use outside knowledge. If evidence is insufficient, respond with HOLD. "
            "Always output strict JSON and include citations (URLs)."
        )

        content = (
            f"Context documents (time-gated):\n{ctx_text}\n\n"
            + prompt
        )

        payload = {
            "model": self.cfg.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }

        import requests
        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": os.environ.get("OPENROUTER_REFERER", "https://example.com"),
            "X-Title": os.environ.get("OPENROUTER_TITLE", "LLM Backtest"),
            "Content-Type": "application/json",
        }
        try:
            r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, data=json.dumps(payload), timeout=60)
            r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            return content
        except Exception:
            # Soft fail to empty decisions
            return json.dumps({"decisions": []})


def build_prompt(as_of: datetime, tickers: List[str], question: str) -> str:
    return (
        f"As of {as_of.isoformat()} (do not use later info), consider tickers {tickers}.\n"
        "You MUST base answers only on the provided documents and cite each claim with URLs."
        " If insufficient evidence, return HOLD.\n"
        f"Question: {question}\n"
        "Respond in strict JSON: {\n  \"decisions\": [\n    {\n      \"ticker\": \"...\", \"action\": \"BUY|SELL|HOLD\", \"confidence\": 0.0-1.0,\n      \"citations\": [\"url\"], \"rationale\": \"...\"\n    }\n  ],\n  \"request_urls\": [\"optional additional URLs to fetch via Wayback\"]\n}\n"
    )


def decide_trades(
    llm: LLMClient,
    as_of: datetime,
    tickers: List[str],
    retrieved: List[Retrieved],
    *,
    docstore: Optional[DocStore] = None,
    max_rounds: int = 2,
) -> List[Decision]:
    """Iterative decision with optional dynamic Wayback fetches requested by the LLM.

    The model may return `request_urls` to fetch additional context. We fetch them (as_of),
    add to the docstore, and re-run once more (bounded by max_rounds).
    """
    round_idx = 0
    current_retrieved = list(retrieved)
    decisions: List[Decision] = []

    while round_idx < max_rounds:
        prompt = build_prompt(as_of, tickers, "What trades (if any) would you recommend today?")
        raw = llm.generate(prompt, current_retrieved)
        try:
            data = json.loads(raw)
        except Exception:
            data = {"decisions": []}

        # Parse decisions
        decisions = []
        for d in data.get("decisions", []):
            try:
                decisions.append(
                    Decision(
                        ticker=str(d.get("ticker", "")).upper(),
                        action=str(d.get("action", "")).upper(),
                        confidence=float(d.get("confidence", 0.0)),
                        citations=[str(u) for u in d.get("citations", [])],
                        rationale=str(d.get("rationale", "")),
                    )
                )
            except Exception:
                continue

        # Fetch requested URLs (Wayback) if any
        req_urls = data.get("request_urls", []) if isinstance(data, dict) else []
        new_docs = []
        if docstore and req_urls:
            for u in req_urls[:8]:  # cap per round
                try:
                    d = fetch_wayback(u, as_of)
                    if d:
                        docstore.add_or_update(d)
                        new_docs.append(d)
                except Exception:
                    continue

        # If we fetched new docs, rebuild retrieved pool for another round
        if new_docs:
            from .retriever import retrieve as _retrieve
            # Combine new docs with previously available docs by re-querying docstore at as_of
            # The caller should pass a fresh retrieved list per day; we just do a light re-rank here
            # to include the new docs with a generic query bucket for the next round.
            # Keep current_retrieved to top N and extend with new ones at high score.
            for nd in new_docs:
                from collections import namedtuple
                RT = namedtuple("RT", ["doc", "score"])  # minimal
                current_retrieved.append(RT(doc=nd, score=999.0))
            round_idx += 1
            continue

        break

    return decisions
