from uuid import uuid4

import pytest
from isska.geocruncher.v1 import project_pb as project_proto

from geocruncher.geological_model_input import (
    GeologicalModelValidationError,
    deserialize_geological_model,
    parse_geological_model,
    validate_geological_model,
)


def point(x=1.0, y=2.0, z=3.0):
    return project_proto.Point3(x=x, y=y, z=z)


def orientation():
    return project_proto.Orientation(
        position=point(), normal=project_proto.Vector3(x=0.0, y=0.0, z=1.0)
    )


def valid_model():
    fault_uuid = str(uuid4())
    return project_proto.GeologicalModel(
        stratigraphy=project_proto.StratigraphicColumn(
            reference=project_proto.StratigraphicReference.BASE,
            series=[
                project_proto.Series(
                    uuid=str(uuid4()),
                    relation=project_proto.SeriesRelation.ONLAP,
                    units=[
                        project_proto.Unit(
                            uuid=str(uuid4()),
                            contact_points=[point()],
                            orientations=[orientation()],
                        )
                    ],
                    influenced_by_faults=[fault_uuid],
                )
            ],
        ),
        faults=[
            project_proto.Fault(
                uuid=fault_uuid,
                contact_points=[point()],
                orientations=[orientation()],
                finite=project_proto.FiniteFault(
                    lateral_extent=10.0,
                    vertical_extent=20.0,
                    influence_radius=30.0,
                ),
            )
        ],
    )


def test_validates_generated_message_without_modifying_it():
    message = valid_model()
    serialized = message.to_binary()

    assert validate_geological_model(message) is None
    assert message.to_binary() == serialized


def test_parses_binary_payload_to_generated_message():
    message = valid_model()

    parsed = parse_geological_model(message.to_binary())

    assert isinstance(parsed, project_proto.GeologicalModel)
    assert parsed == message
    assert parsed is not message


def test_parse_applies_semantic_validation():
    message = valid_model()
    message.clear_field("stratigraphy")

    with pytest.raises(
        GeologicalModelValidationError, match="stratigraphy: is required"
    ):
        parse_geological_model(message.to_binary())


def test_deserialize_does_not_apply_semantic_validation():
    message = valid_model()
    message.clear_field("stratigraphy")

    deserialized = deserialize_geological_model(message.to_binary())

    assert not deserialized.has_field("stratigraphy")


def test_deserialize_still_rejects_malformed_wire_data():
    with pytest.raises(
        GeologicalModelValidationError, match="invalid GeologicalModel protobuf"
    ):
        deserialize_geological_model(b"not a protobuf model")


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda model: model.clear_field("stratigraphy"), "stratigraphy: is required"),
        (
            lambda model: setattr(
                model.stratigraphy,
                "reference",
                project_proto.StratigraphicReference.UNSPECIFIED,
            ),
            "stratigraphy.reference",
        ),
        (
            lambda model: setattr(
                model.stratigraphy.series[0],
                "relation",
                project_proto.SeriesRelation.UNSPECIFIED,
            ),
            r"series\[0\].relation",
        ),
        (
            lambda model: setattr(model.stratigraphy.series[0], "uuid", "not-a-uuid"),
            "must be a valid UUID",
        ),
        (
            lambda model: setattr(
                model.stratigraphy.series[0].units[0],
                "uuid",
                model.stratigraphy.series[0].uuid,
            ),
            "duplicate entity UUID",
        ),
        (
            lambda model: setattr(
                model.stratigraphy.series[0].units[0].contact_points[0],
                "x",
                float("nan"),
            ),
            "must be finite",
        ),
        (
            lambda model: (
                model.stratigraphy.series[0]
                .units[0]
                .orientations[0]
                .clear_field("position")
            ),
            "position: is required",
        ),
        (
            lambda model: setattr(
                model.stratigraphy.series[0].units[0].orientations[0],
                "normal",
                project_proto.Vector3(),
            ),
            "normal: must have unit length",
        ),
        (
            lambda model: setattr(
                model.stratigraphy.series[0].units[0].orientations[0],
                "normal",
                project_proto.Vector3(x=0.0, y=0.0, z=1.01),
            ),
            "normal: must have unit length",
        ),
        (
            lambda model: setattr(model.faults[0].finite, "vertical_extent", 0.0),
            "vertical_extent: must be positive",
        ),
        (lambda model: model.faults[0].contact_points.clear(), "contact_points"),
        (lambda model: model.faults[0].orientations.clear(), "orientations"),
        (
            lambda model: model.faults[0].stops_on.append(str(uuid4())),
            "references unknown fault UUID",
        ),
        (
            lambda model: model.faults[0].stops_on.append(model.faults[0].uuid),
            "must not reference the owning fault",
        ),
    ],
)
def test_rejects_invalid_models(mutate, match):
    model = valid_model()
    mutate(model)

    with pytest.raises(GeologicalModelValidationError, match=match):
        validate_geological_model(model)


def test_rejects_fault_stop_cycles():
    model = valid_model()
    second_fault_uuid = str(uuid4())
    model.faults[0].stops_on.append(second_fault_uuid)
    model.faults.append(
        project_proto.Fault(
            uuid=second_fault_uuid,
            contact_points=[point()],
            orientations=[orientation()],
            stops_on=[model.faults[0].uuid],
        )
    )

    with pytest.raises(GeologicalModelValidationError, match="contains a cycle"):
        validate_geological_model(model)


def test_accepts_small_orientation_normal_rounding_error():
    model = valid_model()
    model.stratigraphy.series[0].units[0].orientations[
        0
    ].normal = project_proto.Vector3(x=0.0, y=0.0, z=1.0009)

    assert validate_geological_model(model) is None
