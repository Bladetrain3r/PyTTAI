#!/usr/bin/env python3
"""
File operations feature - /ls and /persist

These return CommandResults and compose with operators. /ls uses the
DATA render field so it shows one entry per line (and pipes the same way)
rather than dumping JSON.
"""

from lmchat.core.models import CommandResult


def create_ls_handler(chat_controller):
    def handle_ls(args: str):
        return chat_controller.file.list_entries(args.strip() or "*")
    return handle_ls


def create_persist_handler(chat_controller):
    def handle_persist(args: str):
        parts = args.split()
        if not parts:
            return CommandResult.error(
                "No file given",
                code="USAGE",
                suggestion="Usage: /persist <file> [name]"
            )
        source = parts[0]
        name = parts[1] if len(parts) > 1 else None
        return chat_controller.session.persist_file(source, name)
    return handle_persist


def register_commands(chat_controller):
    chat_controller.commands.register_command(
        "ls",
        create_ls_handler(chat_controller),
        "List files/directories (glob patterns: *.py, **/*.log)",
        aliases=["dir"]
    )
    chat_controller.commands.register_command(
        "persist",
        create_persist_handler(chat_controller),
        "Save a file to the persistent sessions directory",
    )
