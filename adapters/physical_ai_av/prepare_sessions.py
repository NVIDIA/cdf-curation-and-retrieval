# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Prepare PhysicalAI-AV camera chunks as Cosmos Curator multi-cam sessions.

Optional one-time end-user helper, not part of the pipeline. No Make target or
Curator stage calls it. Operators run it by hand to turn the gated
PhysicalAI-AV per-camera chunk zips into the ``videos/<clip-id>/<camera>.mp4``
tree the AV recipes expect; Curator then reads that tree from ``DATA_DIR``. The
only contract between the two is the directory layout on disk.

Skip this module entirely if the session tree already exists.
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path

CAMERA_FEATURES = (
    "camera_front_wide_120fov",
    "camera_front_tele_30fov",
    "camera_cross_left_120fov",
    "camera_cross_right_120fov",
)
PRIMARY_CAMERA_FEATURE = "camera_front_wide_120fov"
PRIMARY_CAMERA_KEYWORD = "front_wide"
KNOWN_GOOD_CLIP_ID = "030c760c-ae38-49aa-9ad8-f5650a545d26"
MULTICAM_VIDEOS_DIRNAME = "videos"
SINGLECAM_VIDEOS_DIRNAME = "videos-single"
LAYOUT_MULTICAM = "multicam"
LAYOUT_SINGLE = "single"
LAYOUT_BOTH = "both"
VALID_LAYOUTS = frozenset({LAYOUT_MULTICAM, LAYOUT_SINGLE, LAYOUT_BOTH})


class PrepareSessionsError(ValueError):
    """PhysicalAI-AV session layout cannot be prepared."""


def _dedupe_chunks(paths: Sequence[Path]) -> list[Path]:
    """Collapse copies of the same chunk archive.

    A chunk file name is unique within the dataset, so repeated names are one
    chunk mirrored twice: an extracted tree commonly sits beside the Hugging
    Face cache that produced it. Those copies are not an ambiguous choice.
    Equal names with unequal sizes are a broken mirror and do raise.
    """
    unique: dict[str, Path] = {}
    for path in paths:
        existing = unique.get(path.name)
        if existing is None:
            unique[path.name] = path
            continue
        if existing.stat().st_size != path.stat().st_size:
            raise PrepareSessionsError(
                f"two copies of {path.name} differ in size: {existing} and {path}"
            )
    return list(unique.values())


def _select_camera_zip(
    matches: Sequence[Path],
    camera: str,
    clip_ids: Sequence[str] | None,
) -> Path:
    """Choose the chunk archive that holds the requested clips."""
    if len(matches) == 1:
        return matches[0]
    if not clip_ids:
        names = ", ".join(sorted(path.name for path in matches))
        raise PrepareSessionsError(
            f"found {len(matches)} different {camera} chunk zips; each holds a "
            f"different set of clips, so pass --clip-id to choose or point "
            f"--chunk-dir at a single chunk: {names}"
        )
    wanted = set(clip_ids)
    holders = [path for path in matches if wanted <= set(list_clip_ids_in_zip(path, camera))]
    if not holders:
        raise PrepareSessionsError(
            f"no single {camera} chunk zip contains every requested clip ID: {sorted(wanted)}"
        )
    return holders[0]


def discover_camera_zips(
    root: Path,
    cameras: Sequence[str] = CAMERA_FEATURES,
    *,
    clip_ids: Sequence[str] | None = None,
) -> dict[str, Path]:
    """Find one chunk zip per requested camera under ``root`` (recursive).

    A chunk archive holds only part of the dataset, so when several distinct
    chunks are present the choice must come from ``clip_ids`` rather than
    sort order; an unresolvable choice raises instead of silently preparing
    the wrong sessions.
    """
    if not root.is_dir():
        raise PrepareSessionsError(f"chunk directory does not exist: {root}")
    found: dict[str, Path] = {}
    for camera in cameras:
        matches = _dedupe_chunks(sorted(root.rglob(f"{camera}.chunk_*.zip")))
        if not matches:
            raise PrepareSessionsError(f"missing {camera} chunk zip under {root}")
        found[camera] = _select_camera_zip(matches, camera, clip_ids)
    return found


def list_clip_ids_in_zip(zip_path: Path, camera: str) -> list[str]:
    """Return clip IDs that have an mp4 for ``camera`` inside ``zip_path``."""
    suffix = f".{camera}.mp4"
    clip_ids: list[str] = []
    with zipfile.ZipFile(zip_path) as archive:
        for name in archive.namelist():
            if name.endswith(suffix):
                clip_ids.append(Path(name).name[: -len(suffix)])
    return sorted(set(clip_ids))


def _common_clip_ids(camera_zips: Mapping[str, Path]) -> list[str]:
    per_camera = [set(list_clip_ids_in_zip(path, camera)) for camera, path in camera_zips.items()]
    if not per_camera:
        raise PrepareSessionsError("no camera zips provided")
    common = set.intersection(*per_camera)
    if not common:
        raise PrepareSessionsError("no clip IDs are present in every camera zip")
    return sorted(common)


def _select_clip_ids(
    camera_zips: Mapping[str, Path],
    clip_ids: Sequence[str] | None,
    max_sessions: int,
) -> list[str]:
    if max_sessions < 1:
        raise PrepareSessionsError("max_sessions must be >= 1")
    available = _common_clip_ids(camera_zips)
    if clip_ids:
        missing = [clip_id for clip_id in clip_ids if clip_id not in available]
        if missing:
            raise PrepareSessionsError(f"clip IDs not in all camera zips: {missing}")
        selected = list(clip_ids)
    elif KNOWN_GOOD_CLIP_ID in available:
        rest = [clip_id for clip_id in available if clip_id != KNOWN_GOOD_CLIP_ID]
        selected = [KNOWN_GOOD_CLIP_ID, *rest][:max_sessions]
    else:
        selected = available[:max_sessions]
    if not selected:
        raise PrepareSessionsError("no clip IDs selected")
    return selected


def extract_sessions(
    camera_zips: Mapping[str, Path],
    output_videos_dir: Path,
    *,
    clip_ids: Sequence[str] | None = None,
    max_sessions: int = 1,
) -> list[Path]:
    """Write ``output_videos_dir/<clip_id>/<camera>.mp4`` for selected clips."""
    selected = _select_clip_ids(camera_zips, clip_ids, max_sessions)

    output_videos_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for clip_id in selected:
        session_dir = output_videos_dir / clip_id
        session_dir.mkdir(parents=True, exist_ok=True)
        for camera, zip_path in camera_zips.items():
            member = f"{clip_id}.{camera}.mp4"
            dest = session_dir / f"{camera}.mp4"
            with zipfile.ZipFile(zip_path) as archive:
                dest.write_bytes(archive.read(member))
            written.append(dest)
    return written


def extract_single_camera_videos(
    camera_zips: Mapping[str, Path],
    output_videos_dir: Path,
    *,
    camera: str = PRIMARY_CAMERA_FEATURE,
    clip_ids: Sequence[str] | None = None,
    max_sessions: int = 1,
) -> list[Path]:
    """Write flat ``output_videos_dir/<clip_id>.<camera>.mp4`` for single-cam Curator."""
    if camera not in camera_zips:
        raise PrepareSessionsError(f"camera zip not provided: {camera}")
    selected = _select_clip_ids({camera: camera_zips[camera]}, clip_ids, max_sessions)
    output_videos_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    zip_path = camera_zips[camera]
    for clip_id in selected:
        dest = output_videos_dir / f"{clip_id}.{camera}.mp4"
        with zipfile.ZipFile(zip_path) as archive:
            dest.write_bytes(archive.read(f"{clip_id}.{camera}.mp4"))
        written.append(dest)
    return written


def download_camera_chunks(
    cache_dir: Path,
    clip_id: str,
    features: Sequence[str] = CAMERA_FEATURES,
) -> None:
    """Download camera chunks that contain ``clip_id`` into ``cache_dir``."""
    try:
        import physical_ai_av
    except ImportError as exc:
        raise PrepareSessionsError(
            "physical_ai_av is not installed. Run `pip install physical_ai_av` "
            "after Hugging Face login, or pass --chunk-dir to reuse downloaded zips."
        ) from exc
    cache_dir.mkdir(parents=True, exist_ok=True)
    interface = physical_ai_av.PhysicalAIAVDatasetInterface(
        token=True,
        cache_dir=cache_dir,
        confirm_download_threshold_gb=float("inf"),
    )
    interface.download_clip_features(clip_id, features=list(features))


def _cameras_for_layout(layout: str) -> tuple[str, ...]:
    if layout not in VALID_LAYOUTS:
        raise PrepareSessionsError(f"layout must be one of {sorted(VALID_LAYOUTS)}")
    if layout == LAYOUT_SINGLE:
        return (PRIMARY_CAMERA_FEATURE,)
    return CAMERA_FEATURES


def prepare_curator_sessions(
    output_dir: Path,
    *,
    chunk_dir: Path | None = None,
    cache_dir: Path | None = None,
    clip_ids: Sequence[str] | None = None,
    max_sessions: int = 1,
    download: bool = True,
    layout: str = LAYOUT_BOTH,
) -> list[Path]:
    """Download (optional) then extract Curator inputs under ``output_dir``."""
    cameras = _cameras_for_layout(layout)
    search_root = chunk_dir
    if search_root is None:
        if download:
            resolved_cache = cache_dir if cache_dir is not None else output_dir / ".hf-cache"
            download_id = clip_ids[0] if clip_ids else KNOWN_GOOD_CLIP_ID
            download_camera_chunks(resolved_cache, download_id, features=cameras)
            search_root = resolved_cache
        else:
            raise PrepareSessionsError("pass --chunk-dir when --skip-download is set")
    camera_zips = discover_camera_zips(search_root, cameras, clip_ids=clip_ids)
    written: list[Path] = []
    if layout in {LAYOUT_MULTICAM, LAYOUT_BOTH}:
        written.extend(
            extract_sessions(
                camera_zips,
                output_dir / MULTICAM_VIDEOS_DIRNAME,
                clip_ids=clip_ids,
                max_sessions=max_sessions,
            )
        )
    if layout in {LAYOUT_SINGLE, LAYOUT_BOTH}:
        written.extend(
            extract_single_camera_videos(
                camera_zips,
                output_dir / SINGLECAM_VIDEOS_DIRNAME,
                camera=PRIMARY_CAMERA_FEATURE,
                clip_ids=clip_ids,
                max_sessions=max_sessions,
            )
        )
    return written


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download PhysicalAI-AV camera chunks and extract Curator multi-cam sessions.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Cookbook DATA_DIR. Writes videos/ (multicam) and/or videos-single/.",
    )
    parser.add_argument(
        "--chunk-dir",
        type=Path,
        default=None,
        help="Directory that already contains camera_*.chunk_*.zip (recursive search).",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Hugging Face hub cache for downloads. Defaults to OUTPUT_DIR/.hf-cache.",
    )
    parser.add_argument(
        "--clip-id",
        action="append",
        dest="clip_ids",
        default=None,
        help="Clip UUID to extract. Repeatable. Default: first common clip, or the known-good id on download.",
    )
    parser.add_argument(
        "--max-sessions",
        type=int,
        default=1,
        help="When --clip-id is omitted, extract this many sessions (default: 1).",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Do not call physical_ai_av; require --chunk-dir.",
    )
    parser.add_argument(
        "--layout",
        choices=sorted(VALID_LAYOUTS),
        default=LAYOUT_BOTH,
        help="multicam session folders, single-cam flat MP4s, or both (default).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        written = prepare_curator_sessions(
            args.output_dir,
            chunk_dir=args.chunk_dir,
            cache_dir=args.cache_dir,
            clip_ids=args.clip_ids,
            max_sessions=args.max_sessions,
            download=not args.skip_download,
            layout=args.layout,
        )
    except PrepareSessionsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {len(written)} mp4s under {args.output_dir}")
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
