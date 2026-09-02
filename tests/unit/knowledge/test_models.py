from dataclasses import FrozenInstanceError

import pytest

from innobrain.knowledge.models import Evidence, EvidencePack, EvidenceSource


def test_evidence_models_are_typed_and_immutable() -> None:
    evidence = Evidence("chunk-1", EvidenceSource.LEXICAL, "fact", 0.5, {"kind": "doc"})
    pack = EvidencePack("query", (evidence,))

    assert pack.evidence[0].source is EvidenceSource.LEXICAL
    with pytest.raises(FrozenInstanceError):
        evidence.text = "changed"  # type: ignore[misc]
