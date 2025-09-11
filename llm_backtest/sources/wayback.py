from __future__ import annotations

from datetime import datetime
from typing import Optional
from urllib.parse import quote
import requests
import re

from ..docstore import Document, DocStore


def _closest_snapshot(url: str, as_of: datetime) -> Optional[dict]:
    ts = as_of.strftime("%Y%m%d%H%M%S")
    api = f"https://archive.org/wayback/available?url={quote(url)}&timestamp={ts}"
    try:
        r = requests.get(api, timeout=15)
        r.raise_for_status()
        data = r.json()
        snap = data.get("archived_snapshots", {}).get("closest")
        if snap and snap.get("available"):
            return snap
    except Exception:
        return None
    return None


def _strip_html(html: str) -> str:
    # Very naive removal of tags and scripts/styles; avoid bs4 dependency
    html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    html = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_wayback(url: str, as_of: datetime) -> Optional[Document]:
    snap = _closest_snapshot(url, as_of)
    if not snap:
        return None
    try:
        orig = snap.get("url", url)
        ts = snap.get("timestamp", as_of.strftime("%Y%m%d%H%M%S"))
        archived_url = f"https://web.archive.org/web/{ts}/{orig}"
        r = requests.get(archived_url, timeout=20)
        r.raise_for_status()
        text = _strip_html(r.text)
        published_at = datetime.strptime(ts, "%Y%m%d%H%M%S").isoformat() + "Z"
        doc_id = DocStore.make_id(orig, published_at, "wayback")
        title = orig
        return Document(id=doc_id, url=orig, published_at=published_at, source="wayback", title=title, text=text, meta={"archived_url": archived_url})
    except Exception:
        return None

