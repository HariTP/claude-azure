#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

profile = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'claude-azure-local'
args = sys.argv[1:]
model = 'claude-azure-sol[1m]'
if args and args[0] in ('--luna', '--sol', '--astra', '--grok'):
    model = {'--luna': 'claude-azure-luna[1m]', '--sol': 'claude-azure-sol[1m]',
             '--astra': 'claude-azure-astra[1m]', '--grok': 'claude-azure-grok'}[args.pop(0)]
settings = json.loads((profile / 'connection.json').read_text())
deployments = json.loads((profile / 'settings.json').read_text())
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
           ANTHROPIC_MODEL=model, ANTHROPIC_DEFAULT_OPUS_MODEL='claude-azure-grok',
           ANTHROPIC_DEFAULT_OPUS_MODEL_NAME=deployments['grok_deployment'],
           ANTHROPIC_DEFAULT_OPUS_MODEL_DESCRIPTION='Azure Foundry · ' + deployments['grok_deployment'],
           ANTHROPIC_DEFAULT_SONNET_MODEL='claude-azure-sol[1m]',
           ANTHROPIC_DEFAULT_SONNET_MODEL_NAME=deployments['sol_deployment'],
           ANTHROPIC_DEFAULT_SONNET_MODEL_DESCRIPTION='Azure Foundry · ' + deployments['sol_deployment'],
           ANTHROPIC_DEFAULT_HAIKU_MODEL='claude-azure-luna[1m]',
           ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME=deployments['luna_deployment'],
           ANTHROPIC_DEFAULT_HAIKU_MODEL_DESCRIPTION='Azure Foundry · ' + deployments['luna_deployment'],
           ANTHROPIC_CUSTOM_MODEL_OPTION='claude-azure-astra[1m]',
           ANTHROPIC_CUSTOM_MODEL_OPTION_NAME=deployments['astra_deployment'],
           ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION='Azure Foundry · ' + deployments['astra_deployment'],
           CLAUDE_CODE_SUBAGENT_MODEL='claude-azure-luna[1m]', CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY='0',
           CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1')
os.execvpe('claude', ['claude', '--model', model] + args, env)
