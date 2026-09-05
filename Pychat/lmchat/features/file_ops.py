#!/usr/bin/env python3
"""
File operations feature - /ls, /find and /persist

These return CommandResults and compose with operators. /ls and /find use
the DATA render field so they show one entry per line (and pipe the same
way) rather than dumping JSON. All respect the workspace boundary.
"""

from lmchat.core.models import CommandResult


def create_ls_handler(chat_controller):
    def handle_ls(args: str):
        return chat_controller.file.list_entries(
            args.strip() or "*", root=chat_controller.workspace_root)
    return handle_ls


def create_find_handler(chat_controller):
    def handle_find(args: str):
        parts = args.split(maxsplit=1)
        if not parts:
            return CommandResult.error(
                "No search pattern given", code="USAGE",
                suggestion="Usage: /find <pattern> [start-dir]")
        pattern = parts[0]
        start = parts[1].strip() if len(parts) > 1 else "."
        return chat_controller.file.find(
            pattern, start, root=chat_controller.workspace_root)
    return handle_find


def create_persist_handler(chat_controller):
    def handle_persist(args: str):
        parts = args.split()

        # Variant: /persist@context [name] - save the conversation itself
        if parts and parts[0].startswith('@'):
            variant = parts[0][1:]
            if variant == "context":
                name = parts[1] if len(parts) > 1 else None
                return chat_controller.persist_context(name)
            return CommandResult.error(
                f"Unknown persist variant: @{variant}",
                code="USAGE",
                suggestion="Known: @context (save conversation). "
                           "Plain /persist <file> saves a file."
            )

        if not parts:
            return CommandResult.error(
                "No file given",
                code="USAGE",
                suggestion="Usage: /persist <file> [name]  or  /persist@context [name]"
            )
        source = parts[0]
        name = parts[1] if len(parts) > 1 else None
        return chat_controller.session.persist_file(
            source, name, root=chat_controller.workspace_root)
    return handle_persist


def register_commands(chat_controller):
    chat_controller.commands.register_command(
        "ls",
        create_ls_handler(chat_controller),
        "List files/directories (glob patterns: *.py, **/*.log)",
        aliases=["dir"]
    )
    chat_controller.commands.register_command(
        "find",
        create_find_handler(chat_controller),
        "Recursively find files by name: /find <pattern> [start-dir]",
    )
    chat_controller.commands.register_command(
        "persist",
        create_persist_handler(chat_controller),
        "Save a file (/persist <file>) or the conversation (/persist@context)",
    )
