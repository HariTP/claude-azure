#!/usr/bin/python3
"""Privileged installation boundary. Secret input is stdin, never argv."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if os.geteuid() != 0:
    raise SystemExit('This helper requires sudo.')
source = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(source / 'src'))
from core import validate, select_linux_storage

payload = json.load(sys.stdin)
settings = validate(payload['settings'])
key = payload['azure_key'].strip()
if not key:
    raise SystemExit('Empty Azure key.')
lock = json.loads((source / 'image-lock.json').read_text())
if settings['image'] not in lock['images'].values():
    raise SystemExit('Image must match the repository digest lock.')
tpm = subprocess.run(['systemd-creds', 'has-tpm2', '--quiet'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
mode = select_linux_storage(payload['storage'], tpm)
root = Path('/etc/claude-azure-local')
store = Path('/etc/credstore.encrypted')
store.mkdir(mode=0o700, exist_ok=True)
# Encryption completes before replacing any running service files.
with tempfile.TemporaryDirectory(prefix='.claude-azure-', dir=store) as temporary:
    encrypted = Path(temporary) / 'azure.key'
    subprocess.run(['systemd-creds', 'encrypt', '--with-key=' + mode, '--name=azure.key', '-', str(encrypted)],
                   input=key.encode(), check=True, stdout=subprocess.DEVNULL)
    subprocess.run(['systemd-creds', 'decrypt', '--name=azure.key', str(encrypted), '-'],
                   check=True, stdout=subprocess.DEVNULL)
    del key
    root.mkdir(mode=0o700, exist_ok=True)
    os.chmod(root, 0o700)
    shutil.copytree(source / 'src', root / 'src', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copy2(source / 'linux/start.py', root / 'start.py')
    shutil.copy2(source / 'linux/container-control.py', root / 'container-control.py')
    (root / 'settings.json').write_text(json.dumps(settings))
    (root / 'gateway-token').write_text(payload['gateway_token'])
    for path in (root / 'settings.json', root / 'gateway-token'):
        os.chmod(path, 0o600)
    # The container is non-root; its mounted Python code must be readable.
    for path in (root / 'src').rglob('*'):
        os.chmod(path, 0o755 if path.is_dir() else 0o644)
    os.chmod(root / 'src', 0o755)
    os.chmod(encrypted, 0o600)
    os.replace(encrypted, store / 'claude-azure-local.key')
unit = Path('/etc/systemd/system/claude-azure-local.service')
shutil.copy2(source / 'linux/claude-azure-local.service', unit)
os.chmod(unit, 0o644)
subprocess.run(['systemd-analyze', 'verify', str(unit)], check=True)
subprocess.run(['systemctl', 'daemon-reload'], check=True)
subprocess.run(['systemctl', 'enable', 'claude-azure-local.service'], check=True)
subprocess.run(['systemctl', 'restart', 'claude-azure-local.service'], check=True)
print('Encrypted credential installed using ' + mode + '; startup service enabled.')
