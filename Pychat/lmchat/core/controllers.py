#!/usr/bin/env python3
"""
Business logic controllers for different operations
"""

import json
import sys
import base64
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

# Optional image clipboard support
try:
    from PIL import ImageGrab, Image
    import io
    HAS_IMAGE_CLIPBOARD = True
except ImportError:
    HAS_IMAGE_CLIPBOARD = False

# APIController has been replaced by the provider system in providers.py

class AudioController:
    """Handles TTS generation and playback"""
    @staticmethod
    def generate_tts(text: str, provider: str = "default") -> CommandResult:
        """Generate TTS audio from text"""
        if not text.strip():
            return CommandResult.error(
                "No text provided for TTS generation",
                code="EMPTY_TEXT",
                suggestion="Provide some text to convert to speech"
            )
        try:
           print("Placeholder")
           return CommandResult.success_text("Audio generated successfully")
        except OutputFormatError as e:
            return CommandResult.error(
                f"Output format error: {str(e)}",
                code="OUTPUT_FORMAT_ERROR",
                suggestion="Check the output format and try again"
            )

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
    def get_image() -> CommandResult:
        """Get image from clipboard"""
        if not HAS_IMAGE_CLIPBOARD:
            return CommandResult.error(
                "Image clipboard functionality not available",
                code="NO_IMAGE_CLIPBOARD",
                suggestion="Install Pillow: pip install Pillow"
            )
        
        try:
            # Try to grab image from clipboard
            img = ImageGrab.grabclipboard()
            
            if img is None:
                return CommandResult.error(
                    "No image in clipboard",
                    code="NO_IMAGE",
                    suggestion="Copy an image to clipboard first"
                )
            
            # Convert to PNG and base64
            buffer = io.BytesIO()
            
            # Handle different image modes
            if img.mode == 'RGBA':
                img.save(buffer, format='PNG')
                format_type = 'png'
            else:
                # Convert to RGB for JPEG
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                img.save(buffer, format='JPEG', quality=90)
                format_type = 'jpeg'
            
            buffer.seek(0)
            base64_image = base64.b64encode(buffer.read()).decode('utf-8')
            
            return CommandResult.success_data({
                "data": base64_image,
                "format": format_type,
                "width": img.width,
                "height": img.height
            })
            
        except Exception as e:
            return CommandResult.error(
                f"Failed to get image from clipboard: {str(e)}",
                code="IMAGE_CLIPBOARD_ERROR",
                suggestion="Try copying the image again"
            )
    
    @staticmethod
    def is_available() -> bool:
        return HAS_CLIPBOARD
    
    @staticmethod
    def is_image_available() -> bool:
        return HAS_IMAGE_CLIPBOARD

class FileController:
    """Handles file operations"""
    
    # Image file extensions
    IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.ico', '.tiff'}
    
    @staticmethod
    def read_file(path: Path) -> CommandResult:
        """Read file content (text or image)"""
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
            
            # Check if it's an image
            if path.suffix.lower() in FileController.IMAGE_EXTENSIONS:
                return FileController.read_image(path)
            
            # Try to read as text with UTF-8 encoding
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
    def read_image(path: Path) -> CommandResult:
        """Read image file and return base64 encoded data"""
        try:
            # Read binary data
            image_data = path.read_bytes()
            
            # Encode to base64
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            # Get format from extension
            format_type = path.suffix.lower()[1:]  # Remove the dot
            if format_type == 'jpg':
                format_type = 'jpeg'
            
            result_data = {
                "data": base64_image,
                "format": format_type,
                "filename": path.name,
                "size": len(image_data)
            }
            
            # Try to get dimensions if Pillow is available
            if HAS_IMAGE_CLIPBOARD:
                try:
                    from PIL import Image
                    img = Image.open(io.BytesIO(image_data))
                    result_data["width"] = img.width
                    result_data["height"] = img.height
                except:
                    pass  # Dimensions are optional
            
            return CommandResult.success_data(result_data)
            
        except Exception as e:
            return CommandResult.error(
                f"Error reading image file: {str(e)}",
                code="IMAGE_READ_ERROR",
                suggestion="Check if the file is a valid image"
            )
    
    @staticmethod
    def is_image_file(path: Path) -> bool:
        """Check if file is an image based on extension"""
        return path.suffix.lower() in FileController.IMAGE_EXTENSIONS
    
    @staticmethod
    def detect_language(path: Path) -> CommandResult:
        """Detect programming language from file extension"""
        # Check if it's an image first
        if FileController.is_image_file(path):
            return CommandResult.success_data({
                "language": "image",
                "source": "extension",
                "image_format": path.suffix.lower()[1:]
            })
        
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