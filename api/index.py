
import json
import math
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)

# Keep the JSON dataset inside the api folder
DATA_FILE = Path(__file__).parent / "q-vercel-latency.json"


def percentile_95(values):
    values = sorted(values)
    position = 0.95 * (len(values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)

    return values[lower] + (
        values[upper] - values[lower]
    ) * (position - lower)


@app.post("/")
async def analyse(request: Request):
    try:
        body = await request.json()
        regions = body["regions"]
        threshold = float(body["threshold_ms"])

        with open(DATA_FILE, "r", encoding="utf-8") as file:
            records = json.load(file)

        results = {}

        for region in regions:
            selected = [
                row for row in records
                if row["region"].lower() == region.lower()
            ]

            if not selected:
                raise HTTPException(
                    status_code=404,
                    detail=f"No records found for {region}"
                )

            latencies = [
                float(row["latency_ms"]) for row in selected
            ]
            uptimes = [
                float(row["uptime_pct"]) for row in selected
            ]

            results[region] = {
                "avg_latency": sum(latencies) / len(latencies),
                "p95_latency": percentile_95(latencies),
                "avg_uptime": sum(uptimes) / len(uptimes),
                "breaches": sum(
                    value > threshold for value in latencies
                ),
            }

        return results

    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error))
