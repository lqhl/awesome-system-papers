#!/usr/bin/env python3
"""Update author fields in SOSP 2025 reports based on extracted data."""

import json
import re
from pathlib import Path

REPORTS_DIR = Path("reports/sosp-2025")
EXTRACTED = Path("sosp_authors.json")

with open(EXTRACTED) as f:
    authors_data = json.load(f)

updated = 0
errors = []

for report_path in sorted(REPORTS_DIR.glob("*.md")):
    if report_path.name == "README.md":
        continue

    doi = report_path.stem
    if doi not in authors_data:
        errors.append(f"No extracted data for {doi}")
        continue

    authors = authors_data[doi]["authors"]
    if not authors:
        errors.append(f"No authors found for {doi}")
        continue

    content = report_path.read_text(encoding="utf-8")

    # Format authors string
    # Format: "Name1, Name2, Name3, and Name4"
    if len(authors) == 1:
        author_str = authors[0]
    elif len(authors) == 2:
        author_str = f"{authors[0]} and {authors[1]}"
    else:
        author_str = ", ".join(authors[:-1]) + f", and {authors[-1]}"

    # Replace the author line
    # Pattern: "- **作者**: ..." (the line starts with "- **作者**:" or "- 作者:")
    # Support both formats
    old_line_match = re.search(r'^(- \*\*作者\*\*|.作者)\s*:\s*.+$', content, re.MULTILINE)
    if old_line_match:
        old_line = old_line_match.group(0)
        # Extract leading indent
        indent_match = re.match(r'^(\s*)', old_line)
        indent = indent_match.group(1) if indent_match else "- "
        # Check if bold format
        if '**' in old_line:
            new_line = f'{indent}**作者**: {author_str}'
        else:
            new_line = f'{indent}作者: {author_str}'
        content = content.replace(old_line, new_line, 1)
        report_path.write_text(content, encoding="utf-8")
        updated += 1
    else:
        errors.append(f"No author line found in {doi}")

print(f"Updated: {updated} reports")
if errors:
    print("Errors:")
    for e in errors:
        print(f"  {e}")
