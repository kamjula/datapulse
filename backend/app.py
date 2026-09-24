"""DataPulse API + live simulation loop.

Run:  .venv/bin/uvicorn backend.app:app --host 0.0.0.0 --port 8000
Then open http://localhost:8000
"""
import os
import threading
import time

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.simulator import PipelineSimulator, INJECTABLE
from backend.detector import AnomalyDetector, FEATURES
from backend.rag import RunbookRAG
from backend.narrator import Narrator

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sim = PipelineSimulator(seed=7)
det = AnomalyDetector()
rag = RunbookRAG(os.path.join(BASE, "runbooks"))
narrator = Narrator()

incidents: list[dict] = []
current: dict | None = None
lock = threading.Lock()
INCIDENT_GAP = 40  # ticks; events within this window belong to one incident


def _summarize_events(events: list[dict]) -> str:
    return " ".join(e["metric"] for e in events) + " data pipeline anomaly"


def simulation_loop():
    global current
    while True:
        tick = sim.step()
        events = det.update(tick)
        with lock:
            if events:
                if current is None or tick.t - current["start_t"] > INCIDENT_GAP:
                    current = {
                        "id": len(incidents) + 1,
                        "start_t": tick.t,
                        "events": [],
                        "snapshot": None,
                        "narration": None,
                        "citations": [],
                    }
                    incidents.append(current)
                current["events"].extend(events)
                current["snapshot"] = tick.to_dict()
                if current["narration"] is None:
                    cits = rag.search(_summarize_events(events))
                    current["citations"] = [c["source"] for c in cits]
                    current["narration"] = narrator.narrate(current, cits)
        time.sleep(1)


app = FastAPI(title="DataPulse")


class AskBody(BaseModel):
    question: str


@app.on_event("startup")
def startup():
    threading.Thread(target=simulation_loop, daemon=True).start()


@app.get("/")
def index():
    return FileResponse(os.path.join(BASE, "frontend", "index.html"))


@app.get("/api/status")
def status():
    with lock:
        n_inc = len(incidents)
    return {
        "tick": sim.t,
        "warmed_up": det.warmed_up,
        "narrator_mode": narrator.mode,
        "incidents": n_inc,
        "injectable": INJECTABLE,
    }


@app.get("/api/series")
def series(metric: str = "rows", n: int = 120):
    if metric not in FEATURES + ["freshness_min", "schema_v"]:
        metric = "rows"
    hist = list(sim.history)[-n:]
    return {
        "metric": metric,
        "points": [
            {"t": tk.t, "v": getattr(tk, metric), "injected": tk.injected}
            for tk in hist
        ],
    }


@app.get("/api/incidents")
def get_incidents():
    with lock:
        return {"incidents": list(reversed(incidents[-10:]))}


@app.post("/api/inject/{kind}")
def inject(kind: str):
    ok = sim.inject(kind)
    return {"ok": ok, "kind": kind}


@app.post("/api/ask")
def ask(body: AskBody):
    cits = rag.search(body.question, k=2)
    return narrator.answer(body.question, cits)
