import time
import traceback
from datetime import datetime
from typing import Any
import requests
from collections.abc import Generator
from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage


def check_type(document_type: str):
    """
    Check the publication type.
    WOS support: https://webofscience.help.clarivate.com/en-us/Content/document-types.html
    """
    if not document_type or document_type == 'All':
        return ''
    if document_type in ['Article', 'Review']:
        return document_type
    else:
        raise ValueError(f"Invalid publication type: {document_type}")


class WosSearchAPI:
    """
    Web of Science Search API tool provider.
    API documentation: https://api.clarivate.com/swagger-ui/?apikey=none&url=https%3A%2F%2Fdeveloper.clarivate.com%2Fapis%2Fwos-starter%2Fswagger
    """
    wos_api_key: str = None
    base_url: str = 'https://api.clarivate.com/apis/wos-starter/v1/documents'
    # switch_grammar = {
    #     "+": 'AND',
    #     "|": 'OR',
    #     "-": 'NOT',
    # }

    def __init__(self, api_key: str) -> None:
        """Initialize Web of Science Search API tool provider."""
        self.wos_api_key = api_key
        self.limit = 50

    def check_query(self, query: str):
        # for key, value in self.switch_grammar.items():
        #     query = query.replace(key, value)
        return f"({query})"

    def get_query(self, query: str, query_type: str = 'TS') -> str:
        """
        Get parameters for Web of Science Search API.
        :param query: query string
        :param query_type: query type: TI(title), AU(author), TS(title, abstract, author keywords, keywords plus), DO(doi), IS(ISSN),  PMID(PubMed ID),
        """
        assert query_type in ['TS', 'TI', 'AU', 'DO', 'IS', 'PMID'], 'Invalid query type'
        query = "{}={}".format(query_type, self.check_query(query))
        return query

    @staticmethod
    def _process_response(response: dict) -> list[dict]:
        """
        Process response from Web of Science Search API.
        response example:

        """
        result = []
        if response and 'hits' in response:
            for wos_document in response['hits']:
                identifiers = wos_document.get('identifiers')
                if not identifiers:
                    continue
                document = {
                    'wos_uid': wos_document.get('uid'),
                    'title': wos_document['title'],
                    'doi': identifiers.get('doi', ''),
                    # 'issn': wos_document['identifiers'].get('issn'),
                    'pmid': identifiers.get('pmid', ''),
                    'year': wos_document['source'].get('publishYear'),
                    # 'month': wos_document['source'].get('publishMonth'),
                    # https://webofscience.help.clarivate.com/en-us/Content/document-types.html
                    'types': wos_document.get('types', []),
                    'link': wos_document['links'].get('record'),
                    'keywords': wos_document['keywords'].get('authorKeywords'),
                    'authors': [author['displayName'] for author in wos_document['names']['authors']],
                }
                result.append(document)
        return result

    def query_once(self, query: str, limit: int = 50, page: int = 1, sort_field: str = 'RS+D', db: str = 'WOK') -> tuple[int, list[dict]]:
        """
        Query Web of Science Search API once.

        Args:
            query: query string
            limit: number of results to return
            page: page number, default is 1(start from 1)
            sort_field: sort field, default is 'RS+D'(Relevance + Descending)
            db: database name, default is 'WOK'(all databases), 'WOS' for Web of Science Core Collection,
             Available values : BCI, BIOABS, BIOSIS, CCC, DIIDW, DRCI, MEDLINE, PPRN, WOK, WOS, ZOOREC
        """
        if limit <= 0:
            return 0, []
        request_str = f'{self.base_url}?q={query}&limit={limit}&page={page}&sortField={sort_field}&db={db}'
        try:
            response = requests.get(request_str, headers={'X-ApiKey': self.wos_api_key})
        except Exception as e:
            traceback.print_exc()
            return 0, []
        if response.status_code != 200:
            return 0, []
        response = response.json()
        total = response['metadata']['total']
        data = self._process_response(response)
        return total, data

    def search(self, query: str, query_type: str = 'TS', year: str = "", document_type: str = '',
               num_results: int = 50, sort_field: str = 'RS+D') -> list[dict]:
        """
        web of science api: https://api.clarivate.com/swagger-ui/?apikey=none&url=https%3A%2F%2Fdeveloper.clarivate.com%2Fapis%2Fwos-starter%2Fswagger
        query_type:
            TI - Title
            AU - Author
            DO - DOI
            IS - ISSN
            DT - Document Type
            TS - Topic, Title, Abstract, Author Keywords, Keywords Plus
            etc.
        sortField: Order by field(s). Field name and order by clause separated by '+', use A for ASC and D for DESC, ex: PY+D. Multiple values are separated by comma. Supported fields:
                    LD - Load Date
                    PY - Publication Year
                    RS - Relevance
                    TC - Times Cited
        """
        query = self.get_query(query, query_type)

        if year:
            if year.endswith('-'):
                year = "{}-{}".format(year, datetime.now().year)
            if year.startswith('-'):
                year = '{}-{}'.format(1900, year)
            query = f"{query} AND PY=({year})"

        document_type = check_type(document_type)
        if document_type:
            query = f"{query} AND DT=({document_type})"

        limit = min(num_results, self.limit)
        page = 1
        total, data = self.query_once(query, limit, page=page, sort_field=sort_field)

        if total == 0:
            return []

        result = data
        rest_num = min(num_results, total) - limit

        while rest_num > 0:
            limit = min(rest_num, self.limit)
            page += 1
            total, data = self.query_once(query, limit, page, sort_field)
            if total == 0:
                break

            result.extend(data)
            rest_num -= limit
            time.sleep(10)

        return result


class WOSSearchTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        """
            invoke tools
        """
        api_key = self.runtime.credentials['wos_api_key']
        query = tool_parameters.get('query')
        query_type = tool_parameters.get('query_type')
        year = tool_parameters.get('year', '')
        document_type = tool_parameters.get('document_type', 'All')
        limit = tool_parameters.get('limit')
        sort_field = tool_parameters.get('sort')
        if not query_type:
            query_type = 'TS'
        if not limit:
            limit = 50
        if not sort_field:
            sort_field = 'RS+D'

        results = WosSearchAPI(api_key).search(query, query_type, year, document_type, limit, sort_field)

        yield [self.create_json_message(r) for r in results]
