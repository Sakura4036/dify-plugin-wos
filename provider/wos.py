from typing import Any

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from tools.wos_search import WOSSearchTool


class WosProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        try:
            WOSSearchTool().fork_tool_runtime(
                runtime={
                    "credentials": credentials,
                }
            ).invoke(
                tool_parameters={
                    "query": "test",
                    "query_type": "TS",
                    "limit": 10,
                    "page": 1
                },
            )
        except Exception as e:
            raise ToolProviderCredentialValidationError(str(e))
