"""QuickML adapter — OAuth REST predict path (the deployed forecast route).

Hermetic: urllib is mocked, so these test OUR request shaping, token caching,
envelope unwrapping and the honest-failure contract — never a live Zoho call.
"""

import io
import json

import pytest

from kavach.catalyst import quickml
from kavach.catalyst.quickml import QuickMLClient, QuickMLUnavailable


class FakeResp(io.BytesIO):
    """Minimal urlopen() stand-in: a context manager whose read() returns bytes."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _oauth_client(**over):
    base = dict(
        risk_endpoint="ep-key",
        risk_url="https://api.catalyst.zoho.in/quickml/v1/project/1/endpoints/predict",
        client_id="cid",
        client_secret="secret",
        refresh_token="rtok",
        accounts_url="https://accounts.zoho.in",
        org_id="60078928452",
        environment="Development",
    )
    base.update(over)
    return QuickMLClient(**base)


@pytest.fixture(autouse=True)
def _clear_token_cache():
    quickml._token_cache.clear()
    yield
    quickml._token_cache.clear()


def test_predict_rest_mints_token_and_sends_expected_request(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout=0):
        calls.append(req)
        if req.full_url.endswith("/oauth/v2/token"):
            return FakeResp(json.dumps({"access_token": "AT123", "expires_in": 3600}).encode())
        # predict call
        assert req.get_header("X-quickml-endpoint-key") == "ep-key"
        assert req.get_header("Authorization") == "Zoho-oauthtoken AT123"
        assert req.get_header("Catalyst-org") == "60078928452"
        assert req.get_header("Environment") == "Development"
        body = json.loads(req.data.decode())
        assert set(body) == {"data"}  # payload wrapped exactly as the SDK does
        ok = {"status": "success", "data": {"target_next_count": 42}}
        return FakeResp(json.dumps(ok).encode())

    monkeypatch.setattr(quickml.urllib.request, "urlopen", fake_urlopen)
    out = _oauth_client().predict([{"recent_count": 10}])
    assert out == [{"target_next_count": 42}]
    # token request + one predict
    assert len(calls) == 2


def test_predict_rest_reuses_cached_token_across_rows(monkeypatch):
    token_reqs = {"n": 0}

    def fake_urlopen(req, timeout=0):
        if req.full_url.endswith("/oauth/v2/token"):
            token_reqs["n"] += 1
            return FakeResp(json.dumps({"access_token": "AT", "expires_in": 3600}).encode())
        return FakeResp(json.dumps({"prediction": 7}).encode())

    monkeypatch.setattr(quickml.urllib.request, "urlopen", fake_urlopen)
    out = _oauth_client().predict([{"a": 1}, {"a": 2}, {"a": 3}])
    assert [o["prediction"] for o in out] == [7, 7, 7]
    assert token_reqs["n"] == 1, "one token minted and reused for all rows"


def test_bad_refresh_token_is_unavailable(monkeypatch):
    def fake_urlopen(req, timeout=0):
        # Zoho returns 200 + an error field on a bad refresh token
        return FakeResp(json.dumps({"error": "invalid_code"}).encode())

    monkeypatch.setattr(quickml.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(QuickMLUnavailable, match="oauth token error"):
        _oauth_client().predict([{"a": 1}])


def test_predict_requires_endpoint_key():
    with pytest.raises(QuickMLUnavailable, match="risk endpoint not configured"):
        QuickMLClient().predict([{"a": 1}])


def test_predict_without_oauth_falls_back_to_sdk(monkeypatch):
    """No self-client -> SDK path; with the SDK absent that surfaces honestly."""
    client = QuickMLClient(risk_endpoint="ep-key")  # no risk_url / oauth trio
    monkeypatch.setitem(__import__("sys").modules, "zcatalyst_sdk", None)
    with pytest.raises(QuickMLUnavailable):
        client.predict([{"a": 1}])


def test_unwrap_and_as_dict():
    assert quickml._unwrap({"status": "ok", "data": {"x": 1}}) == {"x": 1}
    assert quickml._unwrap({"x": 1}) == {"x": 1}
    assert quickml._as_dict([{"y": 2}]) == {"y": 2}
    assert quickml._as_dict(5) == {"prediction": 5}
