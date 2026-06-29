#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGISTRY="${GHCR_REGISTRY:-ghcr.io}"
OWNER="${GHCR_OWNER:-hillaliy}"
BACKEND_IMAGE="${BACKEND_IMAGE:-${REGISTRY}/${OWNER}/languard-backend}"
FRONTEND_IMAGE="${FRONTEND_IMAGE:-${REGISTRY}/${OWNER}/languard-frontend}"
PUSH_LATEST="${PUSH_LATEST:-true}"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  echo "Usage: $0 [version]"
  echo
  echo "Defaults:"
  echo "  version: frontend/package.json version"
  echo "  backend: ${BACKEND_IMAGE}"
  echo "  frontend: ${FRONTEND_IMAGE}"
  echo
  echo "Environment overrides:"
  echo "  GHCR_REGISTRY, GHCR_OWNER, BACKEND_IMAGE, FRONTEND_IMAGE, PUSH_LATEST=false"
  exit 0
fi

VERSION="${1:-}"
if [[ -z "${VERSION}" ]]; then
  VERSION="$(node -p "require('${ROOT_DIR}/frontend/package.json').version")"
fi

if [[ -z "${VERSION}" ]]; then
  echo "Version is required."
  exit 1
fi

BACKEND_TAGS=(-t "${BACKEND_IMAGE}:${VERSION}")
FRONTEND_TAGS=(-t "${FRONTEND_IMAGE}:${VERSION}")

if [[ "${PUSH_LATEST}" == "true" ]]; then
  BACKEND_TAGS+=(-t "${BACKEND_IMAGE}:latest")
  FRONTEND_TAGS+=(-t "${FRONTEND_IMAGE}:latest")
fi

echo "Building and pushing LanGuard ${VERSION}"
echo "Backend image:  ${BACKEND_IMAGE}:${VERSION}"
echo "Frontend image: ${FRONTEND_IMAGE}:${VERSION}"

echo "Building backend image..."
docker build -f "${ROOT_DIR}/Dockerfile" "${BACKEND_TAGS[@]}" "${ROOT_DIR}"

echo "Building frontend image..."
docker build -f "${ROOT_DIR}/frontend/Dockerfile" "${FRONTEND_TAGS[@]}" "${ROOT_DIR}/frontend"

echo "Pushing backend image..."
docker push "${BACKEND_IMAGE}:${VERSION}"

echo "Pushing frontend image..."
docker push "${FRONTEND_IMAGE}:${VERSION}"

if [[ "${PUSH_LATEST}" == "true" ]]; then
  echo "Pushing latest tags..."
  docker push "${BACKEND_IMAGE}:latest"
  docker push "${FRONTEND_IMAGE}:latest"
fi

echo "LanGuard images pushed successfully."
