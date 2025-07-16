#!/usr/bin/env python3
"""
Clipboard feature - adds clipboard-related commands
"""

def create_paste_handler(chat_controller):
    """Create paste command handler"""
    def handle_paste(args: str):
        # Get clipboard content (returns CommandResult)
        clipboard_result = chat_controller.clipboard.get_clipboard()
        
        if not clipboard_result.success:
            if not chat_controller.clipboard.is_available():
                print("Clipboard not available. Install: pip install pyperclip")
            else:
                print(f"Clipboard error: {clipboard_result.error}")
            return
        
        # Extract actual content from CommandResult
        clipboard_content = clipboard_result.content
        if not clipboard_content or not clipboard_content.strip():
            print("Clipboard is empty")
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
        "Send clipboard content with optional prompt",
        aliases=["p", "clip"]
    )