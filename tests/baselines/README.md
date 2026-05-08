# Phase 0.B baselines (records-as-policy + bucket→shelf migration)

Checked-in artifacts that detect drift at cutover and across the migration. Each one corresponds to a baseline checkpoint in `migration-plan.md` §0.B.

## Files

| File | What it captures | Renew on |
|---|---|---|
| `mutation-matrix.txt` | Full output of `tests/run-mutation-coverage.py` against the pinned binary. Per-mutation expected/actual fail counts + `# Overall: OK`. | Phase 1.B (write: + policy synth), Phase 2 (bucket→shelf), any change to `MUTATIONS = [...]` |
| `utility-baseline.md` | Per-suite utility numbers from STATUS.md headline table; threshold post-cutover sweeps must beat. | Phase 2 verification + closeout sweep |
| `security-asr-baseline.md` | Slack × direct + slack × important_instructions ASR=0 from runs 25466790521 + 25466791386. The single verified attack canary (post-cutover sweeps must reproduce 0 ASR). | Phase 1.B and Phase 2 security canary runs |

## How to renew

### Mutation matrix

Phase 0 (pinned binary on PATH):

```bash
PATH="$PWD/.bin:$PATH" uv run --project bench python3 tests/run-mutation-coverage.py | tee tests/baselines/mutation-matrix.txt
```

Post-cutover (system mlld; expect this to be re-snapshotted at each phase boundary as the plan calls):

```bash
uv run --project bench python3 tests/run-mutation-coverage.py | tee tests/baselines/mutation-matrix.txt
```

Diff against the previous snapshot to see which mutations shifted classification. Per the migration plan, *unintentional* shifts fail the build — every shift must be documented in the commit message that introduces it.

### Utility / security baselines

Manual updates against STATUS.md "Sweep history" + the relevant attack-run console logs. The migration plan ties specific run IDs to each baseline; refreshing means picking new run IDs and updating the markdown.

## Why pinned binary on PATH for Phase 0

The mlld SDK (`~/mlld/mlld/sdk/python/mlld.py`) spawns whatever `mlld` is on PATH. For Phase 0 work, that needs to resolve to `./.bin/mlld` (the records-baseline pin), not the system mlld. Without the PATH override, the SDK loads current main, and current main's parser rejects the pre-rename `display:` syntax (m-rec-perms-update changed the form).

Post-cutover (Phase 1.A rename complete), `./.bin/mlld` is retired and the PATH override goes away.
