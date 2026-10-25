#!/usr/bin/env bash
# Run inside the single temporary Ubuntu DLAMI as the ubuntu user.
set -euo pipefail
cd "$(dirname "$0")/../.."
test -f /var/tmp/last-warning-budget-installed
sudo systemctl is-active last-warning-budget.timer
nvidia-smi
sudo apt-get update -qq
sudo apt-get install -y -qq ffmpeg python3-pip
python3 -m pip install --user --upgrade uv
export PATH="$HOME/.local/bin:$PATH"
uv venv --python 3.12 --seed tribe-env
uv pip install --python tribe-env/bin/python -r backend/requirements-tribe.lock
git clone https://github.com/facebookresearch/tribev2.git official-tribev2
git -C official-tribev2 checkout af58661791a351a448a489042a28f6c37e1c14b7
uv pip install --python tribe-env/bin/python --no-deps -e official-tribev2
tribe-env/bin/python -c 'import torch; from tribev2 import TribeModel; assert torch.cuda.is_available(); print("GPU_ENVIRONMENT_READY",torch.cuda.get_device_name())'
touch data/gpu-job/BOOTSTRAP_COMPLETE
