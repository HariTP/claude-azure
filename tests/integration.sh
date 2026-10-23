#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
IMAGE=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["images"]["amd64"])' "$ROOT_DIR/image-lock.json")
exec docker run --rm --network none --user 65532:65532 --read-only --cap-drop ALL \
  --security-opt no-new-privileges:true --memory 2g --pids-limit 256 \
  --tmpfs /tmp:rw,nosuid,nodev,size=256m,mode=1777 --env HOME=/tmp \
  --env PYTHONPATH=/repo/src --env LITELLM_TELEMETRY=False --env LITELLM_LOCAL_MODEL_COST_MAP=True \
  --env LITELLM_USE_CHAT_COMPLETIONS_URL_FOR_ANTHROPIC_MESSAGES=true \
  --env LITELLM_ROUTE_ALL_CHAT_OPENAI_TO_RESPONSES=false \
  --mount "type=bind,src=$ROOT_DIR,dst=/repo,readonly" \
  --entrypoint /app/.venv/bin/python "$IMAGE" /repo/tests/mock_gateway.py
