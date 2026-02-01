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
        image_candidates: str,
        image_base64: str = "",
        image_mime: str = "",
        html_content: str = "",
    ) -> LLMOutput:
        ...


def _image_data_url(image_base64: str, image_mime: str) -> str:
    return f"data:{image_mime};base64,{image_base64}"


def _truncate_text(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return text
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


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
    async def extract(
        self,
        *,
        url: str,
        title: str,
        image_candidates: str,
        image_base64: str = "",
        image_mime: str = "",
        html_content: str = "",
    ) -> LLMOutput:
        _ = (image_candidates, image_base64, image_mime, html_content)
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

    async def extract(
        self,
        *,
        url: str,
        title: str,
        image_candidates: str,
        image_base64: str = "",
        image_mime: str = "",
        html_content: str = "",
    ) -> LLMOutput:
        _ = html_content  # Not used by vision client
        truncated_candidates = _truncate_text(image_candidates, self.max_chars)
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
            "- Use the image candidates list to determine image_url only.\n"
            "- Use the screenshot to determine all other fields.\n"
            "- image_url must be the main product image URL selected from the candidates.\n"
            "- Prefer the highest-resolution/original product image URL when multiple sizes exist.\n"
            "- Choose the image that most directly matches the product shown in the screenshot.\n"
            "- If no suitable candidate exists, return null for image_url.\n"
        )
        user = (
            f"URL: {url}\n"
            f"Page title: {title}\n"
            "Image candidates (choose the main product image):\n"
            f"{truncated_candidates}\n"
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


@dataclass
class DeepSeekTextClient:
    """
    LLM client for DeepSeek text-only models.

    Uses HTML content instead of screenshots for product extraction.
    Designed for models without vision capabilities.
    """

    base_url: str
    api_key: str
    model: str
    timeout_s: float
    max_chars: int

    async def extract(
        self,
        *,
        url: str,
        title: str,
        image_candidates: str,
        image_base64: str = "",
        image_mime: str = "",
        html_content: str = "",
    ) -> LLMOutput:
        _ = (image_base64, image_mime)  # Not used by text client

        truncated_candidates = _truncate_text(image_candidates, min(self.max_chars // 4, 10000))
        truncated_html = _truncate_text(html_content, self.max_chars)

        system = (
            "You are a product data extraction assistant. "
            "Extract product information from the provided HTML content and return ONLY a single JSON object.\n\n"
            "Use the exact schema and keys:\n"
            "{\n"
            '  "title": "string|null",\n'
            '  "description": "string|null",\n'
            '  "price_amount": "number|null",\n'
            '  "price_currency": "string|null",\n'
            '  "canonical_url": "string|null",\n'
            '  "confidence": "number",\n'
            '  "image_url": "string|null"\n'
            "}\n\n"
            "Rules:\n"
            "- Output valid JSON with double quotes only, no markdown formatting.\n"
            "- If a field is missing or unclear, use null.\n"
            "- confidence is 0.0 to 1.0 based on how certain you are about the extraction.\n"
            "- For title, use the main product name, not marketing slogans.\n"
            "- For description, extract a concise product description (1-3 sentences).\n"
            "- For image_url, select the best main product image URL from the image candidates list.\n"
            "- Prefer high-resolution product images, not thumbnails or icons.\n"
            "- canonical_url should be the clean product page URL without tracking parameters.\n\n"
            "IMPORTANT - Price extraction:\n"
            "- ALWAYS look carefully for the product price. It is usually prominently displayed.\n"
            "- Prices may have spaces as thousand separators: '93 499' means 93499.\n"
            "- Prices may have dots or commas: '1.299,00' or '1,299.00' - extract as number.\n"
            "- Look for the CURRENT/SALE price, not the crossed-out old price.\n"
            "- Russian sites use ₽ or 'руб' for rubles (RUB).\n"
            "- For price_amount, return ONLY the numeric value (e.g., 93499 not '93 499 ₽').\n"
            "- For price_currency, use ISO code: RUB, USD, EUR, etc.\n"
            "- Check 'Structured metadata' section first - it may contain the price.\n"
        )

        user = (
            f"Extract product information from this page:\n\n"
            f"URL: {url}\n"
            f"Page title: {title}\n\n"
            f"Image candidates (select the main product image from these):\n"
            f"{truncated_candidates}\n\n"
            f"Page content:\n"
            f"{truncated_html}\n"
        )

        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
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
    max_chars = int(os.environ.get("LLM_MAX_CHARS") or 100_000)

    # Determine client type based on LLM_CLIENT_TYPE or model name
    client_type = (os.environ.get("LLM_CLIENT_TYPE") or "").strip().lower()

    # Auto-detect DeepSeek models (text-only)
    if not client_type:
        model_lower = model.lower()
        if "deepseek" in model_lower and "vl" not in model_lower:
            # DeepSeek text models (deepseek-chat, deepseek-coder, etc.)
            client_type = "text"
        elif "gpt-4" in model_lower or "gpt-3" in model_lower or "claude" in model_lower:
            # Vision-capable models
            client_type = "vision"
        else:
            # Default to text for unknown models (safer)
            client_type = "text"

    if client_type == "text":
        return DeepSeekTextClient(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout_s=timeout_s,
            max_chars=max_chars,
        )
    else:
        return OpenAILikeClient(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout_s=timeout_s,
            max_chars=max_chars,
        )
