from openai import OpenAI
from ..infrastructure.config import settings


def get_client() -> OpenAI:
    # Works for OpenAI-compatible endpoints (including Databricks Model Serving in OpenAI-compatible mode)
    if not settings.llm_api_key or not settings.llm_base_url:
        return OpenAI()
    return OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)


def chat(messages: list[dict], temperature: float = 0.0, max_tokens: int = 500) -> str:
    client = get_client()
    resp = client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content or ""
