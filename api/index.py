
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

DATA_FILE = Path(__file__).resolve().parent.parent / "q-vercel-latency.json"


def load_records():
    with open(DATA_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, list):
        return data

    for key in ("data", "records", "telemetry"):
        if isinstance(data, dict) and isinstance(data.get(key), list):
            return data[key]

    raise ValueError("Could not find the telemetry records list")


def get_value(record, possible_names):
    for name in possible_names:
        if name in record:
            return record[name]
    raise ValueError("Missing field: " + possible_names[0])


def percentile_95(values):
    values = sorted(values)

    if len(values) == 1:
        return values[0]

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

        if not isinstance(regions, list):
            raise ValueError("'regions' must be a list")

        records = load_records()
        results = {}

        for region in regions:
            selected = [
                row for row in records
                if str(get_value(row, ["region"])).lower()
                == str(region).lower()
            ]

            if not selected:
                raise HTTPException(
                    status_code=404,
                    detail=f"No records found for {region}"
                )

            latencies = [
                float(get_value(row, [
                    "latency_ms", "latency", "response_time_ms"
                ]))
                for row in selected
            ]

            uptimes = [
                float(get_value(row, [
                    "uptime", "uptime_percent", "uptime_pct"
                ]))
                for row in selected
            ]

            results[region] = {
                "avg_latency": sum(latencies) / len(latencies),
                "p95_latency": percentile_95(latencies),
                "avg_uptime": sum(uptimes) / len(uptimes),
                "breaches": sum(
                    latency > threshold for latency in latencies
                ),
            }

        return results

    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )