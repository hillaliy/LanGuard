#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGISTRY="${GHCR_REGISTRY:-ghcr.io}"
OWNER="${GHCR_OWNER:-hillaliy}"
BACKEND_IMAGE="${BACKEND_IMAGE:-${REGISTRY}/${OWNER}/languard-backend}"
FRONTEND_IMAGE="${FRONTEND_IMAGE:-${REGISTRY}/${OWNER}/languard-frontend}"
PUSH_LATEST="${PUSH_LATEST:-true}"
PLATFORMS="${PLATFORMS:-linux/amd64,linux/arm64}"
BUILDER_NAME="${BUILDER_NAME:-languard-builder}"

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
  echo "  PLATFORMS=linux/amd64,linux/arm64"
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
echo "Platforms:      ${PLATFORMS}"

if ! docker buildx inspect "${BUILDER_NAME}" >/dev/null 2>&1; then
  docker buildx create --name "${BUILDER_NAME}" --use >/dev/null
else
  docker buildx use "${BUILDER_NAME}" >/dev/null
fi

echo "Building and pushing backend image..."
docker buildx build \
  --platform "${PLATFORMS}" \
  --build-arg "APP_VERSION=${VERSION}" \
  -f "${ROOT_DIR}/Dockerfile" \
  "${BACKEND_TAGS[@]}" \
  --push \
  "${ROOT_DIR}"

echo "Building and pushing frontend image..."
docker buildx build \
  --platform "${PLATFORMS}" \
  -f "${ROOT_DIR}/frontend/Dockerfile" \
  "${FRONTEND_TAGS[@]}" \
  --push \
  "${ROOT_DIR}/frontend"

echo "LanGuard images pushed successfully."
