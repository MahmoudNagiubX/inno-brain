from pathlib import Path

from innobrain.event.authoring import load_authoring_bundle

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_alpha_and_beta_fixtures_are_complete_and_isolated() -> None:
    alpha, alpha_inventory = load_authoring_bundle(
        REPOSITORY_ROOT / "fixtures" / "phase4" / "event_alpha"
    )
    beta, beta_inventory = load_authoring_bundle(
        REPOSITORY_ROOT / "fixtures" / "phase4" / "event_beta"
    )

    alpha_guide = (
        REPOSITORY_ROOT / "fixtures" / "phase4" / "event_alpha" / "documents" / "guide.md"
    )
    beta_guide = (
        REPOSITORY_ROOT / "fixtures" / "phase4" / "event_beta" / "documents" / "guide.md"
    )
    assert alpha.event.id == "event-alpha"
    assert beta.event.id == "event-beta"
    assert alpha_inventory.files[0].relative_path == "documents/guide.md"
    assert beta_inventory.files[0].relative_path == "documents/guide.md"
    assert "ALPHA-COMPASS" in alpha_guide.read_text(encoding="utf-8")
    assert "BETA-LANTERN" in beta_guide.read_text(encoding="utf-8")
    assert "BETA-LANTERN" not in alpha_guide.read_text(encoding="utf-8")
    assert "ALPHA-COMPASS" not in beta_guide.read_text(encoding="utf-8")
