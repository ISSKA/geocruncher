def serialize_result_point(point) -> dict:
    return {
        "x": point.p.x,
        "y": point.p.y,
        "z": point.p.z,
        "branchId": point.branch_id,
        "cost": point.cost,
        "equivalentRadius": point.equivalent_radius,
        "vadoseFlag": point.vadose_flag,
    }


def serialize_result_segment(segment) -> dict:
    return {
        "start": serialize_result_point(segment.start),
        "end": serialize_result_point(segment.end),
    }


def serialize_karstnsim_result(result) -> list[dict]:
    return [serialize_result_segment(segment) for segment in result.segments]
