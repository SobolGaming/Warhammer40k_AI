import pytest

from warhammer40k_ai.engine.presentation_envelope import (
    PRESENTATION_SCHEMA_VERSION,
    PresentationEnvelope,
)


def test_presentation_envelope_roundtrip() -> None:
    env = PresentationEnvelope(
        stream_id="match-1:player1",
        sequence_id=42,
        payload={"kind": "decision", "id": "d1"},
    )
    parsed = PresentationEnvelope.from_dict(env.to_dict())

    assert parsed.schema_version == PRESENTATION_SCHEMA_VERSION
    assert parsed.stream_id == "match-1:player1"
    assert parsed.sequence_id == 42
    assert parsed.payload == {"kind": "decision", "id": "d1"}


def test_presentation_envelope_accepts_minor_version_bumps() -> None:
    env = PresentationEnvelope(
        stream_id="s",
        sequence_id=0,
        payload={},
        schema_version="1.9",
    )

    assert env.schema_version == "1.9"


def test_presentation_envelope_rejects_incompatible_major_version() -> None:
    with pytest.raises(ValueError):
        PresentationEnvelope(
            stream_id="s",
            sequence_id=0,
            payload={},
            schema_version="2.0",
        )


def test_presentation_envelope_rejects_invalid_shape() -> None:
    with pytest.raises(ValueError):
        PresentationEnvelope(stream_id="", sequence_id=0, payload={})

    with pytest.raises(ValueError):
        PresentationEnvelope(stream_id="s", sequence_id=-1, payload={})

    with pytest.raises(ValueError):
        PresentationEnvelope.from_dict({"schema_version": "1.0", "stream_id": "s", "payload": {}})
