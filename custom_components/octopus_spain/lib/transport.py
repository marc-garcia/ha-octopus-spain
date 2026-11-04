"""Restricted Octopus transport; never expose response bodies in errors."""

import asyncio
import aiohttp

GRAPH_QL_ENDPOINT = "https://api.oees-kraken.energy/v1/graphql/"


class OctopusTransportError(Exception):
    """An intentionally generic, safe-to-log transport failure."""


class GraphqlClient:
    """Only the small async GraphQL surface used by this integration."""

    def __init__(self, endpoint, headers=None):
        if endpoint != GRAPH_QL_ENDPOINT:
            raise OctopusTransportError("Unexpected Octopus endpoint.")
        self.headers = dict(headers or {})

    async def execute_async(self, query, variables=None):
        body = {"query": query}
        if variables is not None:
            body["variables"] = variables
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                trust_env=False,
                cookie_jar=aiohttp.DummyCookieJar(),
            ) as session:
                async with session.post(
                    GRAPH_QL_ENDPOINT,
                    json=body,
                    headers=self.headers,
                    allow_redirects=False,
                    ssl=True,
                ) as response:
                    if response.status != 200:
                        raise OctopusTransportError("Octopus returned an unexpected HTTP status.")
                    result = await response.json()
                    if not isinstance(result, dict):
                        raise OctopusTransportError("Octopus returned an invalid response.")
                    return result
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            # No server message, response body, URL, request data or exception chain.
            raise OctopusTransportError("Unable to communicate securely with Octopus.") from None
