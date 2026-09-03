"""Production-quality validation and repair tool for Heyino wake word corpora.

Audits an existing corpus directory and manifest for:
- Missing audio files
- Path traversal and out-of-corpus references
- Duplicate clip IDs and duplicate file paths
- Filename-vs-clip_id mismatches
- Clip_id-vs-metadata split/label/speaker mismatches
- Orphan WAV files
- Strict speaker split leakage between train, calibration, and held-out

Safety guarantees:
- Report-only is the safe default.
- Never invents metadata.
- Reconciles only unambiguous rename/path-only cases where a unique in-corpus WAV
  matches the existing clip_id.
- Reports ambiguous cases and makes no changes rather than guessing.
- Atomic manifest updates via save_manifest. Audio files are left completely untouched.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Safe direct-script project-root bootstrap
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.wakeword.heyino_corpus_spec import (  # noqa: E402
    VALID_SPLITS,
    CorpusClip,
    load_manifest,
    save_manifest,
    validate_manifest,
)


@dataclass(slots=True)
class CorpusAuditIssue:
    """Represents a single validation or integrity issue discovered in the corpus."""

    category: str
    message: str
    clip_id: str | None = None
    file_path: str | None = None
    reconcilable: bool = False
    proposed_file_path: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class CorpusAuditReport:
    """Full audit summary for a Heyino corpus directory."""

    corpus_dir: Path
    manifest_path: Path
    manifest_exists: bool = False
    manifest_readable: bool = False
    clip_count: int = 0
    wav_count: int = 0
    orphan_wavs: list[str] = field(default_factory=list)
    issues: list[CorpusAuditIssue] = field(default_factory=list)
    repaired: bool = False
    reconciled_clips: list[str] = field(default_factory=list)

    @property
    def is_healthy(self) -> bool:
        return len(self.issues) == 0

    def to_dict(self) -> dict[str, object]:
        return {
            "corpus_dir": str(self.corpus_dir),
            "manifest_path": str(self.manifest_path),
            "manifest_exists": self.manifest_exists,
            "manifest_readable": self.manifest_readable,
            "clip_count": self.clip_count,
            "wav_count": self.wav_count,
            "orphan_wavs": self.orphan_wavs,
            "is_healthy": self.is_healthy,
            "repaired": self.repaired,
            "reconciled_clips": self.reconciled_clips,
            "issues": [iss.to_dict() for iss in self.issues],
        }


def detect_clip_id_metadata_mismatches(clip: CorpusClip) -> list[str]:
    """Detect discrepancies between clip_id and clip metadata fields."""
    mismatches: list[str] = []

    # 1. Check split prefix against all VALID_SPLITS
    for s in VALID_SPLITS:
        if clip.clip_id.startswith(f"{s}_"):
            if s != clip.split:
                mismatches.append(
                    f"Split mismatch for clip '{clip.clip_id}': "
                    f"metadata split is '{clip.split}' but clip_id indicates split '{s}'"
                )
            break

    # 2. Check embedded label and speaker if clip_id matches canonical format
    expected_spk = (
        clip.speaker_id.replace(" ", "_").lower() if clip.speaker_id else "anon"
    )
    clean_label = (
        clip.label.replace(" ", "_").replace("/", "_").replace("\\", "_").lower()
    )

    # Strip timestamp and short-uuid suffix if present: _<timestamp>_<uuid8>
    ts_uuid_match = re.search(r"_(\d+)_([0-9a-fA-F]{8})$", clip.clip_id)
    prefix = clip.clip_id[: ts_uuid_match.start()] if ts_uuid_match else clip.clip_id

    # Check if prefix starts with any split prefix
    split_prefix: str | None = None
    for s in VALID_SPLITS:
        if prefix.startswith(f"{s}_"):
            split_prefix = s
            break

    if split_prefix is not None:
        body = prefix[len(split_prefix) + 1 :]
        expected_body = f"{clean_label}_{expected_spk}"
        if body != expected_body:
            if body.endswith(f"_{expected_spk}"):
                embedded_label = body[: -len(expected_spk) - 1]
                mismatches.append(
                    f"Label mismatch for clip '{clip.clip_id}': metadata label is '{clip.label}' "
                    f"but clip_id contains label '{embedded_label}'"
                )
            elif body.startswith(f"{clean_label}_"):
                embedded_spk = body[len(clean_label) + 1 :]
                mismatches.append(
                    f"Speaker mismatch for clip '{clip.clip_id}': "
                    f"metadata speaker_id is '{clip.speaker_id}' "
                    f"but clip_id contains speaker '{embedded_spk}'"
                )
            else:
                mismatches.append(
                    f"Metadata mismatch for clip '{clip.clip_id}': expected '{expected_body}' "
                    f"from metadata, but clip_id contains '{body}'"
                )

    return mismatches


def scan_corpus_wav_files(corpus_dir: Path) -> list[Path]:
    """Scan all valid in-corpus WAV files, ignoring hidden files and temporary artifacts."""
    wavs: list[Path] = []
    if not corpus_dir.is_dir():
        return wavs

    for root, _, files in os.walk(corpus_dir):
        root_path = Path(root)
        try:
            rel_root = root_path.relative_to(corpus_dir)
            if any(part.startswith(".") for part in rel_root.parts):
                continue
        except ValueError:
            continue

        for fname in files:
            if fname.startswith("."):
                continue
            if fname.lower().endswith(".wav"):
                wavs.append(root_path / fname)

    return sorted(wavs)


def audit_corpus(
    corpus_dir: Path | str,
    manifest_path: Path | str | None = None,
) -> CorpusAuditReport:
    """Audit corpus directory and manifest for all structural, metadata, and path issues."""
    cdir = Path(corpus_dir).resolve()
    mpath = Path(manifest_path).resolve() if manifest_path else (cdir / "manifest.json")

    report = CorpusAuditReport(
        corpus_dir=cdir,
        manifest_path=mpath,
        manifest_exists=mpath.is_file(),
    )

    # Scan audio before loading the manifest so a missing or malformed manifest
    # cannot hide unindexed WAV files from the repair report.
    all_wavs = scan_corpus_wav_files(cdir)
    report.wav_count = len(all_wavs)

    if not report.manifest_exists:
        report.orphan_wavs = [str(w.relative_to(cdir).as_posix()) for w in all_wavs]
        for wav_path in all_wavs:
            rel_path = str(wav_path.relative_to(cdir).as_posix())
            report.issues.append(
                CorpusAuditIssue(
                    category="orphan_wav",
                    message=f"Orphan audio file not referenced in manifest: '{rel_path}'",
                    file_path=rel_path,
                )
            )
        report.issues.append(
            CorpusAuditIssue(
                category="missing_manifest",
                message=f"Manifest file does not exist: {mpath}",
            )
        )
        return report

    try:
        clips = load_manifest(mpath)
        report.manifest_readable = True
        report.clip_count = len(clips)
    except Exception as err:
        report.orphan_wavs = [str(w.relative_to(cdir).as_posix()) for w in all_wavs]
        for wav_path in all_wavs:
            rel_path = str(wav_path.relative_to(cdir).as_posix())
            report.issues.append(
                CorpusAuditIssue(
                    category="orphan_wav",
                    message=f"Orphan audio file not referenced in manifest: '{rel_path}'",
                    file_path=rel_path,
                )
            )
        report.issues.append(
            CorpusAuditIssue(
                category="malformed_manifest",
                message=f"Failed to read or parse manifest {mpath}: {err}",
            )
        )
        return report

    seen_ids: dict[str, int] = {}
    seen_paths: dict[str, str] = {}
    referenced_wav_paths: set[Path] = set()

    missing_clips: list[CorpusClip] = []

    # Track speaker sets per split for strict leakage detection
    split_speakers: dict[str, set[str]] = {s: set() for s in VALID_SPLITS}

    for idx, clip in enumerate(clips):
        # 1. Duplicate ID check
        if clip.clip_id in seen_ids:
            report.issues.append(
                CorpusAuditIssue(
                    category="duplicate_clip_id",
                    message=f"Duplicate clip_id '{clip.clip_id}' found at entry index {idx} "
                    f"(first seen at index {seen_ids[clip.clip_id]})",
                    clip_id=clip.clip_id,
                    file_path=clip.file_path,
                )
            )
        else:
            seen_ids[clip.clip_id] = idx

        # 2. Path traversal / out-of-corpus check
        raw_fp = clip.file_path
        if ".." in raw_fp or raw_fp.startswith(("/", "\\")):
            report.issues.append(
                CorpusAuditIssue(
                    category="path_traversal",
                    message=(
                        f"Path traversal detected in file_path '{raw_fp}' "
                        f"for clip '{clip.clip_id}'"
                    ),
                    clip_id=clip.clip_id,
                    file_path=raw_fp,
                )
            )

        resolved_target = (cdir / raw_fp).resolve()
        try:
            resolved_target.relative_to(cdir)
        except ValueError:
            report.issues.append(
                CorpusAuditIssue(
                    category="out_of_corpus_path",
                    message=(
                        f"Clip '{clip.clip_id}' references file outside corpus "
                        f"directory: '{resolved_target}'"
                    ),
                    clip_id=clip.clip_id,
                    file_path=raw_fp,
                )
            )

        # 3. Duplicate file path check
        norm_fp = str(Path(raw_fp).as_posix()).lower()
        if norm_fp in seen_paths:
            report.issues.append(
                CorpusAuditIssue(
                    category="duplicate_file_path",
                    message=f"Duplicate file_path '{raw_fp}' for clip '{clip.clip_id}' "
                    f"(already used by clip '{seen_paths[norm_fp]}')",
                    clip_id=clip.clip_id,
                    file_path=raw_fp,
                )
            )
        else:
            seen_paths[norm_fp] = clip.clip_id

        # 4. Filename-vs-clip_id mismatch check
        file_stem = Path(raw_fp).stem
        if file_stem != clip.clip_id:
            report.issues.append(
                CorpusAuditIssue(
                    category="filename_clip_id_mismatch",
                    message=f"Filename stem '{file_stem}' does not match clip_id '{clip.clip_id}'",
                    clip_id=clip.clip_id,
                    file_path=raw_fp,
                )
            )

        # 5. Clip_id-vs-metadata split/label/speaker mismatches
        meta_mismatches = detect_clip_id_metadata_mismatches(clip)
        for mm in meta_mismatches:
            report.issues.append(
                CorpusAuditIssue(
                    category="metadata_mismatch",
                    message=mm,
                    clip_id=clip.clip_id,
                    file_path=raw_fp,
                )
            )

        # 6. File existence check
        if resolved_target.is_file():
            referenced_wav_paths.add(resolved_target)
        else:
            missing_clips.append(clip)
            # Add missing file issue initially; reconciliation will update if unambiguous
            report.issues.append(
                CorpusAuditIssue(
                    category="missing_file",
                    message=f"Audio file not found for clip '{clip.clip_id}': '{raw_fp}'",
                    clip_id=clip.clip_id,
                    file_path=raw_fp,
                    reconcilable=False,
                )
            )

        # Record speakers by split if valid split
        if clip.split in VALID_SPLITS and clip.speaker_id:
            split_speakers[clip.split].add(clip.speaker_id)

    # 7. Strict speaker split leakage checks
    leakage_pairs = [
        ("train", "calibration"),
        ("train", "held_out"),
        ("calibration", "held_out"),
    ]
    for s1, s2 in leakage_pairs:
        overlap = split_speakers[s1] & split_speakers[s2]
        if overlap:
            report.issues.append(
                CorpusAuditIssue(
                    category="speaker_leakage",
                    message=(
                        f"Strict speaker leakage detected between '{s1}' and '{s2}': "
                        f"{sorted(overlap)}"
                    ),
                )
            )

    # 8. Orphan WAVs check
    orphan_wavs = [w for w in all_wavs if w.resolve() not in referenced_wav_paths]
    report.orphan_wavs = [str(w.relative_to(cdir).as_posix()) for w in orphan_wavs]
    for ow in orphan_wavs:
        rel_ow = str(ow.relative_to(cdir).as_posix())
        report.issues.append(
            CorpusAuditIssue(
                category="orphan_wav",
                message=f"Orphan audio file not referenced in manifest: '{rel_ow}'",
                file_path=rel_ow,
            )
        )

    # 9. Evaluate unambiguous reconciliation for missing files
    orphan_by_stem: dict[str, list[Path]] = {}
    for ow in orphan_wavs:
        orphan_by_stem.setdefault(ow.stem, []).append(ow)

    clip_matches: dict[str, list[Path]] = {}
    wav_to_clips: dict[Path, list[str]] = {}

    for mc in missing_clips:
        matches = orphan_by_stem.get(mc.clip_id, [])
        clip_matches[mc.clip_id] = matches
        for m in matches:
            wav_to_clips.setdefault(m, []).append(mc.clip_id)

    for mc in missing_clips:
        matches = clip_matches.get(mc.clip_id, [])
        iss = next(
            (i for i in report.issues if i.category == "missing_file" and i.clip_id == mc.clip_id),
            None,
        )

        if len(matches) > 1:
            report.issues.append(
                CorpusAuditIssue(
                    category="ambiguous_match",
                    message=(
                        f"Ambiguous match for clip '{mc.clip_id}': found {len(matches)} matching "
                        f"orphan WAVs: {[str(p.relative_to(cdir).as_posix()) for p in matches]}. "
                        "Cannot repair safely."
                    ),
                    clip_id=mc.clip_id,
                    file_path=mc.file_path,
                )
            )
        elif len(matches) == 1:
            cand = matches[0]
            competing_clips = wav_to_clips.get(cand, [])
            if len(competing_clips) > 1:
                report.issues.append(
                    CorpusAuditIssue(
                        category="ambiguous_match",
                        message=(
                            f"Ambiguous match for orphan WAV '{cand.name}': claimed by multiple "
                            f"missing clips {competing_clips}. Cannot repair safely."
                        ),
                        clip_id=mc.clip_id,
                        file_path=mc.file_path,
                    )
                )
            else:
                if iss is not None:
                    iss.reconcilable = True
                    iss.proposed_file_path = str(cand.relative_to(cdir).as_posix())

    return report


def repair_corpus(
    corpus_dir: Path | str,
    manifest_path: Path | str | None = None,
) -> CorpusAuditReport:
    """Safely and atomically reconcile unambiguous path-only issues in the corpus manifest.

    Leaves audio untouched. Refuses to guess or make changes if any ambiguous match exists.
    """
    initial_report = audit_corpus(corpus_dir, manifest_path)
    if not initial_report.manifest_readable:
        return initial_report

    reconcilable_issues = [
        iss
        for iss in initial_report.issues
        if iss.reconcilable and iss.clip_id and iss.proposed_file_path
    ]

    if not reconcilable_issues:
        return initial_report

    proposed_paths = {iss.proposed_file_path for iss in reconcilable_issues}
    blocking_issues = [
        issue
        for issue in initial_report.issues
        if not (
            (issue.category == "missing_file" and issue.reconcilable)
            or (issue.category == "orphan_wav" and issue.file_path in proposed_paths)
        )
    ]
    if blocking_issues:
        # A safe rename-only repair is transactional: do not partially repair
        # one entry while leaving unrelated ambiguous or structural defects.
        return initial_report

    original_clips = load_manifest(initial_report.manifest_path)
    clips = [CorpusClip.from_dict(clip.to_dict()) for clip in original_clips]
    reconcile_map = {iss.clip_id: iss.proposed_file_path for iss in reconcilable_issues}

    reconciled_ids: list[str] = []
    for c in clips:
        if c.clip_id in reconcile_map:
            c.file_path = reconcile_map[c.clip_id]
            reconciled_ids.append(c.clip_id)

    val_res = validate_manifest(clips, base_dir=initial_report.corpus_dir, check_file_exists=True)
    if not val_res.valid:
        return initial_report

    save_manifest(initial_report.manifest_path, clips)

    post_report = audit_corpus(corpus_dir, manifest_path)
    if not post_report.is_healthy:
        # The manifest replacement itself was atomic, but an unexpected
        # post-write audit failure must not leave a partially reconciled corpus.
        save_manifest(initial_report.manifest_path, original_clips)
        return initial_report
    post_report.repaired = True
    post_report.reconciled_clips = reconciled_ids
    return post_report


def build_arg_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser for corpus auditing and repair."""
    parser = argparse.ArgumentParser(
        description="Heyino Wake Word Corpus Validation and Atomic Repair Tool"
    )
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=Path("recordings/heyino_corpus"),
        help="Base directory containing the corpus and manifest.json",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Optional explicit path to manifest.json (defaults to <corpus-dir>/manifest.json)",
    )
    parser.add_argument(
        "--repair",
        action="store_true",
        help="Apply atomic manifest repair for unambiguous rename/path-only cases",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output audit and repair results as formatted JSON",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Main CLI entry point for repair_heyino_corpus."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.repair:
        report = repair_corpus(corpus_dir=args.corpus_dir, manifest_path=args.manifest)
    else:
        report = audit_corpus(corpus_dir=args.corpus_dir, manifest_path=args.manifest)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.is_healthy else 1

    print("=== Heyino Wake Word Corpus Audit Report ===")
    print(f"Corpus Directory: {report.corpus_dir}")
    print(f"Manifest Path:    {report.manifest_path}")
    print(f"Clips in Manifest:{report.clip_count}")
    print(f"WAV Files Found:  {report.wav_count}")
    print(f"Orphan WAV Files: {len(report.orphan_wavs)}")
    print(f"Total Issues:     {len(report.issues)}")
    print(f"Status:           {'HEALTHY' if report.is_healthy else 'ISSUES DETECTED'}")

    if report.repaired:
        print(f"\n[REPAIR APPLIED] Reconciled {len(report.reconciled_clips)} clip path(s):")
        for cid in report.reconciled_clips:
            print(f"  - Reconciled clip '{cid}'")

    if report.issues:
        print("\nIssues:")
        for iss in report.issues:
            status_tag = " (reconcilable)" if iss.reconcilable else ""
            print(f"  [{iss.category.upper()}]{status_tag} {iss.message}")

    return 0 if report.is_healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
