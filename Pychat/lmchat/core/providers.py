#!/usr/bin/env python3
"""
LLM Provider abstraction layer

Built on the official provider SDKs:
  - anthropic      (Claude)
  - openai         (OpenAI, plus any OpenAI-compatible server: LM Studio, Ollama, xAI)
  - google-genai   (Gemini)

API keys can live in the provider config ("api_key") or fall back to the
conventional environment variables (ANTHROPIC_API_KEY, OPENAI_API_KEY,
XAI_API_KEY, GEMINI_API_KEY/GOOGLE_API_KEY).
"""

import os
from abc import ABC, abstractmethod
from typing import Generator, List, Dict, Optional

from .models import CommandResult

# Optional SDK imports - a missing package only disables that provider
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    from google import genai
    from google.genai import types as genai_types
    HAS_GENAI = True
except Exception:
    # google-genai pulls in heavyweight transitive deps (google-auth,
    # cryptography); a broken install shouldn't kill PyTTAI startup
    HAS_GENAI = False


class LLMProvider(ABC):
    """Base interface all LLM providers must implement"""

    def __init__(self, config: Dict):
        self.config = config
        self.name = "base"
        # Populated after each completed stream: {"input": n, "output": n}
        self.last_usage: Optional[Dict] = None

    @abstractmethod
    def test_connection(self) -> bool:
        """Test if provider is accessible"""
        pass

    @abstractmethod
    def stream_completion(self, messages: List[Dict], **kwargs) -> Generator[str, None, None]:
        """Stream a completion from the provider"""
        pass

    @abstractmethod
    def get_models(self) -> Optional[List[Dict]]:
        """Get available models from provider"""
        pass

    def _resolve_api_key(self, *env_vars: str) -> Optional[str]:
        """Config api_key first, then environment variables"""
        key = self.config.get("api_key")
        if key:
            return key
        for var in env_vars:
            key = os.environ.get(var)
            if key:
                return key
        return None


class OpenAICompatibleProvider(LLMProvider):
    """
    Any server speaking the OpenAI chat completions API:
    LM Studio, Ollama, xAI, vLLM, llama.cpp server, etc.
    """

    DEFAULT_BASE_URL = "http://localhost:1234/v1"
    DEFAULT_MODEL = "local-model"
    KEY_ENV_VARS = ()
    REQUIRES_KEY = False
    # Token-limit parameter name; newer OpenAI models require max_completion_tokens
    MAX_TOKENS_PARAM = "max_tokens"

    def __init__(self, config: Dict):
        super().__init__(config)
        if not HAS_OPENAI:
            raise RuntimeError("openai package not installed - pip install openai")
        self.name = "openai_compatible"
        base_url = config.get("base_url", self.DEFAULT_BASE_URL)
        # Tolerate configs that omit the /v1 suffix (old PyTTAI style)
        if not base_url.rstrip("/").endswith("/v1"):
            base_url = base_url.rstrip("/") + "/v1"
        self.base_url = base_url
        self.model = config.get("model", self.DEFAULT_MODEL)
        self.timeout = config.get("timeout", 60.0)
        self.api_key = self._resolve_api_key(*self.KEY_ENV_VARS)
        if self.REQUIRES_KEY and not self.api_key:
            env_hint = " or ".join(self.KEY_ENV_VARS) or "config"
            raise RuntimeError(f"No API key - set api_key in config or {env_hint}")
        self.client = openai.OpenAI(
            base_url=self.base_url,
            api_key=self.api_key or "not-needed",
            timeout=self.timeout,
        )

    def test_connection(self) -> bool:
        try:
            self.client.with_options(timeout=5.0).models.list()
            return True
        except Exception:
            return False

    def get_models(self) -> Optional[List[Dict]]:
        try:
            models = self.client.models.list()
            return [{"id": m.id, "name": getattr(m, "display_name", None) or m.id}
                    for m in models]
        except Exception:
            return None

    def _supports_sampling(self) -> bool:
        """Whether the target model accepts a temperature parameter"""
        return True

    def stream_completion(self, messages: List[Dict], **kwargs) -> Generator[str, None, None]:
        self.last_usage = None
        params = {
            "model": kwargs.get("model", self.model),
            "messages": messages,
            "stream": True,
            self.MAX_TOKENS_PARAM: kwargs.get("max_tokens", self.config.get("max_tokens", 4096)),
        }
        temperature = kwargs.get("temperature", self.config.get("temperature"))
        if temperature is not None and self._supports_sampling():
            params["temperature"] = temperature
        reasoning = kwargs.get("reasoning", self.config.get("reasoning"))
        if reasoning and reasoning != "off":
            params["reasoning_effort"] = reasoning
        # Final chunk carries usage; disable via "track_usage": false if a
        # server rejects the stream_options parameter
        if self.config.get("track_usage", True):
            params["stream_options"] = {"include_usage": True}

        usage = None
        stream = self.client.chat.completions.create(**params)
        for chunk in stream:
            if getattr(chunk, "usage", None):
                usage = chunk.usage
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
        if usage:
            self.last_usage = {"input": usage.prompt_tokens, "output": usage.completion_tokens}


class LMStudioProvider(OpenAICompatibleProvider):
    """LM Studio local server"""

    DEFAULT_BASE_URL = "http://localhost:1234/v1"

    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "lmstudio"


class OllamaProvider(OpenAICompatibleProvider):
    """Ollama local server (OpenAI-compatible endpoint)"""

    DEFAULT_BASE_URL = "http://localhost:11434/v1"

    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "ollama"


class OpenAIProvider(OpenAICompatibleProvider):
    """OpenAI GPT provider"""

    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    DEFAULT_MODEL = "gpt-5"
    KEY_ENV_VARS = ("OPENAI_API_KEY",)
    REQUIRES_KEY = True
    MAX_TOKENS_PARAM = "max_completion_tokens"

    # Reasoning-model families that reject custom temperature values
    NO_SAMPLING_PREFIXES = ("gpt-5", "o1", "o3", "o4")

    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "openai"

    def _supports_sampling(self) -> bool:
        return not self.model.startswith(self.NO_SAMPLING_PREFIXES)

    def get_models(self) -> Optional[List[Dict]]:
        models = super().get_models()
        if models:
            # Filter the long list down to chat-capable GPT models
            models = [m for m in models if "gpt" in m["id"].lower()]
        return models


class XAIProvider(OpenAICompatibleProvider):
    """xAI Grok provider (standard OpenAI-compatible endpoints)"""

    DEFAULT_BASE_URL = "https://api.x.ai/v1"
    DEFAULT_MODEL = "grok-4"
    KEY_ENV_VARS = ("XAI_API_KEY",)
    REQUIRES_KEY = True

    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "xai"


class ClaudeProvider(LLMProvider):
    """Anthropic Claude provider (official anthropic SDK)"""

    DEFAULT_MODEL = "claude-opus-4-8"

    # Model families with sampling parameters removed (temperature 400s)
    NO_SAMPLING_PREFIXES = ("claude-opus-4-7", "claude-opus-4-8", "claude-fable")

    def __init__(self, config: Dict):
        super().__init__(config)
        if not HAS_ANTHROPIC:
            raise RuntimeError("anthropic package not installed - pip install anthropic")
        self.name = "claude"
        self.model = config.get("model", self.DEFAULT_MODEL)
        self.timeout = config.get("timeout", 60.0)
        self.api_key = self._resolve_api_key("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise RuntimeError("No API key - set api_key in config or ANTHROPIC_API_KEY")
        self.client = anthropic.Anthropic(api_key=self.api_key, timeout=self.timeout)

    def test_connection(self) -> bool:
        try:
            self.client.with_options(timeout=5.0).models.list(limit=1)
            return True
        except Exception:
            return False

    def get_models(self) -> Optional[List[Dict]]:
        try:
            return [{"id": m.id, "name": m.display_name}
                    for m in self.client.models.list()]
        except Exception:
            return None

    @staticmethod
    def _convert_content(content) -> object:
        """Convert OpenAI-style content (string or block list) to Anthropic blocks"""
        if isinstance(content, str):
            return content
        blocks = []
        for part in content:
            if part.get("type") == "text":
                blocks.append({"type": "text", "text": part["text"]})
            elif part.get("type") == "image_url":
                # data:image/<fmt>;base64,<data>
                url = part["image_url"]["url"]
                header, _, data = url.partition(",")
                media_type = header.split(":", 1)[1].split(";", 1)[0] if ":" in header else "image/png"
                blocks.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": data},
                })
        return blocks

    def stream_completion(self, messages: List[Dict], **kwargs) -> Generator[str, None, None]:
        self.last_usage = None
        system_prompt = None
        claude_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                claude_messages.append({
                    "role": msg["role"],
                    "content": self._convert_content(msg["content"]),
                })

        model = kwargs.get("model", self.model)
        params = {
            "model": model,
            "max_tokens": kwargs.get("max_tokens", self.config.get("max_tokens", 4096)),
            "messages": claude_messages,
        }
        if system_prompt:
            params["system"] = system_prompt
        temperature = kwargs.get("temperature", self.config.get("temperature"))
        if temperature is not None and not model.startswith(self.NO_SAMPLING_PREFIXES):
            params["temperature"] = temperature
        reasoning = kwargs.get("reasoning", self.config.get("reasoning"))
        if reasoning and reasoning != "off":
            # Adaptive thinking on supporting models; the level knob is an
            # OpenAI/Gemini concept - Claude decides depth itself
            params["thinking"] = {"type": "adaptive"}

        with self.client.messages.stream(**params) as stream:
            for text in stream.text_stream:
                yield text
            final = stream.get_final_message()
            self.last_usage = {
                "input": final.usage.input_tokens,
                "output": final.usage.output_tokens,
            }


class GeminiProvider(LLMProvider):
    """Google Gemini provider (google-genai SDK)"""

    DEFAULT_MODEL = "gemini-2.5-flash"

    def __init__(self, config: Dict):
        super().__init__(config)
        if not HAS_GENAI:
            raise RuntimeError("google-genai package not installed - pip install google-genai")
        self.name = "gemini"
        self.model = config.get("model", self.DEFAULT_MODEL)
        self.api_key = self._resolve_api_key("GEMINI_API_KEY", "GOOGLE_API_KEY")
        if not self.api_key:
            raise RuntimeError("No API key - set api_key in config or GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key)

    def test_connection(self) -> bool:
        try:
            next(iter(self.client.models.list()), None)
            return True
        except Exception:
            return False

    def get_models(self) -> Optional[List[Dict]]:
        try:
            return [{"id": m.name.removeprefix("models/"), "name": m.display_name or m.name}
                    for m in self.client.models.list()
                    if "generateContent" in (m.supported_actions or [])]
        except Exception:
            return None

    @staticmethod
    def _convert_parts(content) -> List:
        """Convert OpenAI-style content (string or block list) to genai Parts"""
        import base64
        if isinstance(content, str):
            return [genai_types.Part.from_text(text=content)]
        parts = []
        for part in content:
            if part.get("type") == "text":
                parts.append(genai_types.Part.from_text(text=part["text"]))
            elif part.get("type") == "image_url":
                url = part["image_url"]["url"]
                header, _, data = url.partition(",")
                media_type = header.split(":", 1)[1].split(";", 1)[0] if ":" in header else "image/png"
                parts.append(genai_types.Part.from_bytes(
                    data=base64.b64decode(data), mime_type=media_type))
        return parts

    def stream_completion(self, messages: List[Dict], **kwargs) -> Generator[str, None, None]:
        self.last_usage = None
        system_prompt = None
        contents = []
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                role = "model" if msg["role"] == "assistant" else "user"
                contents.append(genai_types.Content(
                    role=role, parts=self._convert_parts(msg["content"])))

        gen_config = genai_types.GenerateContentConfig(
            max_output_tokens=kwargs.get("max_tokens", self.config.get("max_tokens", 4096)),
            system_instruction=system_prompt,
        )
        temperature = kwargs.get("temperature", self.config.get("temperature"))
        if temperature is not None:
            gen_config.temperature = temperature
        reasoning = kwargs.get("reasoning", self.config.get("reasoning"))
        if reasoning == "off":
            gen_config.thinking_config = genai_types.ThinkingConfig(thinking_budget=0)
        elif reasoning:
            # -1 = dynamic budget; Gemini decides depth per request
            gen_config.thinking_config = genai_types.ThinkingConfig(thinking_budget=-1)

        usage = None
        for chunk in self.client.models.generate_content_stream(
            model=kwargs.get("model", self.model),
            contents=contents,
            config=gen_config,
        ):
            if chunk.usage_metadata:
                usage = chunk.usage_metadata
            if chunk.text:
                yield chunk.text
        if usage:
            prompt_tokens = usage.prompt_token_count or 0
            total_tokens = usage.total_token_count or 0
            self.last_usage = {
                "input": prompt_tokens,
                "output": max(total_tokens - prompt_tokens, 0),
            }


class ProviderManager:
    """Manages LLM providers and switching between them"""

    # Registry of available provider types
    PROVIDERS = {
        "lmstudio": LMStudioProvider,
        "ollama": OllamaProvider,
        "openai": OpenAIProvider,
        "openai_compatible": OpenAICompatibleProvider,
        "xai": XAIProvider,
        "claude": ClaudeProvider,
        "anthropic": ClaudeProvider,
        "gemini": GeminiProvider,
        "google": GeminiProvider,
    }

    def __init__(self):
        self.providers: Dict[str, LLMProvider] = {}
        self.current_provider: Optional[str] = None

    def add_provider(self, name: str, config: Dict) -> CommandResult:
        """Add and configure a provider"""
        provider_type = config.get("type", name)

        if provider_type not in self.PROVIDERS:
            return CommandResult.error(
                f"Unknown provider type: {provider_type}",
                code="UNKNOWN_PROVIDER",
                suggestion=f"Available providers: {', '.join(sorted(set(self.PROVIDERS)))}"
            )

        try:
            provider = self.PROVIDERS[provider_type](config)
            if provider.test_connection():
                self.providers[name] = provider
                if not self.current_provider:
                    self.current_provider = name
                return CommandResult.success_text(f"Added provider: {name}")
            else:
                return CommandResult.error(
                    f"Failed to connect to {name}",
                    code="CONNECTION_FAILED",
                    suggestion="Check your configuration and ensure the service is running"
                )
        except Exception as e:
            return CommandResult.error(
                str(e),
                code="PROVIDER_ERROR",
                suggestion="Check provider configuration"
            )

    def set_current(self, name: str) -> CommandResult:
        """Switch current provider"""
        if name not in self.providers:
            return CommandResult.error(
                f"Provider not found: {name}",
                code="PROVIDER_NOT_FOUND",
                suggestion=f"Available providers: {', '.join(self.providers.keys())}"
            )

        self.current_provider = name
        return CommandResult.success_text(f"Switched to provider: {name}")

    def get_current(self) -> Optional[LLMProvider]:
        """Get current active provider"""
        if self.current_provider:
            return self.providers.get(self.current_provider)
        return None

    def list_providers(self) -> Dict[str, str]:
        """List all configured providers"""
        return {
            name: f"{provider.name} ({'active' if name == self.current_provider else 'inactive'})"
            for name, provider in self.providers.items()
        }
