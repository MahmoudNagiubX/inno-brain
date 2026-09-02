from datetime import date, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from innobrain.event.authoring import (
    AliasSource,
    BoothSource,
    DocumentSource,
    EventAuthoringBundle,
    EventSource,
    GlossaryTerm,
    LocationSource,
    SessionSource,
    SourceInventory,
    SpeakerSource,
    load_authoring_bundle,
)


def _event() -> EventSource:
    return EventSource(
        id="alpha",
        version="1.0.0",
        client_id="client-alpha",
        title="Alpha Event",
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 2),
        venue="Cairo Expo",
        timezone="Africa/Cairo",
        default_locale="ar-EG",
        documents=[
            DocumentSource(
                id="doc-guide",
                path="guide.md",
                title="Guide",
                language="en",
                authority_level="official",
                required=True,
            )
        ],
    )


def _bundle(**overrides: object) -> EventAuthoringBundle:
    payload: dict[str, object] = {
        "event": _event(),
        "locations": [LocationSource(id="hall-a", name="Hall A")],
        "speakers": [SpeakerSource(id="spk-a", name="Ahmed")],
        "sessions": [
            SessionSource(
                id="session-a",
                title="Opening",
                starts_at=datetime(2026, 10, 1, 10, 0, tzinfo=datetime.now().astimezone().tzinfo),
                ends_at=datetime(2026, 10, 1, 11, 0, tzinfo=datetime.now().astimezone().tzinfo),
                location_id="hall-a",
                speaker_ids=["spk-a"],
            )
        ],
        "booths": [BoothSource(id="booth-a", name="Alpha Booth", location_id="hall-a")],
        "aliases": [AliasSource(alias="the opening", entity_type="session", entity_id="session-a")],
        "glossary": [GlossaryTerm(term="AI", definition="Artificial intelligence")],
    }
    payload.update(overrides)
    return EventAuthoringBundle.model_validate(payload)


def test_valid_bundle_checks_references_and_timezone() -> None:
    bundle = _bundle()

    assert bundle.event.timezone == "Africa/Cairo"
    assert bundle.sessions[0].location_id == "hall-a"


@pytest.mark.parametrize(
    "timezone",
    ["Not/AZone", "", "UTC+2"],
)
def test_invalid_iana_timezone_is_rejected(timezone: str) -> None:
    with pytest.raises(ValidationError):
        EventSource.model_validate({**_event().model_dump(), "timezone": timezone})


def test_naive_session_timestamp_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SessionSource(
            id="session",
            title="Talk",
            starts_at=datetime(2026, 10, 1, 10),
            ends_at=datetime(2026, 10, 1, 11),
            location_id="hall-a",
        )


def test_session_start_must_precede_end() -> None:
    with pytest.raises(ValidationError):
        SessionSource(
            id="session",
            title="Talk",
            starts_at=datetime(2026, 10, 1, 11, tzinfo=datetime.now().astimezone().tzinfo),
            ends_at=datetime(2026, 10, 1, 10, tzinfo=datetime.now().astimezone().tzinfo),
            location_id="hall-a",
        )


def test_duplicate_ids_are_rejected() -> None:
    with pytest.raises(ValidationError):
        _bundle(
            locations=[
                LocationSource(id="hall-a", name="A"),
                LocationSource(id="hall-a", name="B"),
            ]
        )


def test_missing_session_location_is_rejected() -> None:
    session = _bundle().sessions[0].model_copy(update={"location_id": "missing"})
    with pytest.raises(ValidationError):
        _bundle(sessions=[session])


def test_missing_session_speaker_is_rejected() -> None:
    session = _bundle().sessions[0].model_copy(update={"speaker_ids": ["missing"]})
    with pytest.raises(ValidationError):
        _bundle(sessions=[session])


def test_missing_booth_location_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _bundle(booths=[BoothSource(id="booth", name="Booth", location_id="missing")])


def test_alias_must_reference_an_existing_entity() -> None:
    with pytest.raises(ValidationError):
        _bundle(aliases=[AliasSource(alias="unknown", entity_type="speaker", entity_id="missing")])


def test_aliases_must_be_unique() -> None:
    alias = AliasSource(alias="opening", entity_type="session", entity_id="session-a")
    with pytest.raises(ValidationError):
        _bundle(aliases=[alias, alias])


def test_location_overlap_is_rejected() -> None:
    second = SessionSource(
        id="session-b",
        title="Second",
        starts_at=datetime(2026, 10, 1, 10, 30, tzinfo=datetime.now().astimezone().tzinfo),
        ends_at=datetime(2026, 10, 1, 11, 30, tzinfo=datetime.now().astimezone().tzinfo),
        location_id="hall-a",
    )
    with pytest.raises(ValidationError):
        _bundle(sessions=[_bundle().sessions[0], second])


def test_speaker_double_booking_is_rejected() -> None:
    second = SessionSource(
        id="session-b",
        title="Second",
        starts_at=datetime(2026, 10, 1, 10, 30, tzinfo=datetime.now().astimezone().tzinfo),
        ends_at=datetime(2026, 10, 1, 11, 30, tzinfo=datetime.now().astimezone().tzinfo),
        location_id="hall-a",
        speaker_ids=["spk-a"],
    )
    with pytest.raises(ValidationError):
        _bundle(sessions=[_bundle().sessions[0], second])


def test_document_path_must_stay_below_source_root(tmp_path: Path) -> None:
    source_root = tmp_path / "authoring"
    source_root.mkdir()
    (source_root / "guide.md").write_text("guide", encoding="utf-8")
    event = _event().model_copy(
        update={
            "documents": [
                _event().documents[0].model_copy(update={"path": "../outside.md"}),
            ]
        }
    )
    with pytest.raises(ValidationError):
        EventAuthoringBundle(event=event, source_root=source_root)


def test_loader_reads_strict_files_and_builds_source_inventory(tmp_path: Path) -> None:
    root = tmp_path / "event"
    (root / "structured").mkdir(parents=True)
    (root / "guide.md").write_text("ALPHA-COMPASS", encoding="utf-8")
    (root / "structured" / "event.yaml").write_text(
        """
        id: alpha
        version: 1.0.0
        client_id: client-alpha
        title: Alpha Event
        start_date: 2026-10-01
        end_date: 2026-10-02
        venue: Cairo Expo
        timezone: Africa/Cairo
        default_locale: ar-EG
        documents:
          - id: doc-guide
            path: guide.md
            title: Guide
            language: en
            authority_level: official
            required: true
        """,
        encoding="utf-8",
    )
    for filename, value in {
        "locations.yaml": "- id: hall-a\n  name: Hall A\n",
        "speakers.yaml": "- id: spk-a\n  name: Ahmed\n",
        "sessions.yaml": (
            "- id: session-a\n  title: Opening\n  starts_at: 2026-10-01T10:00:00+02:00\n"
            "  ends_at: 2026-10-01T11:00:00+02:00\n  location_id: hall-a\n  speaker_ids: [spk-a]\n"
        ),
        "booths.yaml": "- id: booth-a\n  name: Alpha Booth\n  location_id: hall-a\n",
        "aliases.yaml": "- alias: opening\n  entity_type: session\n  entity_id: session-a\n",
        "glossary.yaml": "- term: AI\n  definition: Artificial intelligence\n",
    }.items():
        (root / "structured" / filename).write_text(value, encoding="utf-8")

    bundle, inventory = load_authoring_bundle(root)

    assert bundle.event.id == "alpha"
    assert isinstance(inventory, SourceInventory)
    assert inventory.files[0].relative_path == "guide.md"
    assert inventory.files[0].sha256
