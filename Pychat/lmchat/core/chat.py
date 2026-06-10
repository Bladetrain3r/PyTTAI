#!/usr/bin/env python3
"""
Core ChatController - Orchestrates all components
"""

import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import Conversation, Config, CommandResult, OutputFormat
from .parser import parse_statement, ParseError
from .controllers import (
    ClipboardController, 
    FileController,
    SessionController,
    CommandController
)
from .providers import ProviderManager

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

        # Per-session token usage rows; persisted to tokens.csv unless
        # config "token_log" is false
        self.session_usage = []
        
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
            "max_tokens": self.config.get("max_tokens", 4096),
            "temperature": self.config.get("temperature", 0.7)
        }
        # Optional keys pass through only when set
        for key in ("reasoning", "track_usage"):
            if self.config.get(key) is not None:
                default_provider[key] = self.config.get(key)
        
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
        """Register core commands.

        Handlers return a CommandResult (rendered by render_result), None for
        pure side effects, or False as the session-exit signal. Never return
        a raw bool from send_message/send_image - False would exit.
        """
        # Help command
        self.commands.register_command(
            "help",
            lambda args: CommandResult.success_text(self.commands.get_help()),
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
        
        # Token usage command
        self.commands.register_command(
            "tokenuse",
            self._handle_tokenuse_command,
            "Show session token usage",
            aliases=["tokens"]
        )

        # Exit commands - returning False from a handler ends the session
        self.commands.register_command(
            "exit",
            lambda args: False,
            "Exit the application",
            aliases=["quit", "bye"]
        )
    
    def _handle_provider_command(self, args: str) -> CommandResult:
        """Handle provider management commands"""
        if not args:
            providers = self.providers.list_providers()
            lines = ["Configured providers:"]
            lines.extend(f"  {name}: {info}" for name, info in providers.items())
            return CommandResult.success_text("\n".join(lines))

        parts = args.split(maxsplit=1)
        subcommand = parts[0]

        if subcommand == "switch" and len(parts) > 1:
            return self.providers.set_current(parts[1])
        if subcommand == "add":
            return CommandResult.error(
                "Adding providers at runtime is not supported yet",
                code="NOT_IMPLEMENTED",
                suggestion="Use /config providers.NAME.key=value to add providers"
            )
        return CommandResult.error(
            f"Unknown provider subcommand: {subcommand}",
            code="USAGE",
            suggestion="Usage: /provider [switch NAME]"
        )

    def _handle_model_command(self, args: str) -> CommandResult:
        """Handle model command"""
        provider = self.providers.get_current()
        if not provider:
            return CommandResult.error(
                "No provider configured",
                code="NO_PROVIDER",
                suggestion="Check your config and /provider list"
            )

        models = provider.get_models()
        if not models:
            return CommandResult.error(
                f"Could not fetch model information from {provider.name}",
                code="MODELS_UNAVAILABLE",
                suggestion="Check the provider connection and API key"
            )
        lines = [f"Available models ({provider.name}):"]
        lines.extend(f"  - {model['id']}" for model in models)
        return CommandResult.success_text("\n".join(lines))

    def _handle_config_command(self, args: str) -> CommandResult:
        """Handle config command"""
        if not args:
            lines = ["Current configuration:"]
            for key, value in self.config.data.items():
                if key == "providers" and isinstance(value, dict):
                    lines.append("  providers:")
                    for pname, pconfig in value.items():
                        lines.append(f"    {pname}: {pconfig.get('type', 'unknown')}")
                else:
                    lines.append(f"  {key}: {value}")
            return CommandResult.success_text("\n".join(lines))

        if '=' not in args:
            return CommandResult.error(
                "Missing value",
                code="USAGE",
                suggestion="Usage: /config key=value"
            )

        key, value = args.split('=', 1)
        key = key.strip()
        value = value.strip()

        # Try to parse value as appropriate type
        if value.lower() in ('true', 'false'):
            value = value.lower() == 'true'
        elif value.isdigit():
            value = int(value)
        elif '.' in value and value.replace('.', '', 1).isdigit():
            value = float(value)

        # Handle nested keys (e.g., providers.claude.api_key)
        if isinstance(key, str) and '.' in key:
            keys = key.split('.')
            current = self.config.data
            for k in keys[:-1]:
                if k not in current:
                    current[k] = {}
                current = current[k]
            current[keys[-1]] = value
            self.config.save()
        else:
            self.config.set(key, value)

        return CommandResult.success_text(f"Set {key} = {value}")

    def _clear_conversation(self) -> CommandResult:
        """Clear conversation history"""
        self.conversation.clear()
        return CommandResult.success_text("Conversation cleared.")

    def _handle_tokenuse_command(self, args: str) -> CommandResult:
        """Show per-provider token usage for this session"""
        if not self.session_usage:
            return CommandResult.success_text(
                "No token usage recorded this session.")

        totals = {}
        for row in self.session_usage:
            t = totals.setdefault(row["provider"], [0, 0, 0])
            t[0] += row["tokens_in"]
            t[1] += row["tokens_out"]
            t[2] += 1

        lines = ["Session token usage:"]
        grand_in = grand_out = 0
        for name, (tin, tout, turns) in totals.items():
            lines.append(f"  {name}: {tin} in / {tout} out ({turns} turns)")
            grand_in += tin
            grand_out += tout
        lines.append(f"  total: {grand_in} in / {grand_out} out")
        if self.config.get("token_log", True):
            lines.append(f"Log: {self.app_dir / 'tokens.csv'}")
        return CommandResult.success_text("\n".join(lines))

    def _record_usage(self, provider_name: str, provider):
        """Record token usage for the turn that just streamed"""
        usage = getattr(provider, "last_usage", None)
        if not usage:
            return
        row = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "provider": provider_name,
            "model": provider.config.get("model", getattr(provider, "model", "")),
            "tokens_in": usage.get("input", 0),
            "tokens_out": usage.get("output", 0),
        }
        self.session_usage.append(row)
        provider.last_usage = None

        if not self.config.get("token_log", True):
            return
        log_path = self.app_dir / "tokens.csv"
        try:
            is_new = not log_path.exists()
            with open(log_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if is_new:
                    writer.writerow(
                        ["timestamp", "provider", "model", "tokens_in", "tokens_out"])
                writer.writerow([row["timestamp"], row["provider"], row["model"],
                                 row["tokens_in"], row["tokens_out"]])
        except OSError as e:
            print(f"Warning: could not write token log: {e}", file=sys.stderr)

    @staticmethod
    def render_result(result: CommandResult):
        """Render a CommandResult: content to stdout, errors to stderr"""
        if result.success:
            if result.format == OutputFormat.DATA:
                print(json.dumps(result.content, indent=2, default=str))
            elif result.content:
                print(result.content)
        else:
            print(f"Error: {result.error}", file=sys.stderr)
            if result.suggestion:
                print(result.suggestion, file=sys.stderr)
    
    def test_connection(self) -> bool:
        """Test current provider connection"""
        provider = self.providers.get_current()
        return provider.test_connection() if provider else False
    
    # Most providers cap images around 10MB of base64; downscale before that
    IMAGE_COMPRESS_THRESHOLD = 5_000_000
    IMAGE_HARD_LIMIT = 10_000_000

    def _stream_and_record(self) -> bool:
        """Stream a response for the current conversation and record it.

        On failure with no output, the just-added user message is removed so
        a bad turn (e.g. rejected payload) isn't re-sent on every later turn.
        """
        provider = self.providers.get_current()

        messages = []
        system_prompt = self.config.get("system_prompt")
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(self.conversation.get_messages_for_api(
            max_messages=self.config.get("max_conversation_length", 100)
        ))

        print(f"\n{provider.name.title()}: ", end="", flush=True)
        assistant_response = ""

        try:
            for chunk in provider.stream_completion(messages):
                print(chunk, end="", flush=True)
                assistant_response += chunk
            print()  # New line
            self._record_usage(self.providers.current_provider, provider)

            if assistant_response:
                self.conversation.add_message("assistant", assistant_response)
                return True

            print(f"Warning: empty response from {provider.name}. "
                  "The model may have failed to load or hit its context limit.")
            self.conversation.messages.pop()
            return False

        except Exception as e:
            print(f"\n[{provider.name} error] {e}")
            if assistant_response:
                # Keep the partial exchange; the turn did produce content
                self.conversation.add_message("assistant", assistant_response)
            else:
                # Drop the failed user turn so the error doesn't repeat forever
                self.conversation.messages.pop()
                print("(message removed from history - rephrase or fix and retry)")
            return False

    def send_message(self, message: str) -> bool:
        """Send a message and handle the response"""
        provider = self.providers.get_current()
        if not provider:
            print("No LLM provider configured")
            return False

        self.conversation.add_message("user", message)
        return self._stream_and_record()

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

        # Downscale oversized images instead of letting the provider reject them
        if len(image_data) > self.IMAGE_COMPRESS_THRESHOLD:
            result = self.file.compress_image(image_data)
            if result.success:
                info = result.content
                print(f"(image downscaled to {info['width']}x{info['height']} "
                      f"to fit provider size limits)")
                image_data = info["data"]
                image_format = info["format"]
            elif len(image_data) > self.IMAGE_HARD_LIMIT:
                print(f"Image too large to send ({len(image_data) // 1024} KB as base64, "
                      f"limit ~{self.IMAGE_HARD_LIMIT // 1024} KB).")
                print(f"Could not resize: {result.error}")
                if result.suggestion:
                    print(result.suggestion)
                return False

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

        self.conversation.add_message("user", message_content)
        return self._stream_and_record()

    @staticmethod
    def _pipe_text(result: CommandResult) -> str:
        """Render a CommandResult for the next pipe segment.

        Per spec: TEXT passes verbatim; DATA falls back to pretty JSON
        until plain-text renderings exist; :json is reserved for forcing
        structure later.
        """
        if result.format == OutputFormat.DATA:
            return json.dumps(result.content, indent=2, default=str)
        return result.content if isinstance(result.content, str) else str(result.content)

    def _get_pipeline_provider(self, name: Optional[str]):
        """Resolve the provider for an :ai segment.

        :ai@name connects lazily per spec - configured providers that
        weren't reachable at startup get constructed on first use, with
        no connection test; failure surfaces at call time.
        """
        if name is None:
            provider = self.providers.get_current()
            if not provider:
                raise RuntimeError("No LLM provider configured")
            return provider, self.providers.current_provider

        if name in self.providers.providers:
            return self.providers.providers[name], name

        pconfig = self.config.get("providers", {}).get(name)
        if not pconfig:
            raise RuntimeError(f"Unknown provider: {name}")
        provider_type = pconfig.get("type", name)
        cls = self.providers.PROVIDERS.get(provider_type)
        if not cls:
            raise RuntimeError(f"Unknown provider type: {provider_type}")
        provider = cls(pconfig)  # lazy: no test_connection
        self.providers.providers[name] = provider
        return provider, name

    def _run_ai_segment(self, prev: CommandResult, provider_name: Optional[str],
                        prompt: str) -> CommandResult:
        """Execute one :ai segment: stateless, no conversation history"""
        try:
            provider, name = self._get_pipeline_provider(provider_name)
        except Exception as e:
            return CommandResult.error(
                str(e), code="PROVIDER_ERROR",
                suggestion="Check the provider name against your config")

        piped = self._pipe_text(prev)
        content = f"{prompt}\n\n{piped}" if prompt else piped
        messages = [{"role": "user", "content": content}]

        print(f"\n{provider.name.title()}: ", end="", flush=True)
        response = ""
        try:
            for chunk in provider.stream_completion(messages):
                print(chunk, end="", flush=True)
                response += chunk
            print()
            self._record_usage(name, provider)
        except Exception as e:
            print()
            return CommandResult.error(
                f"[{name}] {e}", code="PROVIDER_ERROR",
                suggestion="Provider failed mid-pipeline; statement aborted")

        if not response:
            return CommandResult.error(
                f"Empty response from {name}", code="EMPTY_RESPONSE")
        return CommandResult.success_text(response)

    def _execute_pipeline(self, statement) -> bool:
        """Run a parsed statement with an operator chain"""
        command, args = self.commands.parse_input(statement.command_raw)
        handled, result = self.commands.execute_command(command, args)
        if not handled:
            print(f"Unknown command: /{command} (use /help)", file=sys.stderr)
            return True
        if result is False:
            return False
        if not isinstance(result, CommandResult):
            self.render_result(CommandResult.error(
                f"/{command} produced no pipeable output",
                code="NOT_PIPEABLE",
                suggestion="Only result-returning command forms can feed operators"))
            return True
        if not result.success:
            # Strict short-circuit; :s/:ss arrive in 0.3.0
            self.render_result(result)
            return True

        for segment in statement.chain:
            result = self._run_ai_segment(result, segment.provider, segment.prompt)
            if not result.success:
                self.render_result(result)
                return True
        # Final :ai output already streamed to the client; nothing to re-render
        return True

    def process_input(self, user_input: str) -> bool:
        """Process user input and return True if should continue"""
        if not user_input.strip():
            return True

        # Check for built-in text commands
        if user_input.lower() == 'clear':
            self.render_result(self._clear_conversation())
            return True

        # Statements: /-prefixed lines get parsed; everything else is chat
        if user_input.startswith('/'):
            try:
                statement = parse_statement(user_input)
            except ParseError as e:
                self.render_result(CommandResult.error(
                    f"Parse error: {e}", code="PARSE_ERROR",
                    suggestion='Quote prompt text containing ":" words, '
                               'e.g. :ai "explain what :this does"'))
                return True
            if statement.chain:
                return self._execute_pipeline(statement)

        # Plain slash command (no operators)
        command, args = self.commands.parse_input(user_input)
        if command:
            handled, result = self.commands.execute_command(command, args)
            if not handled:
                print(f"Unknown command: /{command} (use /help)", file=sys.stderr)
                return True
            # A handler returning False (e.g. /exit) ends the session
            if result is False:
                return False
            if isinstance(result, CommandResult):
                self.render_result(result)
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