#!/usr/bin/env python3
"""Deploy the delegate-learn skill to a consumer surface (H5 discipline).

`install.py codex [--root DIR]`   — deploy `skill/` into `<root>/skills/delegate-learn`
                                    (tests and __pycache__ excluded), stamp a sha256
                                    manifest, append a maintenance ledger line.
`install.py codex --check`        — OK / BEHIND / MISSING / EXTRA against canon;
                                    nonzero exit on BEHIND/MISSING. Extras are reported,
                                    never deleted.
Default root: ~/.codex. Pattern: delegate-runtime/install.py (hand-copies measurably
drifted; installers replace hand-sync family-wide, 2026-08-15).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent
SKILL_NAME = "delegate-learn"
MANIFEST_NAME = "delegate-learn-manifest.json"
LEDGER_NAME = "delegate-learn-maintenance.jsonl"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canon_files() -> list[Path]:
    return [
        p for p in sorted((REPO / "skill").rglob("*"))
        if p.is_file() and "__pycache__" not in p.parts and "tests" not in p.parts
    ]


def source_commit() -> str:
    result = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True,
    )
    return result.stdout.strip() or "unknown"


def install(root: Path) -> int:
    dest_root = root / "skills" / SKILL_NAME
    manifest: dict[str, str] = {}
    for src in canon_files():
        rel = src.relative_to(REPO / "skill")
        dest = dest_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
        manifest[str(rel)] = sha256(src)
    stamp = {
        "v": 1, "source_commit": source_commit(),
        "generated": datetime.now(timezone.utc).isoformat(), "files": manifest,
    }
    (dest_root / MANIFEST_NAME).write_text(
        json.dumps(stamp, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    with (dest_root / LEDGER_NAME).open("a", encoding="utf-8") as ledger:
        ledger.write(json.dumps({
            "ts": stamp["generated"], "action": "install",
            "source_commit": stamp["source_commit"], "files": len(manifest),
        }, sort_keys=True) + "\n")
    print(f"deployed {len(manifest)} files @ {stamp['source_commit']} -> {dest_root}")
    return 0


def check(root: Path) -> int:
    dest_root = root / "skills" / SKILL_NAME
    counts = {"OK": 0, "BEHIND": 0, "MISSING": 0, "EXTRA": 0}
    canon = {str(p.relative_to(REPO / "skill")): sha256(p) for p in canon_files()}
    for rel, canon_hash in sorted(canon.items()):
        deployed = dest_root / rel
        if not deployed.is_file():
            counts["MISSING"] += 1
            print(f"{'MISSING':8} {rel}")
        elif sha256(deployed) != canon_hash:
            counts["BEHIND"] += 1
            print(f"{'BEHIND':8} {rel}")
        else:
            counts["OK"] += 1
    if dest_root.is_dir():
        for p in sorted(dest_root.rglob("*")):
            if not p.is_file() or "__pycache__" in p.parts or p.name.endswith(".pyc"):
                continue
            rel = str(p.relative_to(dest_root))
            if rel in canon or rel in (MANIFEST_NAME, LEDGER_NAME):
                continue
            if rel.startswith("tests/"):
                continue  # pre-adoption deployments carried tests; tolerated
            counts["EXTRA"] += 1
            print(f"{'EXTRA':8} {rel}  (not canon-owned; never deleted)")
    verdict = "OK" if not counts["BEHIND"] and not counts["MISSING"] else "FAIL"
    print(f"delegate-learn deployment: ok {counts['OK']} · behind {counts['BEHIND']} · "
          f"missing {counts['MISSING']} · extra {counts['EXTRA']} · {verdict}")
    return 0 if verdict == "OK" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("target", choices=("codex",))
    parser.add_argument("--root", default=str(Path.home() / ".codex"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.root).expanduser()
    return check(root) if args.check else install(root)


if __name__ == "__main__":
    raise SystemExit(main())
