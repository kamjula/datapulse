"""CI failure analyzer: reads a CI log, suggests a root cause.

Same pattern as the incident narrator: retrieve first, answer second.
The log's error lines (plus tool/step lines, minus platform boilerplate)
are the query; the runbooks library is the knowledge base. Every
suggestion cites the runbook it came from, and if nothing in the log
matches a known pattern the analyzer abstains instead of guessing.
"""
import os
import re

from rag import RunbookRAG

BASE = os.path.dirname(os.path.abspath(__file__))
KB_PATH = os.path.join(BASE, "runbooks")

ABSTAIN = (
    "I couldn't match this log to any known CI failure pattern, "
    "so I won't guess. The error lines below are the place to start."
)

# lines that usually carry the actual failure signal in a CI log
SIGNAL = re.compile(
    r"(error|failed|failure|exception|traceback|killed|denied|forbidden|"
    r"unauthorized|timeout|timed out|cannot|no matching|not found|reformat)",
    re.IGNORECASE,
)

# GitHub Actions footer that ends almost every failed job; it says
# nothing about the cause, so it is stripped before matching
BOILERPLATE = re.compile(r"process completed with exit code", re.IGNORECASE)

# tool names worth keeping from step lines (e.g. "Run black --check .")
TOOL = re.compile(
    r"\b(black|flake8|ruff|eslint|prettier|mypy|pylint|docker|pip|npm|yarn|pytest)\b",
    re.IGNORECASE,
)

MAX_ERROR_LINES = 25


def extract_error_lines(log_text: str) -> list[str]:
    """Pull the signal lines out of a raw CI log, in order, deduped."""
    out: list[str] = []
    seen = set()
    for raw in log_text.splitlines():
        line = raw.strip()
        if not line or BOILERPLATE.search(line) or not SIGNAL.search(line):
            continue
        if line in seen:
            continue
        seen.add(line)
        out.append(line[:300])
        if len(out) >= MAX_ERROR_LINES:
            break
    return out


def _step_lines(log_text: str, errors: list[str]) -> list[str]:
    """Step/tool lines (e.g. 'Run black --check .') that name the tool."""
    out: list[str] = []
    for raw in log_text.splitlines():
        line = raw.strip()
        if not line or line in errors or BOILERPLATE.search(line):
            continue
        if TOOL.search(line) or line.lower().startswith("run "):
            out.append(line[:200])
    return out[:10]


def _diff_keywords(diff_text: str) -> list[str]:
    """File names touched by a PR diff, used to widen the query a bit."""
    files = re.findall(r"^\+\+\+ b/(.+)$", diff_text, re.MULTILINE)
    return files[:10]


def _section(doc_text: str, heading: str) -> str:
    """Text of one ## section from a runbook, '' if absent."""
    parts = doc_text.split("## ")
    for p in parts:
        if p.strip().lower().startswith(heading.lower()):
            body = p[len(heading):].strip(" :\n")
            return " ".join(body.split())[:600]
    return ""


def _full_text(rag: RunbookRAG, source: str) -> str:
    """Reassemble one runbook from its chunks (chunks split on '## ')."""
    parts = [d["text"] for d in rag.docs if d["source"] == source]
    return "\n## ".join(parts)


class CIFailureAnalyzer:
    def __init__(self, kb_path: str = KB_PATH):
        self.rag = RunbookRAG(kb_path)

    def analyze(self, log_text: str, diff_text: str = "") -> dict:
        errors = extract_error_lines(log_text)
        steps = _step_lines(log_text, errors)
        if not errors and not steps:
            return {
                "status": "abstain",
                "message": ABSTAIN,
                "error_lines": errors,
                "citations": [],
            }
        # error lines count double: they carry the failure signal,
        # step lines just name the tool that was running
        query = " ".join(errors + errors + steps)
        if diff_text:
            query += " " + " ".join(_diff_keywords(diff_text))
        hits = self.rag.search(query, k=6)
        if not hits:
            return {
                "status": "abstain",
                "message": ABSTAIN,
                "error_lines": errors,
                "citations": [],
            }
        top = hits[0]
        full = _full_text(self.rag, top["source"])
        return {
            "status": "ok",
            "category": top["source"].replace(".md", ""),
            "likely_cause": _section(full, "Likely cause"),
            "suggested_fix": _section(full, "Fix"),
            "error_lines": errors,
            "citations": [
                {"source": h["source"], "score": h["score"]} for h in hits[:2]
            ],
        }
