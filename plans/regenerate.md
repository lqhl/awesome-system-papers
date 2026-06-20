# Wiki Regeneration Plan

> Last updated: 2026-06-20
> Branch: `codex/rebuild-critical-wiki`

## Goal

Regenerate the wiki synthesis layer with the new critical `wiki-paper` format. The rebuilt paper pages should emphasize each paper's key observations, hidden assumptions, design tradeoffs, experimental boundaries, critical analysis, limitations, and future work.

## Scope

Regenerate from the parsed markdown corpus:

- `wiki/papers/`: 443 paper pages from `markdowns/*/*/*.md`
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
- Manifest persisted at [`plans/wiki_rebuild_manifest.json`](wiki_rebuild_manifest.json) (copied from `/tmp/` on 2026-06-20).
- Executor: Grok main agent + up to 6 parallel subagents; commit per conference/topic directory block.

## Current Progress

Paper pages regenerated and ready to commit: **118 / 443**.

Completed groups:

- AI-Infra / topic papers: 18 / 18
- ATC-2025: 100 / 100

Latest completed batch (ATC-2025 final):

- `MARC-ATC25.md`
- `SAVE-ATC25.md`
- `Hermes-ATC25.md`
- `HyperTurtle-ATC25.md`

All completed batches passed:

- Required section check
- `git diff --check`
- Worker scope check by prompt/report

## Resume Point

Continue paper regeneration from manifest item **119** (`autoresearch`):

1. Next directory: `autoresearch` (manifest 119-132, 14 papers)
2. Then: `fast-2026` (44), `finance` (5), `foundation` (7), `mlsys-2026` (136 + 1 new), `osdi-2025` (53), `sosp-2025` (66)

Use at most 6 concurrent paper workers.

## Remaining Work

1. Finish paper page regeneration for manifest items 49-443.
2. Generate the one new parsed MLSys paper page that did not exist in old `wiki/papers/`.
3. Rebuild conference survey pages:
   - `ATC-2025`
   - `FAST-2026`
   - `MLSys-2026`
   - `OSDI-2025`
   - `SOSP-2025`
4. Rebuild theme survey pages:
   - `AI-Infra`
   - `Auto-Research`
   - `Finance`
   - `Foundation`
5. Compute regenerated-paper inbound links and rebuild entity/concept pages.
6. Add watchlist entity/concept pages only when thresholds pass:
   - entity inbound >= 3 papers
   - concept inbound >= 5 papers
7. Rebuild `wiki/index.md` derived sections.
8. Append one rebuild entry to `wiki/log.md`.
9. Run final validation:
   - paper count = 443
   - conference count = 5
   - theme count = 4
   - `git diff --check`
   - `/wiki-lint`
   - `cd quartz && npx quartz build -d ../wiki`

## Notes

- Some regenerated paper pages intentionally contain prospective wikilinks to not-yet-created concept/entity pages. This is allowed during `--no-update` paper rebuild and should be resolved or classified during the entity/concept rebuild and lint phase.
- Workers frequently noted MinerU/OCR issues in figures, formulas, and tables. The regenerated notes generally avoid overclaiming exact graph-derived values when the markdown is noisy.
- Do not run full `wiki-update` for every regenerated paper; it would create log/index/entity/concept conflicts and excessive `wiki/log.md` noise.
