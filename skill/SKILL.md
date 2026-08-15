---
name: delegate-learn
description: Record privacy-preserving cross-project evidence about worker routing, task-packet quality, advisor value, validation, rework, and friction; synthesize bounded hypotheses without automatically changing routing policy. Use before and after substantive delegation or advice consultations, when a worker stalls or requires revision, when comparing Luna/Terra/Sol routes, or when reviewing orchestration lessons across projects.
---

# Orchestration Learning

Build a cumulative operational evidence program while real work continues.
Record comparable decisions and outcomes, not prompts or activity logs.

## Record a run

1. Before launch, create a `route_planned` event from the triage decision.
   Keep planned, requested, and observed provenance distinct.
2. During work, record only decision-bearing `checkpoint` events such as first
   useful artifact, missed checkpoint, scope violation, or first validation.
3. Record each material advisor result as a `consultation` event. Agreement is
   not value; capture whether it changed action or supplied a reproducible
   counterexample.
4. After root disposition, append a `disposition` event with validator outcome,
   rework, friction codes, confounder codes, and directly observed cost data.
5. Preserve qualitative project context in the repository's own learning or
   decision ledger. Keep the cross-project stream code-only and content-free.

For artifact-transport failures, use bounded codes rather than copying content:

- `duplicate-synthesis`: root restated a worker-owned artifact without a distinct synthesis need;
- `artifact-transport-mismatch`: the selected surface could not deliver the planned artifact;
- `write-scope-overbroad`: direct artifact authorship received broader write authority than needed.

Keep the originating project and artifact references in its ledger or an explicitly requested
Signal Layer observation, never in orchestration telemetry. One event may justify a reversible
contract amendment after human review; it does not establish a route or model ranking.

Read [the event schema](references/schema.md) before constructing an event.
Use `record-route` and `record-disposition` for the recurring lifecycle events;
they derive the envelope and project ID from the current directory. A route's
requested role/model/effort default to its planned values. Keep semantic
judgments explicit, and use raw `record` for other event types or a deliberately
constructed full envelope.

Use the deterministic recorder; run each subcommand with `--help` for fields:

```bash
python3 scripts/orchestration_learning.py record-route --run-id task-1 \
  --task-class bounded-implementation --closure-target reviewed-software-slice \
  --planned-role worker --planned-model gpt-5.6-terra --planned-effort high \
  --nearest-alternative root-local-implementation \
  --validation-oracle focused-and-full-tests --falsifier-code test-failure
python3 scripts/orchestration_learning.py record-disposition --run-id task-1 \
  --disposition accept --rework-count 0 --observation-code review-clean
python3 scripts/orchestration_learning.py record < safe-event.json
python3 scripts/orchestration_learning.py audit
python3 scripts/orchestration_learning.py summarize
```

The default store is
`~/.codex/telemetry/orchestration-learning/events.jsonl`. Override it only with
`ORCHESTRATION_LEARNING_HOME` or `--home` for an isolated forward test.

## Apply epistemic discipline

- Treat one run as a bounded observation, not a model ranking.
- Name confounders such as packet breadth, missing oracle, codebase size, or
  mixed semantic/mechanical ownership.
- Promote a candidate hypothesis only after comparable runs and a check that
  could have weakened it.
- Keep active routing policy reversible, scoped, reviewed, and separate from
  hypotheses.
- Never estimate missing time, token, or monetary data.
- Do not change delegation or advisor policy automatically from telemetry.

## Protect privacy and integrity

Record no prompt, transcript, command, tool output, raw payload, secret,
credential, path, account identity, or artifact content. The recorder rejects
unknown fields and content-bearing keys. Use the generated pseudonymous project
ID rather than a repository path.

Telemetry failure must not block urgent project work. Record the failure in the
project ledger and continue.

## Review the program

Run `audit` before relying on summaries. Use `summarize` for descriptive counts,
then return to project ledgers for interpretation. Require a human decision
before promoting a cross-project heuristic into delegate-policy or
advice-escalation policy.
