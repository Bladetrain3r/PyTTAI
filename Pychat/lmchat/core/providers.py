#!/usr/bin/env python3
"""
LLM Provider abstraction layer
"""

from abc import ABC, abstractmethod
from typing import Generator, List, Dict, Optional
import json
import httpx

from .models import CommandResult

class LLMProvider(ABC):
    """Base interface all LLM providers must implement"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.name = "base"
    
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


class LMStudioProvider(LLMProvider):
    """LM Studio / OpenAI-compatible provider"""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "lmstudio"
        self.base_url = config.get("base_url", "http://localhost:1234")
        self.timeout = config.get("timeout", 60.0)
        self.api_url = f"{self.base_url}/v1/chat/completions"
    
    def test_connection(self) -> bool:
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.base_url}/v1/models")
                return response.status_code == 200
        except:
            return False
    
    def get_models(self) -> Optional[List[Dict]]:
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.base_url}/v1/models")
                return response.json().get("data", [])
        except:
            return None
    
    def stream_completion(self, messages: List[Dict], **kwargs) -> Generator[str, None, None]:
        """Stream completion from LM Studio"""
        data = {
            "model": self.config.get("model", "local-model"),
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.config.get("max_tokens", 1024)),
            "temperature": kwargs.get("temperature", self.config.get("temperature", 0.7)),
            "stream": True
        }
        
        with httpx.Client(timeout=self.timeout) as client:
            with client.stream("POST", self.api_url, json=data) as response:
                for line in response.iter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        
                        try:
                            chunk = json.loads(data_str)
                            if "choices" in chunk and len(chunk["choices"]) > 0:
                                delta = chunk["choices"][0].get("delta", {})
                                if "content" in delta:
                                    yield delta["content"]
                        except json.JSONDecodeError:
                            pass


class ClaudeProvider(LLMProvider):
    """Anthropic Claude provider"""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "claude"
        self.api_key = config.get("api_key")
        self.model = config.get("model", "claude-3-5-sonnet-20241022")
        self.api_url = "https://api.anthropic.com/v1/messages"
        self.timeout = config.get("timeout", 60.0)
    
    def test_connection(self) -> bool:
        if not self.api_key:
            return False
        # Could do a minimal API call here
        return True
    
    def get_models(self) -> Optional[List[Dict]]:
        # Claude doesn't have a list models endpoint
        # Return available models we know about
        return [
            {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet"},
            {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus"},
            {"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku"}
        ]
    
    def stream_completion(self, messages: List[Dict], **kwargs) -> Generator[str, None, None]:
        """Stream completion from Claude"""
        # Convert messages to Claude format (extract system if present)
        system_prompt = None
        claude_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                claude_messages.append(msg)
        
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        data = {
            "model": self.model,
            "max_tokens": kwargs.get("max_tokens", self.config.get("max_tokens", 1024)),
            "temperature": kwargs.get("temperature", self.config.get("temperature", 0.7)),
            "messages": claude_messages,
            "stream": True
        }
        
        if system_prompt:
            data["system"] = system_prompt
        
        with httpx.Client(timeout=self.timeout) as client:
            with client.stream("POST", self.api_url, headers=headers, json=data) as response:
                for line in response.iter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        
                        try:
                            chunk = json.loads(data_str)
                            if chunk["type"] == "content_block_delta" and "text" in chunk["delta"]:
                                yield chunk["delta"]["text"]
                        except json.JSONDecodeError:
                            pass

class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider"""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "openai"
        self.api_key = config.get("api_key")
        self.model = config.get("model", "gpt-4-0125-preview")  # Updated model name
        self.api_url = "https://api.openai.com/v1/chat/completions"
        self.timeout = config.get("timeout", 60.0)
    
    def test_connection(self) -> bool:
        if not self.api_key:
            return False
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                return response.status_code == 200
        except:
            return False
    
    def get_models(self) -> Optional[List[Dict]]:
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                models = response.json().get("data", [])
                # Filter to chat models only
                chat_models = [m for m in models if 'gpt' in m.get('id', '').lower()]
                return chat_models
        except:
            # Return common models if API fails
            return [
                {"id": "gpt-4-0125-preview", "name": "GPT-4 Turbo"},
                {"id": "gpt-4", "name": "GPT-4"},
                {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo"},
                {"id": "gpt-3.5-turbo-0125", "name": "GPT-3.5 Turbo Latest"}
            ]
    
    def stream_completion(self, messages: List[Dict], **kwargs) -> Generator[str, None, None]:
        """Stream completion from OpenAI"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.config.get("max_tokens", 1024)),
            "temperature": kwargs.get("temperature", self.config.get("temperature", 0.7)),
            "stream": True
        }
        
        # Debug: Print what we're sending (remove in production)
        if kwargs.get("debug", False):
            print(f"\nOpenAI Request - Model: {data['model']}")
            print(f"Messages: {len(messages)} messages")
        
        try:
            with httpx.Client(timeout=self.timeout) as client:
                # First, let's try a non-streaming request to see if that works
                # This helps diagnose auth/model issues
                if kwargs.get("test_mode", False):
                    test_data = data.copy()
                    test_data["stream"] = False
                    test_data["max_tokens"] = 10  # Small test
                    
                    test_response = client.post(self.api_url, headers=headers, json=test_data)
                    if test_response.status_code != 200:
                        error = test_response.json()
                        print(f"\nOpenAI Error: {error}")
                        return
                    print(f"\nTest successful: {test_response.json()}")
                    return
                
                # Now the actual streaming request
                response = client.post(
                    self.api_url,
                    headers=headers,
                    json=data,
                    timeout=self.timeout
                )
                
                # Check status before streaming
                if response.status_code != 200:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", "Unknown error")
                    print(f"\nOpenAI API Error: {error_msg}")
                    return
                
                # Now stream the response
                for line in response.iter_lines():
                    if not line:
                        continue
                        
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        
                        try:
                            chunk = json.loads(data_str)
                            if "choices" in chunk and len(chunk["choices"]) > 0:
                                delta = chunk["choices"][0].get("delta", {})
                                if "content" in delta:
                                    yield delta["content"]
                        except json.JSONDecodeError:
                            pass
                            
        except httpx.ConnectError:
            print("\nError: Cannot connect to OpenAI API. Check your internet connection.")
        except httpx.TimeoutException:
            print("\nError: Request to OpenAI timed out.")
        except Exception as e:
            print(f"\nUnexpected error calling OpenAI: {type(e).__name__}: {str(e)}")

class XAIProvider(LLMProvider):
    """xAI Grok provider"""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "xai"
        self.api_key = config.get("api_key")
        self.model = config.get("model", "grok-3")
        self.api_url = "https://api.x.ai/v1/chat/completions"
        self.timeout = config.get("timeout", 60.0)
    
    def test_connection(self) -> bool:
        if not self.api_key:
            return False
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(
                    "https://api.x.ai/v1/models",
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                return response.status_code == 200
        except:
            return False
    
    def get_models(self) -> Optional[List[Dict]]:
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(
                    "https://api.x.ai/v1/models",
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                models = response.json().get("data", [])
                return models
        except:
            # Return common models if API fails
            return [
                {"id": "grok-3", "name": "Grok Beta"},
                {"id": "grok-vision-beta", "name": "Grok Vision Beta"}
            ]
    
    def stream_completion(self, messages: List[Dict], **kwargs) -> Generator[str, None, None]:
        """Stream completion from xAI"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.config.get("max_tokens", 1024)),
            "temperature": kwargs.get("temperature", self.config.get("temperature", 0.7)),
            "stream": True
        }
        
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    self.api_url,
                    headers=headers,
                    json=data,
                    timeout=self.timeout
                )
                
                if response.status_code != 200:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", "Unknown error")
                    print(f"\nxAI API Error: {error_msg}")
                    return
                
                for line in response.iter_lines():
                    if not line:
                        continue
                        
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        
                        try:
                            chunk = json.loads(data_str)
                            if "choices" in chunk and len(chunk["choices"]) > 0:
                                delta = chunk["choices"][0].get("delta", {})
                                if "content" in delta:
                                    yield delta["content"]
                        except json.JSONDecodeError:
                            pass
                            
        except httpx.ConnectError:
            print("\nError: Cannot connect to xAI API. Check your internet connection.")
        except httpx.TimeoutException:
            print("\nError: Request to xAI timed out.")
        except Exception as e:
            print(f"\nUnexpected error calling xAI: {type(e).__name__}: {str(e)}")

class ProviderManager:
    """Manages LLM providers and switching between them"""
    
    # Registry of available providers
    PROVIDERS = {
        "lmstudio": LMStudioProvider,
        "claude": ClaudeProvider,
        "openai": OpenAIProvider,
        "xai": XAIProvider
    }

    PROVIDERS_FUTURE = {
        # For reference, these will be implemented later
        "openai": "OpenAIProvider",
        "ollama": "OllamaProvider",
        "google": "GoogleProvider",
        "azure": "AzureProvider",
        "aws": "AWSProvider",
        "deepseek": "DeepSeekProvider",
        "kokoro": "KokoroProvider", # Text to Speech
        "whisper": "WhisperProvider", # Speech to Text
        "custom": "CustomProvider"
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
                suggestion=f"Available providers: {', '.join(self.PROVIDERS.keys())}"
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