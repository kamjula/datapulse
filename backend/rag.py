"""Tiny TF-IDF retrieval over the runbook library.

Keeps the project dependency-light (no vector DB needed for the MVP) while
demonstrating the RAG pattern: retrieve -> cite -> generate.
"""
import glob
import os

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


def _parse_toc(text: str) -> tuple[str, list[str]]:
    """Extract the `# title` and ordered `## section` headings from a runbook."""
    title = ""
    sections: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not title and line.startswith("# "):
            title = line[2:].strip()
        elif line.startswith("## "):
            sections.append(line[3:].strip())
    return title, sections


class RunbookRAG:
    def __init__(self, path: str):
        self.docs: list[dict] = []
        self.toc: dict[str, dict] = {}  # source -> {"title": str, "sections": [str]}
        for fp in sorted(glob.glob(os.path.join(path, "*.md"))):
            text = open(fp, encoding="utf-8").read()
            source = os.path.basename(fp)
            title, sections = _parse_toc(text)
            self.toc[source] = {"title": title, "sections": sections}
            chunks = [c.strip() for c in text.split("\n## ") if c.strip()]
            for ch in chunks:
                self.docs.append(
                    {"source": source, "text": ch[:1200]}
                )
        if not self.docs:
            raise RuntimeError(f"No runbooks found in {path}")
        self.vec = TfidfVectorizer(stop_words="english", max_features=2000)
        self.mat = self.vec.fit_transform([d["text"] for d in self.docs])

    def search(self, query: str, k: int = 2) -> list[dict]:
        q = self.vec.transform([query])
        scores = (self.mat @ q.T).toarray().ravel()
        idx = np.argsort(scores)[::-1][:k]
        return [
            {
                "source": self.docs[i]["source"],
                "text": self.docs[i]["text"],
                "score": round(float(scores[i]), 3),
            }
            for i in idx
            if scores[i] > 0
        ]

    def section_headings(self, source: str, n: int = 3) -> list[str]:
        """Top n section headings of one runbook file (e.g. ["Symptoms", ...]).

        Used to build the incident response checklist from the cited runbooks.
        """
        return self.toc.get(source, {}).get("sections", [])[:n]

    def top_sources(self, query: str, k: int = 2) -> list[dict]:
        """Per-source best TF-IDF match scores, deduplicated by runbook file.

        A chunk-level search can return several chunks from the same file;
        this collapses them to one entry per runbook (keeping the best
        score) so the Q&A UI can show, e.g.,
        ``matched: null_surge.md (0.87)``.
        """
        best: dict[str, float] = {}
        for c in self.search(query, k=max(k * 3, 6)):
            best[c["source"]] = max(best.get(c["source"], 0.0), c["score"])
        ranked = sorted(best.items(), key=lambda kv: kv[1], reverse=True)[:k]
        return [{"source": s, "score": sc} for s, sc in ranked]
