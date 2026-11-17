"""Export Redis profiler records to CSV for training."""

import argparse
import csv
import os
import re
from datetime import datetime
from numbers import Number
from pathlib import Path

import redis
from redis.exceptions import ResponseError

from .common import FEATURES


def _start_time_ms(value):
    if isinstance(value, (int, float)):
        return int(value)
    return int(datetime.fromisoformat(value).timestamp() * 1000)


def _profile_version(key):
    match = re.search(r":v(\d+)$", key.decode() if isinstance(key, bytes) else key)
    return int(match.group(1)) if match else ""


def _exportable_metadata(metadata):
    return {
        name: value
        for name, value in metadata.items()
        if name != "start_time"
        and (value is None or isinstance(value, (Number, str, bool)))
    }


def export(redis_client, output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for computation_type, features in FEATURES.items():
        records = []
        for key in redis_client.scan_iter(f"profiling:{computation_type}:v*"):
            try:
                profiles = redis_client.json().get(key) or []
            except ResponseError:
                continue
            records.extend((_profile_version(key), record) for record in profiles)
        if not records:
            continue

        rows = []
        step_names = set()
        for profile_version, record in records:
            metadata = record.get("metadata", {})
            steps = record.get("steps", {})
            if "start_time" not in metadata or not steps:
                continue
            row = {
                "start_time": _start_time_ms(metadata["start_time"]),
                "profile_version": profile_version,
                "Total Computation Time": sum(float(value) for value in steps.values()),
            }
            step_values = {
                f"step_{re.sub(r'[^A-Za-z0-9_]+', '_', name)}_ms": float(value)
                for name, value in steps.items()
            }
            step_names.update(step_values)
            row.update(step_values)
            row.update(_exportable_metadata(metadata))
            rows.append(row)

        if not rows:
            continue
        step_columns = sorted(step_names)
        base_columns = [
            "start_time",
            "project_id",
            "profile_version",
            "Total Computation Time",
        ]
        feature_columns = sorted(
            {
                column
                for row in rows
                for column in row
                if column not in base_columns and not column.startswith("step_")
            }
        )
        columns = (
            [column for column in base_columns if any(column in row for row in rows)]
            + feature_columns
            + step_columns
        )
        for row in rows:
            for column in columns:
                row.setdefault(column, "")
        path = output_dir / f"{computation_type}.csv"
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        written += len(rows)
        print(f"{computation_type}: exported {len(rows)} rows to {path}")
    return written


def export_from_config(output_dir: Path) -> int:
    """Export profiler records using the service's Redis configuration."""
    client = redis.Redis(
        host=os.environ["REDIS_HOST"],
        port=int(os.environ.get("REDIS_PORT", "6379")),
        db=int(os.environ.get("REDIS_DB", "3")),
        decode_responses=True,
    )
    return export(client, output_dir)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir", type=Path, default=Path("geocruncher/profiler/data")
    )
    parser.add_argument("--redis-host", default="localhost")
    parser.add_argument("--redis-port", type=int, default=6379)
    parser.add_argument("--redis-db", type=int, default=3)
    args = parser.parse_args()
    client = redis.Redis(
        host=args.redis_host,
        port=args.redis_port,
        db=args.redis_db,
        decode_responses=True,
    )
    export(client, args.output_dir)


if __name__ == "__main__":
    main()
