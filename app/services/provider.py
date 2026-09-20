from dataclasses import dataclass

import httpx

from app.core.config import Settings


class ProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderResult:
    content: str
    provider_id: str
    model_id: str


class OpenAiCompatibleProvider:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient):
        self._settings = settings
        self._http_client = http_client

    async def generate(self, system_prompt: str, user_prompt: str) -> ProviderResult:
        url = f"{self._settings.ai_base_url}/chat/completions"
        try:
            response = await self._http_client.post(
                url,
                headers={
                    "Authorization": f"Bearer {self._settings.ai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._settings.ai_model,
                    "temperature": self._settings.ai_temperature,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )
            response.raise_for_status()
        except httpx.TimeoutException as error:
            raise ProviderError("AI 服务响应超时") from error
        except httpx.HTTPStatusError as error:
            raise ProviderError(f"AI 服务返回 HTTP {error.response.status_code}") from error
        except httpx.HTTPError as error:
            raise ProviderError("无法连接 AI 服务") from error

        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"].strip()
            model = str(body.get("model") or self._settings.ai_model)
        except (KeyError, IndexError, TypeError, AttributeError, ValueError) as error:
            raise ProviderError("AI 服务返回格式无效") from error
        if not content:
            raise ProviderError("AI 服务返回空回答")
        return ProviderResult(content=content, provider_id="openai-compatible", model_id=model)
