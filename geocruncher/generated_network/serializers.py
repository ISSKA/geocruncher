import numpy as np


def compute_cost_threshold(segments) -> float | None:
    costs = [segment.start.cost for segment in segments]

    if not costs:
        return None

    return float(np.percentile(costs, 99))


def serialize_result_point(point, cost_threshold: float | None) -> dict:
    cost = point.cost

    return {
        "x": point.p.x,
        "y": point.p.y,
        "z": point.p.z,
        "branchId": point.branch_id,
        "isHighCost": (
            cost >= cost_threshold
            if cost is not None and cost_threshold is not None
            else False
        ),
        "equivalentRadius": point.equivalent_radius,
        # 1 = vadose, 0 = phreatic, negative = no data
        # vadose_flags is a list of flags for each water table
        # as a ponts should only be considered phreatic for one water table, any flag at 0 means the point is phreatic, otherwise it is vadose
        "vadoseFlag": not any(flag == 0 for flag in point.vadose_flags),
    }


def serialize_result_segment(segment, cost_threshold: float | None) -> dict:
    return {
        "start": serialize_result_point(segment.start, cost_threshold),
        "end": serialize_result_point(segment.end, cost_threshold),
    }


def serialize_karstnsim_result(result) -> list[dict]:
    cost_threshold = compute_cost_threshold(result.segments)

    return [
        serialize_result_segment(segment, cost_threshold) for segment in result.segments
    ]
