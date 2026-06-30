import json
from datetime import datetime

from pykarstnsim.models import KarstNSimResult

from geocruncher.computations import Vec3Int
from geocruncher.karstnsim.models import SimulationParameters


def serialize_output(
    result: KarstNSimResult,
    params: SimulationParameters,
    compute_resolution: Vec3Int,
    runtime_s: float,
) -> bytes:
    lines = ["# Run info"]
    lines.append(
        json.dumps(
            {
                "metadata": {
                    "generationTime": datetime.now().isoformat(),
                    "generationDurationS": runtime_s,
                    "computeResolution": {
                        "x": compute_resolution["x"],
                        "y": compute_resolution["y"],
                        "z": compute_resolution["z"],
                    },
                },
                "config": params.model_dump(by_alias=True),
            },
            indent=2,
        )
    )
    lines.append("# Data")
    lines.append(result.to_string())
    return "\n".join(lines).encode("utf-8")
