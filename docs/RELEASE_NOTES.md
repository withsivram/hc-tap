# Healthcare Text Analytics Pipeline — Release Notes

## Week 1 — No-code groundwork (2025-10-29)
**Scope:** fixtures, contracts, repo hygiene, basic CI

- ✅ Fixtures added: 2 sample notes + entities (`fixtures/notes/*`, `fixtures/entities/*`)
- ✅ Contracts written: `contracts/CONTRACTS_V1.txt`, `contracts/entity.schema.json`
- ✅ Docs: naming/tags, S3 layout, observability, run manifest, local demo, role checklists
- ✅ CI: GitHub Actions validates fixtures; env flags set for stub mode
- ✅ Issues & branches created per role (no code yet)

**Links:**  
- CI runs: _add latest Actions link here_  
- Milestone: _Week 1 — No-code groundwork_  

**Next (planned):**  
- Tiny schema validator in CI (JSONL lines vs entity schema)  
- Local “walking skeleton” plan (ETL stub → API stub → dashboard reads files)
