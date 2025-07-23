#!/usr/bin/env python3
"""
Core ChatController - Orchestrates all components
"""

import sys
from pathlib import Path
from typing import Optional

from .models import Conversation, Config, CommandResult
from .controllers import (
    ClipboardController, 
    FileController,
    SessionController,
    CommandController
)
from .providers import ProviderManager, LMStudioProvider, ClaudeProvider

class ChatController:
    """Main controller that orchestrates all chat functionality"""
    
    def __init__(self, config_path: Optional[Path] = None, verbose: bool = False):
        # Force UTF-8
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stdin.reconfigure(encoding='utf-8')
        
        # Store verbose flag
        self.verbose = verbose
        
        # Setup paths
        self.app_dir = Path.home() / ".pyttai"
        self.app_dir.mkdir(exist_ok=True)
        
        # Initialize configuration
        config_path = config_path or (self.app_dir / "config.json")
        self.config = Config(config_path)
        
        # Set defaults if new config
        if not self.config.data:
            self.config.data = Config.get_default_config()
            self.config.save()
        
        # Initialize provider manager
        self.providers = ProviderManager()
        self._setup_providers()
        
        # Initialize controllers
        self.clipboard = ClipboardController()
        self.file = FileController()
        self.session = SessionController(self.app_dir / "sessions")
        self.commands = CommandController()
        
        # Initialize conversation
        self.conversation = Conversation()
        
        # Register built-in commands
        self._register_builtin_commands()
    
    def _setup_providers(self):
        """Setup LLM providers from config"""
        # Setup default LMStudio provider for backward compatibility
        default_provider = {
            "type": "lmstudio",
            "base_url": self.config.get("base_url", "http://localhost:1234"),
            "model": self.config.get("model", "local-model"),
            "timeout": self.config.get("timeout", 60.0),
            "max_tokens": self.config.get("max_tokens", 1024),
            "temperature": self.config.get("temperature", 0.7)
        }
        
        # Add default provider
        result = self.providers.add_provider("default", default_provider)
        if not result.success:
            print(f"Warning: Could not setup default provider: {result.error}")
        
        # Load additional providers from config
        providers_config = self.config.get("providers", {})
        loaded_providers = []
        failed_providers = []
        
        for name, pconfig in providers_config.items():
            result = self.providers.add_provider(name, pconfig)
            if result.success:
                loaded_providers.append(name)
            else:
                failed_providers.append((name, result.error))
        
        # Show provider loading feedback based on verbose flag
        if self.verbose:
            # Verbose mode: show each provider individually
            for name in loaded_providers:
                print(f"Loaded provider: {name}")
            for name, error in failed_providers:
                print(f"Failed to load provider {name}: {error}")
        else:
            # Quiet mode: only show summary if there are multiple providers or failures
            if len(loaded_providers) > 1 or failed_providers:
                if loaded_providers:
                    print(f"Loaded providers: {', '.join(loaded_providers)}")
                if failed_providers:
                    for name, error in failed_providers:
                        print(f"Failed to load {name}: {error}")
        
        # Set active provider if specified in config
        active_provider = self.config.get("active_provider")
        if active_provider and active_provider in self.providers.providers:
            self.providers.set_current(active_provider)
    
    def _register_builtin_commands(self):
        """Register core commands"""
        # Help command
        self.commands.register_command(
            "help",
            lambda args: print(self.commands.get_help()),
            "Show available commands",
            aliases=["h", "?"]
        )
        
        # Provider commands
        self.commands.register_command(
            "provider",
            self._handle_provider_command,
            "Manage LLM providers",
            aliases=["p"]
        )
        
        # Model info command (for compatibility)
        self.commands.register_command(
            "model",
            self._handle_model_command,
            "Show model information",
            aliases=["m"]
        )
        
        # Clear command (as slash command too)
        self.commands.register_command(
            "clear",
            lambda args: self._clear_conversation(),
            "Clear conversation history",
            aliases=["c"]
        )
        
        # Config command
        self.commands.register_command(
            "config",
            self._handle_config_command,
            "Show or set configuration"
        )
        
        # Exit commands
        self.commands.register_command(
            "exit",
            lambda args: exit(0),  # Return False to exit
            "Exit the application",
            aliases=["quit", "bye"]
        )
    
    def _handle_provider_command(self, args: str):
        """Handle provider management commands"""
        if not args:
            # List providers
            providers = self.providers.list_providers()
            print("\nConfigured providers:")
            for name, info in providers.items():
                print(f"  {name}: {info}")
        else:
            parts = args.split(maxsplit=1)
            subcommand = parts[0]
            
            if subcommand == "switch" and len(parts) > 1:
                result = self.providers.set_current(parts[1])
                print(result.error if not result.success else result.content)
            elif subcommand == "add" and len(parts) > 1:
                # Parse provider config from args
                # Format: add name type=claude api_key=xxx
                print("Use /config providers.name.key=value to add providers")
            else:
                print("Usage: /provider [switch NAME]")
    
    def _handle_model_command(self, args: str):
        """Handle model command"""
        provider = self.providers.get_current()
        if not provider:
            print("No provider configured")
            return
        
        models = provider.get_models()
        if models:
            print(f"\nAvailable models ({provider.name}):")
            for model in models:
                print(f"  - {model['id']}")
        else:
            print("Could not fetch model information")
    
    def _handle_config_command(self, args: str):
        """Handle config command"""
        if not args:
            # Show current config
            print("\nCurrent configuration:")
            for key, value in self.config.data.items():
                if key == "providers" and isinstance(value, dict):
                    print(f"  providers:")
                    for pname, pconfig in value.items():
                        print(f"    {pname}: {pconfig.get('type', 'unknown')}")
                else:
                    print(f"  {key}: {value}")
        else:
            # Parse key=value
            if '=' in args:
                key, value = args.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # Try to parse value as appropriate type
                try:
                    if value.lower() in ('true', 'false'):
                        value = value.lower() == 'true'
                    elif value.isdigit():
                        value = int(value)
                    elif '.' in value and value.replace('.', '').isdigit():
                        value = float(value)
                except:
                    pass
                
                # Handle nested keys (e.g., providers.claude.api_key)
                if '.' in key:
                    keys = key.split('.')
                    current = self.config.data
                    for k in keys[:-1]:
                        if k not in current:
                            current[k] = {}
                        current = current[k]
                    current[keys[-1]] = value
                else:
                    self.config.set(key, value)
                
                self.config.save()
                print(f"Set {key} = {value}")
            else:
                print("Usage: /config key=value")
    
    def _clear_conversation(self):
        """Clear conversation history"""
        self.conversation.clear()
        print("Conversation cleared.")
    
    def test_connection(self) -> bool:
        """Test current provider connection"""
        provider = self.providers.get_current()
        return provider.test_connection() if provider else False
    
    def send_message(self, message: str) -> bool:
        """Send a message and handle the response"""
        provider = self.providers.get_current()
        if not provider:
            print("No LLM provider configured")
            return False
        
        # Add user message
        self.conversation.add_message("user", message)
        
        # Build messages for API
        messages = []
        
        # Add system prompt if configured
        system_prompt = self.config.get("system_prompt")
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Add conversation messages
        messages.extend(self.conversation.get_messages_for_api(
            max_messages=self.config.get("max_conversation_length", 100)
        ))
        
        # Stream response
        print(f"\n{provider.name.title()}: ", end="", flush=True)
        assistant_response = ""
        
        try:
            for chunk in provider.stream_completion(messages):
                print(chunk, end="", flush=True)
                assistant_response += chunk
            
            print()  # New line
            
            # Add assistant response to conversation
            if assistant_response:
                self.conversation.add_message("assistant", assistant_response)
            
            return True
            
        except Exception as e:
            print(f"\nError: {e}")
            return False
    
    def send_image(self, text: str, image_data: str, image_format: str) -> bool:
        """Send a message with an image to the vision model"""
        provider = self.providers.get_current()
        if not provider:
            print("No LLM provider configured")
            return False
        
        # Check if current provider supports vision
        if hasattr(provider, 'supports_vision') and not provider.supports_vision():
            print("Current model doesn't support images. Switch to a vision model.")
            return False
        
        # Create message with image
        message_content = [
            {
                "type": "text",
                "text": text
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/{image_format};base64,{image_data}"
                }
            }
        ]
        
        # Add user message with image
        self.conversation.add_message("user", message_content)
        
        # Build messages for API
        messages = []
        
        # Add system prompt if configured
        system_prompt = self.config.get("system_prompt")
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Add conversation messages
        messages.extend(self.conversation.get_messages_for_api(
            max_messages=self.config.get("max_conversation_length", 100)
        ))
        
        # Stream response
        print(f"\n{provider.name.title()}: ", end="", flush=True)
        assistant_response = ""
        
        try:
            for chunk in provider.stream_completion(messages):
                print(chunk, end="", flush=True)
                assistant_response += chunk
            
            print()  # New line
            
            # Add assistant response to conversation
            if assistant_response:
                self.conversation.add_message("assistant", assistant_response)
            
            return True
            
        except Exception as e:
            print(f"\nError: {e}")
            return False
    
    def process_input(self, user_input: str) -> bool:
        """Process user input and return True if should continue"""
        if not user_input.strip():
            return True
        
        # Note: Exit commands are handled as slash commands below
        
        # Check for built-in text commands
        if user_input.lower() == 'clear':
            self._clear_conversation()
            return True
        
        # Check for slash commands
        command, args = self.commands.parse_input(user_input)
        if command:
            if not self.commands.execute_command(command, args):
                print(f"Unknown command: /{command} (use /help)")
            return True
        
        # Regular message
        self.send_message(user_input)
        return True
    
    def register_feature(self, feature_module):
        """Register commands from a feature module"""
        if hasattr(feature_module, 'register_commands'):
            feature_module.register_commands(self)
    
    def run(self):
        """Main interaction loop - can be overridden by view"""
        print("Pyttai - AI Shell")
        provider = self.providers.get_current()
        if provider:
            print(f"Provider: {provider.name}")
        print("Type /help for commands, 'exit' to quit\n")
        
        while True:
            try:
                user_input = input("\nYou: ")
                if not self.process_input(user_input):
                    break
            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")