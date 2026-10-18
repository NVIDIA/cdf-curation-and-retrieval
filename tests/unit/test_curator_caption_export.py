# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for Curator metas → CDS caption-row conversion."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest
from click.testing import CliRunner

from adapters.cosmos_curator.caption_export import (
    CuratorCaptionExportError,
    convert_curator_captions,
)
from apps.cli.__main__ import main
from apps.workflows.captions import (
    ConvertCuratorCaptionsRequest,
    convert_curator_captions_handoff,
)

_CLIP_A = "11111111-1111-1111-1111-111111111111"
_CLIP_B = "22222222-2222-2222-2222-222222222222"


def _write_meta(
    root: Path, clip_id: str, windows: list[dict[str, object]], **extra: object
) -> Path:
    meta_dir = root / "metas" / "v0"
    meta_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "span_uuid": clip_id,
        "start_ns": 0,
        "end_ns": 10_000_000_000,
        "windows": windows,
        **extra,
    }
    path = meta_dir / f"{clip_id}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_convert_joins_window_captions_and_prefers_enhanced(tmp_path: Path) -> None:
    _write_meta(
        tmp_path,
        _CLIP_A,
        [
            {
                "caption_status": "success",
                "qwen3_vl_30b_fp8_caption": "raw one",
                "qwen_lm_enhanced_caption": "enhanced one",
            },
            {
                "caption_status": "success",
                "qwen3_vl_30b_fp8_caption": "raw two",
                "qwen_lm_enhanced_caption": "enhanced two",
            },
        ],
    )

    rows = convert_curator_captions(tmp_path)

    assert len(rows) == 1
    assert rows[0]["clip_id"] == _CLIP_A
    assert rows[0]["summary"] == "enhanced one enhanced two"
    assert rows[0]["model_name"] == "qwen_lm_enhanced"
    assert rows[0]["start_time"] == 0.0
    assert rows[0]["end_time"] == 10.0


def test_convert_uses_raw_caption_when_enhance_absent(tmp_path: Path) -> None:
    _write_meta(
        tmp_path,
        _CLIP_A,
        [{"caption_status": "success", "qwen3_vl_30b_fp8_caption": "intersection traffic"}],
    )

    rows = convert_curator_captions(tmp_path)

    assert rows[0]["summary"] == "intersection traffic"
    assert rows[0]["model_name"] == "qwen3_vl_30b_fp8"


def test_convert_caption_key_override_ignores_enhanced(tmp_path: Path) -> None:
    _write_meta(
        tmp_path,
        _CLIP_A,
        [
            {
                "caption_status": "success",
                "qwen3_vl_30b_fp8_caption": "raw",
                "qwen_lm_enhanced_caption": "enhanced",
            }
        ],
    )

    rows = convert_curator_captions(tmp_path, caption_key="qwen3_vl_30b_fp8_caption")

    assert rows[0]["summary"] == "raw"
    assert rows[0]["model_name"] == "qwen3_vl_30b_fp8"


def test_convert_skips_failed_windows_and_errors_when_none_remain(tmp_path: Path) -> None:
    _write_meta(
        tmp_path,
        _CLIP_A,
        [
            {"caption_status": "failed", "qwen3_vl_30b_fp8_caption": "should skip"},
            {"caption_status": "success", "qwen3_vl_30b_fp8_caption": "keep"},
        ],
    )
    rows = convert_curator_captions(tmp_path)
    assert rows[0]["summary"] == "keep"

    _write_meta(
        tmp_path,
        _CLIP_B,
        [{"caption_status": "failed", "qwen3_vl_30b_fp8_caption": "nope"}],
    )
    with pytest.raises(CuratorCaptionExportError, match="No caption text"):
        convert_curator_captions(tmp_path)


def test_convert_rejects_missing_metas_empty_dir_and_invalid_json(tmp_path: Path) -> None:
    with pytest.raises(CuratorCaptionExportError, match="Missing Curator metas dir"):
        convert_curator_captions(tmp_path)

    (tmp_path / "metas" / "v0").mkdir(parents=True)
    with pytest.raises(CuratorCaptionExportError, match="No clip meta JSON"):
        convert_curator_captions(tmp_path)

    bad = tmp_path / "metas" / "v0" / f"{_CLIP_A}.json"
    bad.write_text("{not-json", encoding="utf-8")
    with pytest.raises(CuratorCaptionExportError, match="Invalid clip meta JSON"):
        convert_curator_captions(tmp_path)


def test_convert_rejects_uuid_mismatch_and_indexed_id_drift(tmp_path: Path) -> None:
    meta_dir = tmp_path / "metas" / "v0"
    meta_dir.mkdir(parents=True)
    (meta_dir / f"{_CLIP_A}.json").write_text(
        json.dumps(
            {
                "span_uuid": _CLIP_B,
                "windows": [{"qwen3_vl_30b_fp8_caption": "text"}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(CuratorCaptionExportError, match="UUID mismatch"):
        convert_curator_captions(tmp_path)

    _write_meta(tmp_path, _CLIP_A, [{"qwen3_vl_30b_fp8_caption": "ok"}])
    with pytest.raises(CuratorCaptionExportError, match="exactly align"):
        convert_curator_captions(tmp_path, indexed_clip_ids={_CLIP_A, _CLIP_B})


def test_convert_handoff_builds_parquet_and_preserves_indexed_ids(tmp_path: Path) -> None:
    output = tmp_path / "captions.parquet"
    rows = [{"clip_id": _CLIP_A, "summary": "joined"}]
    convert_captions = MagicMock(return_value=rows)
    build_caption = MagicMock(return_value=output)
    validate_caption = MagicMock(return_value={"rows": 1, "identity_aligned": True})
    indexed = {_CLIP_A}

    result = convert_curator_captions_handoff(
        ConvertCuratorCaptionsRequest(
            curator_dir=str(tmp_path),
            output_parquet=str(output),
            indexed_clip_ids=indexed,
            caption_key="qwen3_vl_30b_fp8_caption",
        ),
        convert_captions=convert_captions,
        build_caption=build_caption,
        validate_caption=validate_caption,
    )

    convert_captions.assert_called_once_with(
        str(tmp_path),
        caption_key="qwen3_vl_30b_fp8_caption",
        indexed_clip_ids=indexed,
    )
    build_caption.assert_called_once_with(rows, str(output), indexed_clip_ids=indexed)
    validate_caption.assert_called_once_with(output, indexed_clip_ids=indexed)
    assert result["status"] == "built"
    assert result["source"] == "curator_metas"
    assert result["rows_converted"] == 1


def test_convert_handoff_does_not_build_when_converter_fails(tmp_path: Path) -> None:
    build_caption = MagicMock()
    with pytest.raises(CuratorCaptionExportError, match="Missing Curator metas dir"):
        convert_curator_captions_handoff(
            ConvertCuratorCaptionsRequest(
                curator_dir=str(tmp_path),
                output_parquet=str(tmp_path / "captions.parquet"),
            ),
            convert_captions=convert_curator_captions,
            build_caption=build_caption,
            validate_caption=MagicMock(),
        )
    build_caption.assert_not_called()


def test_from_curator_cli_emits_machine_readable_summary(tmp_path: Path) -> None:
    _write_meta(
        tmp_path,
        _CLIP_A,
        [{"caption_status": "success", "qwen3_vl_30b_fp8_caption": "a car stops"}],
    )
    output = tmp_path / "captions.parquet"

    result = CliRunner().invoke(
        main,
        [
            "integration",
            "captions",
            "from-curator",
            "--curator-dir",
            str(tmp_path),
            "--output-parquet",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "built"
    assert payload["source"] == "curator_metas"
    assert payload["rows"] == 1
    frame = pd.read_parquet(output)
    assert list(frame["clip_id"]) == [_CLIP_A]
    assert list(frame["summary"]) == ["a car stops"]


def test_from_curator_cli_exits_nonzero_without_captions(tmp_path: Path) -> None:
    _write_meta(tmp_path, _CLIP_A, [{"caption_status": "success"}])
    result = CliRunner().invoke(
        main,
        [
            "integration",
            "captions",
            "from-curator",
            "--curator-dir",
            str(tmp_path),
            "--output-parquet",
            str(tmp_path / "captions.parquet"),
        ],
    )
    assert result.exit_code != 0
    assert "No caption text" in result.output
