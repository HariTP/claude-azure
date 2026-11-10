#!/usr/bin/env python3
import argparse
import getpass
import json
import os
import platform
import secrets
import shutil
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'src'))
from core import normalize_endpoint, select_linux_storage, validate


def private_write(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(value)
    os.chmod(path, 0o600)


def ask(prompt, default=''):
    value = input(prompt + (f' [{default}]' if default else '') + ': ').strip()
    return value or default


def main():
    parser = argparse.ArgumentParser(description='Install a private, local Azure gateway.')
    parser.add_argument('--storage', choices=['auto', 'host+tpm2', 'host'], default='auto')
    options = parser.parse_args()
    if sys.platform != 'linux' or not Path('/run/systemd/system').exists():
        raise SystemExit('Linux with systemd is required. No plaintext fallback will be installed.')
    if os.geteuid() == 0:
        raise SystemExit('Run as your normal user; setup requests sudo when needed.')
    if not sys.stdin.isatty():
        raise SystemExit('Run interactively so the key can be entered without echo.')
    for command in ('docker', 'claude', 'systemd-creds', 'sudo', '/usr/bin/python3'):
        if not shutil.which(command):
            raise SystemExit('Install prerequisite first: ' + command)
    destination = Path.home() / '.local/bin/claude-azure'
    profile = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'claude-azure-local'
    if destination.exists() and not (profile / 'installed.json').exists():
        raise SystemExit('A claude-azure command already exists. It was left unchanged. See README migration guidance.')
    original = Path(os.environ.get('CLAUDE_CONFIG_DIR', str(Path.home() / '.claude'))).resolve()
    if not (original / 'projects').is_dir():
        raise SystemExit('Start normal Claude Code once before setup, so its chat directory exists.')
    subprocess.run(['sudo', '-v'], check=True)
    tpm = subprocess.run(['sudo', '-n', 'systemd-creds', 'has-tpm2', '--quiet'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    mode = select_linux_storage(options.storage, tpm)
    print('Credential storage: ' + mode)
    if mode == 'host':
        print('Host-key encryption supports boot without TPM, but does not protect against a full-disk read including the host key.')
    else:
        print('Encryption is bound to this TPM and OS installation. Secure Boot policy changes may require re-enrollment.')
    old = json.loads((profile / 'settings.json').read_text()) if (profile / 'settings.json').exists() else {}
    endpoint = normalize_endpoint(ask('Azure endpoint', old.get('endpoint', '')))
    sol = ask('Sol deployment', old.get('sol_deployment', 'gpt-6.1-sol'))
    luna = ask('Luna deployment', old.get('luna_deployment', 'gpt-6-luna'))
    astra = ask('Astra deployment', old.get('astra_deployment', 'gpt-6-astra'))
    grok = ask('Grok deployment', old.get('grok_deployment', 'grok-4.6'))
    port = int(ask('Local port', str(old.get('port', 48763))))
    settings = validate(dict(endpoint=endpoint, sol_deployment=sol, luna_deployment=luna,
                             astra_deployment=astra, grok_deployment=grok, port=port))
    # A previous instance may own the port; otherwise refuse a collision before asking for a key.
    existing = subprocess.run(['docker', 'inspect', 'claude-azure-local'], capture_output=True, text=True)
    if existing.returncode == 0:
        container = json.loads(existing.stdout)[0]
        if container.get('Config', {}).get('Labels', {}).get('org.claude-azure-local.managed') != 'true':
            raise SystemExit('Container name is occupied by an unmanaged container; left unchanged.')
    running = subprocess.check_output(['docker', 'ps', '--filter', 'name=^/claude-azure-local$', '--format', '{{.Names}}'], text=True).strip()
    if not running:
        with socket.socket() as sock:
            try:
                sock.bind(('127.0.0.1', port))
            except OSError:
                raise SystemExit('Port is occupied. Rerun setup and select another local port.')
    arch = subprocess.check_output(['docker', 'info', '--format', '{{.Architecture}}'], text=True).strip()
    arch = {'x86_64': 'amd64', 'aarch64': 'arm64'}.get(arch, arch)
    images = json.loads((ROOT / 'image-lock.json').read_text())['images']
    if arch not in images:
        raise SystemExit('Unsupported Docker architecture: ' + arch)
    settings['image'] = images[arch]
    subprocess.run(['docker', 'pull', settings['image']], check=True)
    print('Sol and Astra tools use Responses. Luna uses Chat Completions with reasoning disabled.')
    key = getpass.getpass('Azure key (hidden; never saved as plaintext): ').strip()
    if not key:
        raise SystemExit('No key entered; nothing installed.')
    token = (profile / 'gateway-token').read_text().strip() if (profile / 'gateway-token').exists() else 'sk-' + secrets.token_urlsafe(40)
    payload = json.dumps(dict(settings=settings, azure_key=key, gateway_token=token, storage=mode)).encode()
    subprocess.run(['sudo', '-n', '/usr/bin/python3', str(ROOT / 'linux/install-root.py')], input=payload, check=True)
    del key, payload
    profile.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(profile, 0o700)
    # Install only private launcher files; do not replace the user's normal Claude settings.
    shutil.copy2(ROOT / 'linux/launch.py', profile / 'launch.py')
    private_write(profile / 'gateway-token', token)
    private_write(profile / 'connection.json', json.dumps({'port': port}))
    private_write(profile / 'settings.json', json.dumps(settings))
    claude_profile = profile / 'claude'
    claude_profile.mkdir(mode=0o700, exist_ok=True)
    for name in ('projects', 'history.jsonl'):
        source = original / name
        target = claude_profile / name
        if source.exists():
            if target.is_symlink() and target.resolve() == source.resolve():
                continue
            if target.exists() or target.is_symlink():
                raise SystemExit('Existing profile link conflicts; left unchanged: ' + name)
            target.symlink_to(source, target_is_directory=source.is_dir())
    claude_settings_path = claude_profile / 'settings.json'
    claude_settings = json.loads(claude_settings_path.read_text()) if claude_settings_path.exists() else {}
    claude_settings['availableModels'] = [
        'claude-azure-sol[1m]', 'claude-azure-luna[1m]',
        'claude-azure-astra[1m]', 'claude-azure-grok',
    ]
    model_settings = claude_settings.setdefault('modelSettings', {})
    for alias in ('claude-azure-sol', 'claude-azure-luna', 'claude-azure-astra'):
        model_settings.setdefault(alias + '[1m]', {})['autoCompactWindow'] = 900000
    private_write(claude_settings_path, json.dumps(claude_settings, indent=2) + '\n')
    destination.parent.mkdir(parents=True, exist_ok=True)
    # The launcher is a copied script; paths are derived from XDG_CONFIG_HOME at runtime.
    shutil.copy2(ROOT / 'linux/launch.py', destination)
    os.chmod(destination, 0o700)
    private_write(profile / 'installed.json', json.dumps({'version': 1, 'storage': mode}))
    print('Installed. Ensure ~/.local/bin is on PATH. Run: claude-azure --resume')
    print('Verify with: python3 ' + str(ROOT / 'src/verify.py') + ' --port ' + str(port) + ' --token-file ' + str(profile / 'gateway-token'))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, subprocess.CalledProcessError, KeyboardInterrupt) as error:
        if isinstance(error, subprocess.CalledProcessError):
            raise SystemExit('A setup command failed. Credential contents were not printed. Existing files may require rerunning setup.')
        raise SystemExit(str(error) or 'Canceled.')
