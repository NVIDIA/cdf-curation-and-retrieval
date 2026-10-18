<!--
SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: Apache-2.0
-->

# Clean Architecture

Dependency direction inside this repository. Make is the operator
interface; everything below it is contributor detail.

Layers from Make down to the product runtimes:

```mermaid
flowchart TB
  make["Make targets\npublic operator interface"]
  cdf["helper CLI\napps/cli, called by Make"]
  composition["apps/composition.py\nadapter and runner factories"]
  workflows["apps/workflows\ncurator | mining | embeddings"]
  ports["packages/ports\nexternal-boundary protocols"]
  domain["packages/domain\nshared data shapes"]
  analytics["packages/analytics\nin-process algorithms"]
  adapters["adapters\nCurator | Data Mining | Dataset Search | Docker runtime"]
  runtimes["product runtimes\nCosmos Curator | TAO DS / TMM | CDS"]

  make --> cdf
  cdf --> composition
  cdf --> workflows
  composition --> adapters
  workflows --> ports
  workflows --> domain
  workflows --> analytics
  ports --> adapters
  adapters --> runtimes
```

How the helper CLI wires a single command:

```mermaid
flowchart LR
  cli["apps/cli\nClick parsing | env defaults | JSON/error presentation"]
  workflow["apps/workflows\nvalidation order | handoff policy | JSON-ready payloads"]
  compose["apps/composition.py\nconstructs collaborators"]
  port["packages/ports\nprotocols"]
  adapter["adapters\nHTTP | Docker | parquet | object store"]
  runtime["external runtimes\npulled images and deployed services"]

  cli --> workflow
  cli --> compose
  workflow --> port
  compose --> adapter
  adapter --> runtime
```
