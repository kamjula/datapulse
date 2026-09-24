"""Root-cause narration: ML detects, GenAI explains.

Two modes:
  - "claude": calls the Claude API with incident context + retrieved runbook
    excerpts. Requires ANTHROPIC_API_KEY.
  - "template": deterministic, citation-grounded fallback so the demo and
    evals run with zero API cost. The UI always labels which mode produced
    the narration, so there is no ambiguity about what is LLM-generated.

Guardrail: if retrieval returns nothing relevant, the narrator abstains
instead of hallucinating ("not found in the runbooks").
"""
import os

METRIC_LABELS = {
    "rows": "row volume",
    "latency_sec": "pipeline latency",
    "null_rate": "null rate (data quality)",
    "freshness_min": "feed freshness",
    "schema_v": "schema version",
    "multivariate": "combined metrics",
}

ABSTAIN = (
    "I couldn't find anything relevant in the runbooks for this question, "
    "so I won't guess. Try asking about volume, latency, nulls, schema "
    "drift, or feed freshness."
)

AREA = {
    "volume_anomalies.md": "volume anomaly (spike or drop)",
    "latency_spike.md": "latency spike",
    "null_surge.md": "null-rate surge (data quality)",
    "schema_drift.md": "schema drift",
    "stale_feed.md": "stale feed (freshness breach)",
}


class Narrator:
    def __init__(self):
        self.key = os.environ.get("ANTHROPIC_API_KEY")
        self.mode = "claude" if self.key else "template"
        self._client = None

    # ------------------------------------------------------------------ API
    def narrate(self, incident: dict, citations: list[dict]) -> dict:
        """Returns {"text": ..., "mode": ..., "citations": [...]}."""
        if not citations:
            return {"text": ABSTAIN, "mode": self.mode, "citations": []}
        if self.mode == "claude":
            try:
                text = self._claude(incident, citations)
            except Exception as exc:  # fail safe: never break the demo
                text = self._template(incident, citations)
                return {
                    "text": text + f"\n\n_(Claude call failed ({exc}); template fallback used.)_",
                    "mode": "template",
                    "citations": [c["source"] for c in citations],
                }
        else:
            text = self._template(incident, citations)
        return {
            "text": text,
            "mode": self.mode,
            "citations": [c["source"] for c in citations],
        }

    def answer(self, question: str, citations: list[dict]) -> dict:
        if not citations:
            return {"text": ABSTAIN, "mode": self.mode, "citations": []}
        if self.mode == "claude":
            try:
                text = self._claude_qa(question, citations)
            except Exception as exc:
                text = self._template_qa(question, citations)
                return {
                    "text": text + f"\n\n_(Claude call failed ({exc}); template fallback used.)_",
                    "mode": "template",
                    "citations": [c["source"] for c in citations],
                }
        else:
            text = self._template_qa(question, citations)
        return {
            "text": text,
            "mode": self.mode,
            "citations": [c["source"] for c in citations],
        }

    # -------------------------------------------------------------- template
    def _template(self, incident: dict, citations: list[dict]) -> str:
        events = incident.get("events", [])
        snap = incident.get("snapshot", {})
        parts = []
        for e in events:
            label = METRIC_LABELS.get(e["metric"], e["metric"])
            detail = e.get("detail") or f"z={e.get('z')}"
            parts.append(
                f"- **{label}** flagged by {e['method']} ({detail}, "
                f"severity: {e['severity']})"
            )
        cites = " ".join(f"[{c['source']}]" for c in citations)
        area = AREA.get(citations[0]["source"], "pipeline anomaly")
        return (
            f"**Incident #{incident.get('id')}** at tick {snap.get('t')} "
            f"— initial diagnosis:\n\n"
            + "\n".join(parts)
            + f"\n\n**Probable cause area:** {area}.\n"
            f"**Suggested next step:** follow the checks in the cited "
            f"runbook section(s) before paging on-call.\n\nSources: {cites}"
        )

    def _template_qa(self, question: str, citations: list[dict]) -> str:
        # prefer a content chunk over a bare title chunk
        top = next(
            (c for c in citations if not c["text"].lstrip().startswith("# Runbook")),
            citations[0],
        )
        snippet = " ".join(top["text"].split())[:500]
        seen: list[str] = []
        for c in citations:
            if c["source"] not in seen:
                seen.append(c["source"])
        cites = " ".join(f"[{s}]" for s in seen)
        return f"Based on the runbooks: {snippet}...\n\nSources: {cites}"

    # ---------------------------------------------------------------- claude
    def _client_or_raise(self):
        if self._client is None:
            from anthropic import Anthropic

            self._client = Anthropic(api_key=self.key)
        return self._client

    def _claude(self, incident: dict, citations: list[dict]) -> str:
        context = "\n\n".join(
            f"[{c['source']}]\n{c['text']}" for c in citations
        )
        prompt = (
            "You are a data-reliability copilot. An ML anomaly detector "
            "flagged this incident:\n"
            f"{incident}\n\n"
            "Relevant runbook excerpts (cite them like [filename]):\n"
            f"{context}\n\n"
            "Write a concise root-cause analysis: what was flagged, the most "
            "probable cause area, and the single most useful next check. "
            "If the excerpts do not support an answer, say so explicitly "
            "instead of guessing."
        )
        resp = self._client_or_raise().messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text

    def _claude_qa(self, question: str, citations: list[dict]) -> str:
        context = "\n\n".join(
            f"[{c['source']}]\n{c['text']}" for c in citations
        )
        prompt = (
            "You are a data-reliability copilot answering from these runbook "
            f"excerpts (cite them like [filename]):\n{context}\n\n"
            f"Question: {question}\n\n"
            "Answer concisely. If the excerpts do not cover it, say so "
            "explicitly instead of guessing."
        )
        resp = self._client_or_raise().messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text
