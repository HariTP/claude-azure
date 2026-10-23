#!/usr/bin/python3
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path('/etc/claude-azure-local')
sys.path.insert(0, str(ROOT / 'src'))
from core import make_config, docker_args

subprocess.run(['/usr/bin/python3', str(ROOT / 'container-control.py'), 'remove'], check=True)
settings = json.loads((ROOT / 'settings.json').read_text())
key = (Path(os.environ['CREDENTIALS_DIRECTORY']) / 'azure.key').read_text()
token = (ROOT / 'gateway-token').read_text().strip()
config = make_config(settings, key, token)
del key, token
process = subprocess.Popen(docker_args(ROOT / 'src', settings['port'], settings['image']), stdin=subprocess.PIPE)
try:
    process.communicate(json.dumps(config).encode())
    del config
    sys.exit(process.returncode)
except BaseException:
    process.terminate()
    raise
