from litellm.integrations.custom_logger import CustomLogger
from core import normalize_request


class GatewayCompatibility(CustomLogger):
    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        return normalize_request(data)


handler = GatewayCompatibility()
