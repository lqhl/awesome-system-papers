#!/usr/bin/env python3
"""Extract full author list from SOSP 2025 PDFs.

Primary source: ACM Reference Format block (contains full author list)
"""

import fitz
import re
import json
from pathlib import Path

PAPERS_DIR = Path("papers/sosp-2025")
OUTPUT_FILE = Path("sosp_authors.json")

results = {}

# All footnote/affiliation symbols found in SOSP 2025 PDFs
_AFFIL_RAW = (
    '\u2020\u2021\u00a7'  # dagger, double dagger, section
    '\u2660\u2661\u2662\u2663\u2665\u2666'  # spade, white heart, white diamond, club, filled heart, filled diamond
    '\u2605\u2606'  # filled/unfilled stars
    '\u2022\u2023\u25e6\u25cf\u25cb\u2043'  # bullets
    '\u2217'  # mathematical asterisk
    '\u22b3'  # normal superscript (contains as superscript)
    '\u25b3'  # triangle
    '\u00b9\u00b2\u00b3\u00ba\u00aa'  # superscript numbers
    '\u2070\u2074\u2075\u2076\u2077\u2078\u2079'  # more superscripts
    '+\u2020\u2021\u00a7†‡∗\⊳'  # plus, dagger, asterisk variants, etc.
)
# Build symbol set including ASCII asterisk
AFFIL_SYMBOL_SET = set(_AFFIL_RAW)
AFFIL_SYMBOL_SET.add('*')  # ASCII asterisk as affiliation marker
AFFIL_PATTERN = '[' + re.escape(''.join(AFFIL_SYMBOL_SET)) + ']'

for pdf_path in sorted(PAPERS_DIR.glob("*.pdf")):
    doi = pdf_path.stem
    try:
        doc = fitz.open(pdf_path)
        n_pages = len(doc)
        all_text = "".join(doc[i].get_text() for i in range(min(5, n_pages))) + "\n"
        doc.close()

        authors = []

        ref_idx = all_text.find("ACM Reference Format")
        if ref_idx >= 0:
            ref_block = all_text[ref_idx + len("ACM Reference Format"):]
            ref_block = re.sub(r'\.\s*\d{4}.*', '', ref_block, flags=re.DOTALL)
            ref_block = re.sub(r'-\n', '', ref_block)  # remove line-break hyphens
            ref_block = re.sub(r'\n', ' ', ref_block)
            ref_block = re.sub(r'\s+', ' ', ref_block).strip()
            ref_block = re.sub(r'^[\s:]+', '', ref_block)

            # Detect format type:
            # Type A: names concatenated without separators (3731569.3764843-like)
            #   → names followed by ♠∗♥ etc symbols, no "and"
            # Type B: comma-separated names (most papers)
            has_and = ' and ' in ref_block[:300]
            has_symbol_concat = re.search(r'[A-Z][a-z]+\s+[A-Z][a-z]+' + AFFIL_PATTERN + r'+[A-Z]', ref_block)

            if has_symbol_concat and not has_and:
                # Type A: names with affiliation symbols concatenated
                # Pattern: [First Last] followed by one or more symbols
                sym_chars = AFFIL_PATTERN
                name_pat = re.compile(
                    rf'([A-Z][a-z]+(?:\s+[A-Z]\.?\s*){{0,2}}\s+[A-Z][a-zA-Z\-]+){sym_chars}+'
                )
                for m in name_pat.finditer(ref_block):
                    name = m.group(1).strip()
                    if len(name) > 3:
                        authors.append(name)
            else:
                # Type B: comma-separated / " and "-separated
                # Remove institution blocks (lines starting with number + institution name)
                ref_block = re.sub(r'\b\d+(?:\d)*\s*\{[^}]*\}@[^,\s]+', '', ref_block)
                ref_block = re.sub(r'@\S+', '', ref_block)
                ref_block = re.sub(r'\b\d+\s+(University|Institute|College|Corporation|School|Laboratory|Foundation|Center|Centre|Hospital|Microsoft|Google|Meta|Amazon|IBM|NVIDIA|Apple|Facebook|Tencent|Alibaba|Baidu|Huawei|OpenAI|DeepMind|Adobe|Oracle|Samsung|ByteDance)[\w\s,]*', '', ref_block)
                ref_block = re.sub(r'\s+', ' ', ref_block).strip()

                # Remove affiliation symbols
                ref_block_clean = re.sub(AFFIL_PATTERN, '', ref_block)
                ref_block_clean = re.sub(r'\s+', ' ', ref_block_clean).strip()

                # Split by " and "
                parts = re.split(r'\s+and\s+', ref_block_clean)
                for part in parts:
                    # Split by ", " for comma-separated names
                    for name in part.split(', '):
                        name = name.strip().rstrip(',.').strip()
                        # Remove trailing affiliation numbers
                        name = re.sub(r'\d+$', '', name).strip()
                        name = name.rstrip(',.').strip()
                        if len(name) >= 4 and re.match(r"^[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÄËÏÖÜÑÇ\'\-\.]+(?:\s+[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÄËÏÖÜÑÇ\'\-\.]+)*$", name, re.UNICODE):
                            authors.append(name)

        # Fallback
        if not authors:
            cond_pat = re.compile(r'^([A-Z][A-Z\s\'\-\.]+(?:\s+[A-Z][a-z]+)*)\s*,\s*(.+)$', re.MULTILINE)
            for name, affil in cond_pat.findall(all_text[:3000]):
                name = name.strip()
                if len(name) > 3 and not any(kw in name for kw in ['ABSTRACT', 'INDEX', 'SOSP', 'ACM', 'DOI', 'OPEN ACCESS']):
                    authors.append(name)

        # Deduplicate and normalize to Title Case
        seen = set()
        unique = []
        for name in authors:
            norm = name.lower().strip()
            if norm and norm not in seen and len(name) > 3:
                seen.add(norm)
                # Title Case normalization
                def title_case(s):
                    parts = []
                    for part in s.split():
                        if part and part[0].isupper():
                            parts.append(part.capitalize())
                        else:
                            parts.append(part)
                    return ' '.join(parts)
                unique.append(title_case(name))

        results[doi] = {
            "authors": unique,
            "count": len(unique),
        }
        print(f"OK: {doi} | {len(unique)} authors")
    except Exception as e:
        import traceback
        results[doi] = {"error": str(e), "traceback": traceback.format_exc()}
        print(f"ERR: {doi} - {e}")

with open(OUTPUT_FILE, "w") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\nDone: {len(results)} PDFs. Output saved to {OUTPUT_FILE}")
