#!/usr/bin/env bash
# Local Swift gate for the apple-silicon lane.
#
# This component needs the Neural Engine and the macOS 26 SDK, so it cannot run on GitHub's
# hosted runners -- and big-little-mesh is a PUBLIC repo, so we deliberately do NOT register
# a self-hosted runner (a fork PR would otherwise run arbitrary code on the host). The Go,
# Python, and gen-drift lanes still run in CI on hosted Linux runners; Swift is verified
# here, locally, before pushing changes under apple-silicon/ or to Package.swift.
#
# Mirrors the three checks the other lanes get: format-lint, build, test.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail=0
step() {
  local name="$1"; shift
  echo "==> ${name}"
  if "$@"; then
    echo "    [PASS] ${name}"
  else
    echo "    [FAIL] ${name}"
    fail=1
  fi
}

step "format-lint" swift format lint --strict --recursive --configuration .swift-format \
  apple-silicon/Sources apple-silicon/Tests
step "build" swift build
step "test" swift test

if [ "${fail}" -ne 0 ]; then
  echo "[FAIL] swift checks failed"
  exit 1
fi
echo "[PASS] all swift checks passed"
