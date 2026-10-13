# delegate-learn

Delegate-family member: the cross-project orchestration-learning skill — records
privacy-preserving evidence about worker routing, task-packet quality, advisor value,
validation, rework, and friction; synthesizes bounded hypotheses without automatically
changing routing policy.

Canonical home for the skill previously living ONLY as a deployment in
`~/.codex/skills/delegate-learn` (adopted verbatim 2026-08-15 — the deployment predated
this repo; a deployment with no canon was a write-path gap). Layout: `skill/` is the
deployable unit; `install.py` deploys it with a sha256 manifest + `--check`, same H5
discipline as delegate-runtime's installer.

Family: delegate-ops (product) · delegate-policy (routing policy + delegate-triage skill) ·
delegate-runtime (adapters, intent-writer, capture) · delegate-learn (this repo).
Naming ratified 2026-08-14 (delegate-policy `docs/proposals/2026-08-14-family-naming.md`).

## Offline checks

Run the existing stdlib-only CLI regression suite from this repository:

```sh
python3 -B -m unittest discover -s skill/tests -v
```

The tests create synthetic events under explicit temporary homes; they do not
read or write the installed skill's telemetry store, submit work to a provider,
or install the skill. The [CI workflow](.github/workflows/ci.yml) runs this same
suite with Python 3.12 on pull requests and pushes to `main`, using pinned actions,
read-only repository access and no persisted checkout credential. This public
repository uses GitHub-hosted `ubuntu-latest` only, never a self-hosted runner or
the private-repository `CI_RUNNER` override. Branch protection is not changed.
