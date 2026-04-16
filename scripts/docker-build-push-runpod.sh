#!/usr/bin/env bash
# Build linux/amd64 image for RunPod and push to Docker Hub.
# Requires: native x86_64 (or reliable amd64 build), Docker logged in (`docker login`).
# Usage:
#   export IMAGE_NAME=docker.io/osophy/speak2-unmute:runpod   # optional override
#   ./scripts/docker-build-push-runpod.sh

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
IMAGE_NAME="${IMAGE_NAME:-docker.io/osophy/speak2-unmute:runpod}"
CUDA_COMPUTE_CAP="${CUDA_COMPUTE_CAP:-120}"

echo "Building ${IMAGE_NAME} (linux/amd64, CUDA_COMPUTE_CAP=${CUDA_COMPUTE_CAP})..."
docker build --platform linux/amd64 \
  -f Dockerfile.runpod-allinone \
  --build-arg "CUDA_COMPUTE_CAP=${CUDA_COMPUTE_CAP}" \
  -t "${IMAGE_NAME}" .

echo "Pushing ${IMAGE_NAME}..."
docker push "${IMAGE_NAME}"

echo "Done. Use this image on RunPod and ensure the Hub repo is public or add registry credentials."
