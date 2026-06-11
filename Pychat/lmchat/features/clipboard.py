#!/usr/bin/env python3
"""
Clipboard feature - adds clipboard-related commands
"""

import os
import sys
from lmchat.core.models import CommandResult

def create_paste_handler(chat_controller):
    """Create paste command handler"""
    def handle_paste(args: str):
        # Image clipboard doesn't work in WSL/SSH
        is_wsl = 'WSL_DISTRO_NAME' in os.environ
        is_ssh = 'SSH_CLIENT' in os.environ or 'SSH_TTY' in os.environ

        # Only try image clipboard if we're not in WSL/SSH and it's available
        if not (is_wsl or is_ssh) and chat_controller.clipboard.is_image_available():
            try:
                image_result = chat_controller.clipboard.get_image()
                if image_result.success:
                    print("Sending clipboard image...", file=sys.stderr)
                    image_data = image_result.content
                    chat_controller.send_image(
                        args if args else "[Pasted Image]",
                        image_data['data'],
                        image_data['format']
                    )
                    return None  # streaming already rendered
            except Exception as e:
                # Image grab failed, fall through to text clipboard
                if args.lower() == "debug":
                    print(f"Image clipboard error: {e}", file=sys.stderr)

        # Try text clipboard
        clipboard_result = chat_controller.clipboard.get_clipboard()

        if not clipboard_result.success:
            suggestion = clipboard_result.suggestion
            if is_wsl:
                suggestion = ("For WSL clipboard support install xclip (X11) "
                              "or wl-clipboard (Wayland), then try again.")
            elif is_ssh:
                suggestion = "Note: Clipboard access is limited over SSH"
            return CommandResult.error(
                clipboard_result.error,
                code=clipboard_result.code,
                suggestion=suggestion
            )

        clipboard_content = clipboard_result.content
        if not clipboard_content or not clipboard_content.strip():
            return CommandResult.error(
                "Clipboard is empty",
                code="EMPTY_CLIPBOARD",
                suggestion="Copy some text or an image first "
                           "(image support requires Pillow)"
            )

        # Combine with args if provided
        if args:
            message = f"{args}\n\n{clipboard_content}"
        else:
            message = clipboard_content

        print("Sending clipboard content...", file=sys.stderr)
        chat_controller.send_message(message)
        return None

    return handle_paste

def register_commands(chat_controller):
    """Register clipboard commands with the chat controller"""
    chat_controller.commands.register_command(
        "paste",
        create_paste_handler(chat_controller),
        "Send clipboard content (text or image) with optional prompt",
        aliases=["p", "clip"]
    )
