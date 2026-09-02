# InnoBrain event authoring

Phase 4 event sources are local authoring folders. Each folder contains:

```text
structured/
  event.yaml
  locations.yaml
  speakers.yaml
  sessions.yaml
  booths.yaml
  aliases.yaml
  glossary.yaml
documents/
  local source files referenced by structured/event.yaml
```

The builder validates the structured records, parses only local document paths, and emits a self-contained signed `.innoevent` package. Runtime package distribution may download complete `.innoevent` artifacts from an explicit HTTPS allowlist; it never ingests live document URLs.
