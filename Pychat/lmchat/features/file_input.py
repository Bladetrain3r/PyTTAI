#!/usr/bin/env python3
"""
File input feature - adds file reading commands
"""

from pathlib import Path
from lmchat.core.models import OutputFormat

def create_file_handler(chat_controller):
    """Create file command handler"""
    def handle_file(args: str):
        if not args:
            print("Usage: /file <path> [optional prompt]")
            return
        
        # Parse args - first word is path, rest is prompt
        parts = args.split(' ', 1)
        file_path = Path(parts[0])
        prompt = parts[1] if len(parts) > 1 else ""
        
        # Check if file exists
        if not file_path.exists():
            print(f"File not found: {file_path}")
            return
        
        # Read file (returns CommandResult)
        file_result = chat_controller.file.read_file(file_path)
        if not file_result.success:
            print(f"Error reading file: {file_result.error}")
            return
        
        # Check if it's an image
        if file_result.format == OutputFormat.DATA:
            # It's an image
            image_data = file_result.content
            print(f"Sending image {file_path.name}...")
            chat_controller.send_image(
                prompt if prompt else f"[Image: {file_path.name}]",
                image_data['data'],
                image_data['format']
            )
            return
        
        # Text file handling
        content = file_result.content
        
        # Detect language (returns CommandResult)
        language_result = chat_controller.file.detect_language(file_path)
        language = None
        if language_result.success:
            language_info = language_result.content
            language = language_info.get('language')
            
            # Skip code formatting for images
            if language == 'image':
                # This shouldn't happen as we handle images above, but just in case
                print(f"File appears to be an image but was read as text")
                return
        
        # Build message
        if language:
            file_header = f"```{language}\n{content}\n```"
        else:
            file_header = f"```\n{content}\n```"
        
        if prompt:
            message = f"{prompt}\n\n{file_header}"
        else:
            message = f"File: {file_path.name}\n\n{file_header}"
        
        print(f"Sending {file_path.name}...")
        chat_controller.send_message(message)
    
    return handle_file

def register_commands(chat_controller):
    """Register file commands with the chat controller"""
    chat_controller.commands.register_command(
        "file",
        create_file_handler(chat_controller),
        "Read and send file content",
        aliases=["f", "read"]
    )