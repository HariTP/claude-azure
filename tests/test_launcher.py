import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'"alive"')


@unittest.skipUnless(sys.platform == 'linux', 'Tests the Linux launcher; Windows has a PowerShell fixture.')
class LauncherTests(unittest.TestCase):
    def test_resume_and_child_only_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = root / 'config/claude-azure-local'
            profile.mkdir(parents=True)
            server = ThreadingHTTPServer(('127.0.0.1', 0), HealthHandler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            (profile / 'connection.json').write_text(json.dumps({'port': server.server_port}))
            (profile / 'gateway-token').write_text('mock-token')
            bindir = root / 'bin'; bindir.mkdir()
            fake = bindir / 'claude'
            fake.write_text('#!' + sys.executable + '\nimport json,os,sys\nprint(json.dumps({"args":sys.argv[1:],"model":os.environ["ANTHROPIC_MODEL"],"key_present":bool(os.environ.get("ANTHROPIC_API_KEY")),"profile":os.environ["CLAUDE_CONFIG_DIR"]}))\n')
            fake.chmod(0o755)
            env = {**os.environ, 'PATH': str(bindir) + ':' + os.environ['PATH'],
                   'XDG_CONFIG_HOME': str(root / 'config'), 'ANTHROPIC_API_KEY': 'mock-parent-key'}
            try:
                result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'linux/launch.py'), '--luna', '--resume'],
                                        env=env, check=True, capture_output=True, text=True)
                data = json.loads(result.stdout)
                self.assertEqual(data['args'], ['--model', 'claude-azure-luna', '--resume'])
                self.assertFalse(data['key_present'])
                self.assertEqual(data['profile'], str(profile / 'claude'))
                self.assertEqual(env['ANTHROPIC_API_KEY'], 'mock-parent-key')
            finally:
                server.shutdown(); server.server_close()


if __name__ == '__main__':
    unittest.main()
