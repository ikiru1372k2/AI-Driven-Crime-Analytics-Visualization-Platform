"""Catalyst QuickML adapter — area-risk prediction + optional Qwen phrasing.

Two distinct Catalyst capabilities, deliberately kept separate because they are
authenticated differently and matter differently:

1. **Prediction** (`predict`) — the trained QuickML pipeline that forecasts a
   district's next-30-day case count. This is the ONLY source of the forecast
   number. It can be called two ways, tried in this order:

   a. **OAuth REST (server-to-server)** — a self-client refresh token mints a
      short-lived access token; we POST the feature row to the published
      endpoint URL with ``Authorization: Zoho-oauthtoken`` +
      ``X-QUICKML-ENDPOINT-KEY``. This works from the anonymous AppSail runtime
      because it carries its own credentials — no Catalyst request headers
      needed. Preferred, and the path the deployed demo uses.

   b. **Catalyst SDK** (``app.quick_ml().predict``) — fallback for when the app
      is reached THROUGH the authenticated Catalyst gateway, which injects the
      platform headers ``zcatalyst_sdk.initialize()`` requires. It fails with
      "Catalyst headers are empty" on anonymous requests, so it is only a
      fallback, not the primary path.

2. **LLM Serving** (`llm`) — Qwen 2.5 via an OAuth-secured endpoint URL. It only
   rephrases driver facts the engine already computed; it never originates a
   number, and the engine re-checks its output for invented numbers before
   trusting it. Uses the same self-client access token when no static token is
   configured.

Unavailability is normal (unconfigured, not reachable, transient failure). Every
failure raises ``QuickMLUnavailable`` and the caller degrades to an honest
"unavailable" state — never a fabricated forecast.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

#: LLM sampling: low temperature — we want faithful rephrasing, not creativity.
_LLM_TEMPERATURE = 0.2
_LLM_MAX_TOKENS = 160
_LLM_TIMEOUT_S = 12
_PREDICT_TIMEOUT_S = 15
_TOKEN_TIMEOUT_S = 12
#: Refresh the access token this many seconds before it actually expires.
_TOKEN_SKEW_S = 60

#: Process-wide access-token cache, keyed by (accounts_url, client_id,
#: refresh_token). A fresh QuickMLClient is built per request, so caching here
#: (not on the instance) is what avoids minting a token on every /api/risk call.
_token_cache: dict[tuple[str, str, str], tuple[str, float]] = {}
_token_lock = threading.Lock()


class QuickMLUnavailable(RuntimeError):
    """QuickML could not be reached, is unconfigured, or returned junk."""


@dataclass
class QuickMLClient:
    """Live QuickML access.

    OAuth REST path (preferred) needs ``risk_url`` + ``risk_endpoint`` (the
    published endpoint key) + the self-client trio (``client_id``,
    ``client_secret``, ``refresh_token``) + ``accounts_url``. When those are set,
    :meth:`predict` calls the endpoint directly with a minted access token.

    Without the OAuth trio it falls back to the Catalyst SDK (``risk_endpoint``
    only), which only works through the authenticated gateway.

    ``llm_endpoint`` (+ a token, either ``llm_token`` or the minted OAuth token)
    drives the optional Qwen phrasing; when unavailable, :meth:`llm` raises and
    the engine keeps its deterministic sentence.
    """

    risk_endpoint: str | None = None
    risk_url: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    refresh_token: str | None = None
    accounts_url: str = "https://accounts.zoho.in"
    org_id: str | None = None
    environment: str | None = None
    llm_endpoint: str | None = None
    llm_token: str | None = None
    _timeout: int = field(default=_PREDICT_TIMEOUT_S, repr=False)

    # --- OAuth (self-client refresh token -> access token) ----------------
    def _oauth_configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.refresh_token)

    def _access_token(self) -> str:
        """Return a valid access token, minting/refreshing via the refresh token.

        Cached process-wide until shortly before expiry. Raises
        QuickMLUnavailable when the self-client is unconfigured or the token
        endpoint rejects the request.
        """
        if not self._oauth_configured():
            raise QuickMLUnavailable("oauth self-client not configured")
        key = (self.accounts_url, self.client_id or "", self.refresh_token or "")
        now = time.monotonic()
        with _token_lock:
            cached = _token_cache.get(key)
            if cached and cached[1] - _TOKEN_SKEW_S > now:
                return cached[0]

        params = urllib.parse.urlencode(
            {
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
            }
        ).encode("utf-8")
        url = self.accounts_url.rstrip("/") + "/oauth/v2/token"
        req = urllib.request.Request(url, data=params, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=_TOKEN_TIMEOUT_S) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, ValueError, TimeoutError) as exc:
            raise QuickMLUnavailable(
                f"oauth token request failed: {type(exc).__name__}: {exc}"
            ) from exc
        token = payload.get("access_token")
        if not token:
            # Zoho returns 200 with an "error" field on a bad refresh token.
            raise QuickMLUnavailable(f"oauth token error: {payload.get('error', payload)}")
        expires_in = float(payload.get("expires_in", 3600))
        with _token_lock:
            _token_cache[key] = (token, now + expires_in)
        return token

    # --- prediction: OAuth REST (preferred) -------------------------------
    def _predict_rest(self, rows: list[dict]) -> list[dict]:
        token = self._access_token()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Zoho-oauthtoken {token}",
            "X-QUICKML-ENDPOINT-KEY": self.risk_endpoint or "",
        }
        if self.org_id:
            headers["CATALYST-ORG"] = str(self.org_id)
        if self.environment:
            headers["Environment"] = self.environment
        out: list[dict] = []
        for row in rows:
            body = json.dumps({"data": row}).encode("utf-8")
            req = urllib.request.Request(
                self.risk_url or "", data=body, method="POST", headers=headers
            )
            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")[:300]
                raise QuickMLUnavailable(
                    f"quickml predict HTTP {exc.code}: {detail}"
                ) from exc
            except (urllib.error.URLError, ValueError, TimeoutError) as exc:
                raise QuickMLUnavailable(
                    f"quickml predict failed: {type(exc).__name__}: {exc}"
                ) from exc
            out.append(_as_dict(_unwrap(payload)))
        return out

    # --- prediction: Catalyst SDK (fallback) ------------------------------
    def _app(self):
        try:
            import zcatalyst_sdk  # type: ignore[import-not-found]
        except ImportError as exc:  # local dev without the SDK
            raise QuickMLUnavailable("zcatalyst-sdk not installed") from exc
        try:
            return zcatalyst_sdk.initialize()
        except Exception as exc:  # noqa: BLE001 - SDK raises broad errors
            raise QuickMLUnavailable(
                f"catalyst init failed: {type(exc).__name__}: {exc}"
            ) from exc

    def _component(self):
        app = self._app()
        for attr in ("quick_ml", "quickml", "quickML"):
            factory = getattr(app, attr, None)
            if callable(factory):
                return factory()
        raise QuickMLUnavailable("SDK exposes no QuickML component")

    def _predict_sdk(self, rows: list[dict]) -> list[dict]:
        component = self._component()
        out: list[dict] = []
        for row in rows:
            try:
                result = component.predict(self.risk_endpoint, row)
            except Exception as exc:  # noqa: BLE001 - SDK raises broad errors
                raise QuickMLUnavailable(
                    f"quickml predict failed: {type(exc).__name__}: {exc}"
                ) from exc
            out.append(_as_dict(result))
        return out

    def predict(self, rows: list[dict]) -> list[dict]:
        """Predict the target for each feature row via the published endpoint.

        Returns one result dict per input row (order preserved). Prefers the
        OAuth REST path (works from anonymous AppSail); falls back to the SDK
        when the self-client is not configured. Raises QuickMLUnavailable on any
        configuration or call failure so the caller can degrade honestly.
        """
        if not self.risk_endpoint:
            raise QuickMLUnavailable("risk endpoint not configured")
        if not rows:
            return []
        if self.risk_url and self._oauth_configured():
            return self._predict_rest(rows)
        return self._predict_sdk(rows)

    # --- LLM phrasing (OAuth endpoint URL) --------------------------------
    def llm(self, prompt: str) -> str:
        """Rephrase driver facts in plain English via Qwen (LLM Serving).

        Optional polish only. Uses the static ``llm_token`` if set, otherwise the
        minted self-client access token. Raises QuickMLUnavailable when
        unconfigured or on any failure; the engine then keeps its template.
        """
        if not self.llm_endpoint:
            raise QuickMLUnavailable("llm endpoint not configured")
        token = self.llm_token or (self._access_token() if self._oauth_configured() else None)
        if not token:
            raise QuickMLUnavailable("llm token not configured")
        body = json.dumps(
            {
                "prompt": prompt,
                "temperature": _LLM_TEMPERATURE,
                "max_tokens": _LLM_MAX_TOKENS,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            self.llm_endpoint,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Zoho-oauthtoken {token}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=_LLM_TIMEOUT_S) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, ValueError, TimeoutError) as exc:
            raise QuickMLUnavailable(f"llm call failed: {type(exc).__name__}: {exc}") from exc
        text = _llm_text(payload)
        if not text:
            raise QuickMLUnavailable("llm returned no text")
        return text


def _unwrap(payload):
    """Peel a Catalyst REST envelope ({"status","data":…}) down to the payload."""
    if isinstance(payload, dict) and "data" in payload and isinstance(
        payload["data"], (dict, list)
    ):
        return payload["data"]
    return payload


def _as_dict(result) -> dict:
    """Normalise a QuickML predict result into a plain dict."""
    if isinstance(result, dict):
        return result
    if isinstance(result, list) and result and isinstance(result[0], dict):
        return result[0]
    return {"prediction": result}


def _llm_text(payload) -> str:
    """Pull the generated text out of an LLM Serving response, tolerantly."""
    if isinstance(payload, str):
        return payload.strip()
    if not isinstance(payload, dict):
        return ""
    for key in ("output", "text", "response", "generated_text", "content"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    # OpenAI-style choices[].text / choices[].message.content
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            for key in ("text", "content"):
                val = first.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()
            msg = first.get("message")
            if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                return msg["content"].strip()
    return ""
