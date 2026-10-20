# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Dataset Search (CVDS) CLI commands — full standalone retrieval surface."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click

from adapters.dataset_search.retrieval_adapter import (
    BulkJobPollingTimeout,
    DatasetSearchAdapter,
)
from adapters.object_store import ObjectStoreStagingError, resolve_credential_pair
from apps.composition import build_dataset_search_adapter
from apps.workflows.dataset_search import (
    JobStatusRequest,
    SearchQueryInput,
    SubmitBulkInsertRequest,
    delete_document_handoff,
    ingest_documents_handoff,
    is_failed_job_status,
    list_jobs_handoff,
    read_job_status_handoff,
    retrieve_collections_handoff,
    search_collection_handoff,
    submit_bulk_insert_handoff,
    train_refinement_handoff,
)
from packages.domain.types import (
    CollectionCreateSpec,
    CollectionPatchSpec,
)


def _client(cds_url: str | None = None) -> DatasetSearchAdapter:
    return build_dataset_search_adapter(cds_url)


def _echo_json(payload: Any) -> None:
    click.echo(json.dumps(payload, indent=2, default=str))


def _echo_bytes(payload: bytes) -> None:
    click.echo(payload.decode("utf-8", errors="replace"), nl=False)


def _load_json_payload(raw: str | None, path: str | None) -> dict[str, Any]:
    if bool(raw) == bool(path):
        raise click.ClickException("Provide exactly one of --json or --json-file")
    try:
        loaded = json.loads(raw if raw is not None else Path(str(path)).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise click.ClickException(str(exc)) from exc
    if not isinstance(loaded, dict):
        raise click.ClickException("JSON payload must be an object")
    return loaded


def _credential_values(access_key_env: str, secret_key_env: str) -> tuple[str | None, str | None]:
    """Resolve a validated credential pair without accepting values as CLI arguments."""
    try:
        return resolve_credential_pair(access_key_env, secret_key_env)
    except (ObjectStoreStagingError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc


@click.group("ds")
def dataset_search_group() -> None:
    """Dataset Search (CVDS) — collections, search, ingest, jobs, refinement."""


@dataset_search_group.command("health")
@click.option("--cds-url", default=None)
def health(cds_url: str | None) -> None:
    """GET /health."""
    _echo_json({"status": _client(cds_url).health()})


@dataset_search_group.command("pipelines")
@click.option("--cds-url", default=None)
def pipelines(cds_url: str | None) -> None:
    """List available embedding pipelines."""
    items = [
        {
            "id": p.pipeline_id,
            "name": p.name,
            "description": p.description,
        }
        for p in _client(cds_url).list_pipelines()
    ]
    _echo_json({"pipelines": items})


@dataset_search_group.command("pipeline-collections")
@click.argument("pipeline_id")
@click.option("--cds-url", default=None)
def pipeline_collections(pipeline_id: str, cds_url: str | None) -> None:
    """List collections attached to one pipeline."""
    items = [
        {
            "id": c.collection_id,
            "name": c.name,
            "pipeline": c.pipeline,
            "tags": dict(c.tags),
            "total_documents_count": c.total_documents_count,
        }
        for c in _client(cds_url).list_pipeline_collections(pipeline_id)
    ]
    _echo_json({"collections": items})


@dataset_search_group.command("draw-pipeline")
@click.argument("pipeline_name")
@click.option("--mode", default="index", type=click.Choice(["index", "query"]))
@click.option("--output", required=True, type=click.Path(dir_okay=False, writable=True))
@click.option("--cds-url", default=None)
def draw_pipeline(pipeline_name: str, mode: str, output: str, cds_url: str | None) -> None:
    """Write one pipeline diagram PNG from GET /pipelines/draw/{name}."""
    content = _client(cds_url).draw_pipeline(pipeline_name, mode=mode)
    Path(output).write_bytes(content)
    _echo_json({"pipeline": pipeline_name, "mode": mode, "output": output, "bytes": len(content)})


@dataset_search_group.command("collections")
@click.option("--cds-url", default=None)
def collections(cds_url: str | None) -> None:
    """List collections."""
    items = [
        {
            "id": c.collection_id,
            "name": c.name,
            "pipeline": c.pipeline,
            "tags": dict(c.tags),
            "total_documents_count": c.total_documents_count,
        }
        for c in _client(cds_url).list_collections()
    ]
    _echo_json({"collections": items})


@dataset_search_group.command("get-collection")
@click.argument("collection_id")
@click.option("--cds-url", default=None)
def get_collection(collection_id: str, cds_url: str | None) -> None:
    """Get one collection (with document count when available)."""
    c = _client(cds_url).get_collection(collection_id)
    _echo_json(
        {
            "id": c.collection_id,
            "name": c.name,
            "pipeline": c.pipeline,
            "tags": dict(c.tags),
            "total_documents_count": c.total_documents_count,
            "created_at": c.created_at,
        }
    )


@dataset_search_group.command("create-collection")
@click.option("--name", required=True)
@click.option("--pipeline", required=True, help="e.g. cosmos_embed1_embedding_milvus")
@click.option("--id", "collection_id", default=None, help="Optional UUID for the collection")
@click.option("--tags-json", default="{}", help="JSON object of collection tags")
@click.option("--cds-url", default=None)
def create_collection(
    name: str,
    pipeline: str,
    collection_id: str | None,
    tags_json: str,
    cds_url: str | None,
) -> None:
    """Create a collection."""
    tags = json.loads(tags_json)
    created = _client(cds_url).create_collection(
        CollectionCreateSpec(
            name=name,
            pipeline=pipeline,
            tags=tags,
            collection_id=collection_id,
        )
    )
    _echo_json(
        {
            "id": created.collection_id,
            "name": created.name,
            "pipeline": created.pipeline,
            "tags": dict(created.tags),
        }
    )


@dataset_search_group.command("update-collection")
@click.argument("collection_id")
@click.option("--name", default=None)
@click.option("--tags-json", default=None)
@click.option("--cds-url", default=None)
def update_collection(
    collection_id: str,
    name: str | None,
    tags_json: str | None,
    cds_url: str | None,
) -> None:
    """Patch collection name and/or tags."""
    tags = json.loads(tags_json) if tags_json is not None else None
    updated = _client(cds_url).update_collection(
        collection_id, CollectionPatchSpec(name=name, tags=tags)
    )
    _echo_json({"id": updated.collection_id, "name": updated.name, "tags": dict(updated.tags)})


@dataset_search_group.command("delete-collection")
@click.argument("collection_id")
@click.option("--cds-url", default=None)
@click.confirmation_option(prompt="Delete this collection?")
def delete_collection(collection_id: str, cds_url: str | None) -> None:
    """Delete a collection."""
    _client(cds_url).delete_collection(collection_id)
    _echo_json({"deleted": collection_id})


@dataset_search_group.command("flush")
@click.argument("collection_id")
@click.option("--cds-url", default=None)
def flush(collection_id: str, cds_url: str | None) -> None:
    """Force-flush a Milvus-backed collection."""
    _echo_json(dict(_client(cds_url).flush_collection(collection_id)))


@dataset_search_group.command("search")
@click.option("--collection", required=True)
@click.option("--text", default=None, help="Text query")
@click.option("--embedding", default=None, help='JSON array, e.g. "[0.1, 0.2]"')
@click.option("--image", default=None, help="Image data URI or URL (C-Radio)")
@click.option("--video", default=None, help="Video data URI or URL (Cosmos-Embed)")
@click.option("--video-frames", default=None, help="Exactly 8 frames data URI")
@click.option("--top-k", default=10, type=int)
@click.option("--filters-json", default=None, help="JSON filters object or Milvus expr string")
@click.option("--generate-asset-url/--no-asset-url", default=False)
@click.option("--annotation-label", "annotation_labels", multiple=True)
@click.option("--exclude-annotation-label", "exclude_annotation_labels", multiple=True)
@click.option("--project-source", "project_source", multiple=True)
@click.option("--clf-json", default=None, help="JSON linear-classifier payload")
@click.option(
    "--caption-query", default=None, help="Caption keyword query for fused/caption-only search"
)
@click.option("--auto-rewrite/--no-auto-rewrite", default=None)
@click.option("--caption-extra-query", "caption_extra_queries", multiple=True)
@click.option("--classifier-label", default=None)
@click.option("--probability-expression", default=None)
@click.option("--cds-url", default=None)
def search_cmd(
    collection: str,
    text: str | None,
    embedding: str | None,
    image: str | None,
    video: str | None,
    video_frames: str | None,
    top_k: int,
    filters_json: str | None,
    generate_asset_url: bool,
    annotation_labels: tuple[str, ...],
    exclude_annotation_labels: tuple[str, ...],
    project_source: tuple[str, ...],
    clf_json: str | None,
    caption_query: str | None,
    auto_rewrite: bool | None,
    caption_extra_queries: tuple[str, ...],
    classifier_label: str | None,
    probability_expression: str | None,
    cds_url: str | None,
) -> None:
    """Multimodal search within one collection."""
    try:
        payload = search_collection_handoff(
            collection=collection,
            query=SearchQueryInput(
                text=text,
                embedding=embedding,
                image=image,
                video=video,
                video_frames=video_frames,
                top_k=top_k,
                filters_json=filters_json,
                generate_asset_url=generate_asset_url,
                annotation_labels=annotation_labels,
                exclude_annotation_labels=exclude_annotation_labels,
                project_source=project_source,
                clf_json=clf_json,
                caption_query=caption_query,
                auto_rewrite=auto_rewrite,
                # Click yields () for an omitted multiple=True option, which the
                # request layer would forward as an explicit empty list. Only
                # None means "not requested".
                caption_extra_queries=caption_extra_queries or None,
                classifier_label=classifier_label,
                probability_expression=probability_expression,
            ),
            client=_client(cds_url),
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    _echo_json(payload)


@dataset_search_group.command("retrieve")
@click.option("--collection", "collections", multiple=True, required=True)
@click.option("--text", default=None)
@click.option("--embedding", default=None)
@click.option("--image", default=None)
@click.option("--video", default=None)
@click.option("--video-frames", default=None)
@click.option("--top-k", default=10, type=int)
@click.option("--filters-json", default=None)
@click.option("--rerank/--no-rerank", default=True)
@click.option("--generate-asset-url/--no-asset-url", default=False)
@click.option("--cds-url", default=None)
def retrieve_cmd(
    collections: tuple[str, ...],
    text: str | None,
    embedding: str | None,
    image: str | None,
    video: str | None,
    video_frames: str | None,
    top_k: int,
    filters_json: str | None,
    rerank: bool,
    generate_asset_url: bool,
    cds_url: str | None,
) -> None:
    """Multi-collection retrieval (POST /retrieval)."""
    try:
        payload = retrieve_collections_handoff(
            collections=collections,
            query=SearchQueryInput(
                text=text,
                embedding=embedding,
                image=image,
                video=video,
                video_frames=video_frames,
                top_k=top_k,
                filters_json=filters_json,
                generate_asset_url=generate_asset_url,
            ),
            rerank=rerank,
            generate_asset_url=generate_asset_url,
            client=_client(cds_url),
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    _echo_json(payload)


@dataset_search_group.command("ingest-documents")
@click.option("--collection", required=True)
@click.option(
    "--document-json",
    "document_jsons",
    multiple=True,
    required=True,
    help='JSON DocumentSpec, e.g. \'{"mime_type":"text/plain","content":"hi"}\'',
)
@click.option("--cds-url", default=None)
def ingest_documents(collection: str, document_jsons: tuple[str, ...], cds_url: str | None) -> None:
    """Index documents (content / url / embedding)."""
    try:
        payload = ingest_documents_handoff(
            collection=collection,
            document_jsons=document_jsons,
            client=_client(cds_url),
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    _echo_json(payload)


@dataset_search_group.command("delete-document")
@click.option("--collection", required=True)
@click.option("--document-id", required=True)
@click.option("--cds-url", default=None)
def delete_document(collection: str, document_id: str, cds_url: str | None) -> None:
    """Delete one document by id."""
    _echo_json(
        delete_document_handoff(
            collection=collection,
            document_id=document_id,
            client=_client(cds_url),
        )
    )


@dataset_search_group.command("bulk-insert")
@click.option("--collection", required=True, help="Collection name or id")
@click.option(
    "--embedding-family",
    required=True,
    type=click.Choice(["ce1"], case_sensitive=False),
    help="Required artifact declaration; vectors do not identify their model family",
)
@click.option(
    "--parquet",
    "parquet_paths",
    multiple=True,
    required=True,
    help="s3:// path (repeatable)",
)
@click.option("--access-key-env", default="AWS_ACCESS_KEY_ID", show_default=True)
@click.option("--secret-key-env", default="AWS_SECRET_ACCESS_KEY", show_default=True)
@click.option("--endpoint-url", default=None)
@click.option(
    "--allow-lab-http-endpoint",
    is_flag=True,
    help="Lab only: permit an HTTP object-store endpoint",
)
@click.option("--cds-url", default=None)
def bulk_insert(
    collection: str,
    embedding_family: str,
    parquet_paths: tuple[str, ...],
    access_key_env: str,
    secret_key_env: str,
    endpoint_url: str | None,
    allow_lab_http_endpoint: bool,
    cds_url: str | None,
) -> None:
    """Submit one bulk parquet job; POST is never retried automatically."""
    access_key, secret_key = _credential_values(access_key_env, secret_key_env)
    _echo_json(
        submit_bulk_insert_handoff(
            SubmitBulkInsertRequest(
                collection=collection,
                parquet_paths=parquet_paths,
                embedding_family=embedding_family,
                access_key=access_key,
                secret_key=secret_key,
                endpoint_url=endpoint_url,
                allow_lab_http_endpoint=allow_lab_http_endpoint,
            ),
            client=_client(cds_url),
        )
    )


@dataset_search_group.command("job-status")
@click.argument("job_id")
@click.option("--wait/--no-wait", default=False, help="Poll until CDS reports a terminal state")
@click.option("--timeout-seconds", default=900.0, type=click.FloatRange(min=0))
@click.option("--poll-interval-seconds", default=5.0, type=click.FloatRange(min=0, min_open=True))
@click.option("--cds-url", default=None)
def job_status(
    job_id: str,
    wait: bool,
    timeout_seconds: float,
    poll_interval_seconds: float,
    cds_url: str | None,
) -> None:
    """Get or poll externally owned CDS bulk-job status."""
    client = _client(cds_url)
    try:
        payload = read_job_status_handoff(
            JobStatusRequest(
                job_id=job_id,
                wait=wait,
                timeout_seconds=timeout_seconds,
                poll_interval_seconds=poll_interval_seconds,
            ),
            client=client,
        )
    except BulkJobPollingTimeout as exc:
        _echo_json({"job_id": job_id, "status": "timeout", "error": str(exc)})
        raise click.exceptions.Exit(2) from exc

    _echo_json(payload)
    if wait and is_failed_job_status(str(payload["status"])):
        raise click.exceptions.Exit(2)


@dataset_search_group.command("jobs")
@click.option("--cds-url", default=None)
def jobs(cds_url: str | None) -> None:
    """List recent bulk-insert jobs."""
    _echo_json(list_jobs_handoff(_client(cds_url)))


@click.group("captions")
def captions_group() -> None:
    """Caption CRUD, keyword search, rewrite, and stats."""


@captions_group.command("add")
@click.option("--json", "raw_json", default=None)
@click.option("--json-file", default=None, type=click.Path(exists=True, dir_okay=False))
@click.option("--cds-url", default=None)
def captions_add(raw_json: str | None, json_file: str | None, cds_url: str | None) -> None:
    _echo_json(_client(cds_url).add_caption(_load_json_payload(raw_json, json_file)))


@captions_group.command("get")
@click.argument("clip_id")
@click.option("--model-name", default=None)
@click.option("--cds-url", default=None)
def captions_get(clip_id: str, model_name: str | None, cds_url: str | None) -> None:
    _echo_json(_client(cds_url).get_captions(clip_id, model_name=model_name))


@captions_group.command("search")
@click.option("--query", required=True)
@click.option("--limit", default=5000, type=click.IntRange(min=1))
@click.option("--data-source", "data_sources", multiple=True)
@click.option("--extra-query", "extra_queries", multiple=True)
@click.option("--cds-url", default=None)
def captions_search(
    query: str,
    limit: int,
    data_sources: tuple[str, ...],
    extra_queries: tuple[str, ...],
    cds_url: str | None,
) -> None:
    _echo_json(
        _client(cds_url).search_captions(
            query,
            limit=limit,
            data_sources=data_sources,
            extra_queries=extra_queries,
        )
    )


@captions_group.command("stats")
@click.option("--cds-url", default=None)
def captions_stats(cds_url: str | None) -> None:
    _echo_json(_client(cds_url).caption_stats())


@captions_group.command("rewrite")
@click.option("--query", required=True)
@click.option("--num-rewrites", default=3, type=click.IntRange(min=0))
@click.option("--cds-url", default=None)
def captions_rewrite(query: str, num_rewrites: int, cds_url: str | None) -> None:
    _echo_json(_client(cds_url).rewrite_caption_query(query, num_rewrites=num_rewrites))


@captions_group.command("rewrite-status")
@click.option("--cds-url", default=None)
def captions_rewrite_status(cds_url: str | None) -> None:
    _echo_json(_client(cds_url).caption_rewrite_status())


dataset_search_group.add_command(captions_group)


@click.group("annotations")
def annotations_group() -> None:
    """Annotation labels and review workflows."""


@annotations_group.command("list")
@click.option("--document-id", "document_ids", multiple=True)
@click.option("--project-id", default=None)
@click.option("--limit", default=1000, type=click.IntRange(min=1))
@click.option("--offset", default=0, type=click.IntRange(min=0))
@click.option("--cds-url", default=None)
def annotations_list(
    document_ids: tuple[str, ...],
    project_id: str | None,
    limit: int,
    offset: int,
    cds_url: str | None,
) -> None:
    _echo_json(
        _client(cds_url).list_annotations(
            document_ids=document_ids,
            project_id=project_id,
            limit=limit,
            offset=offset,
        )
    )


@annotations_group.command("labels")
@click.option("--collection", required=True)
@click.option("--project-id", default=None)
@click.option("--cds-url", default=None)
def annotation_labels(collection: str, project_id: str | None, cds_url: str | None) -> None:
    _echo_json(_client(cds_url).list_annotation_labels(collection, project_id=project_id))


@annotations_group.command("create")
@click.option("--json", "raw_json", default=None)
@click.option("--json-file", default=None, type=click.Path(exists=True, dir_okay=False))
@click.option("--cds-url", default=None)
def annotation_create(raw_json: str | None, json_file: str | None, cds_url: str | None) -> None:
    _echo_json(_client(cds_url).create_annotation(_load_json_payload(raw_json, json_file)))


@annotations_group.command("batch")
@click.option("--json", "raw_json", default=None)
@click.option("--json-file", default=None, type=click.Path(exists=True, dir_okay=False))
@click.option("--cds-url", default=None)
def annotation_batch(raw_json: str | None, json_file: str | None, cds_url: str | None) -> None:
    _echo_json(_client(cds_url).create_annotations_batch(_load_json_payload(raw_json, json_file)))


@annotations_group.command("upload")
@click.option("--json", "raw_json", default=None)
@click.option("--json-file", default=None, type=click.Path(exists=True, dir_okay=False))
@click.option("--cds-url", default=None)
def annotation_upload(raw_json: str | None, json_file: str | None, cds_url: str | None) -> None:
    _echo_json(_client(cds_url).upload_annotations(_load_json_payload(raw_json, json_file)))


@annotations_group.command("rename-label")
@click.option("--json", "raw_json", default=None)
@click.option("--json-file", default=None, type=click.Path(exists=True, dir_okay=False))
@click.option("--cds-url", default=None)
def annotation_rename_label(
    raw_json: str | None, json_file: str | None, cds_url: str | None
) -> None:
    _echo_json(_client(cds_url).rename_annotation_label(_load_json_payload(raw_json, json_file)))


@annotations_group.command("merge-labels")
@click.option("--json", "raw_json", default=None)
@click.option("--json-file", default=None, type=click.Path(exists=True, dir_okay=False))
@click.option("--cds-url", default=None)
def annotation_merge_labels(
    raw_json: str | None, json_file: str | None, cds_url: str | None
) -> None:
    _echo_json(_client(cds_url).merge_annotation_labels(_load_json_payload(raw_json, json_file)))


@annotations_group.command("update")
@click.argument("annotation_id")
@click.option("--json", "raw_json", default=None)
@click.option("--json-file", default=None, type=click.Path(exists=True, dir_okay=False))
@click.option("--cds-url", default=None)
def annotation_update(
    annotation_id: str, raw_json: str | None, json_file: str | None, cds_url: str | None
) -> None:
    _echo_json(
        _client(cds_url).update_annotation(annotation_id, _load_json_payload(raw_json, json_file))
    )


@annotations_group.command("verify")
@click.argument("annotation_id")
@click.option("--cds-url", default=None)
def annotation_verify(annotation_id: str, cds_url: str | None) -> None:
    _echo_json(_client(cds_url).verify_annotation(annotation_id))


@annotations_group.command("delete")
@click.argument("annotation_id")
@click.option("--cds-url", default=None)
@click.confirmation_option(prompt="Delete this annotation?")
def annotation_delete(annotation_id: str, cds_url: str | None) -> None:
    _echo_json(_client(cds_url).delete_annotation(annotation_id))


@annotations_group.command("delete-label")
@click.option("--collection", required=True)
@click.option("--label", required=True)
@click.option("--cds-url", default=None)
@click.confirmation_option(prompt="Delete all annotations with this label?")
def annotation_delete_label(collection: str, label: str, cds_url: str | None) -> None:
    _echo_json(_client(cds_url).delete_annotation_label(collection, label))


@annotations_group.command("batch-by-search")
@click.option("--collection", required=True)
@click.option("--json", "raw_json", default=None)
@click.option("--json-file", default=None, type=click.Path(exists=True, dir_okay=False))
@click.option("--cds-url", default=None)
def annotation_batch_by_search(
    collection: str, raw_json: str | None, json_file: str | None, cds_url: str | None
) -> None:
    _echo_json(
        _client(cds_url).annotate_batch_by_search(
            collection, _load_json_payload(raw_json, json_file)
        )
    )


dataset_search_group.add_command(annotations_group)


@click.group("classifiers")
def classifiers_group() -> None:
    """Annotation-trained classifiers."""


@classifiers_group.command("train")
@click.option("--collection", required=True)
@click.option("--json", "raw_json", default=None)
@click.option("--json-file", default=None, type=click.Path(exists=True, dir_okay=False))
@click.option("--cds-url", default=None)
def classifier_train(
    collection: str, raw_json: str | None, json_file: str | None, cds_url: str | None
) -> None:
    _echo_json(
        _client(cds_url).train_classifier(collection, _load_json_payload(raw_json, json_file))
    )


@classifiers_group.command("list")
@click.option("--collection", required=True)
@click.option("--cds-url", default=None)
def classifier_list(collection: str, cds_url: str | None) -> None:
    _echo_json(_client(cds_url).list_classifiers(collection))


@classifiers_group.command("export")
@click.option("--collection", required=True)
@click.option("--label", required=True)
@click.option("--cds-url", default=None)
def classifier_export(collection: str, label: str, cds_url: str | None) -> None:
    _echo_json(_client(cds_url).export_classifier(collection, label))


@classifiers_group.command("delete")
@click.option("--collection", required=True)
@click.option("--label", required=True)
@click.option("--cds-url", default=None)
@click.confirmation_option(prompt="Delete this classifier?")
def classifier_delete(collection: str, label: str, cds_url: str | None) -> None:
    _echo_json(_client(cds_url).delete_classifier(collection, label))


dataset_search_group.add_command(classifiers_group)


@click.group("datasets")
def datasets_group() -> None:
    """Dataset registry resources."""


@datasets_group.command("list")
@click.option("--cds-url", default=None)
def datasets_list(cds_url: str | None) -> None:
    _echo_json(_client(cds_url).list_datasets())


@datasets_group.command("get")
@click.argument("dataset_id")
@click.option("--cds-url", default=None)
def dataset_get(dataset_id: str, cds_url: str | None) -> None:
    _echo_json(_client(cds_url).get_dataset(dataset_id))


@datasets_group.command("create")
@click.option("--id", "dataset_id", default=None)
@click.option("--json", "raw_json", default=None)
@click.option("--json-file", default=None, type=click.Path(exists=True, dir_okay=False))
@click.option("--cds-url", default=None)
def dataset_create(
    dataset_id: str | None,
    raw_json: str | None,
    json_file: str | None,
    cds_url: str | None,
) -> None:
    _echo_json(
        _client(cds_url).create_dataset(
            _load_json_payload(raw_json, json_file), dataset_id=dataset_id
        )
    )


@datasets_group.command("update")
@click.argument("dataset_id")
@click.option("--json", "raw_json", default=None)
@click.option("--json-file", default=None, type=click.Path(exists=True, dir_okay=False))
@click.option("--cds-url", default=None)
def dataset_update(
    dataset_id: str, raw_json: str | None, json_file: str | None, cds_url: str | None
) -> None:
    _echo_json(_client(cds_url).update_dataset(dataset_id, _load_json_payload(raw_json, json_file)))


@datasets_group.command("delete")
@click.argument("dataset_id")
@click.option("--cds-url", default=None)
@click.confirmation_option(prompt="Delete this dataset?")
def dataset_delete(dataset_id: str, cds_url: str | None) -> None:
    _echo_json(_client(cds_url).delete_dataset(dataset_id))


dataset_search_group.add_command(datasets_group)


@click.group("projects")
def projects_group() -> None:
    """Project registry and saved-result resources."""


@projects_group.command("list")
@click.option("--cds-url", default=None)
def projects_list(cds_url: str | None) -> None:
    _echo_json(_client(cds_url).list_projects())


@projects_group.command("get")
@click.argument("project_id")
@click.option("--cds-url", default=None)
def project_get(project_id: str, cds_url: str | None) -> None:
    _echo_json(_client(cds_url).get_project(project_id))


@projects_group.command("create")
@click.option("--id", "project_id", default=None)
@click.option("--json", "raw_json", default=None)
@click.option("--json-file", default=None, type=click.Path(exists=True, dir_okay=False))
@click.option("--cds-url", default=None)
def project_create(
    project_id: str | None,
    raw_json: str | None,
    json_file: str | None,
    cds_url: str | None,
) -> None:
    _echo_json(
        _client(cds_url).create_project(
            _load_json_payload(raw_json, json_file), project_id=project_id
        )
    )


@projects_group.command("update")
@click.argument("project_id")
@click.option("--json", "raw_json", default=None)
@click.option("--json-file", default=None, type=click.Path(exists=True, dir_okay=False))
@click.option("--cds-url", default=None)
def project_update(
    project_id: str, raw_json: str | None, json_file: str | None, cds_url: str | None
) -> None:
    _echo_json(_client(cds_url).update_project(project_id, _load_json_payload(raw_json, json_file)))


@projects_group.command("save-documents")
@click.argument("project_id")
@click.option("--json", "raw_json", default=None)
@click.option("--json-file", default=None, type=click.Path(exists=True, dir_okay=False))
@click.option("--cds-url", default=None)
def project_save_documents(
    project_id: str, raw_json: str | None, json_file: str | None, cds_url: str | None
) -> None:
    _echo_json(
        _client(cds_url).save_project_documents(project_id, _load_json_payload(raw_json, json_file))
    )


@projects_group.command("export")
@click.argument("project_id")
@click.option("--output", required=True, type=click.Path(dir_okay=False, writable=True))
@click.option("--cds-url", default=None)
def project_export(project_id: str, output: str, cds_url: str | None) -> None:
    content = _client(cds_url).export_project_csv(project_id)
    Path(output).write_bytes(content)
    _echo_json({"project_id": project_id, "output": output, "bytes": len(content)})


@projects_group.command("delete")
@click.argument("project_id")
@click.option("--cds-url", default=None)
@click.confirmation_option(prompt="Delete this project?")
def project_delete(project_id: str, cds_url: str | None) -> None:
    _echo_json(_client(cds_url).delete_project(project_id))


dataset_search_group.add_command(projects_group)


@dataset_search_group.command("linear-probe")
@click.option("--json", "raw_json", default=None)
@click.option("--json-file", default=None, type=click.Path(exists=True, dir_okay=False))
@click.option("--cds-url", default=None)
def linear_probe(raw_json: str | None, json_file: str | None, cds_url: str | None) -> None:
    """Invoke /linear_probe for deprecated compatibility coverage."""
    _echo_json(_client(cds_url).linear_probe(_load_json_payload(raw_json, json_file)))


@dataset_search_group.command("metrics")
@click.option("--cds-url", default=None)
def metrics(cds_url: str | None) -> None:
    """Print root /metrics Prometheus text."""
    _echo_bytes(_client(cds_url).metrics())


@dataset_search_group.command("cds-metrics")
@click.option("--cds-url", default=None)
def cds_metrics(cds_url: str | None) -> None:
    """Print root /cds_metrics Prometheus text."""
    _echo_bytes(_client(cds_url).cds_metrics())


@dataset_search_group.command("train-refinement")
@click.option(
    "--spec-file",
    required=True,
    type=click.Path(exists=True),
    help="JSON SearchRefinementSpec file",
)
@click.option("--cds-url", default=None)
def train_refinement(spec_file: str, cds_url: str | None) -> None:
    """Train search refinement from a JSON spec file."""
    try:
        payload = train_refinement_handoff(spec_file=spec_file, client=_client(cds_url))
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    _echo_json(payload)
