# Plan — Tech Hotspot Radar

## Execution Plan

```text
┌────┬──────────────────────────────┬────────────────────────────────────────────┐
│ id │ workstream                   │ order                                      │
├────┼──────────────────────────────┼────────────────────────────────────────────┤
│ N1 │ data foundation              │ first                                      │
│ N1B│ local reasoning engine       │ after N1                                   │
│ N2 │ YouTube pipeline             │ after N1B, parallel with N3/N4             │
│ N3 │ social pipeline              │ after N1B, parallel with N2/N4             │
│ N4 │ GitHub pipeline              │ after N1B, parallel with N2/N3             │
│ N5 │ cross-source reporting       │ after N2/N3/N4                             │
│ N6 │ release verification         │ after N5                                   │
└────┴──────────────────────────────┴────────────────────────────────────────────┘
```

## Verification Commands

```bash
python3 -m py_compile scripts/tech_hotspot_radar.py
bash tests/test-tech-hotspot-radar.sh
solar-harness wiki tech-hotspot-radar doctor
solar-harness wiki tech-hotspot-radar report --date 2026-05-23
```

## Stop Points

- Stop N1 if migration cannot create temp DB.
- Stop N2/N3/N4 source-specific work on parser failure, but do not block sibling nodes.
- Stop N5 if source reports are absent and no fixture fallback exists.
- Stop N6 if any source destroys old digest compatibility.
