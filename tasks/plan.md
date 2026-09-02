# Phase 4 Dynamic Event Packages Implementation Plan

> **For agentic workers:** execute the numbered tasks in order, keeping each task testable and committed before the next task.

**Goal:** Build, verify, install, activate, switch, and roll back self-contained signed `.innoevent` packages without changing application code.

**Architecture:** An off-device builder validates strict local authoring data, parses local documents, chunks content to a hard 384-token E5 payload budget, creates portable real-E5 embeddings, hashes payloads, and signs a deterministic manifest. The target runtime treats the archive as untrusted, verifies it before extraction, rebuilds SQLite/FTS5/sqlite-vec locally, stores immutable read-only installed databases, and atomically switches an isolated active context with session-memory reset.

**Tech Stack:** Python `>=3.11,<3.15`, Pydantic/PyYAML, SQLite/FTS5, `sqlite-vec==0.1.9`, ONNX Runtime E5, `cryptography==50.0.1`, pytest/Ruff, builder-only `docling==2.124.0`.

**Spec:** `PHASE4_DESIGN_SPEC.md`, `CODEX_PHASE4_DYNAMIC_EVENT_PACKAGE.md`, and `MASTER_PLAN.md` v1.12.

## Capability map and order

| Capability | Responsibility | Depends on |
|---|---|---|
| package-contract | strict authoring, manifest, crypto and archive boundaries | Phase 3 models/config |
| builder | local parsing, 384-token chunking, portable embeddings and deterministic package output | package-contract |
| target-install | verification, target-local DB compilation, registry and health | package-contract, Phase 3 knowledge |
| activation | atomic active pointer, runtime context, memory reset and rollback | target-install |
| distribution | allowlisted complete-package HTTPS fetch | package-contract |
| evaluation | fixtures, security matrix, isolation, smoke and reports | all preceding capabilities |

Build order: package-contract -> builder -> target-install -> activation/distribution -> evaluation.

## Global constraints

- Branch only from Phase 3 HEAD `3e8d65c078dc6e4bd7ee78d6a4177fc9416de097`.
- Keep `.innoevent` self-contained; never ingest arbitrary live document URLs.
- Keep `docling==2.124.0` in a separate builder environment; Docling and PyTorch must not enter the normal runtime environment.
- Production packages require real `intfloat/multilingual-e5-small` embeddings, trusted Ed25519 signatures, and `deployable=true`.
- Test/synthetic embeddings always force `deployable=false` and never substitute for production validation.
- Rebuild `sqlite-vec` `vec_chunks` on the target; installed DBs are immutable/read-only.
- Verify all archive structure, quotas, hashes, signatures and schema before extraction/install.
- Unknown declared namespaced extensions are preserved but never executed.
- Event switching resets session memory; failed activation leaves the prior active pointer untouched.
- Do not add Phase 5 navigation/ROS work, merge automatically, or claim real-asset validation when it is unavailable.

## Task list

### Task 0: Safety preflight and branch

Verify clean status, fetch `origin`, fast-forward `phase/3-speech-brain-rag`, confirm the required base SHA, then create `phase/4-dynamic-event-package`. Stop on dirty status or an incomplete Phase 3 state.

Verify: `git status --short`, Phase 3 state markers, exact `git rev-parse HEAD`, and branch ancestry.

### Task 1: Sync Phase 4 architecture documents

Copy the three supplied documents into the repository, preserve Phase 3 v1.11 facts, update `MASTER_PLAN.md` to v1.12, and create `docs/phase4/PHASE4_STATE.md` with the required in-progress state.

Verify: v1.12 markers, `.innoevent`, `docling==2.124.0`, state file, and `git diff --check`.

### Task 2: Runtime configuration and builder isolation

Add the exact `EventPackageRuntimeConfig` limits and runtime YAML section; add `cryptography==50.0.1` to runtime dependencies and a separate `event-builder` extra containing only `docling==2.124.0`; add the trusted-key example. Test config defaults and ensure Docling is not in main dependencies.

Verify: focused config tests, dependency metadata inspection, and normal `.venv` import checks.

### Task 3: Strict manifest contract

Implement typed event package errors and Pydantic manifest/file/embedding/signature models with forbidden extras, strict package/event/build/hash/path/version validation, and canonical newline-terminated JSON serialization.

Verify: focused valid/invalid model tests and byte-stability independent of input mapping order.

### Task 4: Strict authoring schema

Implement typed structured event, location, speaker, session, booth, alias, glossary and document sources. Validate IANA timezone, offset-aware bounds, unique IDs, foreign keys, local source containment, overlaps, double-booking and aliases without correction.

Verify: one explicit test per failure mode plus a valid bundle.

### Task 5: Two local event fixtures

Create complete Alpha and Beta authoring trees with different IDs, schedules, speakers, booths, aliases, glossary rows and local Markdown source files. Keep `ALPHA-COMPASS` and `BETA-LANTERN` as exclusive leakage sentinels and document the authoring layout.

Verify: both fixtures load through the strict authoring loader and source inventories contain only local files.

### Task 6: Ed25519 signatures and trusted keys

Sign and verify exact canonical manifest bytes using `cryptography` Ed25519. Support `algorithm`, `key_id`, and base64 signature metadata; reject changed manifests, wrong keys and unknown key IDs without storing private keys.

Verify: ephemeral in-memory key tests for valid, changed, wrong-key and unknown-key cases.

### Task 7: Deterministic safe archives

Write deterministic ZIP archives with fixed timestamps, sorted UTF-8 members, stable permissions and manifest/signature ordering. Validate traversal, absolute/drive/backslash paths, symlinks, duplicates, Unicode/casefold collisions, encryption, undeclared members, compression and all four quotas; extract only validated members below staging.

Verify: programmatically constructed malicious archives and byte-identical repeated writes.

### Task 8: Full package verification

Implement ordered archive, manifest, compatibility, signature policy, payload-set, size and SHA-256 checks, extracting only after all checks. Permit unsigned packages only in an explicitly enabled non-production environment; require trusted signatures and deployability in production.

Verify: payload/manifest/signature tamper, unsigned production, non-deployable production, untrusted signer and valid development package tests.

### Task 9: Knowledge schema v2 metadata

Upgrade event/document/chunk metadata for `event_version`, `client_id`, language, authority and validity fields; set new DB schema version 2 while preserving Phase 3 fixture defaults. Add validity-aware lexical filtering when a reference time is provided.

Verify: schema/repository tests and the complete Phase 3 suite.

### Task 10: Read-only DB and existing VectorStore

Add `connect_event_db(path, readonly=False)` with SQLite `mode=ro` and no write PRAGMAs in read-only mode. Add `VectorStore(..., create_if_missing=False)` to verify and query existing vec tables without creating or committing them.

Verify: write rejection, read-only FTS/vector search and existing Phase 3 vector tests.

### Task 11: Separate builder asset prefetch

Add bounded E5 prefetch and optional Docling model prefetch reporting, separate `.venv-event-builder` setup guidance, and ignore builder/runtime/generated artifacts. Never install builder dependencies into `.venv`.

Verify: script help/negative-path behavior, ignore rules, and runtime dependency scan.

### Task 12: Lazy Docling parser

Implement local UTF-8 TXT parsing plus lazy `DocumentConverter` adaptation for supported local formats. Configure local/offline PDF processing, disable remote services/plugins and external HTML resources, and reject URLs. Keep runtime importable without Docling.

Verify: fake converter unit tests, no-Docling runtime import test, and optional local Docling conversion when installed.

### Task 13: E5-aligned structure-aware chunking

Create canonical chunk records retaining headings/page provenance and all retrieval metadata. Use structure-aware parsed content, merge peers, split oversized paragraphs/sentences/token boundaries in order, and hard-check at most 384 E5 tokenizer tokens with no silent truncation or loss.

Verify: token-cap, order/no-loss, provenance and oversized-content tests.

### Task 14: Portable embedding matrix

Build little-endian float32 `(N, 384)` matrices through the existing real E5 passage provider for production, save/load with `allow_pickle=False`, and isolate deterministic providers to tests with `deployable=false` enforcement.

Verify: dtype/shape/finite/unit-norm checks, safe load, row mapping and production-profile rejection of synthetic vectors.

### Task 15: Deterministic build identity/reporting

Compute build IDs from normalized authoring data, sorted source hashes, builder/chunk/E5 identity and no wall-clock data. Record source, parse, structured, chunk, embedding, dependency, warning/error and duration facts in a JSON report.

Verify: identical inputs produce identical IDs and a one-byte source change changes the ID.

### Task 16: Full package builder and CLI

Implement load -> inventory -> parse -> chunk -> embed -> artifacts -> report -> manifest -> optional signature -> deterministic archive -> self-verification. Require explicit unsigned development mode; require real E5, parse success, signing key and valid shape for production. Add `eventctl build` with builder-dependency setup guidance.

Verify: integration build of both fixtures with deterministic test embeddings, valid package verification, and production failure tests.

### Task 17: Target-local installer

Stage under `runtime_data/events/.staging/<id>`, load structured/chunks/embeddings, create target-local SQLite/FTS5/vec data, enforce equal chunk/FTS/vector/embedding row counts, health-check read-only reopen, atomically place the installed version/build, and preserve `source.innoevent` without overwriting another build.

Verify: install integration tests, target-local vector rebuild and immutable DB health.

### Task 18: Registry and health

Derive installed candidates from the filesystem but verify each identity against its manifest/install report. Expose event/version/build/root/DB/health records and compare validated semantic versions as integer tuples.

Verify: directory-name spoofing, malformed records, health and version ordering tests.

### Task 19: Atomic activation and rollback

Add idle-guard and activation hooks. Activate only healthy candidates, reject busy runtime and normal same-event downgrade, atomically fsync/replace the pointer, append history, reset context hooks, and implement explicit previous-build rollback with revalidation.

Verify: busy/downgrade rejection, successful activation, failed-candidate pointer preservation and explicit rollback.

### Task 20: Active runtime context

Create read-only active contexts containing installed record, connection, repository and open-existing VectorStore. Close old contexts before opening new ones and wire activation hooks to `SessionMemory.reset` plus context replacement.

Verify: lifecycle and memory-reset integration tests.

### Task 21: Two-event zero-leakage E2E

Build/install Alpha and Beta development packages, activate/switch/rollback them, query exact and RAG evidence, assert each sentinel is absent from the other event and assert memory is empty after switching.

Verify: mandatory `tests/e2e/event/test_event_switch_no_leak.py`.

### Task 22: Allowlisted HTTPS package distribution

Implement opt-in HTTPS-only fetching of complete `.innoevent` artifacts with exact host allowlists, redirect host validation, temporary streaming, a 512 MiB limit with or without Content-Length, and untrusted remote filenames. Leave normal verification to the caller; never fetch documents/webpages.

Verify: fake opener/response tests for scheme, host, redirect, size, streaming and default-disabled behavior.

### Task 23: Runtime CLI operations

Add `validate`, `install`, `list`, `status`, `activate`, `rollback` and `fetch` to `eventctl`; non-build operations must import cleanly without Docling, and `build` must print the exact separate-builder setup command when unavailable.

Verify: CLI unit tests and import/module scans.

### Task 24: Bounded real-asset smoke

Attempt the bounded builder asset prefetch and real local Docling/E5 smoke. If assets remain unavailable, record exact reasons and do not substitute test vectors for production evidence. If available, use only an ephemeral ignored smoke key and run build/verify/install/query/switch/no-leak/rollback.

Verify: smoke output and explicit deferred or passed asset gates.

### Task 25: Security/failure checkpoint

Run the complete Phase 4 unit/integration/e2e suites and confirm every required security, schema, isolation, activation, downgrade and rollback gate. Fix failures before wrap-up.

Verify: `.\\.venv\\Scripts\\python.exe -m pytest tests\\unit\\event tests\\integration\\event tests\\e2e\\event -q`.

### Task 26: Full project verification

Run full pytest, Ruff and diff checks; confirm importing `innobrain.event` does not import Docling; confirm generated packages/runtime artifacts are untracked; inspect the repository for private-key markers and confirm no actual private key is present.

Verify: the exact commands in Task 26 of the execution brief.

### Task 27: Reports and authorization

Write the factual Phase 4 report, update state and README, update the supplied Master Plan to v1.13 while preserving all earlier results, and authorize Phase 5 only if automated security/isolation/switching gates pass. Use deferred final state if real assets remain unavailable; do not start Phase 5.

Verify: report/state/master markers and a line-by-line Definition of Done review.

### Task 28: Fresh final verification, commit and push

Run the fresh final pytest/Ruff/diff/status sequence, stage only intended files, commit `feat: complete Phase 4 dynamic event packages`, verify a clean tree and exact final HEAD, then push `phase/4-dynamic-event-package` without merging.

Verify: remote branch SHA equals local HEAD and the final state is one of the specified Phase 4 states.

## Checkpoints

- After Tasks 0-3: branch, documents, config, manifest and crypto contracts are verified.
- After Tasks 4-10: strict authoring, archive, integrity and target knowledge boundaries are green.
- After Tasks 11-16: builder remains isolated and produces self-verifying development artifacts.
- After Tasks 17-23: target install, activation, rollback and package-only distribution are green.
- After Tasks 24-26: asset-dependent status and all automated/security gates are fresh.
- After Tasks 27-28: factual reports, authorization, clean commit and pushed branch are verified.

## Boundaries

- Always: preserve Phase 1-3 history/evidence, use TDD red -> green -> Ruff -> commit, keep private keys out of Git, and report deferred assets honestly.
- Ask first: no additional architecture/provider/phase expansion is authorized by this request.
- Never: add live document URL ingestion, place Docling/PyTorch in runtime, make synthetic vectors deployable, patch active DBs in place, or start Phase 5.
