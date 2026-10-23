#!/usr/bin/env python3
"""Check the Messages adapter without printing credentials or model content."""
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int, default=48763)
parser.add_argument('--token-file', type=Path, required=True)
options = parser.parse_args()
base = 'http://127.0.0.1:' + str(options.port)
token_path = options.token_file
token = token_path.read_text().strip()
headers = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json', 'anthropic-version': '2023-06-01'}


def request(path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    try:
        return urllib.request.urlopen(urllib.request.Request(base + path, data=data, headers=headers), timeout=120)
    except urllib.error.HTTPError as error:
        # Classify this known failure without displaying raw provider content.
        body = error.read().lower()
        if error.code == 400 and b'reasoning_effort' in body and b'function tools' in body:
            raise RuntimeError('Tool calling requires model-specific reasoning/API routing. Run setup again to apply the supported configuration.') from None
        raise


def main():
    for attempt in range(90):
        try:
            with request('/health/liveliness') as response:
                if response.status == 200:
                    break
        except (OSError, urllib.error.URLError):
            time.sleep(1)
    else:
        raise RuntimeError('Gateway did not become ready; check sudo systemctl status litellm-azure.')

    with request('/v1/models') as response:
        discovered = {model['id'] for model in json.load(response)['data']}
    for model in ['claude-azure-sol', 'claude-azure-luna']:
        if model not in discovered:
            raise RuntimeError('Configured model missing from gateway discovery: ' + model)
        messages = [{'role': 'user', 'content': 'Call choose_color with color blue.'}]
        payload = {
            'model': model, 'max_tokens': 1024, 'stream': True, 'messages': messages,
            'tools': [{'name': 'choose_color', 'description': 'Choose a color.', 'input_schema': {
                'type': 'object', 'properties': {'color': {'type': 'string', 'enum': ['blue']}},
                'required': ['color'], 'additionalProperties': False}}],
            'tool_choice': {'type': 'tool', 'name': 'choose_color'},
        }
        tool = None
        arguments = ''
        stopped = False
        with request('/v1/messages', payload) as response:
            for line in response:
                if not line.startswith(b'data:'):
                    continue
                raw = line[5:].strip()
                if raw == b'[DONE]':
                    continue
                event = json.loads(raw)
                kind = event.get('type')
                if kind == 'error':
                    raise RuntimeError('Gateway returned a stream error for ' + model)
                if kind == 'content_block_start' and event['content_block']['type'] == 'tool_use':
                    tool = event['content_block']
                elif kind == 'content_block_delta' and event['delta']['type'] == 'input_json_delta':
                    arguments += event['delta']['partial_json']
                elif kind == 'message_stop':
                    stopped = True
        if not stopped or not tool or tool['name'] != 'choose_color':
            raise RuntimeError('Streaming tool calling failed for ' + model)
        parsed = json.loads(arguments) if arguments else tool.get('input', {})
        if parsed.get('color') != 'blue':
            raise RuntimeError('Unexpected tool arguments for ' + model)
        messages += [
            {'role': 'assistant', 'content': [{'type': 'tool_use', 'id': tool['id'], 'name': tool['name'], 'input': parsed}]},
            {'role': 'user', 'content': [{'type': 'tool_result', 'tool_use_id': tool['id'], 'content': 'Color recorded: blue.'}]},
        ]
        payload.update(messages=messages, stream=False, tool_choice={'type': 'none'})
        with request('/v1/messages', payload) as response:
            result = json.load(response)
        if not any(block.get('type') == 'text' and block.get('text') for block in result.get('content', [])):
            raise RuntimeError('Tool-result continuation produced no text for ' + model)
        print(model + ': discovery, streaming, tool call, and tool-result continuation passed.')


if __name__ == '__main__':
    try:
        main()
    except urllib.error.HTTPError as error:
        raise SystemExit('Gateway request failed (HTTP ' + str(error.code) + '). Response body withheld to avoid logging sensitive data.')
    except (RuntimeError, OSError, ValueError) as error:
        raise SystemExit(str(error))
