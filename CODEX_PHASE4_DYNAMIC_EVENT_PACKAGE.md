# InnoBrain Phase 4 — Portable Dynamic Event Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Goal:** Make event content securely buildable, portable, installable, switchable and rollbackable without application-code changes.
>
> **Architecture:** Heavy document processing runs off-device. A strict local authoring tree is compiled into a deterministic self-contained `.innoevent` ZIP containing structured data, Docling-derived chunks, portable E5 embeddings, hashes and an Ed25519 signature. The target verifies the package, safely extracts it, compiles a target-local immutable SQLite/FTS5/sqlite-vec database, and atomically changes the active-event pointer.
>
> **Tech Stack:** Python `>=3.11,<3.15`; existing Phase 3 SQLite/FTS5/sqlite-vec/E5 stack; `cryptography==50.0.1`; builder-only `docling==2.124.0`; stdlib `zipfile`, `hashlib`, `json`, `zoneinfo`, `urllib`; Pydantic/PyYAML; pytest/Ruff.
>
> **Spec:** `PHASE4_DESIGN_SPEC.md` and `MASTER_PLAN.md`
>
> **Starting branch:** `phase/3-speech-brain-rag`
>
> **Expected starting HEAD:** `3e8d65c078dc6e4bd7ee78d6a4177fc9416de097`
>
> **Target branch:** `phase/4-dynamic-event-package`
>
> **STOP RULE:** Do not start Phase 5.

---

# Global Constraints

- Preserve Phase 1–3 history and deferred validation debt.
- Do not branch from stale `main`.
- Event content is local/self-contained at build time.
- Do not implement arbitrary live URL ingestion.
- Remote distribution can download only complete `.innoevent` package artifacts.
- Docling is builder-only and pinned `2.124.0`.
- Docling must not become a robot runtime dependency.
- Docling remote services and external plugins remain disabled.
- Production packages require real E5 embeddings.
- Test vectors may never produce `deployable=true`.
- `sqlite-vec==0.1.9` remains pinned.
- Rebuild vec0 on the target platform.
- Active runtime DBs are immutable/read-only.
- Production packages require Ed25519 signature verification.
- Never commit private signing keys.
- Do not patch active event DBs in place.
- Event switching must reset session memory.
- Failed activation must leave the old active event untouched.
- Unknown extension payloads are preserved but not executed.
- No Phase 5 navigation/ROS implementation.
- No repeated live microphone gate.
- Every code task uses red → green → Ruff → commit.
- Run fresh verification before completion claims.
- Do not merge automatically.

---

# Phase 4 final states

Exactly one:

```text
PHASE_4_COMPLETE
PHASE_4_IMPLEMENTATION_COMPLETE_VALIDATION_DEFERRED
PHASE_4_BLOCKED
```

Expected current-workflow state if real E5/Docling asset smoke remains unavailable:

```text
PHASE_4_IMPLEMENTATION_COMPLETE_VALIDATION_DEFERRED
```

---

# File Map

```text
src/innobrain/event/
  __init__.py
  errors.py
  models.py
  authoring.py
  manifest.py
  crypto.py
  archive.py
  parser.py
  chunking.py
  embeddings.py
  builder.py
  installer.py
  registry.py
  activation.py
  distribution.py
  runtime.py
  validation.py

src/innobrain/knowledge/
  schema.sql
  database.py
  repository.py
  vector_store.py

config/
  runtime.yaml
  trusted_event_keys.yaml.example

events/
  README.md

fixtures/phase4/
  event_alpha/
  event_beta/

scripts/phase4/
  eventctl.py
  prefetch_builder_assets.py
  phase4_smoke.py

docs/phase4/
  PHASE4_STATE.md
  PHASE4_REPORT.md

tests/unit/event/
tests/integration/event/
tests/e2e/event/
```

---

# Task 0 — Safety preflight and branch

- [ ] Run:

```powershell
Set-Location "C:\Users\mahmo\Desktop\InnoBrainWorkspace\inno-brain"
git status --short
```

Expected empty. If not empty: STOP; do not discard/stash/reset.

- [ ] Update Phase 3:

```powershell
git fetch origin
git switch "phase/3-speech-brain-rag"
git pull --ff-only origin "phase/3-speech-brain-rag"
git rev-parse HEAD
```

Planning-time expected:

```text
3e8d65c078dc6e4bd7ee78d6a4177fc9416de097
```

- [ ] Verify state:

```powershell
Select-String -Path docs\phase3\PHASE3_STATE.md -SimpleMatch "PHASE_3_IMPLEMENTATION_COMPLETE_VALIDATION_DEFERRED"
Select-String -Path MASTER_PLAN.md -Pattern "Version:\*\* 1.11"
```

- [ ] Create branch if absent:

```powershell
git branch --list "phase/4-dynamic-event-package"
```

Then create `phase/4-dynamic-event-package`, or switch to that branch if it already exists legitimately from the expected Phase 3 base.

---

# Task 1 — Sync Phase 4 architecture documents

**Files:**
- Modify: `MASTER_PLAN.md`
- Create: `PHASE4_DESIGN_SPEC.md`
- Create: `CODEX_PHASE4_DYNAMIC_EVENT_PACKAGE.md`
- Create: `docs/phase4/PHASE4_STATE.md`

Before replacing Master Plan, preserve every newer Phase 3 factual result in repository v1.11.

Create state:

```markdown
# Phase 4 State

**Phase:** 4 — Portable Dynamic Event Package
**Branch:** `phase/4-dynamic-event-package`
**Status:** `IN_PROGRESS`
**Last completed task:** Task 1
**Next task:** Task 2 — dependencies and runtime event configuration
**Base Phase 3 HEAD:** `3e8d65c078dc6e4bd7ee78d6a4177fc9416de097`
**Package schema:** 1.0
**Portable extension:** `.innoevent`
**Docling builder:** 2.124.0 — not validated yet
**Signature:** Ed25519 — not validated yet
**Real E5 package build:** pending
**Event switching:** not implemented
**Phase 5 authorized:** No
```

Verify:

```powershell
Select-String -Path MASTER_PLAN.md -Pattern "Version:\*\* 1.12"
Select-String -Path MASTER_PLAN.md -SimpleMatch ".innoevent"
Select-String -Path MASTER_PLAN.md -SimpleMatch "docling==2.124.0"
git diff --check
```

Commit:

```powershell
git add MASTER_PLAN.md PHASE4_DESIGN_SPEC.md CODEX_PHASE4_DYNAMIC_EVENT_PACKAGE.md docs/phase4/PHASE4_STATE.md
git commit -m "docs: start Phase 4 dynamic event packages"
```

---

# Task 2 — Runtime crypto dependency, builder extra and event configuration

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/innobrain/config/models.py`
- Modify: `config/runtime.yaml`
- Create: `config/trusted_event_keys.yaml.example`
- Test: `tests/unit/config/test_loader.py`

Add direct runtime dependency:

```toml
"cryptography==50.0.1",
```

Add builder-only extra:

```toml
event-builder = [
    "docling==2.124.0",
]
```

Do not put Docling in main dependencies.

Add:

```python
class EventPackageRuntimeConfig(StrictModel):
    data_root: str = "runtime_data"
    require_signature_in_production: bool = True
    allow_unsigned_development: bool = False
    allow_remote_package_fetch: bool = False
    allowed_remote_hosts: list[str] = []
    max_archive_bytes: int = 536_870_912
    max_file_count: int = 2000
    max_uncompressed_bytes: int = 1_073_741_824
    max_single_file_bytes: int = 268_435_456
```

Add to `RuntimeConfig`:

```python
events: EventPackageRuntimeConfig = EventPackageRuntimeConfig()
```

YAML:

```yaml
events:
  data_root: runtime_data
  require_signature_in_production: true
  allow_unsigned_development: false
  allow_remote_package_fetch: false
  allowed_remote_hosts: []
  max_archive_bytes: 536870912
  max_file_count: 2000
  max_uncompressed_bytes: 1073741824
  max_single_file_bytes: 268435456
```

Public-key example:

```yaml
trusted_keys: []
```

Write failing config tests first.

Install normal runtime env:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Do NOT install event-builder extra into `.venv`.

Run full tests/Ruff and commit.

---

# Task 3 — Core event package errors and strict manifest models

**Files:**
- Create: `src/innobrain/event/__init__.py`
- Create: `src/innobrain/event/errors.py`
- Create: `src/innobrain/event/models.py`
- Create: `src/innobrain/event/manifest.py`
- Test: `tests/unit/event/test_manifest.py`

Errors:

```python
class EventPackageError(RuntimeError): ...
class EventSchemaError(EventPackageError): ...
class EventIntegrityError(EventPackageError): ...
class EventSignatureError(EventPackageError): ...
class EventCompatibilityError(EventPackageError): ...
class EventInstallError(EventPackageError): ...
class EventActivationError(EventPackageError): ...
class EventActivationBusy(EventActivationError): ...
```

Manifest models use `extra="forbid"`.

Validate:

```text
package_type == innobrain.event
package_schema_version matches 1.x
event_version is strict MAJOR.MINOR.PATCH
build_id is 64 lowercase hexadecimal characters
sha256 fields are 64 lowercase hexadecimal characters
archive paths are relative POSIX paths
```

Define typed file/embedding/manifest models and canonical serialization:

```python
def canonical_manifest_bytes(manifest: EventPackageManifest) -> bytes:
    payload = manifest.model_dump(mode="json")
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
```

Test byte stability independent of dict insertion order.

Commit.

---

# Task 4 — Strict authoring schema

**Files:**
- Create: `src/innobrain/event/authoring.py`
- Test: `tests/unit/event/test_authoring.py`

Strict models:

```text
EventSource
LocationSource
SpeakerSource
SessionSource
BoothSource
AliasSource
GlossaryTerm
DocumentSource
EventAuthoringBundle
```

`EventSource` includes:

```text
id
version
client_id
title
start_date
end_date
venue
timezone
default_locale
documents
```

`DocumentSource` includes:

```text
id
path
title
language
authority_level
valid_from
valid_until
required
```

Authority values:

```text
official
approved
reference
marketing
```

Validation must check:

- IANA timezone with `ZoneInfo`;
- timestamps offset-aware;
- start < end;
- IDs unique;
- session location exists;
- session speakers exist;
- booth location exists;
- aliases reference existing entities;
- source document paths stay below source root;
- location session overlaps fail;
- speaker double-booking fails.

Do not auto-correct invalid references.

Test every failure explicitly.

Commit.

---

# Task 5 — Two deterministic Phase 4 source fixtures

**Files:**
- Create: `fixtures/phase4/event_alpha/...`
- Create: `fixtures/phase4/event_beta/...`
- Create: `events/README.md`
- Test: `tests/integration/event/test_authoring_fixtures.py`

Each fixture is a complete local authoring folder.

Event Alpha contains unique leakage sentinel:

```text
ALPHA-COMPASS
```

Event Beta contains:

```text
BETA-LANTERN
```

Fixtures have different event IDs, sessions, speakers and booths; one local Markdown knowledge file; aliases; glossary.

Authoring loader returns strict models and source inventory.

Commit.

---

# Task 6 — Ed25519 signing and trusted-key verification

**Files:**
- Create: `src/innobrain/event/crypto.py`
- Test: `tests/unit/event/test_crypto.py`

Use `Ed25519PrivateKey` and `Ed25519PublicKey` from `cryptography`.

Define signature metadata:

```text
algorithm = Ed25519
key_id
signature_base64
```

Implement sign and verify functions over exact canonical manifest bytes.

Tests generate ephemeral keys only in memory.

Required:

- valid signature passes;
- changed manifest fails;
- wrong key fails;
- unknown key ID fails.

No private key file committed.

Commit.

---

# Task 7 — Secure deterministic archive writer/verifier

**Files:**
- Create: `src/innobrain/event/archive.py`
- Test: `tests/unit/event/test_archive_security.py`
- Test: `tests/unit/event/test_archive_determinism.py`

Archive writer:

- sort member names;
- fixed timestamp `(1980, 1, 1, 0, 0, 0)`;
- UTF-8;
- `ZIP_DEFLATED`;
- deterministic permission bits;
- manifest/signature before sorted payload.

Security validation rejects:

- absolute path;
- `..`;
- backslash/drive tricks;
- symlink via external mode;
- duplicate path;
- casefold + Unicode NFC collision;
- encrypted entry;
- undeclared payload;
- unsupported compression.

Allowed compression:

```text
ZIP_STORED
ZIP_DEFLATED
```

Enforce Phase 4 quotas.

Never call unchecked `extractall`.

Stream each validated member to a path resolved below staging.

Tests construct malicious ZIPs programmatically.

Commit.

---

# Task 8 — Payload integrity and package verifier

**Files:**
- Create: `src/innobrain/event/validation.py`
- Test: `tests/unit/event/test_package_verifier.py`

Verifier order:

1. archive structure/quotas;
2. read exact manifest bytes;
3. strict manifest parse;
4. package schema compatibility;
5. signature policy;
6. Ed25519 verify;
7. actual payload set equals manifest file set;
8. stream SHA-256 every payload;
9. compare sizes;
10. extract only after all checks.

Production requires:

```text
deployable=true
trusted valid signature
```

Development unsigned acceptance requires non-production environment AND explicit `allow_unsigned_development=true`.

Tamper tests modify payload, manifest and signature.

Commit.

---

# Task 9 — Phase 3 database schema upgrade for event-package metadata

**Files:**
- Modify: `src/innobrain/knowledge/schema.sql`
- Modify: `src/innobrain/knowledge/database.py`
- Modify: `src/innobrain/knowledge/repository.py`
- Test: `tests/unit/knowledge/test_phase4_schema.py`

New package-built DB fields:

Event:

```text
event_version
client_id
```

Documents/chunks:

```text
event_version
client_id
language
authority_level
valid_from
valid_until
```

New databases set:

```text
schema_meta.database_schema_version = 2
```

Keep Phase 3 fixture builder compatible with deterministic defaults.

Repository lexical search excludes invalid-time content when reference time is supplied.

Authority is a tie-break/support signal, not a replacement for retrieval relevance.

Run all Phase 3 tests after changes.

Commit.

---

# Task 10 — Read-only DB and VectorStore open-existing mode

**Files:**
- Modify: `src/innobrain/knowledge/database.py`
- Modify: `src/innobrain/knowledge/vector_store.py`
- Test: `tests/unit/knowledge/test_readonly_database.py`
- Test: `tests/unit/knowledge/test_vector_store.py`

Extend:

```python
connect_event_db(path: Path, *, readonly: bool = False)
```

Read-only uses SQLite URI `mode=ro` and does not issue write PRAGMAs.

Extend:

```python
VectorStore(conn, dimension=384, create_if_missing=False)
```

Open-existing mode verifies `vec_chunks` exists and never creates/commits.

Search must work on read-only DB.

Commit.

---

# Task 11 — Builder environment asset-prefetch script

**Files:**
- Create: `scripts/phase4/prefetch_builder_assets.py`
- Modify: `.gitignore`
- Modify: `docs/phase4/PHASE4_STATE.md`

Create separate builder venv:

```powershell
py -3.14 -m venv .venv-event-builder
.\.venv-event-builder\Scripts\python.exe -m pip install --upgrade pip
.\.venv-event-builder\Scripts\python.exe -m pip install -e ".[event-builder]"
```

If that launcher is unavailable, use the compatible Python executable that created `.venv`.

Prefetch script:

1. calls existing Phase 3 E5 asset resolver with explicit download;
2. performs at most 3 total E5 attempts;
3. delays 2 seconds then 5 seconds between failures;
4. uses Docling public model downloader when available;
5. otherwise prints the supported fallback command `docling-tools models download`;
6. prints cache paths;
7. never places model artifacts in Git.

Ignore:

```text
.venv-event-builder/
.builder-cache/
runtime_data/
*.innoevent
```

Commit.

---

# Task 12 — Docling local document parser adapter

**Files:**
- Create: `src/innobrain/event/parser.py`
- Test: `tests/unit/event/test_parser.py`
- Test: `tests/integration/event/test_docling_optional.py`

Import Docling lazily in the live builder adapter so normal runtime import succeeds without Docling installed.

Define a parsed-document record containing document ID, title, source path, Docling document object when available and plain-text fallback when applicable.

`.txt` uses local UTF-8 text parsing.

Other accepted formats use `DocumentConverter`.

For PDF pipeline:

```text
enable_remote_services=false
allow_external_plugins=false
artifacts_path=local builder cache
```

No URL source.

HTML external resource fetch is disabled.

Unit tests use fake converter.

Optional live Docling test skips when builder dependency absent; when present it converts a local fixture Markdown and requires non-empty content.

Commit.

---

# Task 13 — Structure-aware E5-aligned chunker

**Files:**
- Create: `src/innobrain/event/chunking.py`
- Test: `tests/unit/event/test_chunking.py`

Canonical chunk fields:

```text
chunk_id
document_id
chunk_index
text
normalized_text
language
authority_level
valid_from
valid_until
source_path
headings
page_numbers
embedding_row
```

Hard maximum:

```text
384 E5 tokenizer tokens in contextualized embedding payload
```

Use Docling structure-aware chunks when available and preserve headings/page provenance.

Hard post-check verifies token count.

Oversized content splits by paragraph, then sentence, then token boundary.

Never truncate silently.

Tests verify no text loss/reordering and hard cap.

Commit.

---

# Task 14 — Portable real/test embedding matrix builder

**Files:**
- Create: `src/innobrain/event/embeddings.py`
- Test: `tests/unit/event/test_embeddings_matrix.py`

Production builds call existing `MultilingualE5OnnxProvider.embed_passage()`.

Output matrix:

```text
dtype <f4
shape (N, 384)
finite
approximately unit normalized
```

Write with `np.save(..., allow_pickle=False)`.

Load with `np.load(..., allow_pickle=False)`.

Test-only deterministic embedding provider lives in test helpers and forces `deployable=false`.

Commit.

---

# Task 15 — Deterministic build ID and build report

**Files:**
- Create: `src/innobrain/event/builder.py`
- Test: `tests/unit/event/test_build_id.py`

Build ID input includes:

- normalized authoring data;
- sorted source paths/hashes;
- builder schema version;
- Docling version;
- chunk max tokens;
- E5 model ID/revision/dimension.

Wall-clock timestamp is excluded.

Canonical JSON SHA-256 is build ID.

Test same source twice → same ID; one source byte changes → different ID.

Build report records source counts, structured counts, parsing, warnings/errors, chunks, token stats, embedding checks, dependency versions and durations.

Commit.

---

# Task 16 — Full `.innoevent` builder

**Files:**
- Extend: `src/innobrain/event/builder.py`
- Create: `scripts/phase4/eventctl.py`
- Test: `tests/integration/event/test_package_build.py`

Pipeline:

```text
load/validate source
hash inventory
parse docs
chunk
embed
write knowledge artifacts
write report
create manifest
sign if requested
write deterministic archive
self-verify
```

Development build command uses `.venv-event-builder` and explicit unsigned-development mode.

Production build requires production profile, real E5, signing-key path outside repository and key ID.

Production build fails on required parse failure, missing real E5, missing signing key, invalid embedding shape or validation errors.

Commit.

---

# Task 17 — Target-local package installer

**Files:**
- Create: `src/innobrain/event/installer.py`
- Test: `tests/integration/event/test_installer.py`

Stage in:

```text
runtime_data/events/.staging/<generated-id>/
```

Load structured YAML, chunks JSONL and embeddings NPY.

Create target-local `event.sqlite3`, insert structured/chunk metadata, populate FTS, rebuild `vec_chunks` with existing `VectorStore`.

Require:

```text
chunks count == FTS count == vec count == embedding rows
```

Write install report.

Close then reopen read-only and run health.

Atomically move staging to:

```text
installed/<event>/<version>/<build>/
```

Keep source package as `source.innoevent`.

Never overwrite an existing different build.

Commit.

---

# Task 18 — Registry and installed-package health

**Files:**
- Create: `src/innobrain/event/registry.py`
- Test: `tests/unit/event/test_registry.py`

Installed-event record contains event ID, event version, build ID, root, DB path and health.

Registry derives filesystem candidates but verifies identity against manifest/install report.

Do not trust directory names alone.

Version comparison uses the already-validated integer `MAJOR.MINOR.PATCH` tuple.

Commit.

---

# Task 19 — Atomic activation, memory reset and rollback

**Files:**
- Create: `src/innobrain/event/activation.py`
- Test: `tests/integration/event/test_activation.py`
- Test: `tests/integration/event/test_rollback.py`

Define idle guard protocol and activation hook callback.

Manager operations:

```text
activate
rollback
active
```

Activation:

- healthy candidate only;
- busy runtime → EventActivationBusy;
- normal same-event downgrade → reject;
- open candidate DB read-only;
- write pointer temp;
- flush/fsync;
- os.replace;
- swap/reset hooks;
- append activation history.

Rollback is explicit downgrade permission to a previous healthy event and logs rollback action.

Failed candidate health must leave pointer unchanged.

Commit.

---

# Task 20 — Active runtime context factory

**Files:**
- Create: `src/innobrain/event/runtime.py`
- Test: `tests/integration/event/test_runtime_context.py`

Active context contains installed record, read-only connection, `EventRepository` and open-existing `VectorStore`.

Context close closes connection.

Activation hook closes old context and opens new context.

Integration test wires `SessionMemory.reset` and confirms it runs.

Avoid redesigning `GroundedOrchestrator` beyond a small factory/helper if needed.

Commit.

---

# Task 21 — Zero-leak two-event e2e test

**Files:**
- Create: `tests/e2e/event/test_event_switch_no_leak.py`

Build two development packages with deterministic test embeddings.

Install both.

Alpha active:

```text
ALPHA-COMPASS retrievable
BETA-LANTERN absent
Alpha exact data exists
Beta exact data absent
```

Switch Beta and assert inverse.

Assert session memory empty after switch.

Rollback and assert Alpha returns/Beta disappears.

This is mandatory.

Commit.

---

# Task 22 — Optional HTTPS package fetcher

**Files:**
- Create: `src/innobrain/event/distribution.py`
- Test: `tests/unit/event/test_distribution.py`

Fetcher is disabled by default.

Rules:

- URL scheme exactly HTTPS;
- host in config allowlist;
- redirected hosts also allowlisted;
- stream to temporary file;
- enforce 512 MiB with or without Content-Length;
- never trust remote filename;
- caller performs normal package verifier afterward.

Tests inject fake opener/response; no network.

This is not a general website/RAG fetcher.

Commit.

---

# Task 23 — Builder/install CLI operations

**Files:**
- Extend: `scripts/phase4/eventctl.py`
- Test: `tests/unit/event/test_eventctl.py`

Commands:

```text
build
validate
install
list
status
activate
rollback
fetch
```

Non-build commands run in normal `.venv` and must not import Docling.

`build` detects missing builder dependency and prints the exact builder-environment setup command rather than installing anything globally.

Commit.

---

# Task 24 — Real builder smoke when assets are available

**Files:**
- Create: `scripts/phase4/phase4_smoke.py`
- Modify: `docs/phase4/PHASE4_STATE.md`

Attempt builder asset prefetch.

Run real local Docling conversion when builder dependency/assets exist.

Retry real E5 prefetch only within the bounded retry policy.

Build a production-like package using an ephemeral smoke signing key under ignored `artifacts/phase4/keys/`.

The key is test-only and must never be described as a production key.

Smoke sequence:

```text
build
verify
install
read-only health
exact query
RAG query
switch second event
zero-leak assertion
rollback
```

If Docling/E5 assets remain unavailable after bounded retries, record exact deferred reason and continue only with automated implementation gates.

Never substitute deterministic test embeddings for real-production smoke.

---

# Task 25 — Package security/failure matrix checkpoint

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\event tests\integration\event tests\e2e\event -q
```

Required evidence:

```text
path traversal rejected
absolute path rejected
symlink rejected
case/Unicode collision rejected
undeclared file rejected
payload tamper rejected
manifest/signature tamper rejected
untrusted signer rejected
unsigned production package rejected
quota rejected
bad foreign reference rejected
room overlap rejected
speaker double-booking rejected
failed activation preserves active event
normal downgrade rejected
rollback passes
event leakage test passes
```

Fix any failure before wrap-up.

---

# Task 26 — Full project verification

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests scripts
git diff --check
```

Verify Docling stays out of normal runtime import:

```powershell
.\.venv\Scripts\python.exe -c "import sys, innobrain.event; print('docling' in sys.modules)"
```

Expected:

```text
False
```

Verify generated artifacts are untracked:

```powershell
git ls-files "*.innoevent" runtime_data artifacts recordings
```

Expected no generated packages/runtime data.

Search private-key markers:

```powershell
git grep -n "BEGIN.*PRIVATE KEY"
```

Inspect any documentation-only match. No actual key is allowed.

---

# Task 27 — Reports, Master Plan v1.13 and Phase 5 authorization

**Files:**
- Create: `docs/phase4/PHASE4_REPORT.md`
- Modify: `MASTER_PLAN.md`
- Modify: `README.md`
- Modify: `docs/phase4/PHASE4_STATE.md`

Report actual facts only.

Cover:

- final state;
- branch/base/final HEAD;
- package schema;
- archive/security/signature tests;
- Docling builder environment;
- real Docling smoke;
- real E5 package build;
- install/read-only result;
- two-event no-leak result;
- rollback;
- full pytest/Ruff;
- deferred items.

Use `PHASE_4_COMPLETE` only if all required real production-like builder smoke succeeds.

Use `PHASE_4_IMPLEMENTATION_COMPLETE_VALIDATION_DEFERRED` when implementation/security/isolation gates pass but an asset-dependent real smoke remains deferred.

Update Master Plan `v1.12 → v1.13`.

Phase 5 may be authorized after automated security/isolation/switching gates pass.

Do not start Phase 5.

---

# Task 28 — Fresh final verification, commit and push

Run immediately before final commit:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests scripts
git diff --check
git status --short
```

Commit:

```powershell
git add MASTER_PLAN.md README.md pyproject.toml config src events fixtures scripts tests docs PHASE4_DESIGN_SPEC.md CODEX_PHASE4_DYNAMIC_EVENT_PACKAGE.md .gitignore
git commit -m "feat: complete Phase 4 dynamic event packages"
```

Verify clean and record actual HEAD.

Push:

```powershell
git push -u origin "phase/4-dynamic-event-package"
```

Do not merge.

Do not start Phase 5.

---

# Error Decision Table

| Failure | Required action |
|---|---|
| Dirty repo | STOP without discarding work |
| Wrong base | switch/recreate from completed Phase 3 |
| Phase 3 incomplete | STOP |
| cryptography failure | block signature implementation |
| Docling absent in normal runtime venv | expected |
| Docling builder install failure | preserve runtime work; record exact builder validation state |
| E5 download timeout | bounded retries; never fake production |
| source URL appears | reject |
| Docling remote service/plugins enabled | fail security validation |
| invalid structured relation | reject build |
| required document parse failure | production build fails |
| archive traversal/symlink/collision | reject |
| signature invalid/untrusted | reject before extraction |
| payload hash mismatch | reject |
| unsupported package schema major | reject |
| production unsigned/non-deployable | reject |
| vec rebuild failure | do not install/activate |
| read-only health failure | do not activate |
| runtime busy | return busy; pointer unchanged |
| candidate health failure | old event remains active |
| old-event data after switch | BLOCKED |
| memory survives switch | BLOCKED |
| normal downgrade | reject |
| rollback failure | BLOCKED |
| navigation semantics required | preserve extension; Phase 5 |
| live arbitrary URL ingestion requested | architecture change requires Master Plan revision |

---

# Luna Context-Saving Rules

1. Read `MASTER_PLAN.md`, `PHASE4_DESIGN_SPEC.md` and this plan fully once.
2. Later read only Global Constraints, current task and touched files.
3. Do not rescan donor repos.
4. Do not inspect voice provider SDKs.
5. Docling imports belong only to builder/parser code paths.
6. Keep archive security isolated and heavily unit-tested.
7. Keep verify, install and activate as separate boundaries.
8. Never mix package build and active-event mutation.
9. Before finalization reread Phase 4 contract/state, smoke output and final tasks.
10. Never solve missing model assets by weakening production-profile rules.

---

# Definition of Done

Phase 4 implementation progression is complete only when:

- branch inherits completed Phase 3;
- Master Plan v1.12 is synchronized;
- `.innoevent` schema exists;
- manifest serialization is strict/deterministic;
- authoring schema is strict;
- two event fixtures exist;
- Ed25519 passes;
- archive traversal/symlink/collision/quota defenses pass;
- hashes/tamper detection pass;
- production rejects unsigned/untrusted/non-deployable packages;
- Docling remains builder-only;
- remote Docling services/plugins are disabled;
- chunking enforces 384-token hard cap;
- portable embedding matrix validates;
- test vectors cannot produce deployable package;
- target-local FTS/vec rebuild passes;
- installed DB opens read-only;
- active pointer update is atomic;
- failed activation preserves old event;
- session memory resets on switch;
- two-event exact/RAG leakage test passes;
- rollback passes;
- optional HTTPS distribution is allowlisted/package-only;
- full pytest passes;
- Ruff passes;
- real Docling/E5 smoke is honestly passed or deferred;
- report/Master Plan are updated;
- branch is pushed;
- Phase 5 is not started.

**STOP AFTER PHASE 4.**
