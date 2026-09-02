# InnoBrain Phase 4 Report

Date: 2026-09-02
Branch: `phase/4-dynamic-event-package`
Base: Phase 3 HEAD `3e8d65c078dc6e4bd7ee78d6a4177fc9416de097`
Status: `PHASE_4_COMPLETE`

## Delivered

- Strict local structured authoring and self-contained `.innoevent` archives.
- Canonical manifest hashing, SHA-256 payload integrity and Ed25519 signatures.
- Safe ZIP validation/extraction with traversal, symlink, collision, encryption,
  compression and quota defenses before extraction.
- Builder-only `docling==2.124.0`; Docling and its PyTorch dependencies remain
  outside the normal runtime `.venv`.
- E5-aligned hard 384-token chunking with provenance and portable little-endian
  float32 384-dimensional matrices.
- Target-local SQLite/FTS5/sqlite-vec compilation with sqlite-vec `0.1.9`,
  read-only installed databases, health checks and preserved source archives.
- Registry identity checks, atomic activation, busy guards, rollback and
  zero-leak event switching with session-memory reset.
- Optional package-only HTTPS distribution with host allowlisting and a 512 MiB
  streaming limit. No live document URL ingestion was added.

## Actual validation

The bounded E5 prefetch succeeded and produced the pinned
`intfloat/multilingual-e5-small` revision `614241f` ONNX model and tokenizer.
The isolated builder environment installed `docling==2.124.0` and ran the real
Docling conversion path. The real production-like smoke built and signed Alpha
and Beta packages, verified and installed them, rebuilt target-local indexes,
ran exact and RAG queries, switched without cross-event leakage, reset memory,
and rolled back successfully:

```text
alpha_exact_rows=1
alpha_rag_rows=1
beta_exact_rows=1
beta_alpha_leak_rows=0
rollback_event=event-alpha
```

The Phase 4 security matrix passed with `85 passed, 1 skipped`; the skip is the
normal-runtime optional Docling test because Docling is intentionally absent
from `.venv`. Full project verification passed with `148 passed, 2 skipped`.
The second skip is the opt-in duplicate real-E5 integration test; the real E5
smoke above is the production-like evidence. Ruff passed for `src`, `tests` and
`scripts`; `git diff --check` passed; runtime import confirmed Docling was not
loaded; generated packages/runtime artifacts were not tracked.

The smoke signing key was generated under ignored `artifacts/phase4/keys/` and
was test-only. No private key is stored in Git. Prior Phase 1-3 human/audio and
provider/Pi/S330 deferred validation debt remains preserved and is not promoted
by this package phase.

## Authorization boundary

The automated security, isolation, package, target-local database, switching,
rollback and real builder smoke gates passed. Phase 5 is authorized, but no
Phase 5 implementation was started on this branch.
