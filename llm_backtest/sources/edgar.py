from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict
import json
import os
import time
import requests

from ..docstore import Document, DocStore


SEC_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"


def _sec_headers() -> Dict[str, str]:
    # SEC requires identifying User-Agent. Set via SEC_API_USER_AGENT env.
    ua = os.environ.get("SEC_API_USER_AGENT", "llm-backtest/0.1 (contact@example.com)")
    return {"User-Agent": ua, "Accept-Encoding": "gzip, deflate", "Host": "www.sec.gov"}


def _load_ticker_map(cache_dir: Path) -> Dict[str, Dict]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / "company_tickers.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text())
        except Exception:
            pass
    r = requests.get(SEC_TICKER_MAP_URL, headers=_sec_headers(), timeout=20)
    r.raise_for_status()
    data = r.json()
    cache_file.write_text(json.dumps(data))
    return data


def _ticker_to_cik(ticker: str, cache_dir: Path) -> Optional[str]:
    data = _load_ticker_map(cache_dir)
    ticker = ticker.lower()
    for _, entry in data.items():
        if entry.get("ticker", "").lower() == ticker:
            cik = str(entry.get("cik_str", "")).zfill(10)
            return cik
    return None


def fetch_filings_for_ticker(ticker: str, start: datetime, end: datetime, cache_dir: Path) -> List[Document]:
    """Fetch basic filing texts via the SEC search API (free, best effort).

    This uses the LATEST search endpoint which returns metadata and text excerpts.
    Notes:
      - Rate limited; keep calls modest. Provide proper UA.
      - We only attach lightweight fields and treat 'filedAt' as published time.
    """
    cik = _ticker_to_cik(ticker, cache_dir)
    if not cik:
        return []

    url = "https://efts.sec.gov/LATEST/search-index"
    headers = _sec_headers() | {"Content-Type": "application/json"}
    payload = {
        "keys": cik,
        "category": "custom",
        "startdt": start.strftime("%Y-%m-%d"),
        "enddt": end.strftime("%Y-%m-%d"),
        "from": 0,
        "size": 100,
        "sort": [{"filedAt": {"order": "asc"}}],
        "fields": ["filedAt", "formType", "displayNames", "text"]
    }

    try:
        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []

    hits = data.get("hits", {}).get("hits", [])
    docs: List[Document] = []
    for h in hits:
        src = h.get("_source", {})
        filed_at = src.get("filedAt")
        if not filed_at:
            continue
        published_at = datetime.fromisoformat(filed_at.replace("Z", "+00:00")).isoformat() + "Z"
        title = f"{ticker} {src.get('formType', '')}"
        text = src.get("text", "")
        url_hint = f"sec-search:{ticker}:{filed_at}"
        doc_id = DocStore.make_id(url_hint, published_at, "edgar")
        docs.append(Document(id=doc_id, url=url_hint, published_at=published_at, source="edgar", title=title, text=text, meta={"formType": src.get("formType")}))

    # be polite
    time.sleep(0.2)
    return docs

