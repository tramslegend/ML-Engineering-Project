"""LLM inference boundary. Mirrors the PRD's air-gapped self-hosted LLM node
(private-subnet, no egress, Llama-3.2/Gemma-3 fine-tuned) — this portfolio
build doesn't host a real fine-tuned model, so BPR_USE_MOCK_LLM=true (default)
returns deterministic template output requiring zero API keys. Flipping to
false routes the same call interface through a real model via
langchain_openai (settings.llm_provider picks DeepSeek or Gemini/Gemma), to
demonstrate the architecture works end-to-end against a real model without
changing any calling code.
"""
import re

from app.config import settings

_THOUGHT_TAG = re.compile(r"<thought>.*?</thought>", re.DOTALL)


def strip_thoughts(text: str) -> str:
    """Gemma (via Gemini's OpenAI-compatible endpoint) prefixes its actual
    answer with an inline <thought>...</thought> reasoning block that DeepSeek
    never emits -- every place that parses raw model output (this module's
    complete(), and app/agents/analysis.py's single-shot code generation and
    SQL agent output) needs this, or a stray tag ends up shown to a compliance
    officer as a "rationale," or breaks exec()'d generated code outright."""
    return _THOUGHT_TAG.sub("", text).strip()


# (model, api_key, base_url) per OpenAI-compatible provider -- add a new one
# here only; nothing else in this module needs to change. Ollama is the one
# exception (see build_chat_llm) since it uses LangChain's native ChatOllama,
# not ChatOpenAI -- Ollama Cloud authenticates via a bearer-token header, not
# an api_key constructor param.
_OPENAI_COMPAT_PROVIDERS = {
    "deepseek": lambda: (settings.deepseek_model, settings.deepseek_api_key, settings.deepseek_base_url),
    "gemini": lambda: (settings.gemini_model, settings.gemini_api_key, settings.gemini_base_url),
    "nvidia": lambda: (settings.nvidia_model, settings.nvidia_api_key, settings.nvidia_base_url),
    "mistral": lambda: (settings.mistral_model, settings.mistral_api_key, settings.mistral_base_url),
}


def active_provider_config() -> tuple[str, str, str]:
    getter = _OPENAI_COMPAT_PROVIDERS.get(settings.llm_provider, _OPENAI_COMPAT_PROVIDERS["deepseek"])
    return getter()


def active_api_key() -> str:
    if settings.llm_provider == "ollama":
        return settings.ollama_api_key
    _, api_key, _ = active_provider_config()
    return api_key


def build_chat_llm(temperature: float = 0.2):
    """Constructs the active provider's LangChain chat model -- the one place
    that decides which LangChain integration class to use, so every caller
    (this module's complete() and app/agents/analysis.py's SQL/Python agents)
    stays provider-agnostic."""
    if settings.llm_provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            client_kwargs={"headers": {"Authorization": f"Bearer {settings.ollama_api_key}"}},
            temperature=temperature,
        )
    from langchain_openai import ChatOpenAI

    model, api_key, base_url = active_provider_config()
    return ChatOpenAI(model=model, api_key=api_key, base_url=base_url, temperature=temperature)


def complete(system_prompt: str, user_prompt: str) -> str:
    if settings.use_mock_llm or not active_api_key():
        return _mock_complete(system_prompt, user_prompt)
    return _real_complete(system_prompt, user_prompt)


def _mock_complete(system_prompt: str, user_prompt: str) -> str:
    # Deterministic, keyword-driven stand-in for the fine-tuned local model.
    # Good enough to exercise the full agent graph without any external call.
    return f"[mock-llm rationale] {user_prompt.strip()[:400]}"


def _real_complete(system_prompt: str, user_prompt: str) -> str:
    llm = build_chat_llm(temperature=0.2)
    response = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ])
    # NVIDIA NIM's reasoning models keep thinking out of `.content` entirely
    # (a separate reasoning_content field), so this is a no-op for them --
    # only Gemma needs it, but it's harmless to always apply.
    return strip_thoughts(response.content)
