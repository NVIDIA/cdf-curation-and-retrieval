#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Create the S3 bucket Milvus persists to, mirroring the CDS 1.2.0 standalone
# deployment. LocalStack runs everything in /etc/localstack/init/ready.d once
# it is ready to serve, so Milvus finds the bucket on first start.

set -euo pipefail

BUCKET_NAME="${BUCKET_NAME:-cosmos-test-bucket}"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
ENDPOINT_URL="${AWS_ENDPOINT_URL:-http://localhost:4566}"

aws_cmd() {
  if command -v awslocal >/dev/null 2>&1; then
    awslocal "$@"
  else
    aws --endpoint-url "${ENDPOINT_URL}" "$@"
  fi
}

if aws_cmd s3api head-bucket --bucket "${BUCKET_NAME}" 2>/dev/null; then
  echo "[localstack:init] bucket '${BUCKET_NAME}' already exists"
  exit 0
fi

# us-east-1 rejects an explicit LocationConstraint.
if [ "${REGION}" = "us-east-1" ]; then
  aws_cmd s3api create-bucket --bucket "${BUCKET_NAME}"
else
  aws_cmd s3api create-bucket --bucket "${BUCKET_NAME}" \
    --create-bucket-configuration LocationConstraint="${REGION}"
fi

echo "[localstack:init] created bucket '${BUCKET_NAME}'"
