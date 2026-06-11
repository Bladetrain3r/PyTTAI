#!/usr/bin/env python3
"""
File input feature - adds file reading commands
"""

import sys
from pathlib import Path
from lmchat.core.models import CommandResult, OutputFormat

def create_file_handler(chat_controller):
    """Create file command handler.

    Three invocation forms per the slash-colon spec:
      /file <path>            bare: cat-equivalent CommandResult, no AI
      /file <path> <prompt>   chat-coupled: joins the conversation with
                              full history (content not re-echoed)
      /file <path> :ai ...    pipeline: the bare result feeds the operator
                              (the :ai chain is handled upstream by the
                              parser - this handler just sees the bare form)
    """
    def handle_file(args: str):
        if not args:
            return CommandResult.error(
                "No file path given",
                code="USAGE",
                suggestion="Usage: /file <path> [optional prompt]"
            )

        if args.lstrip().startswith('['):
            return CommandResult.error(
                "List input lands in v0.2.5",
                code="NOT_YET_IMPLEMENTED",
                suggestion="Pass a single path for now"
            )

        # Parse args - first word is path, rest is prompt
        parts = args.split(' ', 1)
        file_path = Path(parts[0])
        prompt = parts[1] if len(parts) > 1 else ""

        # Read file (returns CommandResult)
        file_result = chat_controller.file.read_file(file_path)
        if not file_result.success:
            return file_result

        # Image handling
        if file_result.format == OutputFormat.DATA:
            if prompt:
                # Chat-coupled: send to the vision model in-conversation
                image_data = file_result.content
                print(f"Sending image {file_path.name}...", file=sys.stderr)
                chat_controller.send_image(
                    prompt,
                    image_data['data'],
                    image_data['format']
                )
                return None  # streamed; never return send bools
            # Bare: MIME/metadata only - no base64 dump to the terminal
            meta = {k: v for k, v in file_result.content.items() if k != "data"}
            meta["mime_type"] = f"image/{meta.get('format', 'unknown')}"
            return CommandResult.success_data(meta)

        content = file_result.content

        if not prompt:
            # Bare: cat-equivalent, raw content as the result
            return CommandResult.success_text(content)

        # Chat-coupled: language-fenced content + prompt join the conversation
        language_result = chat_controller.file.detect_language(file_path)
        language = ""
        if language_result.success:
            language = language_result.content.get('language') or ""
        message = f"{prompt}\n\n```{language}\n{content}\n```"

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
