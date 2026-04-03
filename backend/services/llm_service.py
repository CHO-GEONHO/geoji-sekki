from __future__ import annotations

import json
import logging
import re
import time
from typing import Optional

from openai import AsyncOpenAI

from backend.config import settings
from backend.services import usage_logger

logger = logging.getLogger("geojisekki.llm")


class LLMService:
    """Gemini Pro (피드 primary) + DeepSeek (크롤러 분류) + Gemini Flash (fallback) LLM 서비스."""

    def __init__(self):
        self._deepseek: Optional[AsyncOpenAI] = None
        self._gemini: Optional[AsyncOpenAI] = None

    @property
    def deepseek(self) -> AsyncOpenAI:
        if self._deepseek is None:
            self._deepseek = AsyncOpenAI(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
            )
        return self._deepseek

    @property
    def gemini(self) -> Optional[AsyncOpenAI]:
        if not settings.gemini_api_key:
            return None
        if self._gemini is None:
            self._gemini = AsyncOpenAI(
                api_key=settings.gemini_api_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            )
        return self._gemini

    async def chat_feed(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4000,
    ) -> dict:
        """피드 생성 전용 — Gemini Pro 우선, 실패 시 DeepSeek fallback.

        Gemini Pro는 긴 컨텍스트와 구조화된 출력에 강점.
        """
        providers = []
        if self.gemini:
            providers.append(("gemini", self.gemini, settings.gemini_pro_model))
        providers.append(("deepseek", self.deepseek, settings.deepseek_model))

        last_error = None
        for provider_name, client, model in providers:
            try:
                result = await self._call(
                    client, model, system_prompt, user_prompt,
                    json_mode=True, max_tokens=max_tokens,
                    provider_name=provider_name,
                )
                parsed = self._parse_json(result["content"])
                return {"data": parsed, "model": result["model"], "tokens": result["tokens"]}
            except Exception as e:
                logger.warning("[%s] 피드 LLM 호출 실패: %s", provider_name, e)
                last_error = e

        raise RuntimeError(f"모든 LLM provider 실패. 마지막 에러: {last_error}")

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = False,
        max_tokens: int = 2000,
    ) -> dict:
        """LLM 호출 → {"content": str, "model": str, "tokens": {...}} 반환.

        DeepSeek 실패 시 Gemini Flash로 자동 fallback.
        """
        providers = [
            ("deepseek", self.deepseek, settings.deepseek_model),
        ]
        if self.gemini:
            providers.append(("gemini", self.gemini, "gemini-2.0-flash"))

        last_error = None
        for provider_name, client, model in providers:
            try:
                return await self._call(
                    client, model, system_prompt, user_prompt,
                    json_mode=json_mode, max_tokens=max_tokens,
                    provider_name=provider_name,
                )
            except Exception as e:
                logger.warning("[%s] LLM 호출 실패: %s", provider_name, e)
                last_error = e

        raise RuntimeError(f"모든 LLM provider 실패. 마지막 에러: {last_error}")

    async def _call(
        self,
        client: AsyncOpenAI,
        model: str,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool,
        max_tokens: int,
        provider_name: str,
    ) -> dict:
        kwargs = {}
        # Gemini는 response_format json_object 미지원 → 파라미터 제외
        if json_mode and "gemini" not in provider_name:
            kwargs["response_format"] = {"type": "json_object"}

        # Gemini 2.5 Pro는 thinking 토큰이 max_tokens에 포함됨
        # → 실제 출력 공간 확보를 위해 max_tokens를 크게 설정
        if "gemini" in provider_name:
            max_tokens = max(max_tokens, 16000)

        t0 = time.monotonic()
        # Gemini 빈 응답 대비 최대 2회 시도
        max_attempts = 2 if "gemini" in provider_name else 1
        content = None
        response = None
        for attempt in range(max_attempts):
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=max_tokens,
                    temperature=0.7,
                    **kwargs,
                )
            except Exception:
                await usage_logger.record(provider_name, error=True)
                raise

            content = response.choices[0].message.content
            if content:
                break
            if attempt < max_attempts - 1:
                logger.warning("[%s] 빈 응답 — 재시도 %d/%d", provider_name, attempt + 2, max_attempts)

        latency_ms = (time.monotonic() - t0) * 1000
        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0

        logger.info(
            "[%s] model=%s, prompt_tokens=%d, completion_tokens=%d",
            provider_name, model, input_tokens, output_tokens,
        )

        await usage_logger.record(
            provider_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
        )

        return {
            "content": content,
            "model": model,
            "tokens": {
                "prompt": input_tokens,
                "completion": output_tokens,
            },
        }

    async def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2000,
    ) -> dict:
        """LLM 호출 후 JSON 파싱까지 수행.

        반환: {"data": parsed_json, "model": str, "tokens": {...}}
        """
        result = await self.chat(
            system_prompt, user_prompt,
            json_mode=True, max_tokens=max_tokens,
        )
        parsed = self._parse_json(result["content"])
        return {
            "data": parsed,
            "model": result["model"],
            "tokens": result["tokens"],
        }

    @staticmethod
    def _parse_json(text):
        """JSON 파싱 + 마크다운 코드블럭 제거 fallback."""
        if not text:
            raise ValueError("LLM 응답이 비어있음 (None or empty)")
        text = text.strip()

        # 1차: 직접 파싱
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 2차: 마크다운 코드블럭 제거 후 파싱
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # 3차: 첫 번째 [ 또는 { 부터 마지막 ] 또는 } 까지 추출
        match = re.search(r"[\[{][\s\S]*[\]}]", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        raise ValueError(f"JSON 파싱 실패: {text[:200]}")

    async def batch_classify(
        self,
        items: list[dict],
        system_prompt: str,
        max_tokens: int = 3000,
    ) -> list[dict]:
        """여러 아이템을 한 번에 분류/요약 (배치 처리).

        items: [{"id": ..., "title": ...}, ...]
        반환: [{"id": ..., "category": ..., "summary": ...}, ...]
        """
        user_prompt = (
            "아래 아이템들의 카테고리를 분류하고 한줄 요약을 작성해줘.\n"
            "JSON 배열로만 응답해. 각 아이템에 id, category, summary 포함.\n\n"
            + json.dumps(items, ensure_ascii=False)
        )
        result = await self.chat_json(system_prompt, user_prompt, max_tokens=max_tokens)
        data = result["data"]
        return data if isinstance(data, list) else data.get("items", [])


# 싱글톤
llm_service = LLMService()
