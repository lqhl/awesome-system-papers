# Wiki Regeneration Plan

> Last updated: 2026-06-20
> Branch: `codex/rebuild-critical-wiki`
> Status: **COMPLETE**

## Goal

Regenerate the wiki synthesis layer with the new critical `wiki-paper` format. The rebuilt paper pages should emphasize each paper's key observations, hidden assumptions, design tradeoffs, experimental boundaries, critical analysis, limitations, and future work.

## Scope

Regenerate from the parsed markdown corpus:

- `wiki/papers/`: 443 paper pages from `markdowns/*/*/*.md` (442 unique wiki pages; EventTensor duplicate PDF merged)
- `wiki/conferences/`: 5 conference survey pages
- `wiki/themes/`: 4 theme survey pages
- `wiki/entities/`: rebuild existing entity pages and add threshold-approved watchlist entities
- `wiki/concepts/`: rebuild existing concept pages and add threshold-approved watchlist concepts

Preserve:

- `wiki/proposals/`
- `wiki/proposals/probes/`
- `wiki/proposals/_log.md`
- historical `wiki/log.md` entries

## Execution Rules

- One subagent owns exactly one paper, conference, theme, entity, or concept page.
- Paper workers must use `wiki-paper --force --no-update --output <target>`.
- Paper workers must not edit `wiki/log.md`, `wiki/index.md`, `wiki/entities/`, `wiki/concepts/`, conference pages, theme pages, or other paper pages.
- Survey workers must use `wiki-survey --skip-papers --no-index-log --output <target>`.
- Entity/concept workers must use `wiki-entity-concept` and only edit their assigned page.
- The main agent alone rebuilds `wiki/index.md`, appends the single rebuild entry to `wiki/log.md`, runs lint/build checks, and commits integration changes.
- Keep old paper filenames for the 442 existing pages; generate the one newly parsed MLSys page with normal wiki-paper naming.

## Completed Setup

- Created branch: `codex/rebuild-critical-wiki`
- Committed rebuild-safe skill changes:
  - `4dcf7b00 Add rebuild-safe wiki skill modes`
- Added `wiki-paper` rebuild options:
  - `--no-update`
  - `--output <path>`
- Added `wiki-survey` rebuild options:
  - `--no-index-log`
  - `--output <path>`
- Added `wiki-entity-concept` skill for one-page entity/concept rebuild workers.
- Manifest persisted at [`plans/wiki_rebuild_manifest.json`](wiki_rebuild_manifest.json)

## Final Progress

**443 / 443 papers regenerated** (442 unique wiki pages on disk).

Completed directory blocks (all committed):

| Block | Papers | Commit |
|-------|--------|--------|
| ai-infra | 18 | early |
| atc-2025 | 100 | `4ac3b03f` |
| autoresearch | 14 | `89bda38f` |
| fast-2026 | 44 | `8ad7a365` |
| finance | 5 | `b82c5bc1` |
| foundation | 7 | `f9e51fce` |
| mlsys-2026 | 136 | `7b1811f4` |
| osdi-2025 | 53 | `f52a3330` |
| sosp-2025 | 66 | `fd25a36e` |

Survey pages (9): `ece1c319`

Entity/concept rebuild (23 pages): `9db6990f`

Integration: index + log updated in final commit.

## Validation Checklist

- [x] Paper pages: 442 on disk, 0 old-format remaining
- [x] Conference surveys: 5
- [x] Theme surveys: 4
- [x] Entity pages rebuilt: 4
- [x] Concept pages rebuilt: 19
- [x] `wiki/index.md` updated
- [x] Single rebuild entry in `wiki/log.md`
- [x] `git diff --check` clean
- [x] `/wiki-lint` report reviewed (SOSP-2025 hybrid wikilink fixed; 4 entity watchlist deferred)
- [x] `cd quartz && npx quartz build -d ../wiki` passes (482 files, 2313 emitted)

## Notes

- EventTensor: orphan arXiv uid `07e1cd7dca891345f7ba84e9b0bc6f44` removed; canonical uid `07e1cd7dca89a1678042477183b7ac3f` (`md5(sourceid=119)`) is the sole source for `EventTensor-MLSys26.md`.
- Some regenerated paper pages intentionally contain prospective wikilinks to not-yet-created concept/entity pages. Resolved or classified during entity/concept rebuild and lint phase.
- Workers frequently noted MinerU/OCR issues in figures, formulas, and tables. Regenerated notes avoid overclaiming exact graph-derived values when markdown is noisy.