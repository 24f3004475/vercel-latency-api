
import json
import math
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_FILE = Path(__file__).parent / "q-vercel-latency.json"


def percentile(values, percent):
    values = sorted(values)

    if len(values) == 1:
        return values[0]

    position = (len(values) - 1) * percent / 100
    lower = math.floor(position)
    upper = math.ceil(position)

    return values[lower] + (
        values[upper] - values[lower]
    ) * (position - lower)


@app.post("/")
async def analyze(request: Request):
    body = await request.json()

    regions = body.get("regions", [])
    threshold = body.get("threshold_ms", 180)

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Could not load telemetry data"
        )

    # The sample file's structure must match this code.
    records = data if isinstance(data, list) else data.get("records", [])

    result = {}

    for region in regions:
        rows = [
            row for row in records
            if row.get("region", "").lower() == region.lower()
        ]

        if not rows:
            result[region] = {
                "avg_latency": None,
                "p95_latency": None,
                "avg_uptime": None,
                "breaches": 0
            }
            continue

        latencies = [
            float(row["latency_ms"]) for row in rows
        ]

        uptimes = [
            float(row["uptime_pct"]) for row in rows
        ]

        result[region] = {
            "avg_latency": sum(latencies) / len(latencies),
            "p95_latency": percentile(latencies, 95),
            "avg_uptime": sum(uptimes) / len(uptimes),
            "breaches": sum(
                latency > threshold for latency in latencies
            )
        }

    return result
