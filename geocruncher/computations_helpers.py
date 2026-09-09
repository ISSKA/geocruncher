from forgeo.gmlib.GeologicalModel3D import GeologicalModel

RANK_SKY = 0


def rank_to_unit_uuid(model: GeologicalModel, rank: int) -> str | None:
    if rank == RANK_SKY:
        return None

    unit_index = rank - 1

    if model.pile.reference == "base" and unit_index == 0:
        # dummy
        unit_index = len(model.formations) - 1
    elif model.pile.reference == "base":
        unit_index -= 1

    return model.formations[unit_index].name
