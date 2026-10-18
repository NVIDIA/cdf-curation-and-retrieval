# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Convert Cosmos Curator clip metas into CDS EA caption rows.

Curator writes per-clip JSON under ``{base_dir}/metas/v0/{uuid}.json`` with
caption text on window objects (for example ``qwen3_vl_30b_fp8_caption``).
CDS caption upload requires unique ``clip_id`` plus a single ``summary``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

_ENHANCED_CAPTION_KEY = "qwen_lm_enhanced_caption"
_CAPTION_SUFFIX = "_caption"
_NS_PER_SECOND = 1_000_000_000.0


class CuratorCaptionExportError(ValueError):
    """Curator metas cannot be converted into CDS caption rows."""


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _ns_to_seconds(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value) / _NS_PER_SECOND
    except (TypeError, ValueError):
        return None


def _caption_keys(window: Mapping[str, Any], caption_key: str | None) -> tuple[str, ...]:
    if caption_key:
        return (caption_key,)
    keys = [key for key in window if isinstance(key, str) and key.endswith(_CAPTION_SUFFIX)]
    preferred = [key for key in keys if key == _ENHANCED_CAPTION_KEY]
    rest = sorted(key for key in keys if key != _ENHANCED_CAPTION_KEY)
    return tuple(preferred + rest)


def _window_caption(window: Mapping[str, Any], caption_key: str | None) -> tuple[str, str]:
    status = _clean_text(window.get("caption_status")).lower()
    if status and status != "success":
        return "", ""
    for key in _caption_keys(window, caption_key):
        text = _clean_text(window.get(key))
        if text:
            return text, key
    return "", ""


def _row_from_meta(
    path: Path,
    payload: Mapping[str, Any],
    *,
    caption_key: str | None,
) -> dict[str, Any]:
    clip_id = _clean_text(payload.get("span_uuid")) or path.stem
    if not clip_id:
        raise CuratorCaptionExportError(f"Meta is missing span_uuid: {path}")
    span = _clean_text(payload.get("span_uuid"))
    if span and span != path.stem:
        raise CuratorCaptionExportError(f"UUID mismatch: file={path.stem} meta.span_uuid={span}")

    windows = payload.get("windows")
    if not isinstance(windows, list):
        raise CuratorCaptionExportError(f"Meta windows must be a list: {path}")

    texts: list[str] = []
    selected_key = ""
    for window in windows:
        if not isinstance(window, Mapping):
            raise CuratorCaptionExportError(f"Caption window must be an object: {path}")
        text, key = _window_caption(window, caption_key)
        if not text:
            continue
        texts.append(text)
        if not selected_key:
            selected_key = key

    if not texts:
        raise CuratorCaptionExportError(f"No caption text in {path}")

    row: dict[str, Any] = {
        "clip_id": clip_id,
        "summary": " ".join(texts),
    }
    if selected_key.endswith(_CAPTION_SUFFIX):
        row["model_name"] = selected_key[: -len(_CAPTION_SUFFIX)]
    start_time = _ns_to_seconds(payload.get("start_ns"))
    end_time = _ns_to_seconds(payload.get("end_ns"))
    if start_time is not None:
        row["start_time"] = start_time
    if end_time is not None:
        row["end_time"] = end_time
    return row


def convert_curator_captions(
    curator_dir: str | Path,
    *,
    caption_key: str | None = None,
    indexed_clip_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Return CDS caption rows from Curator ``metas/v0/*.json`` sidecars."""
    root = Path(curator_dir)
    meta_dir = root / "metas" / "v0"
    if not meta_dir.is_dir():
        raise CuratorCaptionExportError(
            f"Missing Curator metas dir: {meta_dir} (pass the Curator output root)"
        )
    paths = sorted(meta_dir.glob("*.json"))
    if not paths:
        raise CuratorCaptionExportError(f"No clip meta JSON under {meta_dir}")

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CuratorCaptionExportError(f"Invalid clip meta JSON: {path}") from exc
        if not isinstance(payload, Mapping):
            raise CuratorCaptionExportError(f"Clip meta must be a JSON object: {path}")
        row = _row_from_meta(path, payload, caption_key=caption_key)
        clip_id = str(row["clip_id"])
        if clip_id in seen:
            raise CuratorCaptionExportError(f"Duplicate clip_id {clip_id}")
        seen.add(clip_id)
        rows.append(row)

    if indexed_clip_ids is not None:
        caption_ids = {str(row["clip_id"]) for row in rows}
        missing = indexed_clip_ids - caption_ids
        unknown = caption_ids - indexed_clip_ids
        if missing or unknown:
            raise CuratorCaptionExportError(
                "Caption clip identities do not exactly align with the supplied indexed-ID set "
                f"(missing={len(missing)}, unknown={len(unknown)})"
            )
    return rows
