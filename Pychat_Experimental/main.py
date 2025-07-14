#!/usr/bin/env python3
"""
Pyttai - AI Shell - Main entry point
"""

import sys
import os
from pathlib import Path


# Add parent directory to path for development
sys.path.insert(0, str(Path(__file__).parent))
from lmchat.core.chat import ChatController
from lmchat.features import clipboard, file_input


def main():
    """Main entry point"""
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Pyttai - AI Shell')
    parser.add_argument('-v', '--verbose', action='store_true', 
                       help='Enable verbose output for debugging')
    args = parser.parse_args()
    
    # Clear screen
    os.system('cls' if os.name == 'nt' else 'clear')
    
    # ASCII art header (optional)
    print("""
    ╔═══════════════════════════════╗
    ║       Pyttai - AI Shell       ║
    ╚═══════════════════════════════╝
    """)
    
    # Initialize chat controller with verbose flag
    chat = ChatController(verbose=args.verbose)
    
    # Test connection
    print("Testing AI providers...", end="", flush=True)
    if not chat.test_connection():
        print(" FAILED")
        print(f"\nCannot connect to any AI provider")
        print("Check your provider configuration and ensure services are running.")
        sys.exit(1)
    print(" OK")
    
    # Register feature modules
    chat.register_feature(clipboard)
    chat.register_feature(file_input)
    
    # Show basic info
    provider = chat.providers.get_current()
    if provider:
        print(f"\nActive Provider: {provider.name}")
        if hasattr(provider, 'base_url'):
            print(f"Server: {provider.base_url}")
        print(f"Model: {provider.config.get('model', 'default')}")
    print("\nType /help for commands, 'exit' to quit")
    print("-" * 40)
    
    # Main interaction loop
    while True:
        try:
            # Custom prompt with color (if terminal supports it)
            if sys.platform != 'win32':
                prompt = "\n\033[93mYou:\033[0m "  # Yellow color
            else:
                prompt = "\nYou: "
            
            user_input = input(prompt)
            
            # Process input
            if not chat.process_input(user_input):
                print("\nGoodbye! 👋")
                break
                
        except KeyboardInterrupt:
            print("\n\nInterrupted. Goodbye! 👋")
            break
        except EOFError:
            # Handle Ctrl+D
            print("\n\nGoodbye! 👋")
            break
        except Exception as e:
            print(f"\nUnexpected error: {e}")
            print("Type 'exit' to quit or press Enter to continue...")

if __name__ == "__main__":
    main()