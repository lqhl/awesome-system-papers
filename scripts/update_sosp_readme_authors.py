#!/usr/bin/env python3
"""Update author fields in SOSP 2025 README based on extracted data."""

import json
import re
from pathlib import Path

README_PATH = Path("reports/sosp-2025/README.md")
EXTRACTED = Path("sosp_authors.json")

with open(EXTRACTED) as f:
    authors_data = json.load(f)

content = README_PATH.read_text(encoding="utf-8")

# Pattern: DOI in parentheses inside a markdown link: [Title](DOI.md)
# Find all DOI references
matches = list(re.finditer(r'\(([0-9]+\.[0-9]+)\.md\)', content))
print(f"Found {len(matches)} DOI references in README")

updated = 0

for m in matches:
    doi = m.group(1)
    if doi not in authors_data:
        print(f"  SKIP: {doi} not in extracted data")
        continue

    authors = authors_data[doi]["authors"]
    if not authors:
        print(f"  SKIP: {doi} no authors")
        continue

    # Format: "Name1, Name2, Name3, and Name4"
    if len(authors) == 1:
        author_str = authors[0]
    elif len(authors) == 2:
        author_str = f"{authors[0]} and {authors[1]}"
    else:
        author_str = ", ".join(authors[:-1]) + f", and {authors[-1]}"

    # Find the author line after this DOI reference
    author_pos = content.find('- 作者：', m.end())
    if author_pos < 0:
        print(f"  SKIP: {doi} no 作者 line")
        continue

    # Find end of this author line (next newline)
    line_end = content.find('\n', author_pos)
    if line_end < 0:
        line_end = len(content)

    old_line = content[author_pos:line_end]
    # Replace: "- 作者：OLD_AUTHORS（...）" → "- 作者：NEW_AUTHORS"
    new_line = re.sub(r'^(- 作者：).+?(（.+）)?$', r'\1' + author_str, old_line)

    if new_line != old_line:
        content = content[:author_pos] + new_line + content[line_end:]
        updated += 1
    else:
        print(f"  NO CHANGE: {doi}")

README_PATH.write_text(content, encoding="utf-8")
print(f"\nUpdated: {updated} entries in README.md")
