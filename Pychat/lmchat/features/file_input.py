#!/usr/bin/env python3
"""
File input feature - adds file reading commands
"""

import sys
from pathlib import Path
from lmchat.core.models import CommandResult, OutputFormat

def create_file_handler(chat_controller):
    """Create file command handler"""
    def handle_file(args: str):
        if not args:
            return CommandResult.error(
                "No file path given",
                code="USAGE",
                suggestion="Usage: /file <path> [optional prompt]"
            )

        # Parse args - first word is path, rest is prompt
        parts = args.split(' ', 1)
        file_path = Path(parts[0])
        prompt = parts[1] if len(parts) > 1 else ""

        # Read file (returns CommandResult)
        file_result = chat_controller.file.read_file(file_path)
        if not file_result.success:
            return file_result

        # Check if it's an image
        if file_result.format == OutputFormat.DATA:
            image_data = file_result.content
            print(f"Sending image {file_path.name}...", file=sys.stderr)
            chat_controller.send_image(
                prompt if prompt else f"[Image: {file_path.name}]",
                image_data['data'],
                image_data['format']
            )
            return None  # streaming already rendered; never return send bools

        # Text file handling
        content = file_result.content

        # Detect language (returns CommandResult)
        language_result = chat_controller.file.detect_language(file_path)
        language = None
        if language_result.success:
            language = language_result.content.get('language')

        # Build message
        if language:
            file_header = f"```{language}\n{content}\n```"
        else:
            file_header = f"```\n{content}\n```"

        if prompt:
            message = f"{prompt}\n\n{file_header}"
        else:
            message = f"File: {file_path.name}\n\n{file_header}"

        print(f"Sending {file_path.name}...", file=sys.stderr)
        chat_controller.send_message(message)
        return None

    return handle_file

def register_commands(chat_controller):
    """Register file commands with the chat controller"""
    chat_controller.commands.register_command(
        "file",
        create_file_handler(chat_controller),
        "Read and send file content",
        aliases=["f", "read"]
    )
