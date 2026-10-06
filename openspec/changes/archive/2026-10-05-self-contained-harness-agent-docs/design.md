# Design: Docs map and self-contained OpenSpec model

## Docs map

`template/docs/README.md` is platform-owned (updated by Copier) and lists, per concern, the canonical document and when to read it. It deliberately excludes `docs/context/README.md` ownership (project-owned, selectively loaded) and `docs/engineering/project-rules.md` (project-owned) by pointing to them rather than copying them. It states the source-of-truth roles and that the root `AGENTS.md` remains the process map.

## OpenSpec model

The model lives in the existing `openspec-workflow.md` (concern document already linked from AGENTS.md) rather than a new file, so existing pointers, `platform_doctor` required-file checks and `harness_mode=project` skip rules keep working. Content is limited to what an agent needs for the standard lifecycle and is phrased in terms of Dev Platform entrypoints: `scripts/openspec_lifecycle.py archive|check` and `scripts/start_managed_task.py`. Only entrypoints present under `template/scripts/` are named. Upstream OpenSpec docs are described as supplementary reference.

## Risks

Doc drift against real commands: mitigated by a test that every `scripts/*.py` path named in the new sections exists in `template/scripts/`, and by the existing docs link checker.
