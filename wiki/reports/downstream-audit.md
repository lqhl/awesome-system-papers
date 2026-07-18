# Downstream Rebuild Audit

## Scope and method

The audit uses the current `wiki/papers` frontmatter as the regenerated source graph. For each conference it compares every page whose `venue` and `year` match the conference metadata with wikilinks in the conference page. For themes it compares the declared topic count with the topic corpus; extra paper links are retained only as cross-topic evidence, not counted as corpus members.

## Conference coverage

| Page | Regenerated paper pages | Linked matching pages | Result |
|---|---:|---:|---|
| [[ATC-2025]] | 100 | 100 | Current; 5 cross-venue comparison links are retained. |
| [[FAST-2026]] | 44 | 44 | Current. |
| [[MLSys-2026]] | 135 | 135 | Current; corrected the stale declared count from 136 to 135. |
| [[OSDI-2025]] | 53 | 53 | Current; 1 cross-venue comparison link is retained. |
| [[SOSP-2025]] | 66 | 66 | Current; 8 cross-venue comparison links are retained. |

## Theme coverage

| Page | Declared topic corpus | Linked in topic list | Result |
|---|---:|---:|---|
| [[AI-Infra]] | 18 | 18 | Current. |
| [[Auto-Research]] | 14 | 14 | Current. |
| [[Finance]] | 5 | 5 | Current. |
| [[Foundation]] | 7 | 7 | Current; 2 additional paper links are cross-topic evidence in the synthesis. |

## Entity and concept revalidation

- Revalidated 17 entity pages and 45 concept pages against the repaired paper graph: all have frontmatter and all concept pages have direct paper backlinks.
- `KTransformers` is anchored by its own [[KTransformers-SOSP25]] source page and appears in repaired-paper discussion through the paper-page link; its entity stem is intentionally not backfilled into historical paper prose.
- Newly promoted entity/concept pages named in [[downstream-rebuild-manifest]] retain source-backed initial rebuilds and remain reachable from the regenerated graph.

## Proposal follow-up

No proposal was rewritten. Revalidate paper-derived claims before the next substantive revision of [[ElasticMoEP2P]], [[HeteroSmallClusterMultiModelAgent]], [[ImportanceGuidedKVTiering]], and [[ThinkingModelKVCache]].
