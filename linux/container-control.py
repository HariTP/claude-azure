#!/usr/bin/python3
"""Operate only on this package's labeled container."""
import json
import subprocess
import sys

name = 'claude-azure-local'
result = subprocess.run(['docker', 'inspect', name], capture_output=True, text=True)
if result.returncode:
    sys.exit(0)
container = json.loads(result.stdout)[0]
if container.get('Config', {}).get('Labels', {}).get('org.claude-azure-local.managed') != 'true':
    raise SystemExit('Container name is occupied by an unmanaged container; left unchanged.')
command = ['docker', 'stop', '--time', '20', name] if sys.argv[1:] == ['stop'] else ['docker', 'rm', '-f', name]
subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
