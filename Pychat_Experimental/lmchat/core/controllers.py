#!/usr/bin/env python3
"""
Business logic controllers for different operations
"""

import json
import sys
from typing import Optional, Callable, Generator, Dict, List
from pathlib import Path

import httpx

from .models import CommandResult, OutputFormat

# Optional clipboard support
try:
    import pyperclip
    HAS_CLIPBOARD = True
except ImportError:
    HAS_CLIPBOARD = False

# APIController has been replaced by the provider system in providers.py

class ClipboardController:
    """Handles clipboard operations"""
    @staticmethod
    def get_clipboard() -> CommandResult:
        if not HAS_CLIPBOARD:
            return CommandResult.error(
                "Clipboard functionality not available",
                code="NO_CLIPBOARD",
                suggestion="Install pyperclip: pip install pyperclip"
            )
        
        try:
            content = pyperclip.paste()
            if content:
                return CommandResult.success_text(content)
            else:
                return CommandResult.error(
                    "Clipboard is empty",
                    code="EMPTY_CLIPBOARD",
                    suggestion="Copy some text to clipboard first"
                )
        except Exception as e:
            return CommandResult.error(
                f"Failed to access clipboard: {str(e)}",
                code="CLIPBOARD_ERROR",
                suggestion="Check clipboard permissions and try again"
            )
    
    @staticmethod
    def is_available() -> bool:
        return HAS_CLIPBOARD

class FileController:
    """Handles file operations"""
    @staticmethod
    def read_file(path: Path) -> CommandResult:
        """Read file content"""
        try:
            # Check if path exists
            if not path.exists():
                return CommandResult.error(
                    f"File not found: {path}",
                    code="FILE_NOT_FOUND",
                    suggestion="Check the file path and try again"
                )
            
            # Check if it's a file (not directory)
            if not path.is_file():
                return CommandResult.error(
                    f"Path is not a file: {path}",
                    code="NOT_A_FILE",
                    suggestion="Provide a path to a file, not a directory"
                )
            
            # Try to read with UTF-8 encoding
            try:
                content = path.read_text(encoding='utf-8')
                return CommandResult.success_text(content)
            except UnicodeDecodeError:
                # Try with different encoding
                try:
                    content = path.read_text(encoding='latin-1')
                    return CommandResult.success_text(content)
                except UnicodeDecodeError:
                    return CommandResult.error(
                        f"Cannot decode file: {path}",
                        code="ENCODING_ERROR",
                        suggestion="File may be binary or use unsupported encoding"
                    )
        
        except PermissionError:
            return CommandResult.error(
                f"Permission denied: {path}",
                code="PERMISSION_ERROR",
                suggestion="Check file permissions or run with appropriate privileges"
            )
        except Exception as e:
            return CommandResult.error(
                f"Error reading file: {str(e)}",
                code="FILE_ERROR",
                suggestion="Check file path and permissions"
            )
    
    @staticmethod
    def detect_language(path: Path) -> CommandResult:
        """Detect programming language from file extension"""
        extensions = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.go': 'go',
            '.rs': 'rust',
            '.rb': 'ruby',
            '.php': 'php',
            '.sh': 'bash',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.json': 'json',
            '.xml': 'xml',
            '.html': 'html',
            '.css': 'css',
            '.sql': 'sql',
            '.dockerfile': 'dockerfile',
            'Dockerfile': 'dockerfile'
        }
        
        # Check exact filename first
        if path.name in extensions:
            language = extensions[path.name]
            return CommandResult.success_data({"language": language, "source": "filename"})
        
        # Then check extension
        language = extensions.get(path.suffix.lower())
        if language:
            return CommandResult.success_data({"language": language, "source": "extension"})
        
        return CommandResult.error(
            f"Unknown file type: {path.suffix or 'no extension'}",
            code="UNKNOWN_FILETYPE",
            suggestion="Language detection based on file extension only"
        )

class SessionController:
    """Handles session management"""
    def __init__(self, session_dir: Path):
        self.session_dir = session_dir
        self.session_dir.mkdir(exist_ok=True)
    
    def get_session_path(self, name: str) -> Path:
        return self.session_dir / f"{name}.json"
    
    def list_sessions(self) -> List[str]:
        """List all saved sessions"""
        return [f.stem for f in self.session_dir.glob("*.json")]
    
    def session_exists(self, name: str) -> bool:
        return self.get_session_path(name).exists()

class CommandController:
    """Handles command parsing and execution"""
    def __init__(self):
        self.commands = {}
        self.aliases = {}
    
    def register_command(self, name: str, handler: Callable, description: str = "", aliases: Optional[List[str]] = None):
        """Register a command handler"""
        self.commands[name] = {
            "handler": handler,
            "description": description
        }
        
        if aliases:
            for alias in aliases:
                self.aliases[alias] = name
    
    def parse_input(self, user_input: str) -> tuple:
        """Parse user input into command and arguments"""
        if not user_input.startswith('/'):
            return None, user_input
        
        parts = user_input[1:].split(' ', 1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        # Check aliases
        if command in self.aliases:
            command = self.aliases[command]
        
        return command, args
    
    def execute_command(self, command: str, args: str) -> bool:
        """Execute a command if it exists"""
        if command in self.commands:
            self.commands[command]["handler"](args)
            return True
        return False
    
    def get_help(self) -> str:
        """Get help text for all commands"""
        lines = ["Available commands:"]
        for name, info in self.commands.items():
            if info["description"]:
                lines.append(f"  /{name} - {info['description']}")
        return "\n".join(lines)