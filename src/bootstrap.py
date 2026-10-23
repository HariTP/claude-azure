"""Read the secret-bearing configuration from stdin, then replace this process."""
import json
import os
import sys

config = json.load(sys.stdin)
fd = os.open('/tmp/gateway.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as stream:
    json.dump(config, stream)
del config
os.execv('/app/.venv/bin/litellm', ['litellm', '--config', '/tmp/gateway.json', '--host', '0.0.0.0', '--port', '4000'])
