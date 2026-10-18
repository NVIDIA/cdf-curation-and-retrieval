# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for PhysicalAI-AV -> Curator session extraction."""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from adapters.physical_ai_av.prepare_sessions import (
    CAMERA_FEATURES,
    KNOWN_GOOD_CLIP_ID,
    PRIMARY_CAMERA_FEATURE,
    PRIMARY_CAMERA_KEYWORD,
    PrepareSessionsError,
    discover_camera_zips,
    download_camera_chunks,
    extract_sessions,
    extract_single_camera_videos,
    list_clip_ids_in_zip,
    main,
    prepare_curator_sessions,
)


def _write_camera_zip(path: Path, camera: str, clip_ids: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for clip_id in clip_ids:
            archive.writestr(f"{clip_id}.{camera}.mp4", f"{clip_id}-{camera}".encode())
            archive.writestr(f"{clip_id}.{camera}.timestamps.parquet", b"parquet")
    return path


def _chunk_tree(tmp_path: Path, clip_ids: list[str]) -> Path:
    root = tmp_path / "chunks"
    for camera in CAMERA_FEATURES:
        _write_camera_zip(root / camera / f"{camera}.chunk_3119.zip", camera, clip_ids)
    return root


class TestDiscoverAndList:
    def test_discovers_nested_chunk_zips(self, tmp_path: Path) -> None:
        root = _chunk_tree(tmp_path, ["clip-a"])
        found = discover_camera_zips(root)
        assert set(found) == set(CAMERA_FEATURES)
        assert all(path.is_file() for path in found.values())

    def test_missing_camera_zip_raises(self, tmp_path: Path) -> None:
        root = tmp_path / "empty"
        root.mkdir()
        with pytest.raises(PrepareSessionsError, match="missing camera_front_wide"):
            discover_camera_zips(root)

    def test_missing_root_raises(self, tmp_path: Path) -> None:
        with pytest.raises(PrepareSessionsError, match="does not exist"):
            discover_camera_zips(tmp_path / "nope")

    def test_ambiguous_chunks_without_clip_ids_raises(self, tmp_path: Path) -> None:
        root = _chunk_tree(tmp_path, ["clip-a"])
        for camera in CAMERA_FEATURES:
            _write_camera_zip(root / camera / f"{camera}.chunk_4000.zip", camera, ["clip-z"])
        with pytest.raises(PrepareSessionsError, match="different camera_front_wide"):
            discover_camera_zips(root)

    def test_ambiguous_chunks_resolved_by_clip_id(self, tmp_path: Path) -> None:
        root = _chunk_tree(tmp_path, ["clip-a"])
        for camera in CAMERA_FEATURES:
            _write_camera_zip(root / camera / f"{camera}.chunk_4000.zip", camera, ["clip-z"])
        found = discover_camera_zips(root, clip_ids=["clip-z"])
        assert all(path.name.endswith("chunk_4000.zip") for path in found.values())

    def test_clip_id_in_no_single_chunk_raises(self, tmp_path: Path) -> None:
        root = _chunk_tree(tmp_path, ["clip-a"])
        for camera in CAMERA_FEATURES:
            _write_camera_zip(root / camera / f"{camera}.chunk_4000.zip", camera, ["clip-z"])
        with pytest.raises(PrepareSessionsError, match="every requested clip ID"):
            discover_camera_zips(root, clip_ids=["clip-a", "clip-z"])

    def test_mirrored_duplicate_chunk_is_not_ambiguous(self, tmp_path: Path) -> None:
        """An extracted tree beside its Hugging Face cache duplicates each chunk."""
        root = _chunk_tree(tmp_path, ["clip-a"])
        for camera in CAMERA_FEATURES:
            cached = root / ".hf-cache" / camera / f"{camera}.chunk_3119.zip"
            _write_camera_zip(cached, camera, ["clip-a"])
        found = discover_camera_zips(root)
        assert set(found) == set(CAMERA_FEATURES)

    def test_same_chunk_name_with_different_size_raises(self, tmp_path: Path) -> None:
        root = _chunk_tree(tmp_path, ["clip-a"])
        camera = PRIMARY_CAMERA_FEATURE
        _write_camera_zip(
            root / ".hf-cache" / camera / f"{camera}.chunk_3119.zip",
            camera,
            ["clip-a", "clip-b", "clip-c"],
        )
        with pytest.raises(PrepareSessionsError, match="differ in size"):
            discover_camera_zips(root)

    def test_list_clip_ids_ignores_sidecar_files(self, tmp_path: Path) -> None:
        zip_path = _write_camera_zip(
            tmp_path / "camera_front_wide_120fov.chunk_1.zip",
            "camera_front_wide_120fov",
            ["aaa", "bbb"],
        )
        assert list_clip_ids_in_zip(zip_path, "camera_front_wide_120fov") == ["aaa", "bbb"]


class TestExtractSessions:
    def test_writes_session_mp4s(self, tmp_path: Path) -> None:
        root = _chunk_tree(tmp_path, ["clip-a", "clip-b"])
        zips = discover_camera_zips(root)
        written = extract_sessions(zips, tmp_path / "videos", clip_ids=["clip-b"])
        assert len(written) == 4
        session = tmp_path / "videos" / "clip-b"
        for camera in CAMERA_FEATURES:
            payload = (session / f"{camera}.mp4").read_bytes()
            assert payload == f"clip-b-{camera}".encode()

    def test_prefers_known_good_clip(self, tmp_path: Path) -> None:
        other = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        root = _chunk_tree(tmp_path, [other, KNOWN_GOOD_CLIP_ID])
        written = extract_sessions(
            discover_camera_zips(root),
            tmp_path / "videos",
            max_sessions=1,
        )
        assert written[0].parent.name == KNOWN_GOOD_CLIP_ID

    def test_missing_requested_clip_raises(self, tmp_path: Path) -> None:
        root = _chunk_tree(tmp_path, ["clip-a"])
        with pytest.raises(PrepareSessionsError, match="not in all camera zips"):
            extract_sessions(
                discover_camera_zips(root),
                tmp_path / "videos",
                clip_ids=["missing"],
            )

    def test_max_sessions_rejects_zero(self, tmp_path: Path) -> None:
        root = _chunk_tree(tmp_path, ["clip-a"])
        with pytest.raises(PrepareSessionsError, match="max_sessions"):
            extract_sessions(discover_camera_zips(root), tmp_path / "videos", max_sessions=0)

    def test_single_camera_writes_flat_mp4(self, tmp_path: Path) -> None:
        root = _chunk_tree(tmp_path, ["clip-a"])
        written = extract_single_camera_videos(
            discover_camera_zips(root),
            tmp_path / "videos-single",
            clip_ids=["clip-a"],
        )
        assert written == [tmp_path / "videos-single" / f"clip-a.{PRIMARY_CAMERA_FEATURE}.mp4"]
        assert written[0].read_bytes() == f"clip-a-{PRIMARY_CAMERA_FEATURE}".encode()

    def test_intersection_required(self, tmp_path: Path) -> None:
        root = tmp_path / "chunks"
        for camera in CAMERA_FEATURES:
            clip = "shared" if camera != CAMERA_FEATURES[-1] else "other"
            _write_camera_zip(root / f"{camera}.chunk_1.zip", camera, [clip])
        with pytest.raises(PrepareSessionsError, match="no clip IDs"):
            extract_sessions(discover_camera_zips(root), tmp_path / "videos")


class TestPrepareAndCli:
    def test_skip_download_requires_chunk_dir(self, tmp_path: Path) -> None:
        with pytest.raises(PrepareSessionsError, match="--chunk-dir"):
            prepare_curator_sessions(tmp_path, download=False)

    def test_skip_download_extracts_from_chunk_dir(self, tmp_path: Path) -> None:
        chunks = _chunk_tree(tmp_path, [KNOWN_GOOD_CLIP_ID])
        written = prepare_curator_sessions(
            tmp_path / "data",
            chunk_dir=chunks,
            download=False,
            max_sessions=1,
        )
        assert (
            tmp_path / "data" / "videos" / KNOWN_GOOD_CLIP_ID / "camera_front_wide_120fov.mp4"
        ).is_file()
        assert (
            tmp_path
            / "data"
            / "videos-single"
            / f"{KNOWN_GOOD_CLIP_ID}.{PRIMARY_CAMERA_FEATURE}.mp4"
        ).is_file()
        assert len(written) == 5

    def test_download_camera_chunks_uses_interface(self, tmp_path: Path) -> None:
        fake_mod = MagicMock()
        with patch.dict(sys.modules, {"physical_ai_av": fake_mod}):
            download_camera_chunks(tmp_path / "cache", KNOWN_GOOD_CLIP_ID)
        fake_mod.PhysicalAIAVDatasetInterface.assert_called_once()
        kwargs = fake_mod.PhysicalAIAVDatasetInterface.call_args.kwargs
        assert kwargs["cache_dir"] == tmp_path / "cache"
        assert kwargs["token"] is True
        fake_mod.PhysicalAIAVDatasetInterface.return_value.download_clip_features.assert_called_once_with(
            KNOWN_GOOD_CLIP_ID,
            features=list(CAMERA_FEATURES),
        )

    def test_download_camera_chunks_missing_package(self, tmp_path: Path) -> None:
        with patch.dict(sys.modules, {"physical_ai_av": None}):
            with pytest.raises(PrepareSessionsError, match="not installed"):
                download_camera_chunks(tmp_path / "cache", KNOWN_GOOD_CLIP_ID)

    def test_single_layout_requests_primary_camera_download(self, tmp_path: Path) -> None:
        chunks = _chunk_tree(tmp_path, [KNOWN_GOOD_CLIP_ID])
        with patch(
            "adapters.physical_ai_av.prepare_sessions.download_camera_chunks",
        ) as download:
            prepare_curator_sessions(
                tmp_path / "data",
                cache_dir=chunks,
                download=True,
                layout="single",
                clip_ids=[KNOWN_GOOD_CLIP_ID],
            )
        assert download.call_args.kwargs["features"] == (PRIMARY_CAMERA_FEATURE,)

    def test_download_then_extracts_from_cache_dir(self, tmp_path: Path) -> None:
        chunks = _chunk_tree(tmp_path, [KNOWN_GOOD_CLIP_ID])
        with patch(
            "adapters.physical_ai_av.prepare_sessions.download_camera_chunks",
        ) as download:
            written = prepare_curator_sessions(
                tmp_path / "data",
                cache_dir=chunks,
                download=True,
                clip_ids=[KNOWN_GOOD_CLIP_ID],
            )
        download.assert_called_once()
        assert len(written) == 5

    def test_cli_skip_download_prints_session(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        chunks = _chunk_tree(tmp_path, [KNOWN_GOOD_CLIP_ID])
        code = main(
            [
                "--output-dir",
                str(tmp_path / "data"),
                "--chunk-dir",
                str(chunks),
                "--skip-download",
            ]
        )
        assert code == 0
        captured = capsys.readouterr()
        assert KNOWN_GOOD_CLIP_ID in captured.out
        assert "5 mp4s" in captured.out

    def test_single_layout_writes_only_flat_mp4(self, tmp_path: Path) -> None:
        chunks = _chunk_tree(tmp_path, [KNOWN_GOOD_CLIP_ID])
        written = prepare_curator_sessions(
            tmp_path / "data",
            chunk_dir=chunks,
            download=False,
            layout="single",
        )
        assert len(written) == 1
        assert written[0].parent.name == "videos-single"
        assert not (tmp_path / "data" / "videos").exists()

    def test_invalid_layout_raises(self, tmp_path: Path) -> None:
        with pytest.raises(PrepareSessionsError, match="layout"):
            prepare_curator_sessions(tmp_path, download=False, layout="stereo")

    def test_cli_error_is_nonzero(self, tmp_path: Path) -> None:
        code = main(["--output-dir", str(tmp_path), "--skip-download"])
        assert code == 1

    def test_primary_keyword_is_unique(self) -> None:
        assert PRIMARY_CAMERA_KEYWORD == "front_wide"
        matches = [camera for camera in CAMERA_FEATURES if PRIMARY_CAMERA_KEYWORD in camera]
        assert matches == ["camera_front_wide_120fov"]
