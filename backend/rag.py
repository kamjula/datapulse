"""Tiny TF-IDF retrieval over the runbook library.

Keeps the project dependency-light (no vector DB needed for the MVP) while
demonstrating the RAG pattern: retrieve -> cite -> generate.
"""
import glob
import os

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


class RunbookRAG:
    def __init__(self, path: str):
        self.docs: list[dict] = []
        for fp in sorted(glob.glob(os.path.join(path, "*.md"))):
            text = open(fp, encoding="utf-8").read()
            chunks = [c.strip() for c in text.split("\n## ") if c.strip()]
            for ch in chunks:
                self.docs.append(
                    {"source": os.path.basename(fp), "text": ch[:1200]}
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
