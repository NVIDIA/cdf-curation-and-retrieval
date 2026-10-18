# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Dataset Search retrieval adapter — HTTP client over the CVDS / CDS API.

Exposes the full standalone Dataset Search (CVDS) surface used by CDF:

- Collections CRUD + admin flush
- Pipelines list / draw
- Multimodal search + multi-collection retrieval
- Document ingest / delete
- Bulk parquet insert + job status
- Search refinement training
- Health

Does not reimplement Milvus or Haystack. Does not expose DataScout-only APIs.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import requests

from adapters.dataset_search.common import (
    TERMINAL_JOB_STATES,
    BulkIngestUnavailableError,
    BulkJobPollingTimeout,
    normalize_cds_base_url,
    validate_cds_embedding_family,
)
from adapters.dataset_search.mappers import (
    document_payload as _document_payload,
)
from adapters.dataset_search.mappers import (
    document_specs_from_cds_parquet as _document_specs_from_cds_parquet,
)
from adapters.dataset_search.mappers import (
    parse_collection as _parse_collection,
)
from adapters.dataset_search.mappers import (
    parse_hits as _parse_hits,
)
from adapters.dataset_search.mappers import (
    query_payload as _query_payload,
)
from adapters.dataset_search.mappers import (
    sanitize_document_metadata,
)
from adapters.dataset_search.mappers import (
    search_request_body as _search_request_body,
)
from adapters.object_store import validate_s3_endpoint
from packages.domain.types import (
    BulkInsertRequest,
    BulkJobStatus,
    CollectionCreateSpec,
    CollectionInfo,
    CollectionPatchSpec,
    CollectionRef,
    DocumentInfo,
    DocumentSpec,
    EmbeddingRecord,
    MultiCollectionQuery,
    PipelineInfo,
    SearchHit,
    SearchQuery,
    SearchRefinementResult,
    SearchRefinementSpec,
)

__all__ = [
    "BulkIngestUnavailableError",
    "BulkJobPollingTimeout",
    "DatasetSearchAdapter",
    "normalize_cds_base_url",
    "sanitize_document_metadata",
    "validate_cds_embedding_family",
]

# Builds disagree on how they reject a parquet path they cannot read. 1.0.0 and
# the prerelease resolve the collection and open the file first, so a host path
# the container cannot see comes back 404 ("File not found" / "Collection not
# found"); they only reach 400 "Invalid S3 path format" when the file is
# readable but is not an s3:// URI. 1.2.0 validates up front instead and returns
# 400 "Parquet imports require plain s3://bucket/key paths[ without globbing]"
# for any non-s3 path. All of them mean the local parquet is unreachable, which
# is what the document fallback exists for.
_UNREADABLE_PARQUET_MARKERS = (
    "file not found",
    "collection not found",
    "s3 path",
    "parquet imports require",
)


def _http_detail(response: requests.Response) -> str:
    """Best-effort FastAPI ``detail`` string, falling back to the raw body."""
    try:
        body = response.json()
    except ValueError:
        return str(response.text).strip()[:200]
    if isinstance(body, dict) and "detail" in body:
        return str(body["detail"])
    return str(body)[:200]


def _is_unreadable_parquet_error(response: requests.Response) -> bool:
    """True when CDS rejected the request because it cannot read the parquet.

    A 400 is only treated this way when the message names the path, so genuine
    payload rejections (bad embedding family, missing field) still raise.
    """
    if response.status_code == 404:
        return True
    if response.status_code != 400:
        return False
    detail = _http_detail(response).lower()
    return any(marker in detail for marker in _UNREADABLE_PARQUET_MARKERS)


class DatasetSearchAdapter:
    """Full CVDS client implementing retrieval, collection admin, ingest, and refinement."""

    def __init__(self, base_url: str, session: requests.Session | None = None) -> None:
        self._base_url = normalize_cds_base_url(base_url)
        self._session = session or requests.Session()

    @property
    def base_url(self) -> str:
        """Normalized API root including ``/v1``."""
        return self._base_url

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{self._base_url}{path}"

    def _root_url(self, path: str) -> str:
        if not path.startswith("/"):
            path = f"/{path}"
        root = self._base_url
        if root.endswith("/v1"):
            root = root[: -len("/v1")]
        return f"{root}{path}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: Mapping[str, Any] | None = None,
        timeout: float = 120,
        expect_json: bool = True,
    ) -> Any:
        response = self._session.request(
            method,
            self._url(path),
            json=json,
            params=dict(params) if params else None,
            timeout=timeout,
        )
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return None
        if not expect_json:
            return response.content
        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type or response.text[:1] in ("{", "["):
            return response.json()
        return response.text

    def _request_root(
        self,
        method: str,
        path: str,
        *,
        timeout: float = 60,
        expect_json: bool = False,
    ) -> Any:
        response = self._session.request(method, self._root_url(path), timeout=timeout)
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return None
        if not expect_json:
            return response.content if isinstance(response.content, bytes) else response.text
        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type or response.text[:1] in ("{", "["):
            return response.json()
        return response.text

    # ------------------------------------------------------------------ health

    def health(self) -> str:
        """GET /health at the service root (not under ``/v1``).

        Public blueprint docs and the container HEALTHCHECK use ``/health``.
        ``/v1/health`` may also work on some builds; prefer the root path.
        """
        root = self._base_url
        if root.endswith("/v1"):
            root = root[: -len("/v1")]
        response = self._session.request("GET", f"{root}/health", timeout=30)
        response.raise_for_status()
        if "application/json" in response.headers.get("Content-Type", ""):
            body = response.json()
            return str(body)
        return str(response.text).strip().strip('"')

    # -------------------------------------------------------------- pipelines

    def list_pipelines(self) -> Sequence[PipelineInfo]:
        """GET /pipelines."""
        body = self._request("GET", "/pipelines", timeout=60)
        if not isinstance(body, (dict, list)):
            raise ValueError("Unexpected pipelines response: expected an object or list")
        pipelines = body.get("pipelines", body) if isinstance(body, dict) else body
        result: list[PipelineInfo] = []
        for item in pipelines or []:
            if isinstance(item, str):
                result.append(PipelineInfo(pipeline_id=item, name=item))
                continue
            if not isinstance(item, dict):
                raise ValueError("Unexpected pipelines response item: expected a string or object")
            pid = str(item.get("id", item.get("name", item.get("pipeline_id", ""))))
            if not pid:
                raise ValueError("Unexpected pipelines response item: missing id")
            result.append(
                PipelineInfo(
                    pipeline_id=pid,
                    name=item.get("name"),
                    description=item.get("description"),
                    raw=dict(item),
                )
            )
        return result

    def draw_pipeline(self, name: str, mode: str = "index") -> bytes:
        """GET /pipelines/draw/{name}."""
        if not name:
            raise ValueError("pipeline name is required")
        content = self._request(
            "GET",
            f"/pipelines/draw/{name}",
            params={"mode": mode},
            timeout=120,
            expect_json=False,
        )
        return content if isinstance(content, (bytes, bytearray)) else bytes(content or b"")

    def list_pipeline_collections(self, pipeline_id: str) -> Sequence[CollectionInfo]:
        """GET /pipelines/{pipeline_id}/collections."""
        if not pipeline_id:
            raise ValueError("pipeline_id is required")
        body = self._request("GET", f"/pipelines/{pipeline_id}/collections", timeout=120)
        if not isinstance(body, dict):
            raise ValueError("Unexpected pipeline-collections response: expected an object")
        items = body.get("collections", [])
        if not isinstance(items, list):
            raise ValueError("Unexpected pipeline-collections response: collections must be a list")
        collections: list[CollectionInfo] = []
        for item_number, item in enumerate(items, start=1):
            if not isinstance(item, Mapping):
                raise ValueError(
                    f"Unexpected pipeline-collections response item {item_number}: expected object"
                )
            raw = item.get("collection", item)
            if not isinstance(raw, Mapping):
                raise ValueError(
                    f"Unexpected pipeline-collections response item {item_number}: missing collection"
                )
            collections.append(_parse_collection(raw, total=item.get("total_documents_count")))
        return collections

    # ------------------------------------------------------------- collections

    def list_collections(self) -> Sequence[CollectionInfo]:
        """GET /collections."""
        body = self._request("GET", "/collections", timeout=60)
        if not isinstance(body, dict):
            raise ValueError("Unexpected collections response: expected an object")
        collections = body.get("collections", [])
        if not isinstance(collections, list):
            raise ValueError("Unexpected collections response: collections must be a list")
        result: list[CollectionInfo] = []
        for item_number, collection in enumerate(collections, start=1):
            if not isinstance(collection, Mapping):
                raise ValueError(
                    f"Unexpected collections response item {item_number}: expected an object"
                )
            if not collection.get("id", collection.get("collection_id")):
                raise ValueError(f"Unexpected collections response item {item_number}: missing id")
            result.append(_parse_collection(collection))
        return result

    def get_collection(self, collection_id: str) -> CollectionInfo:
        """GET /collections/{id} (info envelope when available)."""
        if not collection_id:
            raise ValueError("collection_id is required")
        body = self._request("GET", f"/collections/{collection_id}", timeout=60)
        if not isinstance(body, dict):
            raise ValueError("Unexpected collection response")
        raw = body.get("collection", body)
        total = body.get("total_documents_count")
        return _parse_collection(raw, total=total)

    def create_collection(self, spec: CollectionCreateSpec) -> CollectionInfo:
        """POST /collections."""
        if not spec.name or not spec.pipeline:
            raise ValueError("CollectionCreateSpec requires name and pipeline")
        payload: dict[str, Any] = {
            "name": spec.name,
            "pipeline": spec.pipeline,
            "tags": dict(spec.tags),
            "collection_config": dict(spec.collection_config),
            "index_config": dict(spec.index_config),
            "metadata_config": dict(spec.metadata_config) or {"allow_dynamic_schema": True},
        }
        params = {"id": spec.collection_id} if spec.collection_id else None
        body = self._request("POST", "/collections", json=payload, params=params, timeout=120)
        raw = body.get("collection", body) if isinstance(body, dict) else body
        return _parse_collection(raw)

    def update_collection(self, collection_id: str, patch: CollectionPatchSpec) -> CollectionInfo:
        """PATCH /collections/{id}."""
        if not collection_id:
            raise ValueError("collection_id is required")
        if patch.name is None and patch.tags is None:
            raise ValueError("CollectionPatchSpec requires name and/or tags")
        payload: dict[str, Any] = {}
        if patch.name is not None:
            payload["name"] = patch.name
        if patch.tags is not None:
            payload["tags"] = dict(patch.tags)
        body = self._request("PATCH", f"/collections/{collection_id}", json=payload, timeout=60)
        raw = body.get("collection", body) if isinstance(body, dict) else body
        return _parse_collection(raw)

    def delete_collection(self, collection_id: str) -> None:
        """DELETE /collections/{id}."""
        if not collection_id:
            raise ValueError("collection_id is required")
        self._request("DELETE", f"/collections/{collection_id}", timeout=120)

    def flush_collection(self, collection_id: str) -> Mapping[str, Any]:
        """POST /admin/collections/{id}/flush."""
        if not collection_id:
            raise ValueError("collection_id is required")
        body = self._request("POST", f"/admin/collections/{collection_id}/flush", timeout=300)
        return dict(body) if isinstance(body, dict) else {"result": body}

    # ----------------------------------------------------------------- search

    def search(self, collection: CollectionRef, query: SearchQuery) -> Sequence[SearchHit]:
        """POST /collections/{id}/search."""
        if not collection.collection_id:
            raise ValueError("collection_id is required")
        body = self._request(
            "POST",
            f"/collections/{collection.collection_id}/search",
            json=_search_request_body(query),
            timeout=120,
        )
        return _parse_hits(body)

    def multi_collection_search(self, request: MultiCollectionQuery) -> Sequence[SearchHit]:
        """POST /retrieval across multiple collections."""
        if not request.collection_ids:
            raise ValueError("collection_ids must be non-empty")
        q = request.query
        payload: dict[str, Any] = {
            "collections": list(request.collection_ids),
            "query": _query_payload(q),
            "params": {
                "nb_neighbors": q.top_k,
                "search_params": dict(q.search_params),
                "filters": (dict(q.filters) if isinstance(q.filters, Mapping) else q.filters)
                if q.filters
                else {},
                "reconstruct": q.reconstruct,
            },
            "generate_asset_url": request.generate_asset_url,
            "rerank": request.rerank,
        }
        if request.payload_keys is not None:
            payload["payload_keys"] = list(request.payload_keys)
        body = self._request("POST", "/retrieval", json=payload, timeout=180)
        return _parse_hits(body)

    def export_embeddings(self, collection: CollectionRef) -> Sequence[EmbeddingRecord]:
        """Best-effort export via document listing if the deployment exposes it.

        Standalone CVDS does not guarantee a documents GET list; callers should
        prefer reconstruct=True search or parquet export when available.
        """
        if not collection.collection_id:
            raise ValueError("collection_id is required")
        body = self._request(
            "GET",
            f"/collections/{collection.collection_id}/documents",
            timeout=300,
        )
        docs = body if isinstance(body, list) else (body or {}).get("documents", [])
        records: list[EmbeddingRecord] = []
        for doc in docs or []:
            if not isinstance(doc, dict):
                continue
            emb = doc.get("embedding")
            if emb is None:
                continue
            records.append(
                EmbeddingRecord(
                    record_id=str(doc.get("id", "")),
                    embedding=list(emb),
                    metadata=dict(doc.get("meta", doc.get("metadata", {})) or {}),
                )
            )
        return records

    # --------------------------------------------------------------- documents

    def ingest_documents(
        self, collection: CollectionRef, documents: Sequence[DocumentSpec]
    ) -> Sequence[DocumentInfo]:
        """POST /collections/{id}/documents."""
        if not collection.collection_id:
            raise ValueError("collection_id is required")
        if not documents:
            raise ValueError("documents must be non-empty")
        payload = [_document_payload(d) for d in documents]
        body = self._request(
            "POST",
            f"/collections/{collection.collection_id}/documents",
            json=payload,
            timeout=600,
        )
        if isinstance(body, dict):
            docs = body.get("documents", [])
        elif isinstance(body, list):
            docs = body
        else:
            raise ValueError("Unexpected document-ingest response: expected an object or list")
        if not isinstance(docs, list):
            raise ValueError("Unexpected document-ingest response: documents must be a list")
        result: list[DocumentInfo] = []
        for item_number, doc in enumerate(docs, start=1):
            if not isinstance(doc, dict):
                raise ValueError(
                    f"Unexpected document-ingest response item {item_number}: expected an object"
                )
            if not doc.get("id"):
                raise ValueError(
                    f"Unexpected document-ingest response item {item_number}: missing id"
                )
            result.append(
                DocumentInfo(
                    document_id=str(doc.get("id", "")),
                    metadata=dict(doc.get("metadata") or {}),
                    indexed_at=(
                        str(doc["indexed_at"]) if doc.get("indexed_at") is not None else None
                    ),
                )
            )
        return result

    def delete_document(self, collection: CollectionRef, document_id: str) -> None:
        """DELETE /collections/{id}/documents/{document_id}."""
        if not collection.collection_id or not document_id:
            raise ValueError("collection_id and document_id are required")
        self._request(
            "DELETE",
            f"/collections/{collection.collection_id}/documents/{document_id}",
            timeout=120,
        )

    def delete_documents_by_filter(
        self, collection: CollectionRef, filters: Mapping[str, Any]
    ) -> None:
        """DELETE /collections/{id}/documents with filter body."""
        if not collection.collection_id:
            raise ValueError("collection_id is required")
        if not filters:
            raise ValueError("filters must be non-empty")
        self._request(
            "DELETE",
            f"/collections/{collection.collection_id}/documents",
            json=dict(filters),
            timeout=300,
        )

    # ------------------------------------------------------------------- bulk

    def ingest_parquet(
        self,
        collection: CollectionRef,
        parquet_paths: Sequence[str],
        *,
        embedding_family: str,
        allow_document_fallback: bool = False,
    ) -> str:
        """Ingest CDS-shaped parquet into a collection.

        Use ``POST /insert-data`` by default. The document path is a lab-only
        compatibility fallback and must be opted into explicitly.
        """
        try:
            status = self.bulk_insert(
                BulkInsertRequest(
                    collection_name=collection.name or collection.collection_id,
                    parquet_paths=list(parquet_paths),
                    embedding_family=embedding_family,
                )
            )
            return status.job_id
        except requests.HTTPError as exc:
            response = exc.response
            if response is None or not _is_unreadable_parquet_error(response):
                raise
            if not allow_document_fallback:
                raise BulkIngestUnavailableError(
                    "CDS bulk ingest is unavailable (POST /insert-data returned HTTP "
                    f"{response.status_code}: {_http_detail(response)}); "
                    "document fallback is disabled by default"
                ) from exc
            return self._ingest_parquet_via_documents(collection, parquet_paths)

    def _ingest_parquet_via_documents(
        self, collection: CollectionRef, parquet_paths: Sequence[str]
    ) -> str:
        """GA fallback when ``/insert-data`` is unavailable."""
        if not collection.collection_id and not collection.name:
            raise ValueError("collection_id or name is required for document ingest fallback")
        collection_id = collection.collection_id or collection.name
        assert collection_id is not None

        docs: list[DocumentSpec] = []
        for path in parquet_paths:
            path_str = str(path)
            if path_str.startswith(("s3://", "http://", "https://")):
                raise RuntimeError(
                    "CDS POST /insert-data is unavailable (HTTP 404). "
                    "Document-ingest fallback only supports local parquet paths; "
                    f"got remote path: {path_str}"
                )
            docs.extend(_document_specs_from_cds_parquet(path_str))
        if not docs:
            raise ValueError("No embedding rows found in parquet for document ingest fallback")

        # Batch in chunks to keep request bodies reasonable.
        chunk_size = 32
        for i in range(0, len(docs), chunk_size):
            self.ingest_documents(
                CollectionRef(collection_id=collection_id, name=collection.name),
                docs[i : i + chunk_size],
            )
        return f"documents:{len(docs)}"

    def bulk_insert(self, request: BulkInsertRequest) -> BulkJobStatus:
        """POST /insert-data after fail-closed embedding-family validation."""
        validate_cds_embedding_family(request.embedding_family)
        if not request.collection_name:
            raise ValueError("collection_name is required")
        if not request.parquet_paths:
            raise ValueError("parquet_paths must be non-empty")
        if any(not str(path).strip() for path in request.parquet_paths):
            raise ValueError("parquet_paths must not contain empty values")
        if bool(request.access_key) != bool(request.secret_key):
            raise ValueError("access_key and secret_key must be provided together")
        validate_s3_endpoint(
            request.endpoint_url,
            allow_insecure=request.allow_insecure_endpoint,
        )
        payload: dict[str, Any] = {
            "collection_name": request.collection_name,
            "parquet_paths": list(request.parquet_paths),
        }
        if request.access_key is not None:
            payload["access_key"] = request.access_key
        if request.secret_key is not None:
            payload["secret_key"] = request.secret_key
        if request.endpoint_url is not None:
            payload["endpoint_url"] = request.endpoint_url
        body = self._request("POST", "/insert-data", json=payload, timeout=600)
        body = body if isinstance(body, dict) else {}
        status = BulkJobStatus(
            job_id=str(body.get("job_id", "")),
            status=str(body.get("status", "accepted")),
            details=str(body.get("message", "")),
            raw=dict(body),
        )
        if not status.job_id:
            raise ValueError("CDS bulk-insert response did not include a job_id")
        return status

    def get_job_status(self, job_id: str) -> BulkJobStatus:
        """GET /job-status/{job_id}."""
        if not job_id:
            raise ValueError("job_id is required")
        body = self._request("GET", f"/job-status/{job_id}", timeout=60)
        body = body if isinstance(body, dict) else {}
        return BulkJobStatus(
            job_id=str(body.get("job_id", job_id)),
            status=str(body.get("status", "unknown")),
            details=str(body.get("details", "")),
            progress=body.get("progress"),
            collection_name=body.get("collection_name"),
            raw=dict(body),
        )

    def wait_for_job(
        self,
        job_id: str,
        *,
        timeout_seconds: float = 900,
        poll_interval_seconds: float = 5,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> BulkJobStatus:
        """Poll the idempotent status endpoint until CDS reports a terminal state."""
        if not job_id:
            raise ValueError("job_id is required")
        if timeout_seconds < 0:
            raise ValueError("timeout_seconds must be non-negative")
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive")

        deadline = monotonic() + timeout_seconds
        last_status = "unknown"
        while True:
            try:
                status = self.get_job_status(job_id)
                last_status = status.status.strip().lower()
                if last_status in TERMINAL_JOB_STATES:
                    return status
            except requests.RequestException as exc:
                response = getattr(exc, "response", None)
                if response is not None and response.status_code < 500:
                    raise
            now = monotonic()
            if now >= deadline:
                raise BulkJobPollingTimeout(
                    f"Timed out waiting for CDS job {job_id!r}; last status was {last_status!r}"
                )
            sleep(min(poll_interval_seconds, max(0.0, deadline - now)))

    def list_jobs(self) -> Sequence[BulkJobStatus]:
        """GET /jobs."""
        body = self._request("GET", "/jobs", timeout=60)
        if isinstance(body, dict):
            jobs = body.get("jobs", body.get("items", []))
        elif isinstance(body, list):
            jobs = body
        else:
            raise ValueError("Unexpected jobs response: expected an object or list")
        if not isinstance(jobs, list):
            raise ValueError("Unexpected jobs response: jobs must be a list")
        result: list[BulkJobStatus] = []
        for item_number, job in enumerate(jobs, start=1):
            if not isinstance(job, dict):
                raise ValueError(f"Unexpected jobs response item {item_number}: expected an object")
            if not job.get("job_id"):
                raise ValueError(f"Unexpected jobs response item {item_number}: missing job_id")
            result.append(
                BulkJobStatus(
                    job_id=str(job.get("job_id", "")),
                    status=str(job.get("status", "unknown")),
                    details=str(job.get("details", "")),
                    progress=job.get("progress"),
                    collection_name=job.get("collection_name"),
                    raw=dict(job),
                )
            )
        return result

    # ------------------------------------------------------------ EA captions

    def add_caption(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        """POST /captions/ for one caption row."""
        if not payload:
            raise ValueError("caption payload is required")
        body = self._request("POST", "/captions/", json=dict(payload), timeout=120)
        return dict(body) if isinstance(body, dict) else {"result": body}

    def get_captions(self, clip_id: str, *, model_name: str | None = None) -> Mapping[str, Any]:
        """GET /captions/{clip_id}."""
        if not clip_id:
            raise ValueError("clip_id is required")
        params = {"model_name": model_name} if model_name else None
        body = self._request("GET", f"/captions/{clip_id}", params=params, timeout=60)
        return dict(body) if isinstance(body, dict) else {"result": body}

    def search_captions(
        self,
        query: str,
        *,
        limit: int = 5000,
        data_sources: Sequence[str] | None = None,
        extra_queries: Sequence[str] | None = None,
    ) -> Mapping[str, Any]:
        """POST /captions/search for EA caption keyword search."""
        if not query:
            raise ValueError("query is required")
        payload: dict[str, Any] = {"query": query, "limit": limit}
        if data_sources:
            payload["data_sources"] = list(data_sources)
        if extra_queries:
            payload["extra_queries"] = list(extra_queries)
        body = self._request("POST", "/captions/search", json=payload, timeout=120)
        return dict(body) if isinstance(body, dict) else {"result": body}

    def caption_stats(self) -> Mapping[str, Any]:
        """GET /captions/stats."""
        body = self._request("GET", "/captions/stats", timeout=60)
        return dict(body) if isinstance(body, dict) else {"result": body}

    def rewrite_caption_query(self, query: str, *, num_rewrites: int = 3) -> Mapping[str, Any]:
        """POST /captions/rewrite."""
        if not query:
            raise ValueError("query is required")
        body = self._request(
            "POST",
            "/captions/rewrite",
            json={"query": query, "num_rewrites": num_rewrites},
            timeout=120,
        )
        return dict(body) if isinstance(body, dict) else {"result": body}

    def caption_rewrite_status(self) -> Mapping[str, Any]:
        """GET /captions/rewrite/status."""
        body = self._request("GET", "/captions/rewrite/status", timeout=60)
        return dict(body) if isinstance(body, dict) else {"result": body}

    # ---------------------------------------------------------- EA annotations

    def list_annotations(
        self,
        *,
        document_ids: Sequence[str] | None = None,
        project_id: str | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> Mapping[str, Any]:
        """GET /annotations."""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if document_ids:
            params["document_ids"] = list(document_ids)
        if project_id:
            params["project_id"] = project_id
        body = self._request("GET", "/annotations", params=params, timeout=120)
        return dict(body) if isinstance(body, dict) else {"result": body}

    def list_annotation_labels(
        self, collection_id: str, *, project_id: str | None = None
    ) -> Mapping[str, Any]:
        """GET /annotations/labels."""
        if not collection_id:
            raise ValueError("collection_id is required")
        params = {"collection_id": collection_id}
        if project_id:
            params["project_id"] = project_id
        body = self._request("GET", "/annotations/labels", params=params, timeout=120)
        return dict(body) if isinstance(body, dict) else {"result": body}

    def create_annotation(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        """POST /annotations."""
        return self._post_mapping("/annotations", payload)

    def create_annotations_batch(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        """POST /annotations/batch."""
        return self._post_mapping("/annotations/batch", payload)

    def rename_annotation_label(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        """PUT /annotations/labels."""
        return self._put_mapping("/annotations/labels", payload)

    def update_annotation(
        self, annotation_id: str, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """PATCH /annotations/{annotation_id}."""
        if not annotation_id:
            raise ValueError("annotation_id is required")
        return self._patch_mapping(f"/annotations/{annotation_id}", payload)

    def delete_annotation_label(self, collection_id: str, label: str) -> Mapping[str, Any]:
        """DELETE /annotations/labels."""
        if not collection_id or not label:
            raise ValueError("collection_id and label are required")
        body = self._request(
            "DELETE",
            "/annotations/labels",
            params={"collection_id": collection_id, "label": label},
            timeout=120,
        )
        return dict(body) if isinstance(body, dict) else {"result": body}

    def merge_annotation_labels(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        """POST /annotations/merge."""
        return self._post_mapping("/annotations/merge", payload)

    def upload_annotations(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        """POST /annotations/upload."""
        return self._post_mapping("/annotations/upload", payload)

    def verify_annotation(self, annotation_id: str) -> Mapping[str, Any]:
        """POST /annotations/{annotation_id}/verify."""
        if not annotation_id:
            raise ValueError("annotation_id is required")
        body = self._request("POST", f"/annotations/{annotation_id}/verify", timeout=120)
        return dict(body) if isinstance(body, dict) else {"result": body}

    def delete_annotation(self, annotation_id: str) -> Mapping[str, Any]:
        """DELETE /annotations/{annotation_id}."""
        if not annotation_id:
            raise ValueError("annotation_id is required")
        body = self._request("DELETE", f"/annotations/{annotation_id}", timeout=120)
        return dict(body) if isinstance(body, dict) else {"result": body}

    def annotate_batch_by_search(
        self, collection_id: str, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """POST /collections/{collection_id}/annotations/batch-by-search."""
        if not collection_id:
            raise ValueError("collection_id is required")
        return self._post_mapping(
            f"/collections/{collection_id}/annotations/batch-by-search", payload
        )

    # ----------------------------------------------------------- EA classifiers

    def train_classifier(self, collection_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        """POST /collections/{collection_id}/classifiers."""
        if not collection_id:
            raise ValueError("collection_id is required")
        return self._post_mapping(f"/collections/{collection_id}/classifiers", payload)

    def list_classifiers(self, collection_id: str) -> Mapping[str, Any]:
        """GET /collections/{collection_id}/classifiers."""
        if not collection_id:
            raise ValueError("collection_id is required")
        body = self._request("GET", f"/collections/{collection_id}/classifiers", timeout=120)
        return dict(body) if isinstance(body, dict) else {"result": body}

    def export_classifier(self, collection_id: str, label: str) -> Mapping[str, Any]:
        """GET /collections/{collection_id}/classifiers/{label}/export."""
        if not collection_id or not label:
            raise ValueError("collection_id and label are required")
        body = self._request(
            "GET",
            f"/collections/{collection_id}/classifiers/{label}/export",
            timeout=120,
        )
        return dict(body) if isinstance(body, dict) else {"result": body}

    def delete_classifier(self, collection_id: str, label: str) -> Mapping[str, Any]:
        """DELETE /collections/{collection_id}/classifiers/{label}."""
        if not collection_id or not label:
            raise ValueError("collection_id and label are required")
        body = self._request(
            "DELETE",
            f"/collections/{collection_id}/classifiers/{label}",
            timeout=120,
        )
        return dict(body) if isinstance(body, dict) else {"result": body}

    # ------------------------------------------------------ EA datasets/projects

    def list_datasets(self) -> Mapping[str, Any]:
        """GET /datasets."""
        body = self._request("GET", "/datasets", timeout=120)
        return dict(body) if isinstance(body, dict) else {"result": body}

    def get_dataset(self, dataset_id: str) -> Mapping[str, Any]:
        """GET /datasets/{dataset_id}."""
        if not dataset_id:
            raise ValueError("dataset_id is required")
        body = self._request("GET", f"/datasets/{dataset_id}", timeout=120)
        return dict(body) if isinstance(body, dict) else {"result": body}

    def create_dataset(
        self, payload: Mapping[str, Any], *, dataset_id: str | None = None
    ) -> Mapping[str, Any]:
        """POST /datasets."""
        params = {"id": dataset_id} if dataset_id else None
        return self._post_mapping("/datasets", payload, params=params)

    def update_dataset(self, dataset_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        """PATCH /datasets/{dataset_id}."""
        if not dataset_id:
            raise ValueError("dataset_id is required")
        return self._patch_mapping(f"/datasets/{dataset_id}", payload)

    def delete_dataset(self, dataset_id: str) -> Mapping[str, Any]:
        """DELETE /datasets/{dataset_id}."""
        if not dataset_id:
            raise ValueError("dataset_id is required")
        body = self._request("DELETE", f"/datasets/{dataset_id}", timeout=120)
        return dict(body) if isinstance(body, dict) else {"result": body}

    def list_projects(self) -> Mapping[str, Any]:
        """GET /projects."""
        body = self._request("GET", "/projects", timeout=120)
        return dict(body) if isinstance(body, dict) else {"result": body}

    def get_project(self, project_id: str) -> Mapping[str, Any]:
        """GET /projects/{project_id}."""
        if not project_id:
            raise ValueError("project_id is required")
        body = self._request("GET", f"/projects/{project_id}", timeout=120)
        return dict(body) if isinstance(body, dict) else {"result": body}

    def create_project(
        self, payload: Mapping[str, Any], *, project_id: str | None = None
    ) -> Mapping[str, Any]:
        """POST /projects."""
        params = {"id": project_id} if project_id else None
        return self._post_mapping("/projects", payload, params=params)

    def update_project(self, project_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        """PATCH /projects/{project_id}."""
        if not project_id:
            raise ValueError("project_id is required")
        return self._patch_mapping(f"/projects/{project_id}", payload)

    def save_project_documents(
        self, project_id: str, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """POST /projects/{project_id}/documents."""
        if not project_id:
            raise ValueError("project_id is required")
        return self._post_mapping(f"/projects/{project_id}/documents", payload)

    def export_project_csv(self, project_id: str) -> bytes:
        """GET /projects/{project_id}/export."""
        if not project_id:
            raise ValueError("project_id is required")
        content = self._request(
            "GET",
            f"/projects/{project_id}/export",
            timeout=120,
            expect_json=False,
        )
        return content if isinstance(content, (bytes, bytearray)) else str(content or "").encode()

    def delete_project(self, project_id: str) -> Mapping[str, Any]:
        """DELETE /projects/{project_id}."""
        if not project_id:
            raise ValueError("project_id is required")
        body = self._request("DELETE", f"/projects/{project_id}", timeout=120)
        return dict(body) if isinstance(body, dict) else {"result": body}

    # ------------------------------------------------------- EA misc/telemetry

    def linear_probe(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        """POST /linear_probe (deprecated upstream but still part of EA route surface)."""
        return self._post_mapping("/linear_probe", payload)

    def metrics(self) -> bytes:
        """GET /metrics at the service root."""
        content = self._request_root("GET", "/metrics", timeout=60)
        return content if isinstance(content, (bytes, bytearray)) else str(content or "").encode()

    def cds_metrics(self) -> bytes:
        """GET /cds_metrics at the service root."""
        content = self._request_root("GET", "/cds_metrics", timeout=60)
        return content if isinstance(content, (bytes, bytearray)) else str(content or "").encode()

    def _post_mapping(
        self,
        path: str,
        payload: Mapping[str, Any],
        *,
        params: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        if not payload:
            raise ValueError("JSON payload is required")
        body = self._request("POST", path, json=dict(payload), params=params, timeout=300)
        return dict(body) if isinstance(body, dict) else {"result": body}

    def _put_mapping(self, path: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        if not payload:
            raise ValueError("JSON payload is required")
        body = self._request("PUT", path, json=dict(payload), timeout=300)
        return dict(body) if isinstance(body, dict) else {"result": body}

    def _patch_mapping(self, path: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        if not payload:
            raise ValueError("JSON payload is required")
        body = self._request("PATCH", path, json=dict(payload), timeout=300)
        return dict(body) if isinstance(body, dict) else {"result": body}

    # --------------------------------------------------------- refinement

    def train_search_refinement(self, spec: SearchRefinementSpec) -> SearchRefinementResult:
        """POST /search_refinement/train."""
        if not spec.grounding_queries:
            raise ValueError("grounding_queries must be non-empty")
        if not spec.labels:
            raise ValueError("labels must be non-empty")
        payload = {
            "model_type": spec.model_type,
            "grounding_queries": [_query_payload(q) for q in spec.grounding_queries],
            "labels": [
                {
                    "collection_name": label.collection_name,
                    "labelled_documents": dict(label.labelled_documents),
                }
                for label in spec.labels
            ],
            "regularization_strength": spec.regularization_strength,
        }
        body = self._request("POST", "/search_refinement/train", json=payload, timeout=600)
        if not isinstance(body, dict):
            raise ValueError("Unexpected search-refinement response: expected an object")
        query_items = body.get("queries", [])
        if not isinstance(query_items, list):
            raise ValueError("Unexpected search-refinement response: queries must be a list")
        queries: list[list[float]] = []
        for item_number, item in enumerate(query_items, start=1):
            if isinstance(item, dict) and "embedding" in item:
                queries.append(list(item["embedding"]))
            elif isinstance(item, (list, tuple)):
                queries.append(list(item))
            else:
                raise ValueError(
                    f"Unexpected search-refinement response item {item_number}: "
                    "expected an embedding object or list"
                )
        weights = body.get("weights") or {}
        return SearchRefinementResult(
            model_type=spec.model_type,
            queries=tuple(queries),
            coef=weights.get("coef"),
            intercept=weights.get("intercept"),
            raw=dict(body),
        )
