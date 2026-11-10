"""Run inside the pinned image with --network none. No Azure credentials needed."""
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, '/repo/src')
from core import make_config
paths = []


def response_object(model, output):
    return dict(id='resp_mock', object='response', created_at=1, status='completed', model=model,
                output=output, error=None, incomplete_details=None, instructions=None,
                parallel_tool_calls=True, tools=[], tool_choice='auto', metadata={},
                usage={'input_tokens': 20, 'output_tokens': 5, 'total_tokens': 25,
                       'input_tokens_details': {'cached_tokens': 0}, 'output_tokens_details': {'reasoning_tokens': 0}})


class Upstream(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        paths.append((body['model'], self.path))
        model = body['model']
        self.send_response(200)
        if model in ('gpt-6.1-sol', 'gpt-6-astra'):
            assert self.path == '/v1/responses', self.path
            assert body.get('reasoning', {}).get('effort') != 'none'
            call = {'id': 'fc_mock', 'type': 'function_call', 'call_id': 'call_mock',
                    'name': 'choose_color', 'arguments': '{"color":"blue"}', 'status': 'completed'}
            if body.get('stream'):
                self.send_header('Content-Type', 'text/event-stream'); self.end_headers()
                seq = 0
                def emit(kind, **extra):
                    nonlocal seq
                    event = {'type': kind, 'sequence_number': seq, **extra}; seq += 1
                    self.wfile.write(('event: ' + kind + '\ndata: ' + json.dumps(event) + '\n\n').encode()); self.wfile.flush()
                started = response_object(model, []); started['status'] = 'in_progress'; started['usage'] = None
                emit('response.created', response=started)
                emit('response.output_item.added', output_index=0, item={**call, 'arguments': '', 'status': 'in_progress'})
                emit('response.function_call_arguments.delta', item_id='fc_mock', output_index=0, delta=call['arguments'])
                emit('response.function_call_arguments.done', item_id='fc_mock', output_index=0, arguments=call['arguments'], name='choose_color')
                emit('response.output_item.done', output_index=0, item=call)
                emit('response.completed', response=response_object(model, [call]))
            else:
                assert any(item.get('type') == 'function_call_output' for item in body['input'])
                self.send_header('Content-Type', 'application/json'); self.end_headers()
                message = {'id': 'msg_mock', 'type': 'message', 'status': 'completed', 'role': 'assistant',
                           'content': [{'type': 'output_text', 'text': 'Recorded blue.', 'annotations': []}]}
                self.wfile.write(json.dumps(response_object(model, [message])).encode())
        else:
            assert model in ('gpt-6-luna', 'grok-4.6'), model
            assert self.path == '/v1/chat/completions', self.path
            if model == 'gpt-6-luna':
                assert body.get('reasoning_effort') == 'none', body.get('reasoning_effort')
            else:
                assert 'reasoning_effort' not in body, body.get('reasoning_effort')
            base = {'id': 'chatcmpl-mock', 'object': 'chat.completion', 'created': 1, 'model': model}
            if body.get('stream'):
                self.send_header('Content-Type', 'text/event-stream'); self.end_headers()
                def emit(delta, finish=None):
                    chunk = {**base, 'object': 'chat.completion.chunk', 'choices': [{'index': 0, 'delta': delta, 'finish_reason': finish}]}
                    self.wfile.write(('data: ' + json.dumps(chunk) + '\n\n').encode()); self.wfile.flush()
                emit({'role': 'assistant', 'content': None})
                emit({'tool_calls': [{'index': 0, 'id': 'call_mock', 'type': 'function', 'function': {'name': 'choose_color', 'arguments': ''}}]})
                emit({'tool_calls': [{'index': 0, 'function': {'arguments': '{"color":"blue"}'}}]})
                emit({}, 'tool_calls')
                self.wfile.write(b'data: [DONE]\n\n'); self.wfile.flush()
            else:
                assert any(item.get('role') == 'tool' for item in body['messages'])
                self.send_header('Content-Type', 'application/json'); self.end_headers()
                self.wfile.write(json.dumps({**base, 'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': 'Recorded blue.'}, 'finish_reason': 'stop'}],
                                            'usage': {'prompt_tokens': 20, 'completion_tokens': 5, 'total_tokens': 25}}).encode())


server = ThreadingHTTPServer(('127.0.0.1', 48864), Upstream)
threading.Thread(target=server.serve_forever, daemon=True).start()
settings = {'endpoint': 'https://example.services.ai.azure.com/openai/v1',
            'sol_deployment': 'gpt-6.1-sol', 'luna_deployment': 'gpt-6-luna',
            'astra_deployment': 'gpt-6-astra', 'grok_deployment': 'grok-4.6', 'port': 4000}
config = make_config(settings, 'mock-azure-key', 'sk-mock-token')
for model in config['model_list']:
    model['litellm_params']['api_base'] = 'http://127.0.0.1:48864/v1/'
Path('/tmp/token').write_text('sk-mock-token')
process = subprocess.Popen(['/app/.venv/bin/python', '/repo/src/bootstrap.py'], stdin=subprocess.PIPE,
                           stdout=subprocess.DEVNULL, stderr=open('/tmp/proxy-errors', 'w'))
process.stdin.write(json.dumps(config).encode()); process.stdin.close()
try:
    result = subprocess.run(['/app/.venv/bin/python', '/repo/src/verify.py', '--port', '4000', '--token-file', '/tmp/token'], timeout=120)
    if result.returncode:
        print(Path('/tmp/proxy-errors').read_text()[-5000:])
        raise SystemExit(result.returncode)
    assert paths == ([('gpt-6.1-sol', '/v1/responses')] * 2
                     + [('gpt-6-luna', '/v1/chat/completions')] * 2
                     + [('gpt-6-astra', '/v1/responses')] * 2
                     + [('grok-4.6', '/v1/chat/completions')] * 2), paths
    print('Verified: Sol and Astra Responses, Luna and Grok Chat Completions; streaming and tool-result round trips.')
finally:
    process.terminate(); process.wait(timeout=20); server.shutdown()
