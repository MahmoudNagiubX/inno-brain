# InnoBrain Phase 4 — Portable Dynamic Event Package Design Specification

> **Status:** Approved architecture for implementation
> **Date:** 2026-09-02
> **Base:** `phase/3-speech-brain-rag` @ `3e8d65c078dc6e4bd7ee78d6a4177fc9416de097`
> **Target branch:** `phase/4-dynamic-event-package`

# 1. Goal

An event/client content set must be replaceable without changing InnoBrain application code.

Phase 4 creates a secure content supply chain:

```text
Local event authoring folder
  → validate
  → parse with Docling
  → chunk
  → embed
  → package/sign
  → verify
  → install on target
  → compile local SQLite/FTS5/vec
  → activate atomically
```

# 2. Package choice

Use one portable `.innoevent` archive.

It is self-contained.

No runtime document URL ingestion.

Remote distribution, when enabled, downloads the complete signed `.innoevent` artifact over HTTPS.

# 3. Package contents

```text
manifest.json
signature.json
structured/*
documents/*
knowledge/chunks.jsonl
knowledge/embeddings.npy
knowledge/build_meta.json
assets/*
extensions/*
reports/build_report.json
```

`manifest.json` hashes every payload file.

`signature.json` signs the canonical manifest bytes.

# 4. Build/runtime split

Heavy work stays off the robot:

- Docling conversion;
- OCR/layout/table processing;
- chunking;
- embedding.

Runtime only verifies, compiles SQLite indexes and activates.

`docling==2.124.0` is builder-only in `.venv-event-builder`.

Runtime keeps the Phase 3 lean dependency model.

# 5. Supported authoring content

Primary:

- PDF;
- DOCX;
- XLSX;
- PPTX;
- HTML/XHTML;
- Markdown;
- CSV;
- TXT;
- common document images.

Legacy DOC/XLS/PPT are conditional on LibreOffice availability.

Unsupported formats produce a clear error.

# 6. Offline/confidential processing

Docling configuration must keep:

```text
enable_remote_services=false
allow_external_plugins=false
```

Model assets are prefetched.

Source URLs in event content are not fetched.

# 7. Structured files

```text
event.yaml
locations.yaml
speakers.yaml
sessions.yaml
booths.yaml
aliases.yaml
glossary.yaml
```

Strict validation covers identity, references, timezones, timestamps, schedule collisions and file references.

# 8. Chunking

Use structure-aware Docling output.

Align chunk sizing with multilingual E5.

```text
max chunk tokens = 384
merge peers = true
embedding dimension = 384
```

Tables preserve meaningful headers/structure where possible.

Each chunk carries provenance and retrieval metadata.

# 9. Portable embeddings

`knowledge/embeddings.npy`:

```text
dtype = <f4
shape = (number_of_chunks, 384)
allow_pickle = false
```

The package contains embeddings but not a cross-platform writable vec0 DB.

Installer rebuilds vec0 locally.

# 10. Package identity

```text
package_schema_version = 1.0
event_version = semantic version
build_id = SHA-256 deterministic content/config digest
```

Schema version and event content version are independent.

# 11. Integrity/authenticity

SHA-256 protects each payload.

Ed25519 authenticates the canonical manifest.

Production runtime requires a trusted valid signature.

Private signing key never leaves the build/operations machine.

# 12. Safe archive rules

Reject:

- traversal;
- absolute paths;
- symlinks;
- path collisions;
- undeclared entries;
- encryption;
- unsupported compression;
- over-quota archives/files.

Limits:

```text
archive <= 512 MiB
files <= 2,000
uncompressed total <= 1 GiB
single uncompressed file <= 256 MiB
```

# 13. Runtime installation

Installed DBs are target-local.

Each runtime DB contains exactly one event ID/version.

DB is immutable/read-only after install.

Location:

```text
runtime_data/events/installed/<event>/<version>/<build>/
```

# 14. Atomic activation

Activation only after full health validation.

Write `active_event.json.tmp`, flush/fsync, then `os.replace()`.

Do not switch while the conversation runtime is busy.

Reset visitor/session memory after switch.

# 15. Rollback

Keep previous healthy builds.

Normal activation does not silently downgrade.

Explicit rollback revalidates and activates a previous healthy build.

# 16. Extension path

Unknown but declared namespaced extensions are preserved but never executed.

This allows Phase 5 navigation/screen payloads without breaking package schema 1.x.

# 17. Remote distribution

Optional HTTPS package fetch is disabled by default.

Only configured hosts are accepted.

Redirects remain within allowlist.

Downloaded content still goes through the normal full verifier.

# 18. Production profile

Production package requires:

- real E5;
- zero required parse failures;
- valid strict structured data;
- trusted Ed25519 signature;
- `deployable=true`;
- successful self-validation.

Development/test packages cannot masquerade as production.

# 19. Failure safety

If a new package is corrupt, malicious, incompatible or fails install:

- previous active package stays active;
- no pointer update occurs;
- staging is discarded/quarantined;
- error is reported.

# 20. Success definition

The final automated demonstration installs Event A and Event B, activates each, queries exact and RAG knowledge, verifies zero cross-event leakage, then explicitly rolls back and verifies Event A again.
