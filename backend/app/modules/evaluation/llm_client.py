import json
import re
import time
from dataclasses import dataclass

import requests


class ProviderError(RuntimeError):
    code = "provider_error"


class ProviderTimeout(ProviderError):
    code = "timeout"


class ProviderRateLimited(ProviderError):
    code = "rate_limited"


class InvalidProviderResponse(ProviderError):
    code = "invalid_response"


@dataclass(frozen=True)
class ProviderResult:
    parsed: dict
    raw_text: str
    latency_ms: int


class LlmClient:
    def classify(
        self, *, base_url: str, api_key: str, model_id: str,
        system_prompt: str, user_prompt: str, timeout_seconds: int,
    ) -> ProviderResult:
        started = time.perf_counter()
        try:
            response = requests.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model_id, "temperature": 0,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
                timeout=timeout_seconds,
            )
        except requests.Timeout as exc:
            raise ProviderTimeout(str(exc)) from exc
        except requests.RequestException as exc:
            raise ProviderError(str(exc)) from exc
        if response.status_code == 429:
            raise ProviderRateLimited("Provider rate limit")
        if response.status_code >= 400:
            raise ProviderError(f"Provider HTTP {response.status_code}: {response.text[:300]}")
        try:
            raw = response.json()["choices"][0]["message"]["content"]
            cleaned = re.sub(r"^\s*```(?:json)?|\s*```\s*$", "", raw.strip(), flags=re.I)
            parsed = json.loads(cleaned)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise InvalidProviderResponse(response.text[:5000]) from exc
        return ProviderResult(parsed=parsed, raw_text=raw[:5000], latency_ms=round((time.perf_counter() - started) * 1000))
