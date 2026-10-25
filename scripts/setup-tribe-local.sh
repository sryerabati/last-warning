#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
  echo 'This setup is pinned for Apple Silicon macOS.' >&2
  exit 1
fi
revision=af58661791a351a448a489042a28f6c37e1c14b7
mkdir -p cache
if [[ ! -d cache/tribev2-source/.git ]]; then
  git init cache/tribev2-source
  git -C cache/tribev2-source remote add origin https://github.com/facebookresearch/tribev2.git
  git -C cache/tribev2-source fetch --depth 1 origin "$revision"
  git -C cache/tribev2-source checkout --detach FETCH_HEAD
fi
if [[ "$(git -C cache/tribev2-source rev-parse HEAD)" != "$revision" || -n "$(git -C cache/tribev2-source status --porcelain --untracked-files=no)" ]]; then
  echo 'The cached official source must be clean at the pinned revision.' >&2
  exit 1
fi
if [[ ! -x cache/tribe-env/bin/python ]]; then
  uv venv --python 3.12 cache/tribe-env
fi
uv pip install --python cache/tribe-env/bin/python -r backend/requirements-tribe-mac.lock --editable cache/tribev2-source --no-deps
cache/tribe-env/bin/python -c 'import torch, tribev2; print("Local Mini runtime ready. Apple Metal:", torch.backends.mps.is_available())'
echo 'Use Neural Lab > Run Mini locally. Model weights download once on the first run.'
