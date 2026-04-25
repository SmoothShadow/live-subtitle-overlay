from __future__ import annotations

from abc import ABC, abstractmethod
import json
import urllib.error
import urllib.parse
import urllib.request
import uuid

from .config import AzureTranslatorConfig


class TranslationError(RuntimeError):
    """Raised when translation failed."""


class Translator(ABC):
    @abstractmethod
    def translate_text(self, text: str) -> str:
        raise NotImplementedError


class PassthroughTranslator(Translator):
    def translate_text(self, text: str) -> str:
        return text


class AzureTranslator(Translator):
    def __init__(self, config: AzureTranslatorConfig) -> None:
        self._config = config

    def translate_text(self, text: str) -> str:
        cleaned = text.strip()
        if not cleaned:
            return ""
        if not self._config.is_enabled:
            return cleaned

        query = urllib.parse.urlencode(
            {
                "api-version": "3.0",
                "from": self._config.source_language,
                "to": self._config.target_language,
            }
        )
        url = f"{self._config.endpoint}/translate?{query}"
        body = json.dumps([{"text": cleaned}]).encode("utf-8")
        request = urllib.request.Request(
            url=url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json; charset=UTF-8",
                "Ocp-Apim-Subscription-Key": self._config.key,
                "Ocp-Apim-Subscription-Region": self._config.region,
                "X-ClientTraceId": str(uuid.uuid4()),
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise TranslationError(f"Azure Translator HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise TranslationError(f"Azure Translator network error: {exc.reason}") from exc

        try:
            return payload[0]["translations"][0]["text"].strip()
        except (IndexError, KeyError, TypeError) as exc:
            raise TranslationError(f"Unexpected Azure Translator response: {payload!r}") from exc
