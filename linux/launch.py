#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

profile = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'claude-azure-local'
args = sys.argv[1:]
model = 'claude-azure-sol'
if args and args[0] in ('--luna', '--sol'):
    model = 'claude-azure-luna' if args.pop(0) == '--luna' else model
settings = json.loads((profile / 'connection.json').read_text())
try:
    with urllib.request.urlopen(f"http://127.0.0.1:{settings['port']}/health/liveliness", timeout=5):
        pass
except OSError:
    raise SystemExit('Gateway unavailable. Check: sudo systemctl status claude-azure-local')
env = dict(os.environ)
for name in ('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'CLAUDE_CODE_OAUTH_TOKEN',
             'CLAUDE_CODE_USE_BEDROCK', 'CLAUDE_CODE_USE_VERTEX', 'CLAUDE_CODE_USE_FOUNDRY'):
    env.pop(name, None)
env.update(CLAUDE_CONFIG_DIR=str(profile / 'claude'),
           ANTHROPIC_BASE_URL=f"http://127.0.0.1:{settings['port']}",
           ANTHROPIC_AUTH_TOKEN=(profile / 'gateway-token').read_text().strip(),
           ANTHROPIC_MODEL=model, ANTHROPIC_DEFAULT_OPUS_MODEL='claude-azure-sol',
           ANTHROPIC_DEFAULT_SONNET_MODEL='claude-azure-sol', ANTHROPIC_DEFAULT_HAIKU_MODEL='claude-azure-luna',
           CLAUDE_CODE_SUBAGENT_MODEL='claude-azure-luna', CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY='1',
           CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1')
os.execvpe('claude', ['claude', '--model', model] + args, env)
