# InnoBrain Bootstrap Report

## Environment

- OS: Microsoft Windows 11 Home Single Language, version 10.0.26200, build 26200.
- Shell: Windows PowerShell Desktop 5.1.26100.9278.
- Git: 2.55.0.windows.3.
- GitHub CLI: 2.98.0.
- GitHub auth status: authenticated as `MahmoudNagiubX`; token values were not recorded.
- Python: 3.14.6 detected.
- Workspace: `C:\Users\mahmo\Desktop\InnoBrainWorkspace`

## Production Repository

- Local path: `C:\Users\mahmo\Desktop\InnoBrainWorkspace\inno-brain`
- Branch: `main`
- Initial scaffold commit: `c58790e` (`chore: scaffold InnoBrain repository`)
- Bootstrap reports commit: second local commit after the scaffold; exact SHA is verified in the final Git check.
- Remote: `https://github.com/MahmoudNagiubX/inno-brain.git`
- Creation: `gh repo create inno-brain --private --source . --remote origin --push`.
- Visibility: private.

## Donors

- Expected count: 13.
- Actual count: 13.
- All required donor directories are siblings under `C:\Users\mahmo\Desktop\InnoBrainWorkspace\donor-repos`.
- Every donor has a valid 40-character inspected commit SHA.
- Every donor reported clean status after cloning.
- Every donor has an entry in `docs/research/DONOR_REPOS.lock.yaml`.

## Inspection

- Report: `docs/research/DONOR_INSPECTION.md`.
- Human-readable index: `docs/research/DONOR_REPOS.md`.
- Root code licenses were recorded from repository evidence; no license was guessed.
- Blocking license review: `sqlite-vec` has no root `LICENSE` or `COPYING` file in the inspected commit.
- Separate asset/license review notes: Silero and Pipecat tracked model files;
  llama.cpp vocabulary GGUF files and third-party notices; Metro-ASR external
  checkpoint/dataset; VoiceTuT-TTS OmniVoice/checkpoint/data/reference voices;
  pywebrtc-audio vendored components; Compact RAG binaries/databases/media;
  Pepper external SDK/assets.
- No broken donor URL was observed during cloning.
- No excluded donor repository was cloned.

## Architecture Findings

No architecture-blocking findings discovered during bootstrap.

The inspection reinforces the existing plan: donor code remains outside the
production repository, provider/model selection remains benchmark-driven, S330
software AEC/NS remains opt-in pending measurement, and pre-event ingestion is
kept off the Pi where possible.

## Blockers

- None for local bootstrap.
- `sqlite-vec` license review is required before copying or redistributing its
  source/binary, but it is reference-only and is not a production dependency.

## Verification Evidence

- Workspace has separate `inno-brain` and `donor-repos` directories.
- Donor count: 13 expected / 13 present.
- Donor Git health: each is inside a work tree, clean, and has a valid 40-character HEAD.
- Production scaffold contains no Phase 1 runtime implementation.
- Canonical documents were copied byte-for-byte from the attached package by SHA-256.
- Staged scaffold scan found no obvious API-key patterns.
- No model package, provider, or full Docling installation was run.
- Production code has no donor-repository import/reference.

## Final State

READY_FOR_PHASE_1

Next: begin Phase 1 — Foundation + Hardware Validation.
