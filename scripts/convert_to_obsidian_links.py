#!/usr/bin/env python3
"""
Convert standard Markdown links to Obsidian wikilink format.

Usage:
    uv run scripts/convert_to_obsidian_links.py [--dry-run] [--root DIR]

Options:
    --dry-run   Show what would change, do not write files
    --root DIR  Repo root (defaults to parent of scripts/ directory)
"""

import argparse
import os
import re
from pathlib import Path

# ── Patterns ─────────────────────────────────────────────────────────────────

LINK_RE = re.compile(
    r'(!?)'          # group 1: optional ! for image embeds
    r'\[([^\]]*)\]'  # group 2: link text
    r'\(([^)]+)\)'   # group 3: URL or path
)
CODE_FENCE_RE = re.compile(r'(```.*?```)', re.DOTALL)
INLINE_CODE_RE = re.compile(r'(`[^`\n]+`)')

EXCLUDE_DIRS = {'.venv', '.venv-pdf', '.claude', '.git', '__pycache__', 'node_modules'}

# ── Conversion logic ──────────────────────────────────────────────────────────

def replace_link(match: re.Match) -> str:
    bang = match.group(1)
    text = match.group(2)
    url  = match.group(3).strip()

    # External URLs and anchor-only links stay unchanged
    if url.startswith(('http://', 'https://', 'ftp://', 'mailto:')):
        return match.group(0)
    if url.startswith('#'):
        return match.group(0)

    # Split anchor fragment
    if '#' in url:
        path_part, anchor = url.split('#', 1)
    else:
        path_part, anchor = url, ''

    if not path_part:
        return match.group(0)

    filename = os.path.basename(path_part)
    stem, ext = os.path.splitext(filename)

    # Build the wikilink target
    if ext.lower() == '.md':
        target = stem          # drop .md extension
    else:
        target = filename      # keep full name (e.g. fast2025-jiao.pdf)

    if anchor:
        target = f'{target}#{anchor}'

    # Suppress alias when text is redundant
    if ext.lower() == '.md':
        redundant = (text == stem)
    else:
        redundant = (text == filename)

    # Build wikilink
    if bang == '!':
        if redundant or not text:
            return f'![[{target}]]'
        else:
            return f'![[{target}|{text}]]'
    else:
        if redundant:
            return f'[[{target}]]'
        else:
            return f'[[{target}|{text}]]'


def convert_content(content: str) -> str:
    """Apply link conversion while skipping content inside code fences/spans."""
    segments = CODE_FENCE_RE.split(content)
    result = []
    for i, seg in enumerate(segments):
        if i % 2 == 1:
            result.append(seg)  # fenced code block — unchanged
        else:
            sub_segs = INLINE_CODE_RE.split(seg)
            for j, sub in enumerate(sub_segs):
                if j % 2 == 1:
                    result.append(sub)  # inline code — unchanged
                else:
                    result.append(LINK_RE.sub(replace_link, sub))
    return ''.join(result)


# ── File discovery ────────────────────────────────────────────────────────────

def find_md_files(root: Path) -> list[Path]:
    result = []
    for path in sorted(root.rglob('*.md')):
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        result.append(path)
    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    script_dir = Path(__file__).resolve().parent
    default_root = script_dir.parent

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Show changes without writing files')
    parser.add_argument('--root', type=Path, default=default_root,
                        metavar='DIR', help=f'Repo root (default: {default_root})')
    args = parser.parse_args()

    root: Path = args.root.resolve()
    dry_run: bool = args.dry_run

    mode = '[DRY RUN] ' if dry_run else ''
    print(f'{mode}Root: {root}\n')

    md_files = find_md_files(root)
    print(f'Found {len(md_files)} .md files\n')

    files_changed = 0
    links_converted = 0

    for filepath in md_files:
        original = filepath.read_text(encoding='utf-8')
        converted = convert_content(original)

        if converted == original:
            continue

        old_lines = original.splitlines()
        new_lines = converted.splitlines()

        # Count new wikilinks introduced
        for a, b in zip(old_lines, new_lines):
            if a != b:
                links_converted += b.count('[[') - a.count('[[')

        changed_lines = sum(1 for a, b in zip(old_lines, new_lines) if a != b)
        files_changed += 1
        rel = filepath.relative_to(root)

        if dry_run:
            print(f'  WOULD CHANGE: {rel}  ({changed_lines} line(s))')
            shown = 0
            for a, b in zip(old_lines, new_lines):
                if a != b and shown < 3:
                    print(f'    - {a.strip()}')
                    print(f'    + {b.strip()}')
                    shown += 1
        else:
            filepath.write_text(converted, encoding='utf-8')
            print(f'  Updated: {rel}  ({changed_lines} line(s))')

    print(f'\n{"=" * 50}')
    if dry_run:
        print(f'DRY RUN COMPLETE')
        print(f'  Would modify : {files_changed} file(s)')
        print(f'  Would convert: ~{links_converted} link(s)')
    else:
        print(f'DONE')
        print(f'  Modified : {files_changed} file(s)')
        print(f'  Converted: ~{links_converted} link(s)')


if __name__ == '__main__':
    main()
