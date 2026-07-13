def serialize_result_point(point) -> dict:
    return {
        "x": point.p.x,
        "y": point.p.y,
        "z": point.p.z,
        "branch_id": point.branch_id,
        "cost": point.cost,
        "equivalent_radius": point.equivalent_radius,
        "vadose_flag": point.vadose_flag,
    }


def serialize_result_segment(segment) -> dict:
    return {
        "start": serialize_result_point(segment.start),
        "end": serialize_result_point(segment.end),
    }


def serialize_karstnsim_result(result) -> dict:
    return {
        "segments": [serialize_result_segment(segment) for segment in result.segments]
    }
