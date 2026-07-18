# Downstream Rebuild Manifest

## [2026-07-18] Scope

- Trigger: paper repair manifest is complete (`443` complete-candidate pages); candidate link audit has no remaining candidate entries.
- Rebuild policy: regenerate only pages in the existing publication graph; do not rewrite proposals.

## Conference pages

- `wiki/conferences/ATC-2025.md`
- `wiki/conferences/FAST-2026.md`
- `wiki/conferences/MLSys-2026.md`
- `wiki/conferences/OSDI-2025.md`
- `wiki/conferences/SOSP-2025.md`

## Theme pages

- `wiki/themes/AI-Infra.md`
- `wiki/themes/Auto-Research.md`
- `wiki/themes/Finance.md`
- `wiki/themes/Foundation.md`

## Entity and concept pages

- Revalidate every existing page in `wiki/entities/` and `wiki/concepts/` after the conference/theme rebuild, prioritizing pages with newly promoted aliases or inbound paper repairs.
- Newly promoted pages already have a source-backed initial rebuild: `FSDP`, `ZNS`, `PyTorch`, `SPDK`, `LSM-Tree`, `NCCL`, `ZeRO`, `FEMU`, `DiskANN`, `HNSW`, `Serverless`, `EROFS`, `WebRTC`, `Ext4`, `Congestion-Control`, `Tensor-Core`, `PCIe`, `DRF`, `CUDA-Graph`, `Federated-Learning`, `NUMA`, `Online-Softmax`, `Erasure-Coding`, `Chain-of-Thought`, `Vector-Search`, `Garbage-Collection`.

## Proposal revalidation only

- `wiki/proposals/ElasticMoEP2P.md`
- `wiki/proposals/HeteroSmallClusterMultiModelAgent.md`
- `wiki/proposals/ImportanceGuidedKVTiering.md`
- `wiki/proposals/ThinkingModelKVCache.md`

No proposal content is automatically rewritten. Revalidate each proposal's linked-paper claims after the downstream pages are regenerated.
