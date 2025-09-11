from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Dict, Any, Optional
import hashlib
import json
import os


@dataclass
class Document:
    id: str
    url: str
    published_at: str  # ISO timestamp (UTC)
    source: str  # e.g., "wayback", "edgar"
    title: str
    text: str
    meta: Dict[str, Any]

    def published_dt(self) -> datetime:
        return datetime.fromisoformat(self.published_at.replace("Z", "+00:00"))


def _hash_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class DocStore:
    """Very simple JSONL-backed document store.

    Layout:
      base_dir/
        docs.jsonl       # one JSON doc per line
        index.json       # { id -> byte_offset } for fast reads (optional)
    """

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.docs_path = self.base_dir / "docs.jsonl"
        self.index_path = self.base_dir / "index.json"
        self._index: Dict[str, int] = {}
        if self.index_path.exists():
            try:
                self._index = json.loads(self.index_path.read_text())
            except Exception:
                self._index = {}

    def _append(self, doc: Document) -> None:
        line = json.dumps(asdict(doc), ensure_ascii=False) + "\n"
        with open(self.docs_path, "a", encoding="utf-8") as fh:
            pos = fh.tell()
            fh.write(line)
        self._index[doc.id] = pos

    def add_or_update(self, doc: Document) -> None:
        # Simple dedup by id: rewrite index to last occurrence
        self._append(doc)
        self.index_path.write_text(json.dumps(self._index))

    def add_many(self, docs: Iterable[Document]) -> int:
        n = 0
        for d in docs:
            self.add_or_update(d)
            n += 1
        return n

    def all_docs(self) -> Iterable[Document]:
        if not self.docs_path.exists():
            return []
        with open(self.docs_path, "r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    data = json.loads(line)
                    yield Document(**data)
                except Exception:
                    continue

    def query_asof(self, as_of: datetime, limit: Optional[int] = None) -> List[Document]:
        out: List[Document] = []
        for d in self.all_docs():
            try:
                if d.published_dt() <= as_of:
                    out.append(d)
            except Exception:
                continue
            if limit and len(out) >= limit:
                break
        return out

    @staticmethod
    def make_id(url: str, published_at: str, source: str) -> str:
        key = f"{url}|{published_at}|{source}"
        return _hash_text(key)

