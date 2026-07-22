"""Catalyst QuickML adapter — area-risk prediction + optional Qwen phrasing.

Two distinct Catalyst capabilities, deliberately kept separate because they are
authenticated differently and matter differently:

1. **Prediction** (`predict`) — the trained QuickML pipeline that forecasts a
   district's next-30-day case count. Called live from AppSail through the
   Catalyst SDK: ``app.quick_ml().predict(endpoint_key, row)`` resolves the
   project's own credentials inside the runtime, so no end-user request headers
   are needed (verified capability, docs.catalyst.zoho.com/.../execute-quickml-endpoints).
   This is the ONLY source of the forecast number.

2. **LLM Serving** (`llm`) — Qwen 2.5 via an OAuth-secured endpoint URL (NOT the
   SDK predict path; LLM Serving is endpoint-URL + OAuth). It only rephrases
   driver facts the engine already computed; it never originates a number, and
   the engine re-checks its output for invented numbers before trusting it.

Unavailability is normal (SDK absent locally, endpoint unset, not a Catalyst
runtime, transient failure). Every failure raises ``QuickMLUnavailable`` and the
caller degrades to an honest "unavailable" state — never a fabricated forecast.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass

logger = logging.getLogger(__name__)

#: LLM sampling: low temperature — we want faithful rephrasing, not creativity.
_LLM_TEMPERATURE = 0.2
_LLM_MAX_TOKENS = 160
_LLM_TIMEOUT_S = 12


class QuickMLUnavailable(RuntimeError):
    """QuickML could not be reached, is unconfigured, or returned junk."""


@dataclass
class QuickMLClient:
    """Live QuickML access from the Catalyst runtime.

    ``risk_endpoint`` is the published pipeline endpoint key (SDK predict).
    ``llm_endpoint``/``llm_token`` drive the optional Qwen phrasing call; when
    either is missing, :meth:`llm` raises and the engine keeps its deterministic
    sentence.
    """

    risk_endpoint: str | None = None
    llm_endpoint: str | None = None
    llm_token: str | None = None

    # --- prediction (SDK) -------------------------------------------------
    def _app(self):
        try:
            import zcatalyst_sdk  # type: ignore[import-not-found]
        except ImportError as exc:  # local dev without the SDK
            raise QuickMLUnavailable("zcatalyst-sdk not installed") from exc
        try:
            # AppSail resolves the project's own credentials — no request headers.
            return zcatalyst_sdk.initialize()
        except Exception as exc:  # noqa: BLE001 - SDK raises broad errors
            raise QuickMLUnavailable(
                f"catalyst init failed: {type(exc).__name__}: {exc}"
            ) from exc

    def _component(self):
        app = self._app()
        # The Python SDK exposes QuickML as app.quick_ml(); tolerate camelCase
        # aliases across SDK versions rather than assume one spelling.
        for attr in ("quick_ml", "quickml", "quickML"):
            factory = getattr(app, attr, None)
            if callable(factory):
                return factory()
        raise QuickMLUnavailable("SDK exposes no QuickML component")

    def predict(self, rows: list[dict]) -> list[dict]:
        """Predict the target for each feature row via the published endpoint.

        Returns one result dict per input row (order preserved). Raises
        QuickMLUnavailable on any configuration or call failure so the caller
        can fall back to the honest "unavailable" state.
        """
        if not self.risk_endpoint:
            raise QuickMLUnavailable("risk endpoint not configured")
        if not rows:
            return []
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

    # --- LLM phrasing (OAuth endpoint URL) --------------------------------
    def llm(self, prompt: str) -> str:
        """Rephrase driver facts in plain English via Qwen (LLM Serving).

        Optional polish only. Raises QuickMLUnavailable when unconfigured or on
        any failure; the engine then keeps its deterministic sentence.
        """
        if not self.llm_endpoint or not self.llm_token:
            raise QuickMLUnavailable("llm endpoint/token not configured")
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
                "Authorization": f"Zoho-oauthtoken {self.llm_token}",
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
