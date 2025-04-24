from typing import Any

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from tools.wos_search import WosSearchAPI


class WosProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        try:
            WosSearchAPI(api_key=credentials.get('wos_api_key')).query_once(
                query="test",
            )
        except Exception as e:
            raise ToolProviderCredentialValidationError(str(e))
