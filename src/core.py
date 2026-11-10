"""Shared configuration, validation and Docker arguments. Python standard library only."""
import json
import re
from urllib.parse import urlsplit

CONTAINER = 'claude-azure-local'
SERVICE = 'claude-azure-local.service'
MODEL_SOL = 'claude-azure-sol'
MODEL_LUNA = 'claude-azure-luna'
MODEL_ASTRA = 'claude-azure-astra'
MODEL_GROK = 'claude-azure-grok'
GPT_MODELS = (MODEL_SOL, MODEL_LUNA, MODEL_ASTRA)


def normalize_endpoint(value):
    url = urlsplit(value.strip())
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError('Use an HTTPS Azure resource URL without credentials, query or fragment.')
    path = url.path.rstrip('/')
    for suffix in ('/chat/completions', '/responses'):
        if path.endswith(suffix):
            path = path[:-len(suffix)]
            break
    if path in ('', '/openai'):
        path = '/openai/v1'
    if path != '/openai/v1':
        raise ValueError('Expected an Azure resource URL or a single /openai/v1/ endpoint.')
    return f'https://{url.netloc}{path}/'


def validate(settings):
    result = dict(settings)
    result['endpoint'] = normalize_endpoint(result['endpoint'])
    for field in ('sol_deployment', 'luna_deployment', 'astra_deployment', 'grok_deployment'):
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', result[field]):
            raise ValueError(f'Invalid deployment name: {field}')
    port = int(result['port'])
    if isinstance(result['port'], bool) or not 1024 <= port <= 65535:
        raise ValueError('Choose a port between 1024 and 65535.')
    result['port'] = port
    return result


def make_config(settings, azure_key, gateway_token):
    settings = validate(settings)
    azure_key = azure_key.strip()
    if not azure_key or not gateway_token:
        raise ValueError('Both credentials must be nonempty.')
    models = []
    for alias, deployment, effort in (
        (MODEL_SOL, settings['sol_deployment'], 'low'),
        (MODEL_LUNA, settings['luna_deployment'], 'none'),
        (MODEL_ASTRA, settings['astra_deployment'], 'low'),
        (MODEL_GROK, settings['grok_deployment'], None),
    ):
        params = {'model': 'openai/' + deployment, 'api_base': settings['endpoint'],
                  'api_key': azure_key, 'use_chat_completions_api': True}
        if effort is not None:
            params['reasoning_effort'] = effort
        for name in ((alias, alias + '[1m]') if alias in GPT_MODELS else (alias,)):
            models.append({'model_name': name, 'litellm_params': dict(params),
                           'model_info': {'display_name': deployment}})
    return {
        'model_list': models,
        'litellm_settings': {
            'drop_params': True, 'set_verbose': False, 'turn_off_message_logging': True,
            'telemetry': False, 'use_chat_completions_url_for_anthropic_messages': True,
            'route_all_chat_openai_to_responses': False, 'callbacks': ['compat.handler'],
        },
        'general_settings': {'master_key': gateway_token, 'disable_spend_logs': True},
    }


def normalize_request(data):
    """Keep Luna on Chat Completions and reasoning enabled for Sol and Astra."""
    model = data.get('model')
    if model in (MODEL_LUNA, MODEL_LUNA + '[1m]'):
        data['reasoning_effort'] = 'none'
        data['thinking'] = {'type': 'disabled'}
        if isinstance(data.get('output_config'), dict):
            data['output_config'] = {k: v for k, v in data['output_config'].items() if k != 'effort'}
    elif model in (MODEL_SOL, MODEL_SOL + '[1m]', MODEL_ASTRA, MODEL_ASTRA + '[1m]'):
        if data.get('reasoning_effort') in (None, 'none', 'minimal'):
            data['reasoning_effort'] = 'low'
        if isinstance(data.get('thinking'), dict) and data['thinking'].get('type') == 'disabled':
            data['thinking'] = {'type': 'enabled', 'budget_tokens': 1024}
        if isinstance(data.get('output_config'), dict) and data['output_config'].get('effort') in ('none', 'minimal'):
            data['output_config']['effort'] = 'low'
    return data


def select_linux_storage(requested, tpm_available):
    if requested not in ('auto', 'host', 'host+tpm2'):
        raise ValueError('Unknown credential-storage mode.')
    if requested == 'host+tpm2' and not tpm_available:
        raise ValueError('TPM protection was requested but is unavailable; no downgrade performed.')
    if requested == 'auto':
        return 'host+tpm2' if tpm_available else 'host'
    return requested


def docker_args(source, port, image, *, network=None):
    args = ['docker', 'run', '--rm', '-i', '--name', CONTAINER,
            '--label', 'org.claude-azure-local.managed=true',
            '--user', '65532:65532', '--read-only', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges:true', '--pids-limit', '256',
            '--memory', '2g', '--cpus', '2', '--log-driver', 'none',
            '--tmpfs', '/tmp:rw,nosuid,nodev,size=256m,mode=1777',
            '--env', 'HOME=/tmp', '--env', 'PYTHONPATH=/opt/claude-azure',
            '--env', 'LITELLM_TELEMETRY=False', '--env', 'LITELLM_LOCAL_MODEL_COST_MAP=True',
            '--env', 'LITELLM_USE_CHAT_COMPLETIONS_URL_FOR_ANTHROPIC_MESSAGES=true',
            '--env', 'LITELLM_ROUTE_ALL_CHAT_OPENAI_TO_RESPONSES=false',
            '--mount', f'type=bind,src={source},dst=/opt/claude-azure,readonly']
    if network:
        args += ['--network', network]
    else:
        args += ['--publish', f'127.0.0.1:{int(port)}:4000']
    return args + ['--entrypoint', '/app/.venv/bin/python', image, '/opt/claude-azure/bootstrap.py']
