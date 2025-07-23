#!/usr/bin/env python3
"""
Clipboard feature - adds clipboard-related commands
"""

from lmchat.core.models import OutputFormat

def create_paste_handler(chat_controller):
    """Create paste command handler"""
    def handle_paste(args: str):
        # Check platform - image clipboard doesn't work in WSL/SSH
        import os
        is_wsl = 'WSL_DISTRO_NAME' in os.environ
        is_ssh = 'SSH_CLIENT' in os.environ or 'SSH_TTY' in os.environ
        
        # Only try image clipboard if we're not in WSL/SSH and it's available
        if not (is_wsl or is_ssh) and chat_controller.clipboard.is_image_available():
            try:
                image_result = chat_controller.clipboard.get_image()
                
                if image_result.success:
                    print("Sending clipboard image...")
                    image_data = image_result.content
                    chat_controller.send_image(
                        args if args else "[Pasted Image]",
                        image_data['data'],
                        image_data['format']
                    )
                    return
            except Exception as e:
                # Image grab failed, continue to text
                if args.lower() == "debug":
                    print(f"Image clipboard error: {e}")
                pass
        
        # Try text clipboard
        clipboard_result = chat_controller.clipboard.get_clipboard()
        
        if not clipboard_result.success:
            if not chat_controller.clipboard.is_available():
                print("Clipboard not available. Install: pip install pyperclip")
                if is_wsl:
                    print("For WSL, also install: sudo apt-get install xclip")
                elif is_ssh:
                    print("Note: Clipboard access is limited over SSH")
            else:
                print(f"Clipboard error: {clipboard_result.error}")
                if is_wsl and "could not find" in clipboard_result.error.lower():
                    print("\nFor WSL clipboard support:")
                    print("  X11: sudo apt-get install xclip")
                    print("  Wayland: sudo apt-get install wl-clipboard")
                    print("\nThen try again.")
            return
        
        # Extract actual content from CommandResult
        clipboard_content = clipboard_result.content
        if not clipboard_content or not clipboard_content.strip():
            print("Clipboard is empty")
            if not (is_wsl or is_ssh) and not chat_controller.clipboard.is_image_available():
                print("Note: Image clipboard support requires: pip install Pillow")
            return
        
        # Combine with args if provided
        if args:
            message = f"{args}\n\n{clipboard_content}"
        else:
            message = clipboard_content
        
        print("Sending clipboard content...")
        chat_controller.send_message(message)
    
    return handle_paste

def register_commands(chat_controller):
    """Register clipboard commands with the chat controller"""
    chat_controller.commands.register_command(
        "paste",
        create_paste_handler(chat_controller),
        "Send clipboard content (text or image) with optional prompt",
        aliases=["p", "clip"]
    )