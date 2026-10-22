#!/usr/bin/env python3
"""Claude Code PreToolUse guard: block actions the migration rules forbid.

Exit code 2 blocks the tool call and returns the message to the agent.
Adjust the constants to the application's accepted layout; a human owns this file.
"""
import json
from pathlib import Path
import re
import subprocess
import sys

READ_ONLY = ('legacy/', 'analysis-local/')
MIGRATIONS = 'src-tauri/migrations/'
GENERATED = ('src/bindings/',)
DESTRUCTIVE_SQL = re.compile(r'\b(DROP\s+(TABLE|COLUMN|INDEX|VIEW)|TRUNCATE|DELETE\s+FROM\s+\w+\s*;)', re.I)
SECRETS = re.compile(r'(-----BEGIN [A-Z ]*PRIVATE KEY-----|\bgh[pousr]_[A-Za-z0-9]{30,}|\bAKIA[0-9A-Z]{16}\b'
                     r'|\bsk-[A-Za-z0-9_-]{20,}|;\s*(password|pwd)\s*=\s*[^\s;"\']{4,})', re.I)
BASH_RULES = [
    (re.compile(r'\bgit\s+push\b.*(--force\b|-f\b)'), 'Force-push is forbidden; ask the human.'),
    (re.compile(r'\bgit\s+(add\s+(-A|--all|\.)(\s|$)|commit\s+(-\w*a|--all))'),
     'Stage explicit files only (git add <path>); never add everything.'),
    (re.compile(r'\brm\s+-\w*r\w*\s+.*\b(legacy|analysis-local)\b'), 'Legacy evidence is read-only.'),
    (re.compile(r'\b(npm|pnpm|yarn)\s+(publish|unpublish)\b'), 'Publishing packages needs the human.'),
]


def relative(path, root):
    try:
        return Path(path).resolve().relative_to(root).as_posix()
    except ValueError:
        return Path(path).as_posix()


def tracked(path, root):
    result = subprocess.run(['git', 'ls-files', '--error-unmatch', path], cwd=root,
                            capture_output=True, text=True)
    return result.returncode == 0


def decide(event, root):
    """Return a blocking reason, or None to allow."""
    tool = event.get('tool_name', '')
    data = event.get('tool_input', {}) or {}
    if tool == 'Bash':
        command = data.get('command', '')
        for pattern, reason in BASH_RULES:
            if pattern.search(command):
                return reason
        return None
    if tool not in ('Edit', 'MultiEdit', 'Write', 'NotebookEdit'):
        return None
    path = relative(data.get('file_path') or data.get('notebook_path') or '', root)
    text = data.get('content') or data.get('new_string') or ''
    text += ''.join(e.get('new_string', '') for e in data.get('edits', []) or [])
    if path.startswith(READ_ONLY):
        return f'{path} is legacy evidence: read it, never modify it.'
    if path.startswith(GENERATED):
        return f'{path} is generated: change the source and regenerate.'
    if path.startswith(MIGRATIONS):
        if tracked(path, root):
            return 'Committed migrations are immutable: add a new migration instead.'
        if DESTRUCTIVE_SQL.search(text):
            return 'Destructive SQL in a migration needs a human-approved ADR; propose it instead.'
    if SECRETS.search(text):
        return 'This content looks like a secret: use environment variables or ignored local config.'
    return None


def main():
    event = json.load(sys.stdin)
    root = Path(event.get('cwd') or '.').resolve()
    reason = decide(event, root)
    if reason:
        print(f'Blocked by migration guard: {reason}', file=sys.stderr)
        raise SystemExit(2)


if __name__ == '__main__':
    main()
