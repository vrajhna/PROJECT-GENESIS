"""Centralized Meta Model API client. Stdlib only.

Contract (verified live 2026-11-02, latency 1169 ms):
  base URL https://api.meta.ai/v1, bearer MODEL_API_KEY,
  GET /models for connectivity, POST /responses for agentic calls.
Model IDs live in env (META_PRIMARY_MODEL / META_ADVANCED_MODEL), never
hardcoded in callers. No key ever leaves the backend or enters logs.
Every call is recorded in the ModelRegistry with a request ID.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass

from .model_registry import ModelCall, ModelRegistry


@dataclass
class MetaConfig:
    api_key: str
    base_url: str
    primary_model: str
    advanced_model: str
    timeout_s: int = 30
    max_retries: int = 2

    @classmethod
    def from_env(cls) -> "MetaConfig":
        return cls(
            api_key=os.environ.get("MODEL_API_KEY", ""),
            base_url=os.environ.get("META_BASE_URL", "https://api.meta.ai/v1").rstrip("/"),
            primary_model=os.environ.get("META_PRIMARY_MODEL", "muse-spark-1.3"),
            advanced_model=os.environ.get("META_ADVANCED_MODEL", "muse-wonder-1.0"),
            timeout_s=int(os.environ.get("META_TIMEOUT_S", "30")),
            max_retries=int(os.environ.get("META_MAX_RETRIES", "2")),
        )


class MetaClient:
    def __init__(self, config: MetaConfig | None = None,
                 registry: ModelRegistry | None = None) -> None:
        self.config = config or MetaConfig.from_env()
        self.registry = registry or ModelRegistry()
        self.last_call: dict = {}

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

    def _record(self, **kwargs) -> None:
        self.registry.record(ModelCall(**kwargs))

    def check_connectivity(self) -> dict:
        """GET {base}/models. Returns status dict; never raises on HTTP errors."""
        request_id = f"req-{uuid.uuid4().hex[:12]}"
        if not self.config.api_key:
            self._record(id=request_id, model="(none)", task="connectivity",
                         latency_ms=0, ok=False, error="MODEL_API_KEY is not set")
            return {"ok": False, "error": "MODEL_API_KEY is not set"}
        url = f"{self.config.base_url}/models"
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        start = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout_s) as resp:
                body = resp.read(65536).decode("utf-8", "replace")
                latency_ms = int((time.monotonic() - start) * 1000)
                self.last_call = {"request_id": request_id, "latency_ms": latency_ms}
                self._record(id=request_id, model="(models)", task="connectivity",
                             latency_ms=latency_ms, ok=True)
                return {"ok": True, "latency_ms": latency_ms, "body": body[:2000]}
        except urllib.error.HTTPError as e:
            latency_ms = int((time.monotonic() - start) * 1000)
            self._record(id=request_id, model="(models)", task="connectivity",
                         latency_ms=latency_ms, ok=False, error=f"HTTP {e.code}")
            return {"ok": False, "error": f"HTTP {e.code}: {e.read(2000)!r}"}
        except Exception as e:
            latency_ms = int((time.monotonic() - start) * 1000)
            self._record(id=request_id, model="(models)", task="connectivity",
                         latency_ms=latency_ms, ok=False, error=type(e).__name__)
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    def build_payload(self, model: str, user_input: str,
                      tools: list[dict] | None = None,
                      response_format: dict | None = None,
                      effort: str | None = None,
                      stream: bool = False) -> dict:
        """Agentic payload: tool calling, structured outputs, reasoning effort.

        Pure function — unit-tested without network. The caller picks every
        knob; nothing here ever swaps the model.
        """
        payload: dict = {"model": model, "input": user_input}
        if tools:
            payload["tools"] = tools
        if response_format:
            payload["response_format"] = response_format
        if effort:
            payload["reasoning"] = {"effort": effort}
        if stream:
            payload["stream"] = True
        return payload

    @staticmethod
    def _delta_text(event: dict) -> str:
        """Best-effort text delta out of a streamed SSE event envelope."""
        if not isinstance(event, dict):
            return ""
        if isinstance(event.get("delta"), str):
            return event["delta"]
        for key in ("output_text", "text"):
            val = event.get(key)
            if isinstance(val, str):
                return val
        try:
            choices = event.get("choices") or []
            delta = (choices[0] or {}).get("delta") or {}
            content = delta.get("content")
            return content if isinstance(content, str) else ""
        except (IndexError, AttributeError, TypeError):
            return ""

    def respond_stream(self, model: str, user_input: str, task: str = "adhoc",
                       on_progress=None, read_timeout: int = 60,
                       deadline_s: int = 600) -> dict:
        """POST {base}/responses with stream:true. Calls
        on_progress(chars_so_far, elapsed_s) as deltas arrive. Returns the
        same dict shape as respond(), with data synthesized so extract_text
        works unchanged. Same bounded retries as respond()."""
        request_id = f"req-{uuid.uuid4().hex[:12]}"
        if not self.config.api_key:
            self._record(id=request_id, model=model, task=task,
                         latency_ms=0, ok=False, error="MODEL_API_KEY is not set")
            return {"ok": False, "error": "MODEL_API_KEY is not set"}
        url = f"{self.config.base_url}/responses"
        payload = json.dumps(self.build_payload(
            model, user_input, stream=True)).encode()
        retries = 0
        start = time.monotonic()

        def fail(error: str):
            latency_ms = int((time.monotonic() - start) * 1000)
            self._record(id=request_id, model=model, task=task,
                         latency_ms=latency_ms, ok=False, error=error,
                         retries=retries)
            return {"ok": False, "error": error, "retries": retries,
                    "request_id": request_id}

        while True:
            headers = dict(self._headers())
            headers["Accept"] = "text/event-stream"
            req = urllib.request.Request(url, data=payload, headers=headers,
                                         method="POST")
            try:
                full: list[str] = []
                tokens = 0
                with urllib.request.urlopen(req, timeout=read_timeout) as resp:
                    for raw in resp:
                        if time.monotonic() - start > deadline_s:
                            raise TimeoutError("stream deadline exceeded")
                        line = raw.decode("utf-8", "replace").strip()
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if not data or data == "[DONE]":
                            continue
                        try:
                            event = json.loads(data)
                        except ValueError:
                            continue
                        # Deltas are the content channel. Done/completed
                        # envelopes repeat the text — accumulating them
                        # would duplicate the output.
                        etype = event.get("type") if isinstance(event, dict) else None
                        if (etype is None or "choices" in event
                                or (isinstance(etype, str) and etype.endswith(".delta"))):
                            chunk = self._delta_text(event)
                            if chunk:
                                full.append(chunk)
                                if on_progress is not None:
                                    try:
                                        on_progress(sum(map(len, full)),
                                                    time.monotonic() - start)
                                    except Exception:
                                        pass
                        try:
                            use = event.get("usage") or {}
                            tokens = int(use.get("total_tokens") or tokens)
                        except (ValueError, TypeError, AttributeError):
                            pass
                text = "".join(full)
                latency_ms = int((time.monotonic() - start) * 1000)
                self._record(id=request_id, model=model, task=task,
                             latency_ms=latency_ms, ok=True,
                             retries=retries, tokens=tokens)
                return {"ok": True, "latency_ms": latency_ms,
                        "data": {"output": [{"content": [
                            {"type": "output_text", "text": text}]}]},
                        "request_id": request_id, "retries": retries,
                        "streamed": True}
            except urllib.error.HTTPError as e:
                retryable = e.code in (429, 500, 502, 503, 504)
                if retryable and retries < self.config.max_retries:
                    retries += 1
                    time.sleep(min(2 ** retries, 8))
                    continue
                return fail(f"HTTP {e.code}: {e.read(2000)!r}")
            except (TimeoutError, ConnectionError) as e:
                if retries < self.config.max_retries:
                    retries += 1
                    time.sleep(min(2 ** retries, 8))
                    continue
                return fail(f"{type(e).__name__}: {e}")
            except Exception as e:
                return fail(f"{type(e).__name__}: {e}")

    def respond(self, model: str, user_input: str, task: str = "adhoc",
                tools: list[dict] | None = None,
                response_format: dict | None = None,
                effort: str | None = None) -> dict:
        """POST {base}/responses with retry + backoff on 429/5xx.

        Never silently switches models: the requested model is the one
        recorded, win or lose. Missing key returns an informative error.
        """
        request_id = f"req-{uuid.uuid4().hex[:12]}"
        if not self.config.api_key:
            self._record(id=request_id, model=model, task=task,
                         latency_ms=0, ok=False, error="MODEL_API_KEY is not set")
            return {"ok": False, "error": "MODEL_API_KEY is not set"}
        url = f"{self.config.base_url}/responses"
        payload = json.dumps(self.build_payload(
            model, user_input, tools, response_format, effort)).encode()
        retries = 0
        start = time.monotonic()
        while True:
            req = urllib.request.Request(url, data=payload, headers=self._headers(), method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.config.timeout_s) as resp:
                    data = json.loads(resp.read(1_000_000).decode("utf-8", "replace"))
                    latency_ms = int((time.monotonic() - start) * 1000)
                    tokens = 0
                    try:
                        tokens = int(data.get("usage", {}).get("total_tokens", 0))
                    except (ValueError, TypeError, AttributeError):
                        tokens = 0
                    self.last_call = {"request_id": request_id, "model": model,
                                      "latency_ms": latency_ms}
                    self._record(id=request_id, model=model, task=task,
                                 latency_ms=latency_ms, ok=True,
                                 retries=retries, tokens=tokens)
                    return {"ok": True, "latency_ms": latency_ms, "data": data,
                            "request_id": request_id}
            except urllib.error.HTTPError as e:
                retryable = e.code in (429, 500, 502, 503, 504)
                if retryable and retries < self.config.max_retries:
                    retries += 1
                    time.sleep(min(2 ** retries, 8))
                    continue
                latency_ms = int((time.monotonic() - start) * 1000)
                self._record(id=request_id, model=model, task=task,
                             latency_ms=latency_ms, ok=False,
                             error=f"HTTP {e.code}", retries=retries)
                return {"ok": False, "error": f"HTTP {e.code}: {e.read(2000)!r}",
                        "retries": retries, "request_id": request_id}
            except (TimeoutError, ConnectionError) as e:
                # Network blips are transient: same bounded backoff as 5xx.
                # Proven need: full-app generation exceeds one window.
                if retries < self.config.max_retries:
                    retries += 1
                    time.sleep(min(2 ** retries, 8))
                    continue
                latency_ms = int((time.monotonic() - start) * 1000)
                self._record(id=request_id, model=model, task=task,
                             latency_ms=latency_ms, ok=False,
                             error=type(e).__name__, retries=retries)
                return {"ok": False, "error": f"{type(e).__name__}: {e}",
                        "retries": retries, "request_id": request_id}
            except Exception as e:
                latency_ms = int((time.monotonic() - start) * 1000)
                self._record(id=request_id, model=model, task=task,
                             latency_ms=latency_ms, ok=False,
                             error=type(e).__name__, retries=retries)
                return {"ok": False, "error": f"{type(e).__name__}: {e}",
                        "request_id": request_id}
