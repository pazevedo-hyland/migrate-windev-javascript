#!/usr/bin/env python3
"""Migration guardrails shared by every agent and by Git.

Copy to the application as scripts/guard.py. One rule set, three entry points:
  --staged             Git pre-commit check (any agent, any human)
  --hook               Claude Code PreToolUse hook: JSON event on stdin, exit 2 blocks
  --command / --write  ad-hoc checks for other agents' hooks or wrappers
A human owns this file; adjust the constants to the accepted repository layout.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

READ_ONLY = ('legacy/', 'analysis-local/', 'origine/')
MIGRATIONS = 'src-tauri/migrations/'
GENERATED = ('src/bindings/',)
HUMAN_OWNED = ('scripts/guard.py', '.githooks/', '.claude/')  # the guardrails themselves
NEVER_COMMIT = re.compile(r'(\.(fic|ndx|mmo|ftx|bak|bkp)$|(^|/)\.env(\.(?!example$)[^/]+)?$)', re.I)
DESTRUCTIVE_SQL = re.compile(r'\b(DROP\s+(TABLE|COLUMN|INDEX|VIEW)|TRUNCATE|DELETE\s+FROM\s+\w+\s*;)', re.I)
SECRETS = re.compile(r'(-----BEGIN [A-Z ]*PRIVATE KEY-----|\bgh[pousr]_[A-Za-z0-9]{30,}|\bAKIA[0-9A-Z]{16}\b'
                     r'|\bsk-[A-Za-z0-9_-]{20,}|;\s*(password|pwd)\s*=\s*[^\s;"\']{4,})', re.I)
COMMAND_RULES = [
    (re.compile(r'\bgit\s+push\b.*(--force\b|-f\b)'), 'Force-push is forbidden; ask the human.'),
    (re.compile(r'\bgit\s+(add\s+(-A|--all|\.)(\s|$)|commit\s+(-\w*a|--all))'),
     'Stage explicit files only (git add <path>); never add everything.'),
    (re.compile(r'\bgit\s+commit\b.*--no-verify'), 'Do not bypass the pre-commit guard.'),
    (re.compile(r'\brm\s+-\w*r\w*\s+.*\b(legacy|analysis-local)\b'), 'Legacy evidence is read-only.'),
    (re.compile(r'\b(npm|pnpm|yarn)\s+(publish|unpublish)\b'), 'Publishing packages needs the human.'),
]


def git(root, *args):
    return subprocess.run(['git', *args], cwd=root, capture_output=True, text=True)


def relative(path, root):
    try:
        return Path(root, path).resolve().relative_to(root).as_posix()
    except ValueError:
        return Path(path).as_posix()


def check_command(command):
    for pattern, reason in COMMAND_RULES:
        if pattern.search(command):
            return reason
    return None


def check_write(path, text, root):
    """Rules for an agent about to create or modify a file."""
    path = relative(path, root)
    if path.startswith(READ_ONLY):
        return f'{path} is legacy evidence: read it, never modify it.'
    if path.startswith(HUMAN_OWNED):
        return f'{path} belongs to the human (guardrails and agent configuration): propose the change in the handoff.'
    if path.startswith(GENERATED):
        return f'{path} is generated: change the source and regenerate.'
    if path.startswith(MIGRATIONS):
        if git(root, 'ls-files', '--error-unmatch', path).returncode == 0:
            return 'Committed migrations are immutable: add a new migration instead.'
        if DESTRUCTIVE_SQL.search(text):
            return 'Destructive SQL in a migration needs a human-approved ADR; propose it instead.'
    if SECRETS.search(text):
        return 'This content looks like a secret: use environment variables or ignored local config.'
    return None


def check_staged(root):
    """Rules for a commit, whoever wrote it. Returns every violation."""
    problems = []
    listing = git(root, 'diff', '--cached', '--name-status', '--no-renames').stdout.splitlines()
    for line in listing:
        status, path = line.split('\t', 1)
        if path.startswith(READ_ONLY):
            problems.append(f'{path} is private legacy evidence')
        elif NEVER_COMMIT.search(path):
            problems.append(f'{path} must not be committed (data, backup or secret file)')
        elif path.startswith(MIGRATIONS) and status in ('M', 'D'):
            problems.append(f'{path} is an existing migration; add a new one instead')
        if status == 'D':
            continue
        added = '\n'.join(l[1:] for l in git(root, 'diff', '--cached', '-U0', '--', path).stdout.splitlines()
                          if l.startswith('+') and not l.startswith('+++'))
        if path.startswith(MIGRATIONS) and status == 'A' and DESTRUCTIVE_SQL.search(added):
            problems.append(f'{path} contains destructive SQL; it needs a human-approved ADR')
        if SECRETS.search(added):
            problems.append(f'{path} adds content that looks like a secret')
    return problems


def decide(event, root):
    """Claude Code PreToolUse event → blocking reason or None."""
    tool = event.get('tool_name', '')
    data = event.get('tool_input', {}) or {}
    if tool == 'Bash':
        return check_command(data.get('command', ''))
    if tool not in ('Edit', 'MultiEdit', 'Write', 'NotebookEdit'):
        return None
    text = data.get('content') or data.get('new_string') or ''
    text += ''.join(e.get('new_string', '') for e in data.get('edits', []) or [])
    return check_write(data.get('file_path') or data.get('notebook_path') or '', text, root)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--staged', action='store_true', help='check the staged Git changes')
    mode.add_argument('--hook', action='store_true', help='read a Claude Code PreToolUse event on stdin')
    mode.add_argument('--command', help='check a shell command')
    mode.add_argument('--write', metavar='PATH', help='check writing stdin content to PATH')
    args = parser.parse_args()
    root = Path.cwd().resolve()
    if args.staged:
        problems = check_staged(root)
        for problem in problems:
            print(f'guard: {problem}', file=sys.stderr)
        raise SystemExit(1 if problems else 0)
    if args.hook:
        event = json.load(sys.stdin)
        reason = decide(event, Path(event.get('cwd') or root).resolve())
    elif args.command is not None:
        reason = check_command(args.command)
    else:
        reason = check_write(args.write, sys.stdin.read(), root)
    if reason:
        print(f'Blocked by migration guard: {reason}', file=sys.stderr)
        raise SystemExit(2)


if __name__ == '__main__':
    main()
