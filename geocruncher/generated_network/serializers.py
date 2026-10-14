import logging

import numpy as np


def serialize_result_point(point) -> dict:
    if point.cost is not None and np.isnan(point.cost):
        logging.warning(
            f"Point cost is NaN for point {point.p.x}, {point.p.y}, {point.p.z}. Setting cost to None."
        )
        point.cost = None
    return {
        "x": point.p.x,
        "y": point.p.y,
        "z": point.p.z,
        "branchId": point.branch_id,
        "cost": point.cost,
        "equivalentRadius": point.equivalent_radius,
        # 1 = vadose, 0 = phreatic, negative = no data
        # vadose_flags is a list of flags for each water table
        # as a ponts should only be considered phreatic for one water table, any flag at 0 means the point is phreatic, otherwise it is vadose
        "vadoseFlag": not any(flag == 0 for flag in point.vadose_flags),
    }


def serialize_result_segment(segment) -> dict:
    return {
        "start": serialize_result_point(segment.start),
        "end": serialize_result_point(segment.end),
    }


def serialize_karstnsim_result(result) -> list[dict]:
    return [serialize_result_segment(segment) for segment in result.segments]
