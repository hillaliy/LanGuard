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
USE_REGISTRY_CACHE="${USE_REGISTRY_CACHE:-true}"
LOCAL_ARCH_ONLY="${LOCAL_ARCH_ONLY:-false}"

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
  echo "  LOCAL_ARCH_ONLY=true to publish only this Mac's CPU architecture"
  echo "  USE_REGISTRY_CACHE=false to disable buildx registry cache"
  exit 0
fi

if [[ "${LOCAL_ARCH_ONLY}" == "true" ]]; then
  case "$(uname -m)" in
    arm64|aarch64)
      PLATFORMS="linux/arm64"
      ;;
    x86_64|amd64)
      PLATFORMS="linux/amd64"
      ;;
    *)
      echo "Could not map local architecture $(uname -m) to a Docker platform."
      exit 1
      ;;
  esac
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
if [[ "${LOCAL_ARCH_ONLY}" == "true" ]]; then
  echo "Local arch only: enabled"
fi

if ! docker buildx inspect "${BUILDER_NAME}" >/dev/null 2>&1; then
  docker buildx create --name "${BUILDER_NAME}" --use >/dev/null
else
  docker buildx use "${BUILDER_NAME}" >/dev/null
fi

BACKEND_CACHE_ARGS=()
FRONTEND_CACHE_ARGS=()
if [[ "${USE_REGISTRY_CACHE}" == "true" ]]; then
  BACKEND_CACHE_ARGS=(
    --cache-from "type=registry,ref=${BACKEND_IMAGE}:buildcache"
    --cache-to "type=registry,ref=${BACKEND_IMAGE}:buildcache,mode=max"
  )
  FRONTEND_CACHE_ARGS=(
    --cache-from "type=registry,ref=${FRONTEND_IMAGE}:buildcache"
    --cache-to "type=registry,ref=${FRONTEND_IMAGE}:buildcache,mode=max"
  )
fi

echo "Building and pushing backend image..."
docker buildx build \
  --platform "${PLATFORMS}" \
  --build-arg "APP_VERSION=${VERSION}" \
  -f "${ROOT_DIR}/Dockerfile" \
  "${BACKEND_CACHE_ARGS[@]}" \
  "${BACKEND_TAGS[@]}" \
  --push \
  "${ROOT_DIR}"

echo "Building and pushing frontend image..."
docker buildx build \
  --platform "${PLATFORMS}" \
  -f "${ROOT_DIR}/frontend/Dockerfile" \
  "${FRONTEND_CACHE_ARGS[@]}" \
  "${FRONTEND_TAGS[@]}" \
  --push \
  "${ROOT_DIR}/frontend"

echo "LanGuard images pushed successfully."
