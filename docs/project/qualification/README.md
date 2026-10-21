# Qualification records (roadmap §6.4–6.5, P20.S4.T4, QUALIFICATION-01)

A capacity, security or device claim is bound to the release manifest that was measured. Each measured scenario gets one
record in `records/<id>.json`. `python -m portal_api.qualification check` validates the records in CI, and the release
manifest lists them under `qualification_records`.

**No records exist yet.** No load, device or security qualification run has taken place. Those runs need a deployment
(B03), devices (B07/B09/B13) and the P20 scenarios. Until a record exists, no capacity, security or device claim is
evidenced. The tool reports this as `standard_checks_only: null`.

## Record format

```json
{
  "id": "QR-YYYY-MM-DD-short-name",
  "scenario": "burst_load",
  "claim": "What this evidence supports, in one sentence",
  "measured_at": "YYYY-MM-DD",
  "manifest": { "...": "the full output of `python -m portal_api.release manifest` for the measured build" },
  "environment": "where it ran: instance classes, pool sizes, region, client devices",
  "data_volume": "the data the run used (e.g. `loadtest/volume.py` report)",
  "results": { "...": "the measured figures" },
  "limitations": ["what the run did not cover"],
  "evidence": ["report files, CI runs"],
  "content_snapshot": "QR-YYYY-MM-DD-short-name.snapshot.json"
}
```

- **`scenario`** is one of `portal_api.qualification.SCENARIOS`.
- **`manifest`** must carry the full 40-character `git_commit` and the `migration_head`.
- **`content_snapshot`** is optional. When the measurement depends on content (device budgets, rendering, catalogue and search), take it at the time of the run:

  ```
  python -m portal_api.qualification snapshot > records/<id>.snapshot.json
  ```

  It holds item ids, kinds, versions, block types and byte sizes, and no academic text.

## Release-checklist step

```
python -m portal_api.qualification snapshot > candidate.json   # against the deployment database
python -m portal_api.qualification impact --content candidate.json
```

For each record, `impact` compares three things with the candidate:

- the files changed since the measured commit;
- the manifest fields;
- the live content set, when both snapshots exist.

It matches each change against the §6.4 trigger table (`portal_api.qualification.TRIGGERS`). It then lists the records the change invalidates and the retest each one needs. A change that matches no row needs only the standard release checks; caption, text and copy corrections are one example.

Matching is deliberately conservative. Any edit to a lesson renderer, an attempt endpoint module or an auth, upload or export path counts as material.
