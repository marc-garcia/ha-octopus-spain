"""Exercise the real API class without loading Home Assistant."""

import asyncio
import importlib
from pathlib import Path
import sys
import types

import pytest

package = types.ModuleType("_octopus_review_lib")
package.__path__ = [str(Path(__file__).parents[1] / "custom_components/octopus_spain/lib")]
sys.modules[package.__name__] = package
api_module = importlib.import_module(package.__name__ + ".octopus_spain")


def test_runtime_client_does_not_retain_plaintext(monkeypatch):
    seen = []
    count = 0

    async def provider():
        nonlocal count
        count += 1
        return "synthetic-email", "synthetic-password"

    class Client:
        def __init__(self, **kwargs):
            pass

        async def execute_async(self, query, variables):
            seen.append(variables)
            return {"data": {"obtainKrakenToken": {"token": "synthetic-token"}}}

    monkeypatch.setattr(api_module, "GraphqlClient", Client)
    api = api_module.OctopusSpain(credentials_provider=provider)
    assert asyncio.run(api.login())
    assert asyncio.run(api.login())
    assert count == 2
    assert seen[0]["input"]["password"] == "synthetic-password"
    assert api._email is None and api._password is None
    assert "synthetic-password" not in repr(vars(api))


def test_remote_error_message_is_not_forwarded():
    response = {"errors": [{"message": "server echoes synthetic-password"}]}
    assert "synthetic-password" not in api_module.OctopusSpain._error_message(response)


def test_unavailable_credentials_prevent_network(monkeypatch):
    async def provider():
        raise ValueError("external key unavailable")

    def forbidden(**kwargs):
        pytest.fail("Network client must not be constructed")

    monkeypatch.setattr(api_module, "GraphqlClient", forbidden)
    with pytest.raises(ValueError, match="external key unavailable"):
        asyncio.run(api_module.OctopusSpain(credentials_provider=provider).login())
