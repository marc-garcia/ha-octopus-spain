"""Offline transport tests using synthetic credentials and fake responses."""

import asyncio
import importlib.util
from pathlib import Path
import traceback

import pytest

spec = importlib.util.spec_from_file_location("transport", Path(__file__).parents[1] / "custom_components/octopus_spain/lib/transport.py")
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
SECRET = "SYNTHETIC-PASSWORD-FOR-TESTS"


class Response:
    status = 200
    payload = {"data": {"ok": True}}
    exception = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def json(self):
        if self.exception:
            raise self.exception
        return self.payload


@pytest.fixture
def fake_session(monkeypatch):
    response = Response()
    calls = []

    class Session:
        def __init__(self, **kwargs):
            calls.append(("session", kwargs))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def post(self, url, **kwargs):
            calls.append((url, kwargs))
            return response

    monkeypatch.setattr(t.aiohttp, "ClientSession", Session)
    return response, calls


def request():
    return asyncio.run(t.GraphqlClient(t.GRAPH_QL_ENDPOINT).execute_async("query", {"password": SECRET}))


def test_success_and_transport_boundaries(fake_session):
    response, calls = fake_session
    assert request() == response.payload
    session, request_call = calls
    assert session[1]["trust_env"] is False
    assert isinstance(session[1]["cookie_jar"], t.aiohttp.DummyCookieJar)
    assert request_call[0] == t.GRAPH_QL_ENDPOINT
    assert request_call[1]["ssl"] is True
    assert request_call[1]["allow_redirects"] is False
    assert request_call[1]["json"]["variables"]["password"] == SECRET


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308, 401, 500])
def test_redirects_and_http_errors_fail_without_echo(fake_session, status, caplog):
    response, calls = fake_session
    response.status = status
    response.payload = {"error": SECRET}
    with pytest.raises(t.OctopusTransportError) as e:
        request()
    assert SECRET not in "".join(traceback.format_exception(e.value))
    assert SECRET not in caplog.text
    assert len(calls) == 2


@pytest.mark.parametrize("failure", [ValueError(SECRET), t.aiohttp.ClientConnectionError(SECRET), TimeoutError(SECRET)])
def test_exceptions_do_not_echo_credentials(fake_session, failure, caplog):
    response, _ = fake_session
    response.exception = failure
    with pytest.raises(t.OctopusTransportError) as e:
        request()
    assert SECRET not in "".join(traceback.format_exception(e.value))
    assert SECRET not in caplog.text


@pytest.mark.parametrize(
    "url",
    ["http://api.oees-kraken.energy/v1/graphql/", "https://example.invalid", "https://api.oees-kraken.energy.evil.invalid/v1/graphql/"],
)
def test_rejects_other_endpoints(url):
    with pytest.raises(t.OctopusTransportError):
        t.GraphqlClient(url)


def test_bad_response_type(fake_session):
    response, _ = fake_session
    response.payload = [SECRET]
    with pytest.raises(t.OctopusTransportError):
        request()
