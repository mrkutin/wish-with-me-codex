from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional, Protocol
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel


class LLMOutput(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    price_amount: Optional[float] = None
    price_currency: Optional[str] = None
    canonical_url: Optional[str] = None
    confidence: Optional[float] = None
    image_url: Optional[str] = None


class LLMClient(Protocol):
    async def extract(
        self,
        *,
        url: str,
        title: str,
        html: str,
        image_base64: str,
        image_mime: str,
    ) -> LLMOutput:
        ...


def _image_data_url(image_base64: str, image_mime: str) -> str:
    return f"data:{image_mime};base64,{image_base64}"


def _truncate_html(html: str, max_chars: int) -> str:
    if max_chars <= 0:
        return html
    if len(html) <= max_chars:
        return html
    return html[:max_chars]


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        raise ValueError("empty LLM response")
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no json object found")
    return json.loads(text[start : end + 1])


def _default_canonical_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return url
    return parsed.geturl()


@dataclass
class StubLLMClient:
    async def extract(self, *, url: str, title: str, html: str, image_base64: str, image_mime: str) -> LLMOutput:
        _ = (html, image_base64, image_mime)
        return LLMOutput(
            title=title or None,
            description=None,
            price_amount=None,
            price_currency=None,
            canonical_url=_default_canonical_url(url),
            confidence=0.0,
            image_url=None,
        )


@dataclass
class OpenAILikeClient:
    base_url: str
    api_key: str
    model: str
    timeout_s: float
    max_chars: int

    async def extract(self, *, url: str, title: str, html: str, image_base64: str, image_mime: str) -> LLMOutput:
        truncated_html = _truncate_html(html, self.max_chars)
        system = (
            "Return ONLY a single JSON object and nothing else. "
            "Use the exact schema and keys:\n"
            "{\n"
            '  "title": "string|null",\n'
            '  "description": "string|null",\n'
            '  "price_amount": "number|null",\n'
            '  "price_currency": "string|null",\n'
            '  "canonical_url": "string|null",\n'
            '  "confidence": "number",\n'
            '  "image_url": "string|null"\n'
            "}\n"
            "Rules:\n"
            "- Output valid JSON with double quotes.\n"
            "- Do not wrap in markdown.\n"
            "- If a field is missing, use null.\n"
            "- confidence is 0.0 to 1.0.\n"
            "- Use page source to determine image_url only.\n"
            "- Use the screenshot to determine all other fields.\n"
        )
        user = (
            f"URL: {url}\n"
            f"Page title: {title}\n"
            "Page source (for image_url only):\n"
            f"{truncated_html}\n"
            "Screenshot of the page is attached.\n"
        )
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user},
                        {
                            "type": "image_url",
                            "image_url": {"url": _image_data_url(image_base64, image_mime)},
                        },
                    ],
                },
            ],
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        timeout = httpx.Timeout(self.timeout_s, connect=self.timeout_s)
        async with httpx.AsyncClient(base_url=self.base_url, timeout=timeout) as client:
            resp = await client.post("/v1/chat/completions", json=payload, headers=headers)
            resp.raise_for_status()
            body = resp.json()

        try:
            content = body["choices"][0]["message"]["content"]
        except Exception as exc:
            raise ValueError("LLM response missing content") from exc

        parsed = _extract_json(content)
        out = LLMOutput.model_validate(parsed)
        return out


def load_llm_client_from_env() -> LLMClient:
    mode = (os.environ.get("LLM_MODE") or "live").strip().lower()
    if mode == "stub":
        return StubLLMClient()

    base_url = (os.environ.get("LLM_BASE_URL") or "").strip()
    api_key = (os.environ.get("LLM_API_KEY") or "").strip()
    model = (os.environ.get("LLM_MODEL") or "").strip()
    if not base_url or not api_key or not model:
        raise RuntimeError("LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL are required for live LLM mode")

    timeout_s = float(os.environ.get("LLM_TIMEOUT_S") or 60)
    max_chars = int(os.environ.get("LLM_MAX_CHARS") or 200_000)
    return OpenAILikeClient(
        base_url=base_url,
        api_key=api_key,
        model=model,
        timeout_s=timeout_s,
        max_chars=max_chars,
    )
