# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for DatasetSearchAdapter — full CVDS surface with mocked HTTP."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import requests

from adapters.dataset_search.retrieval_adapter import (
    BulkIngestUnavailableError,
    BulkJobPollingTimeout,
    DatasetSearchAdapter,
    normalize_cds_base_url,
    sanitize_document_metadata,
)
from packages.domain.types import (
    BulkInsertRequest,
    CollectionCreateSpec,
    CollectionPatchSpec,
    CollectionRef,
    DocumentSpec,
    LabelledDocuments,
    MultiCollectionQuery,
    SearchQuery,
    SearchRefinementSpec,
)


def _json_response(payload, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.content = b"{}" if payload is not None else b""
    response.text = "{}" if isinstance(payload, dict) else ""
    response.headers = {"Content-Type": "application/json"}
    response.json.return_value = payload
    if status_code >= 400:
        http_error = requests.HTTPError(response=response)
        response.raise_for_status.side_effect = http_error
    else:
        response.raise_for_status = MagicMock()
    return response


class TestSanitizeDocumentMetadata:
    def test_keeps_scalars_drops_nested(self) -> None:
        clean = sanitize_document_metadata(
            {
                "span_uuid": "abc",
                "num_frames": 10,
                "valid": False,
                "score": 1.5,
                "filtered_windows": [],
                "windows": [{"x": 1}],
                "nested": {"a": 1},
                "ok_none": None,
            }
        )
        assert clean == {
            "span_uuid": "abc",
            "num_frames": 10,
            "valid": False,
            "score": 1.5,
            "ok_none": None,
        }

    def test_empty_and_none(self) -> None:
        assert sanitize_document_metadata(None) == {}
        assert sanitize_document_metadata({}) == {}


class TestNormalizeCdsBaseUrl:
    def test_empty_raises(self):
        with pytest.raises(ValueError, match="base_url"):
            normalize_cds_base_url("")

    def test_appends_v1(self):
        assert normalize_cds_base_url("http://localhost:8888") == "http://localhost:8888/v1"

    def test_keeps_existing_v1(self):
        assert normalize_cds_base_url("http://localhost:8888/v1/") == "http://localhost:8888/v1"

    def test_drops_query_and_fragment(self):
        assert (
            normalize_cds_base_url("https://cds.example/api?token=bad#frag")
            == "https://cds.example/api/v1"
        )

    def test_rejects_relative(self):
        with pytest.raises(ValueError, match="absolute"):
            normalize_cds_base_url("/v1")

    def test_rejects_non_http_scheme(self):
        with pytest.raises(ValueError, match="HTTP"):
            normalize_cds_base_url("ftp://cds.example")


class TestDatasetSearchAdapter:
    def test_requires_base_url(self):
        with pytest.raises(ValueError, match="base_url"):
            DatasetSearchAdapter(base_url="")

    def test_normalizes_base_url_property(self):
        adapter = DatasetSearchAdapter("http://cds.example", session=MagicMock())
        assert adapter.base_url == "http://cds.example/v1"

    def test_search_text_query(self):
        session = MagicMock()
        session.request.return_value = _json_response(
            {"retrievals": [{"id": "doc1", "score": 0.9, "meta": {"cam": "front"}}]}
        )
        adapter = DatasetSearchAdapter("http://cds.example", session=session)
        hits = adapter.search(
            CollectionRef("col-1"),
            SearchQuery(text="pedestrian", top_k=5),
        )
        assert len(hits) == 1
        assert hits[0].record_id == "doc1"
        assert hits[0].score == 0.9
        method, url = session.request.call_args.args[:2]
        assert method == "POST"
        assert url.endswith("/v1/collections/col-1/search")
        assert session.request.call_args.kwargs["json"]["query"] == [{"text": "pedestrian"}]
        assert session.request.call_args.kwargs["json"]["generate_asset_url"] is False

    def test_search_embedding_query(self):
        session = MagicMock()
        session.request.return_value = _json_response(
            {"results": [{"document_id": "x", "distance": 0.1}]}
        )
        adapter = DatasetSearchAdapter("http://cds.example/v1", session=session)
        hits = adapter.search(
            CollectionRef("c"),
            SearchQuery(embedding=[1.0, 0.0], filters={"cluster_id": 1}),
        )
        assert hits[0].record_id == "x"
        payload = session.request.call_args.kwargs["json"]
        assert payload["query"] == [{"embedding": [1.0, 0.0]}]
        assert payload["filters"]["cluster_id"] == 1

    def test_search_uses_aliases_when_primary_values_are_null(self):
        session = MagicMock()
        session.request.return_value = _json_response(
            {"results": [{"id": None, "document_id": "x", "score": None, "distance": 0.1}]}
        )
        adapter = DatasetSearchAdapter("http://cds.example/v1", session=session)

        hits = adapter.search(CollectionRef("c"), SearchQuery(text="forklift"))

        assert hits[0].record_id == "x"
        assert hits[0].score == 0.1

    def test_search_video_query(self):
        session = MagicMock()
        session.request.return_value = _json_response({"retrievals": []})
        adapter = DatasetSearchAdapter("http://cds.example", session=session)
        adapter.search(CollectionRef("c"), SearchQuery(video="data:video/mp4;base64,abc"))
        assert session.request.call_args.kwargs["json"]["query"][0]["video"].startswith(
            "data:video"
        )

    def test_search_image_path_compat(self):
        session = MagicMock()
        session.request.return_value = _json_response({"retrievals": []})
        adapter = DatasetSearchAdapter("http://cds.example", session=session)
        adapter.search(CollectionRef("c"), SearchQuery(image_path="https://ex/a.jpg"))
        assert session.request.call_args.kwargs["json"]["query"][0]["image"] == "https://ex/a.jpg"

    def test_search_session_segment(self):
        session = MagicMock()
        session.request.return_value = _json_response({"retrievals": []})
        adapter = DatasetSearchAdapter("http://cds.example", session=session)
        adapter.search(
            CollectionRef("c"),
            SearchQuery(
                session_segment={
                    "session_id": "s1",
                    "start_timestamp": 0,
                    "end_timestamp": 1,
                    "camera": "front",
                }
            ),
        )
        seg = session.request.call_args.kwargs["json"]["query"][0]["session_segment"]
        assert seg["session_id"] == "s1"
        assert seg["start_timestamp"] == 0

    def test_search_requires_exactly_one_modality(self):
        adapter = DatasetSearchAdapter("http://cds.example", session=MagicMock())
        with pytest.raises(ValueError, match="exactly one"):
            adapter.search(CollectionRef("c"), SearchQuery())
        with pytest.raises(ValueError, match="exactly one"):
            adapter.search(CollectionRef("c"), SearchQuery(text="a", video="b"))

    def test_search_empty_text_raises(self):
        adapter = DatasetSearchAdapter("http://cds.example", session=MagicMock())
        with pytest.raises(ValueError, match="non-empty"):
            adapter.search(CollectionRef("c"), SearchQuery(text="  "))

    @pytest.mark.parametrize(
        ("payload", "message"),
        [
            ({"unexpected": []}, "missing retrievals or results"),
            ({"retrievals": "not-a-list"}, "results must be a list"),
            ({"retrievals": ["not-an-object"]}, "item 1"),
            ({"retrievals": [{"score": 0.5}]}, "missing id"),
            ({"retrievals": [{"id": "doc"}]}, "missing score"),
            (
                {"retrievals": [{"id": "doc", "score": 0.5, "metadata": []}]},
                "metadata must be an object",
            ),
        ],
    )
    def test_search_rejects_malformed_response_items(self, payload: object, message: str):
        session = MagicMock()
        session.request.return_value = _json_response(payload)
        adapter = DatasetSearchAdapter("http://cds.example", session=session)

        with pytest.raises(ValueError, match=message):
            adapter.search(CollectionRef("c"), SearchQuery(text="car"))

    def test_multi_collection_search(self):
        session = MagicMock()
        session.request.return_value = _json_response(
            {
                "retrievals": [
                    {"id": "a", "score": 0.8, "collection_id": "c1", "metadata": {}},
                ]
            }
        )
        adapter = DatasetSearchAdapter("http://cds.example", session=session)
        hits = adapter.multi_collection_search(
            MultiCollectionQuery(
                collection_ids=["c1", "c2"],
                query=SearchQuery(text="car", top_k=3),
                rerank=True,
            )
        )
        assert hits[0].collection_id == "c1"
        payload = session.request.call_args.kwargs["json"]
        assert payload["collections"] == ["c1", "c2"]
        assert payload["params"]["nb_neighbors"] == 3
        assert session.request.call_args.args[1].endswith("/v1/retrieval")

    def test_multi_collection_empty_raises(self):
        adapter = DatasetSearchAdapter("http://cds.example", session=MagicMock())
        with pytest.raises(ValueError, match="collection_ids"):
            adapter.multi_collection_search(
                MultiCollectionQuery(collection_ids=[], query=SearchQuery(text="x"))
            )

    def test_list_and_create_collection(self):
        session = MagicMock()
        session.request.side_effect = [
            _json_response(
                {"collections": [{"id": "c1", "name": "demo", "pipeline": "p1", "tags": {}}]}
            ),
            _json_response(
                {
                    "collection": {
                        "id": None,
                        "collection_id": "c2",
                        "name": "new",
                        "pipeline": "p1",
                        "tags": {"k": "v"},
                    }
                }
            ),
        ]
        adapter = DatasetSearchAdapter("http://cds.example", session=session)
        listed = adapter.list_collections()
        assert listed[0].collection_id == "c1"
        created = adapter.create_collection(
            CollectionCreateSpec(name="new", pipeline="p1", tags={"k": "v"})
        )
        assert created.collection_id == "c2"
        assert session.request.call_args.kwargs["json"]["pipeline"] == "p1"

    def test_create_collection_requires_fields(self):
        adapter = DatasetSearchAdapter("http://cds.example", session=MagicMock())
        with pytest.raises(ValueError, match="name and pipeline"):
            adapter.create_collection(CollectionCreateSpec(name="", pipeline="p"))

    def test_update_and_delete_collection(self):
        session = MagicMock()
        delete_resp = _json_response(None)
        delete_resp.content = b""
        delete_resp.status_code = 204
        session.request.side_effect = [
            _json_response({"collection": {"id": "c1", "name": "renamed", "pipeline": "p"}}),
            delete_resp,
        ]
        adapter = DatasetSearchAdapter("http://cds.example", session=session)
        updated = adapter.update_collection("c1", CollectionPatchSpec(name="renamed"))
        assert updated.name == "renamed"
        adapter.delete_collection("c1")
        assert session.request.call_args.args[0] == "DELETE"

    def test_update_collection_requires_patch(self):
        adapter = DatasetSearchAdapter("http://cds.example", session=MagicMock())
        with pytest.raises(ValueError, match="name and/or tags"):
            adapter.update_collection("c1", CollectionPatchSpec())

    def test_list_pipelines_and_health(self):
        session = MagicMock()
        session.request.side_effect = [
            _json_response({"pipelines": [{"id": "cosmos_embed", "name": "Cosmos"}]}),
            MagicMock(
                status_code=200,
                content=b"OK",
                text="OK",
                headers={"Content-Type": "text/plain"},
                raise_for_status=MagicMock(),
            ),
        ]
        adapter = DatasetSearchAdapter("http://cds.example", session=session)
        pipes = adapter.list_pipelines()
        assert pipes[0].pipeline_id == "cosmos_embed"
        assert adapter.health() == "OK"
        health_url = session.request.call_args.args[1]
        assert health_url == "http://cds.example/health"

    def test_list_pipelines_preserves_string_compatibility(self):
        session = MagicMock()
        session.request.return_value = _json_response({"pipelines": ["cosmos_embed"]})

        pipelines = DatasetSearchAdapter("http://cds.example", session=session).list_pipelines()

        assert pipelines[0].pipeline_id == "cosmos_embed"
        assert pipelines[0].name == "cosmos_embed"

    @pytest.mark.parametrize(
        ("method_name", "payload", "message"),
        [
            ("list_pipelines", "bad", "expected an object or list"),
            ("list_pipelines", {"pipelines": [1]}, "pipelines response item"),
            ("list_pipelines", {"pipelines": [{}]}, "missing id"),
            ("list_collections", "bad", "expected an object"),
            ("list_collections", {"collections": ["bad"]}, "collections response item 1"),
            ("list_collections", {"collections": [{}]}, "missing id"),
            ("list_jobs", "bad", "expected an object or list"),
            ("list_jobs", {"jobs": ["bad"]}, "jobs response item 1"),
            ("list_jobs", {"jobs": [{}]}, "missing job_id"),
        ],
    )
    def test_list_endpoints_reject_malformed_items(
        self,
        method_name: str,
        payload: object,
        message: str,
    ):
        session = MagicMock()
        session.request.return_value = _json_response(payload)
        adapter = DatasetSearchAdapter("http://cds.example", session=session)

        with pytest.raises(ValueError, match=message):
            getattr(adapter, method_name)()

    def test_flush_collection(self):
        session = MagicMock()
        session.request.return_value = _json_response(
            {"id": "c1", "message": "Collection flushed successfully."}
        )
        adapter = DatasetSearchAdapter("http://cds.example", session=session)
        result = adapter.flush_collection("c1")
        assert "flushed" in result.get("message", "").lower() or result.get("id") == "c1"
        assert "/admin/collections/c1/flush" in session.request.call_args.args[1]

    def test_export_embeddings(self):
        session = MagicMock()
        session.request.return_value = _json_response(
            {
                "documents": [
                    {"id": "a", "embedding": [1.0, 2.0], "meta": {"k": 1}},
                    {"id": "b", "embedding": None},
                ]
            }
        )
        adapter = DatasetSearchAdapter("http://cds.example", session=session)
        records = adapter.export_embeddings(CollectionRef("c"))
        assert len(records) == 1
        assert records[0].record_id == "a"
        assert list(records[0].embedding) == [1.0, 2.0]

    def test_ingest_documents_url_and_embedding(self):
        session = MagicMock()
        session.request.return_value = _json_response(
            {"documents": [{"id": "d1", "indexed_at": "2026-01-01T00:00:00"}]}
        )
        adapter = DatasetSearchAdapter("http://cds.example", session=session)
        infos = adapter.ingest_documents(
            CollectionRef("c"),
            [
                DocumentSpec(mime_type="image/jpeg", url="https://ex/a.jpg"),
            ],
        )
        assert infos[0].document_id == "d1"
        payload = session.request.call_args.kwargs["json"]
        assert payload[0]["url"] == "https://ex/a.jpg"

    def test_ingest_documents_validation(self):
        adapter = DatasetSearchAdapter("http://cds.example", session=MagicMock())
        with pytest.raises(ValueError, match="non-empty"):
            adapter.ingest_documents(CollectionRef("c"), [])
        with pytest.raises(ValueError, match="exactly one"):
            adapter.ingest_documents(
                CollectionRef("c"),
                [DocumentSpec(mime_type="text/plain", content="a", url="http://x")],
            )

    @pytest.mark.parametrize(
        ("documents", "message"),
        [
            ("not-a-list", "documents must be a list"),
            (["not-an-object"], "item 1"),
            ([{}], "missing id"),
        ],
    )
    def test_ingest_documents_rejects_malformed_acknowledgments(
        self,
        documents: object,
        message: str,
    ):
        session = MagicMock()
        session.request.return_value = _json_response({"documents": documents})
        adapter = DatasetSearchAdapter("http://cds.example", session=session)

        with pytest.raises(ValueError, match=message):
            adapter.ingest_documents(
                CollectionRef("c"),
                [DocumentSpec(mime_type="text/plain", content="hello")],
            )

    def test_ingest_documents_rejects_malformed_response_envelope(self):
        session = MagicMock()
        session.request.return_value = _json_response("bad")
        adapter = DatasetSearchAdapter("http://cds.example", session=session)

        with pytest.raises(ValueError, match="expected an object or list"):
            adapter.ingest_documents(
                CollectionRef("c"),
                [DocumentSpec(mime_type="text/plain", content="hello")],
            )

    def test_delete_document_and_by_filter(self):
        session = MagicMock()
        empty = _json_response(None)
        empty.content = b""
        empty.status_code = 204
        session.request.return_value = empty
        adapter = DatasetSearchAdapter("http://cds.example", session=session)
        adapter.delete_document(CollectionRef("c"), "doc-1")
        adapter.delete_documents_by_filter(
            CollectionRef("c"), {"field": "session_id", "operator": "==", "value": "s"}
        )
        with pytest.raises(ValueError, match="filters"):
            adapter.delete_documents_by_filter(CollectionRef("c"), {})

    def test_ingest_parquet_returns_job_id(self):
        session = MagicMock()
        session.request.return_value = _json_response(
            {"status": "success", "message": "started", "job_id": "42"}
        )
        adapter = DatasetSearchAdapter("http://cds.example", session=session)
        job_id = adapter.ingest_parquet(
            CollectionRef("c", name="demo"),
            ["s3://bucket/a.parquet"],
            embedding_family="ce1",
        )
        assert job_id == "42"
        payload = session.request.call_args.kwargs["json"]
        assert payload["collection_name"] == "demo"
        assert payload["parquet_paths"] == ["s3://bucket/a.parquet"]
        assert session.request.call_args.args[1].endswith("/v1/insert-data")

    def test_ingest_parquet_fails_closed_on_404_by_default(self) -> None:
        session = MagicMock()
        session.request.return_value = _json_response({"detail": "missing"}, status_code=404)
        adapter = DatasetSearchAdapter("http://cds.example", session=session)

        with pytest.raises(BulkIngestUnavailableError, match="disabled by default"):
            adapter.ingest_parquet(
                CollectionRef("c1"),
                ["local.parquet"],
                embedding_family="ce1",
            )

        assert session.request.call_count == 1

    def test_ingest_parquet_lab_fallback_on_404(self, tmp_path: Path) -> None:
        parquet_path = tmp_path / "ingest.parquet"
        meta = {"span_uuid": "u1", "filtered_windows": [], "num_frames": 3}
        table = pa.table(
            {
                "id": ["doc-1"],
                "embedding": [[0.1, 0.2, 0.3]],
                "$meta": [json.dumps(meta)],
            }
        )
        pq.write_table(table, parquet_path)

        session = MagicMock()
        session.request.side_effect = [
            _json_response({"detail": "missing"}, status_code=404),
            _json_response(
                {
                    "documents": [
                        {"id": "doc-1", "indexed_at": "2026-01-01T00:00:00", "metadata": {}}
                    ]
                }
            ),
        ]
        adapter = DatasetSearchAdapter("http://cds.example", session=session)
        job_id = adapter.ingest_parquet(
            CollectionRef("c1", name="demo"),
            [str(parquet_path)],
            embedding_family="ce1",
            allow_document_fallback=True,
        )
        assert job_id == "documents:1"
        assert session.request.call_count == 2
        assert session.request.call_args_list[0].args[1].endswith("/v1/insert-data")
        docs_call = session.request.call_args_list[1]
        assert docs_call.args[0] == "POST"
        assert docs_call.args[1].endswith("/v1/collections/c1/documents")
        body = docs_call.kwargs["json"]
        assert isinstance(body, list) and len(body) == 1
        assert body[0]["embedding"] == [0.1, 0.2, 0.3]
        assert "filtered_windows" not in body[0]["metadata"]
        assert body[0]["metadata"]["num_frames"] == 3

    def test_ingest_parquet_lab_fallback_on_400_s3_path_rejection(self, tmp_path: Path) -> None:
        """Builds that validate the path up front reject a local parquet with 400."""
        parquet_path = tmp_path / "ingest.parquet"
        table = pa.table(
            {
                "id": ["doc-1"],
                "embedding": [[0.1, 0.2, 0.3]],
                "$meta": [json.dumps({"span_uuid": "u1"})],
            }
        )
        pq.write_table(table, parquet_path)

        session = MagicMock()
        session.request.side_effect = [
            _json_response(
                {"detail": f"Invalid S3 path format: '{parquet_path}'."},
                status_code=400,
            ),
            _json_response(
                {
                    "documents": [
                        {"id": "doc-1", "indexed_at": "2026-01-01T00:00:00", "metadata": {}}
                    ]
                }
            ),
        ]
        adapter = DatasetSearchAdapter("http://cds.example", session=session)

        job_id = adapter.ingest_parquet(
            CollectionRef("c1", name="demo"),
            [str(parquet_path)],
            embedding_family="ce1",
            allow_document_fallback=True,
        )

        assert job_id == "documents:1"
        assert session.request.call_count == 2

    @pytest.mark.parametrize(
        "detail",
        [
            "Parquet imports require plain s3://bucket/key paths",
            "Parquet imports require plain s3://bucket/key paths without globbing",
        ],
    )
    def test_ingest_parquet_lab_fallback_on_400_fetch_policy_rejection(
        self, tmp_path: Path, detail: str
    ) -> None:
        """CDS 1.2.0 rejects a local parquet with FetchPolicyError wording."""
        parquet_path = tmp_path / "ingest.parquet"
        table = pa.table(
            {
                "id": ["doc-1"],
                "embedding": [[0.1, 0.2, 0.3]],
                "$meta": [json.dumps({"span_uuid": "u1"})],
            }
        )
        pq.write_table(table, parquet_path)

        session = MagicMock()
        session.request.side_effect = [
            _json_response({"detail": detail}, status_code=400),
            _json_response(
                {
                    "documents": [
                        {"id": "doc-1", "indexed_at": "2026-01-01T00:00:00", "metadata": {}}
                    ]
                }
            ),
        ]
        adapter = DatasetSearchAdapter("http://cds.example", session=session)

        job_id = adapter.ingest_parquet(
            CollectionRef("c1", name="demo"),
            [str(parquet_path)],
            embedding_family="ce1",
            allow_document_fallback=True,
        )

        assert job_id == "documents:1"
        assert session.request.call_count == 2

    def test_ingest_parquet_fails_closed_on_400_with_server_detail(self) -> None:
        session = MagicMock()
        session.request.return_value = _json_response(
            {"detail": "Invalid S3 path format: '/tmp/records.parquet'."},
            status_code=400,
        )
        adapter = DatasetSearchAdapter("http://cds.example", session=session)

        with pytest.raises(BulkIngestUnavailableError, match="Invalid S3 path format"):
            adapter.ingest_parquet(
                CollectionRef("c1"),
                ["/tmp/records.parquet"],
                embedding_family="ce1",
            )

    def test_ingest_parquet_reraises_unrelated_400(self, tmp_path: Path) -> None:
        """An unrelated 400 must stay loud instead of falling back silently."""
        parquet_path = tmp_path / "ingest.parquet"
        pq.write_table(pa.table({"id": ["doc-1"], "embedding": [[0.1]]}), parquet_path)

        session = MagicMock()
        session.request.return_value = _json_response(
            {"detail": "collection_name field required"},
            status_code=400,
        )
        adapter = DatasetSearchAdapter("http://cds.example", session=session)

        with pytest.raises(requests.HTTPError):
            adapter.ingest_parquet(
                CollectionRef("c1", name="demo"),
                [str(parquet_path)],
                embedding_family="ce1",
                allow_document_fallback=True,
            )

        assert session.request.call_count == 1

    def test_ingest_parquet_fallback_rejects_missing_later_embedding(self, tmp_path: Path) -> None:
        parquet_path = tmp_path / "ingest.parquet"
        pq.write_table(
            pa.table(
                {
                    "id": ["doc-1", "doc-2"],
                    "embedding": [[0.1, 0.2], None],
                }
            ),
            parquet_path,
        )
        session = MagicMock()
        session.request.return_value = _json_response({"detail": "missing"}, status_code=404)
        adapter = DatasetSearchAdapter("http://cds.example", session=session)

        with pytest.raises(ValueError, match="row 2 is missing embedding"):
            adapter.ingest_parquet(
                CollectionRef("c1"),
                [str(parquet_path)],
                embedding_family="ce1",
                allow_document_fallback=True,
            )

        assert session.request.call_count == 1

    def test_ingest_parquet_fallback_rejects_remote_paths(self) -> None:
        session = MagicMock()
        session.request.return_value = _json_response({"detail": "missing"}, status_code=404)
        adapter = DatasetSearchAdapter("http://cds.example", session=session)
        with pytest.raises(RuntimeError, match="local parquet"):
            adapter.ingest_parquet(
                CollectionRef("c1"),
                ["s3://bucket/a.parquet"],
                embedding_family="ce1",
                allow_document_fallback=True,
            )

    def test_document_payload_sanitizes_metadata(self) -> None:
        session = MagicMock()
        session.request.return_value = _json_response({"documents": [{"id": "1"}]})
        adapter = DatasetSearchAdapter("http://cds.example", session=session)
        adapter.ingest_documents(
            CollectionRef("c"),
            [
                DocumentSpec(
                    mime_type="application/octet-stream",
                    embedding=[1.0, 2.0],
                    metadata={"ok": "x", "filtered_windows": []},
                )
            ],
        )
        payload = session.request.call_args.kwargs["json"][0]
        assert payload["metadata"] == {"ok": "x"}

    def test_bulk_insert_with_credentials_and_job_status(self):
        session = MagicMock()
        session.request.side_effect = [
            _json_response({"status": "success", "message": "ok", "job_id": "7"}),
            _json_response(
                {
                    "job_id": "7",
                    "status": "completed",
                    "details": "done",
                    "progress": 100,
                    "collection_name": "demo",
                }
            ),
            _json_response(
                {
                    "jobs": [
                        {"job_id": "7", "status": "completed", "details": "done"},
                    ]
                }
            ),
        ]
        adapter = DatasetSearchAdapter("http://cds.example", session=session)
        status = adapter.bulk_insert(
            BulkInsertRequest(
                collection_name="demo",
                parquet_paths=["s3://b/x.parquet"],
                embedding_family="ce1",
                access_key="ak",
                secret_key="sk",
                endpoint_url="http://minio:9000",
                allow_insecure_endpoint=True,
            )
        )
        assert status.job_id == "7"
        assert session.request.call_args.kwargs["json"]["access_key"] == "ak"
        got = adapter.get_job_status("7")
        assert got.status == "completed"
        assert got.progress == 100
        jobs = adapter.list_jobs()
        assert jobs[0].job_id == "7"

    def test_bulk_insert_validation(self):
        adapter = DatasetSearchAdapter("http://cds.example", session=MagicMock())
        with pytest.raises(ValueError, match="parquet_paths"):
            adapter.bulk_insert(
                BulkInsertRequest(
                    collection_name="c",
                    parquet_paths=[],
                    embedding_family="ce1",
                )
            )
        with pytest.raises(ValueError, match="provided together"):
            adapter.bulk_insert(
                BulkInsertRequest(
                    collection_name="c",
                    parquet_paths=["s3://b/x.parquet"],
                    embedding_family="ce1",
                    access_key="only-one",
                )
            )
        with pytest.raises(ValueError, match="lab-only"):
            adapter.bulk_insert(
                BulkInsertRequest(
                    collection_name="c",
                    parquet_paths=["s3://b/x.parquet"],
                    embedding_family="ce1",
                    endpoint_url="http://minio:9000",
                )
            )

    @pytest.mark.parametrize("embedding_family", ["", "iv2", "clip", "siglip", "auto"])
    def test_bulk_insert_rejects_incompatible_family_without_http(
        self,
        embedding_family: str,
    ) -> None:
        session = MagicMock()
        adapter = DatasetSearchAdapter("http://cds.example", session=session)

        with pytest.raises(ValueError, match="requires embedding_family='ce1'"):
            adapter.bulk_insert(
                BulkInsertRequest(
                    collection_name="demo",
                    parquet_paths=["s3://bucket/data.parquet"],
                    embedding_family=embedding_family,
                )
            )

        session.request.assert_not_called()

    def test_ingest_parquet_rejects_incompatible_family_without_http(self) -> None:
        session = MagicMock()
        adapter = DatasetSearchAdapter("http://cds.example", session=session)

        with pytest.raises(ValueError, match="requires embedding_family='ce1'"):
            adapter.ingest_parquet(
                CollectionRef("demo", name="demo"),
                ["s3://bucket/data.parquet"],
                embedding_family="iv2",
            )

        session.request.assert_not_called()

    def test_wait_for_job_returns_terminal_state(self):
        adapter = DatasetSearchAdapter("http://cds.example", session=MagicMock())
        adapter.get_job_status = MagicMock(
            return_value=type(
                "Status",
                (),
                {"status": "completed", "job_id": "7"},
            )()
        )

        status = adapter.wait_for_job("7", sleep=MagicMock())

        assert status.status == "completed"
        adapter.get_job_status.assert_called_once_with("7")

    def test_wait_for_job_times_out_on_nonterminal_state(self):
        adapter = DatasetSearchAdapter("http://cds.example", session=MagicMock())
        adapter.get_job_status = MagicMock(
            return_value=type(
                "Status",
                (),
                {"status": "running", "job_id": "7"},
            )()
        )
        clock = iter([0.0, 1.0])

        with pytest.raises(BulkJobPollingTimeout, match="last status"):
            adapter.wait_for_job(
                "7",
                timeout_seconds=1,
                poll_interval_seconds=0.5,
                monotonic=lambda: next(clock),
                sleep=MagicMock(),
            )

    def test_train_search_refinement_linear_probe(self):
        session = MagicMock()
        session.request.return_value = _json_response({"queries": [{"embedding": [0.1, 0.2, 0.3]}]})
        adapter = DatasetSearchAdapter("http://cds.example", session=session)
        result = adapter.train_search_refinement(
            SearchRefinementSpec(
                grounding_queries=[SearchQuery(text="cat")],
                labels=[
                    LabelledDocuments(
                        collection_name="c1",
                        labelled_documents={"d1": True, "d2": False},
                    )
                ],
            )
        )
        assert result.model_type == "linear_probe"
        assert list(result.queries[0]) == [0.1, 0.2, 0.3]
        payload = session.request.call_args.kwargs["json"]
        assert payload["grounding_queries"][0]["text"] == "cat"
        assert "/search_refinement/train" in session.request.call_args.args[1]

    def test_train_search_refinement_requires_labels(self):
        adapter = DatasetSearchAdapter("http://cds.example", session=MagicMock())
        with pytest.raises(ValueError, match="labels"):
            adapter.train_search_refinement(
                SearchRefinementSpec(grounding_queries=[SearchQuery(text="x")], labels=[])
            )

    @pytest.mark.parametrize(
        ("payload", "message"),
        [
            ("bad", "expected an object"),
            ({"queries": "bad"}, "queries must be a list"),
            ({"queries": [{"unexpected": []}]}, "item 1"),
        ],
    )
    def test_train_search_refinement_rejects_malformed_response(
        self,
        payload: object,
        message: str,
    ):
        session = MagicMock()
        session.request.return_value = _json_response(payload)
        adapter = DatasetSearchAdapter("http://cds.example", session=session)
        spec = SearchRefinementSpec(
            grounding_queries=[SearchQuery(text="cat")],
            labels=[LabelledDocuments(collection_name="c", labelled_documents={"d": True})],
        )

        with pytest.raises(ValueError, match=message):
            adapter.train_search_refinement(spec)

    def test_draw_pipeline_returns_bytes(self):
        session = MagicMock()
        response = MagicMock()
        response.status_code = 200
        response.content = b"\x89PNG"
        response.headers = {"Content-Type": "image/png"}
        response.raise_for_status = MagicMock()
        session.request.return_value = response
        adapter = DatasetSearchAdapter("http://cds.example", session=session)
        data = adapter.draw_pipeline("cosmos_embed", mode="query")
        assert data.startswith(b"\x89PNG")
        assert session.request.call_args.kwargs["params"]["mode"] == "query"

    def test_pipeline_collections_parses_collection_envelopes(self):
        session = MagicMock()
        session.request.return_value = _json_response(
            {
                "collections": [
                    {
                        "collection": {"id": "c1", "name": "traffic", "pipeline": "p"},
                        "total_documents_count": 12,
                    }
                ]
            }
        )
        adapter = DatasetSearchAdapter("http://cds.example", session=session)

        collections = adapter.list_pipeline_collections("p")

        assert collections[0].collection_id == "c1"
        assert collections[0].total_documents_count == 12
        assert session.request.call_args.args[1].endswith("/v1/pipelines/p/collections")

    def test_search_supports_caption_annotation_and_classifier_fields(self):
        session = MagicMock()
        session.request.return_value = _json_response({"retrievals": [{"id": "d1", "score": 0.9}]})
        adapter = DatasetSearchAdapter("http://cds.example", session=session)

        adapter.search(
            CollectionRef("c"),
            SearchQuery(
                caption_query="hard hat",
                top_k=5,
                annotation_labels=("approved",),
                exclude_annotation_labels=("rejected",),
                project_source=("project-1",),
                auto_rewrite=True,
                caption_extra_queries=("helmet",),
                classifier_label="safety",
                probability_expression="p > 0.8",
                clf={"coef": [1.0], "intercept": 0.1},
            ),
        )

        payload = session.request.call_args.kwargs["json"]
        assert "query" not in payload
        assert payload["caption_query"] == "hard hat"
        assert payload["annotation_labels"] == ["approved"]
        assert payload["exclude_annotation_labels"] == ["rejected"]
        assert payload["project_source"] == ["project-1"]
        assert payload["auto_rewrite"] is True
        assert payload["caption_extra_queries"] == ["helmet"]
        assert payload["classifier_label"] == "safety"
        assert payload["probability_expression"] == "p > 0.8"
        assert payload["clf"] == {"coef": [1.0], "intercept": 0.1}

    def test_search_distinguishes_unset_from_empty_caption_extra_queries(self):
        session = MagicMock()
        session.request.return_value = _json_response({"retrievals": []})
        adapter = DatasetSearchAdapter("http://cds.example", session=session)

        adapter.search(CollectionRef("c"), SearchQuery(caption_query="hard hat"))
        assert "caption_extra_queries" not in session.request.call_args.kwargs["json"]

        adapter.search(
            CollectionRef("c"),
            SearchQuery(caption_query="hard hat", caption_extra_queries=()),
        )
        assert session.request.call_args.kwargs["json"]["caption_extra_queries"] == []

    @pytest.mark.parametrize("blank_caption", ["", "   ", "\t", "\n"])
    def test_search_rejects_blank_caption_only_query(self, blank_caption):
        session = MagicMock()
        adapter = DatasetSearchAdapter("http://cds.example", session=session)

        with pytest.raises(ValueError, match="requires exactly one modality"):
            adapter.search(CollectionRef("c"), SearchQuery(caption_query=blank_caption))

        session.request.assert_not_called()

    def test_search_omits_blank_caption_query_alongside_a_modality(self):
        session = MagicMock()
        session.request.return_value = _json_response({"retrievals": []})
        adapter = DatasetSearchAdapter("http://cds.example", session=session)

        adapter.search(CollectionRef("c"), SearchQuery(text="hard hat", caption_query="   "))

        payload = session.request.call_args.kwargs["json"]
        assert payload["query"] == [{"text": "hard hat"}]
        assert "caption_query" not in payload

    def test_caption_annotation_classifier_and_registry_wrappers(self):
        session = MagicMock()
        session.request.side_effect = [
            _json_response({"status": "ok", "clip_id": "clip-1"}),
            _json_response({"enabled": True}),
            _json_response({"annotations": []}),
            _json_response({"annotation": {"id": "a1"}}),
            _json_response({"label": "positive"}),
            _json_response({"datasets": []}),
            _json_response({"project": {"id": "p1"}}),
            _json_response({"queries": [[0.1, 0.2]]}),
        ]
        adapter = DatasetSearchAdapter("http://cds.example", session=session)

        assert adapter.add_caption({"clip_id": "clip-1", "caption": "x"})["clip_id"] == "clip-1"
        assert adapter.caption_rewrite_status()["enabled"] is True
        assert adapter.list_annotations()["annotations"] == []
        assert (
            adapter.create_annotation({"document_id": "d", "label": "x"})["annotation"]["id"]
            == "a1"
        )
        assert adapter.train_classifier("c", {"positive_label": "x"})["label"] == "positive"
        assert adapter.list_datasets()["datasets"] == []
        assert adapter.create_project({"name": "p", "collection_ids": []})["project"]["id"] == "p1"
        assert adapter.linear_probe({"grounding_queries": [], "labels": []})["queries"] == [
            [0.1, 0.2]
        ]

        calls = [call.args[:2] for call in session.request.call_args_list]
        assert ("POST", "http://cds.example/v1/captions/") in calls
        assert ("GET", "http://cds.example/v1/captions/rewrite/status") in calls
        assert ("GET", "http://cds.example/v1/annotations") in calls
        assert ("POST", "http://cds.example/v1/collections/c/classifiers") in calls
        assert ("GET", "http://cds.example/v1/datasets") in calls
        assert ("POST", "http://cds.example/v1/projects") in calls
        assert ("POST", "http://cds.example/v1/linear_probe") in calls

    def test_project_export_and_metrics_use_expected_content_paths(self):
        session = MagicMock()
        csv_response = MagicMock(
            status_code=200,
            content=b"id,score\n1,0.9\n",
            text="id,score\n1,0.9\n",
            headers={"Content-Type": "text/csv"},
            raise_for_status=MagicMock(),
        )
        metrics_response = MagicMock(
            status_code=200,
            content=b"cds_search_total 1\n",
            text="cds_search_total 1\n",
            headers={"Content-Type": "text/plain"},
            raise_for_status=MagicMock(),
        )
        session.request.side_effect = [csv_response, metrics_response]
        adapter = DatasetSearchAdapter("http://cds.example", session=session)

        assert adapter.export_project_csv("p1").startswith(b"id,score")
        assert adapter.cds_metrics().startswith(b"cds_search_total")

        assert session.request.call_args_list[0].args[1].endswith("/v1/projects/p1/export")
        assert session.request.call_args_list[1].args[1] == "http://cds.example/cds_metrics"
