import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from core import normalize_endpoint, validate, select_linux_storage, make_config, docker_args, normalize_request

SETTINGS = {'endpoint': 'https://example.services.ai.azure.com/openai/v1/',
            'sol_deployment': 'sol-team', 'luna_deployment': 'luna-team', 'port': 48763}


class ConfigurationTests(unittest.TestCase):
    def test_normalizes_resource_and_operation_urls(self):
        for suffix in ('', '/openai', '/openai/v1/', '/openai/v1/responses', '/openai/v1/chat/completions'):
            self.assertEqual(normalize_endpoint('https://example.services.ai.azure.com' + suffix), SETTINGS['endpoint'])

    def test_rejects_duplicated_or_credential_bearing_urls(self):
        for endpoint in ('https://example.test/openai/v1/responseshttps://example.test/openai/v1/responses',
                         'http://example.test', 'https://user:key@example.test', 'https://example.test/?key=secret'):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                normalize_endpoint(endpoint)

    def test_storage_detection_and_explicit_no_downgrade(self):
        self.assertEqual(select_linux_storage('auto', True), 'host+tpm2')
        self.assertEqual(select_linux_storage('auto', False), 'host')
        self.assertEqual(select_linux_storage('host', True), 'host')
        with self.assertRaises(ValueError):
            select_linux_storage('host+tpm2', False)

    def test_bad_deployments_and_ports(self):
        for changes in ({'sol_deployment': '../bad'}, {'luna_deployment': 'x\nkey'}, {'port': 80}, {'port': 65536}, {'port': True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate({**SETTINGS, **changes})

    def test_strips_key_whitespace_and_keeps_config_separate(self):
        original = copy.deepcopy(SETTINGS)
        config = make_config(SETTINGS, '  mock-azure-key \n', 'mock-gateway-token')
        self.assertEqual(SETTINGS, original)
        models = config['model_list']
        self.assertEqual(models[0]['litellm_params']['reasoning_effort'], 'low')
        self.assertEqual(models[1]['litellm_params']['reasoning_effort'], 'none')
        self.assertTrue(all(x['litellm_params']['api_key'] == 'mock-azure-key' for x in models))
        self.assertNotIn('api_key', SETTINGS)

    def test_credentials_never_appear_in_docker_arguments(self):
        args = docker_args('/path with spaces/src', 48763, 'image@sha256:abc')
        self.assertIn('127.0.0.1:48763:4000', args)
        self.assertIn('type=bind,src=/path with spaces/src,dst=/opt/claude-azure,readonly', args)
        self.assertNotIn('mock-azure-key', json.dumps(args))
        self.assertNotIn('--privileged', args)
        self.assertIn('--read-only', args)
        self.assertIn('none', args)  # log driver

    def test_luna_ignores_incompatible_thinking_without_losing_output_format(self):
        request = {'model': 'claude-azure-luna', 'thinking': {'type': 'adaptive'},
                   'output_config': {'effort': 'high', 'format': {'type': 'json_schema'}}}
        result = normalize_request(request)
        self.assertEqual(result['reasoning_effort'], 'none')
        self.assertEqual(result['thinking']['type'], 'disabled')
        self.assertEqual(result['output_config'], {'format': {'type': 'json_schema'}})

    def test_sol_cannot_disable_reasoning_but_can_request_high(self):
        result = normalize_request({'model': 'claude-azure-sol', 'thinking': {'type': 'disabled'}, 'reasoning_effort': 'none'})
        self.assertEqual(result['reasoning_effort'], 'low')
        self.assertEqual(result['thinking']['type'], 'enabled')
        result = normalize_request({'model': 'claude-azure-sol', 'reasoning_effort': 'high'})
        self.assertEqual(result['reasoning_effort'], 'high')

    def test_other_models_are_not_modified(self):
        request = {'model': 'unrelated', 'reasoning_effort': 'high'}
        self.assertEqual(normalize_request(dict(request)), request)


if __name__ == '__main__':
    unittest.main()
