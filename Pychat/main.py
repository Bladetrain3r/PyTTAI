#!/usr/bin/env python3
"""
Pyttai - AI Shell - Main entry point
"""

import sys
import os
from pathlib import Path
try:
    import readline  # This enables arrow keys/history in Unix-like systems
except ImportError:
    pass  # readline not available on Windows, but not needed there


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
    parser.add_argument('-a', '--ass', action='store_true',
                       help='Assume endpoints work.')
    parser.add_argument('-c', '--command', nargs='*',
                       help='Run in non-interactive command mode. Use "-" for stdin, file path to read from file, or command string')
    args = parser.parse_args()
    
    # Clear screen
    if not args.command:
        os.system('cls' if os.name == 'nt' else 'clear')
    else:
        print("Running Non-Interactively", file=sys.stderr)
    
    # ASCII art header (optional)
    print("""
    ╔═══════════════════════════════╗
    ║       Pyttai - AI Shell       ║
    ╚═══════════════════════════════╝
    """, file=sys.stderr)
    
    # Initialize chat controller with verbose flag
    chat = ChatController(verbose=args.verbose)
    
    # Test connection
    if args.ass:
        print("Skipping Testing", file=sys.stderr)
    else:
        print("Testing AI providers...", end="", flush=True, file=sys.stderr)
        if not chat.test_connection():
            print(" FAILED", file=sys.stderr)
            print(f"\nCannot connect to any AI provider", file=sys.stderr)
            print("Check your provider configuration and ensure services are running.", file=sys.stderr)
            sys.exit(1)
        print(" OK", file=sys.stderr)
    
    # Register feature modules
    chat.register_feature(clipboard)
    chat.register_feature(file_input)
    
    # Show basic info
    provider = chat.providers.get_current()
    if provider:
        print(f"\nActive Provider: {provider.name}", file=sys.stderr)
        # if hasattr(provider, 'base_url'):
        #     print(f"Server: {provider.base_url}", file=sys.stderr)
        print(f"Model: {provider.config.get('model', 'default')}", file=sys.stderr)
    print("\nType /help for commands, 'exit' to quit", file=sys.stderr)
    print("-" * 40, file=sys.stderr)

    # Handle non-interactive mode
    if args.command:
        print("\nRunning in command mode...", file=sys.stderr)
        
        # Check if we have a single argument
        if len(args.command) == 1:
            command_input = args.command[0]
            
            # Read from stdin
            if command_input == '-':
                print("Reading from stdin...", file=sys.stderr)
                try:
                    commands = sys.stdin.read().strip().split('\n')
                except KeyboardInterrupt:
                    print("\nInterrupted while reading stdin", file=sys.stderr)
                    sys.exit(1)
            
            # Read from file
            elif os.path.exists(command_input):
                print(f"Reading from file: {command_input}", file=sys.stderr)
                try:
                    with open(command_input, 'r', encoding='utf-8') as f:
                        commands = f.read().strip().split('\n')
                except Exception as e:
                    print(f"Error reading file: {e}", file=sys.stderr)
                    sys.exit(1)
            
            # Single command
            else:
                commands = [command_input]
        else:
            # Multiple arguments - join as single command
            commands = [' '.join(args.command)]
        
        # Execute each command
        for cmd in commands:
            if cmd.strip():  # Skip empty lines
                print(f"\n> {cmd}", file=sys.stderr)
                result = chat.process_input(cmd.strip())
                if args.verbose is True:
                    print(f"Debug: process_input returned: {result}")
                if not result:
                    break
        
        # Exit after processing
        sys.exit(0)
    
    # Main interaction loop
    while True and not args.command:
        try:
            # Custom prompt with color (if terminal supports it)
            if sys.platform != 'win32':
                prompt = "\n\033[93mYou:\033[0m "  # Yellow color
            else:
                prompt = "\nYou: "
            
            user_input = input(prompt)
            
            # Process input
            if not chat.process_input(user_input):
                print("\nGoodbye! 👋", file=sys.stderr)
                break
                
        except KeyboardInterrupt:
            break
        except EOFError:
            # Handle Ctrl+D
            print("End of input detected. Exiting...", file=sys.stderr)
            break
        except Exception as e:
            print(f"\nUnexpected error: {e}", file=sys.stderr)
            print("Type 'exit' to quit or press Enter to continue...", file=sys.stderr)

if __name__ == "__main__":
    main()