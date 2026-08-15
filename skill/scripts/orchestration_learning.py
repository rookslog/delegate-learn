#!/usr/bin/env python3
"""Record and audit privacy-preserving orchestration learning events."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sys
import tempfile
import time
import uuid


SCHEMA_VERSION = 1
EVENT_TYPES = {
    "route_planned",
    "checkpoint",
    "consultation",
    "disposition",
    "hypothesis",
    "policy_decision",
}
COMMON = {
    "schema_version",
    "event_id",
    "ts",
    "event_type",
    "project_id",
    "run_id",
    "consult_id",
}
ALLOWED = COMMON | {
    "task_class",
    "closure_target",
    "consequence",
    "reversibility",
    "ambiguity",
    "planned_role",
    "planned_model",
    "planned_effort",
    "requested_role",
    "requested_model",
    "requested_effort",
    "observed_role",
    "observed_model",
    "observed_effort",
    "observed_identity_source",
    "nearest_alternative",
    "validation_oracle",
    "falsifier_code",
    "expected_advantage_code",
    "packet_completeness_code",
    "write_scope_count",
    "checkpoint_code",
    "checkpoint_outcome",
    "advice_tier",
    "advice_changed_action",
    "reproducible_counterexample",
    "root_disposition",
    "disposition",
    "validator_outcome",
    "rework_count",
    "friction_codes",
    "confounder_codes",
    "observation_code",
    "elapsed_seconds",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "hypothesis_id",
    "policy_id",
    "decision",
    "corroborating_run_count",
    "rollback_code",
}
REQUIRED = {
    "route_planned": {
        "task_class",
        "closure_target",
        "planned_role",
        "planned_model",
        "planned_effort",
        "requested_role",
        "requested_model",
        "requested_effort",
        "nearest_alternative",
        "validation_oracle",
        "falsifier_code",
    },
    "checkpoint": {"checkpoint_code", "checkpoint_outcome"},
    "consultation": {
        "consult_id",
        "advice_tier",
        "advice_changed_action",
        "reproducible_counterexample",
        "root_disposition",
    },
    "disposition": {
        "disposition",
        "validator_outcome",
        "rework_count",
        "friction_codes",
        "confounder_codes",
        "observation_code",
    },
    "hypothesis": {"hypothesis_id", "decision", "corroborating_run_count"},
    "policy_decision": {
        "policy_id",
        "decision",
        "corroborating_run_count",
        "rollback_code",
    },
}
LIST_FIELDS = {"friction_codes", "confounder_codes"}
BOOL_FIELDS = {"advice_changed_action", "reproducible_counterexample"}
NUMBER_FIELDS = {
    "write_scope_count",
    "rework_count",
    "elapsed_seconds",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "corroborating_run_count",
}
CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+/@-]{0,127}$")
PROJECT_RE = re.compile(r"^project-[0-9a-f]{16}$")
INFERRED_VALIDATOR_OUTCOMES = {
    "accept": "approved",
    "accept-after-revision": "approved",
    "revise": "changes-required",
}


class EventError(ValueError):
    pass


def home_path(raw: str | None) -> Path:
    value = raw or os.environ.get("ORCHESTRATION_LEARNING_HOME")
    return (
        Path(value).expanduser()
        if value
        else Path.home() / ".codex" / "telemetry" / "orchestration-learning"
    )


def ensure_home(home: Path) -> None:
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(home, 0o700)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def validate_code(value: object, field: str) -> None:
    if not isinstance(value, str) or not CODE_RE.fullmatch(value):
        raise EventError(f"{field} must be a bounded operational code")


def validate_event(raw: object, *, fill_defaults: bool = False) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise EventError("event must be a JSON object")
    unknown = set(raw) - ALLOWED
    if unknown:
        raise EventError(f"unknown/content-bearing fields rejected: {sorted(unknown)}")
    event = dict(raw)
    if fill_defaults:
        event.setdefault("schema_version", SCHEMA_VERSION)
        event.setdefault("event_id", str(uuid.uuid4()))
        event.setdefault("ts", utc_now())
    envelope_missing = {"schema_version", "event_id", "ts", "event_type"} - set(event)
    if envelope_missing:
        raise EventError(f"missing envelope fields: {sorted(envelope_missing)}")
    if event.get("schema_version") != SCHEMA_VERSION:
        raise EventError("unsupported schema_version")
    event_type = event.get("event_type")
    if event_type not in EVENT_TYPES:
        raise EventError("unsupported event_type")
    missing = ({"project_id", "run_id"} | REQUIRED[event_type]) - set(event)
    if missing:
        raise EventError(f"missing required fields: {sorted(missing)}")
    if not PROJECT_RE.fullmatch(str(event["project_id"])):
        raise EventError("project_id must come from project-id")
    for field, value in event.items():
        if field in {"schema_version"}:
            continue
        if field in BOOL_FIELDS:
            if type(value) is not bool:
                raise EventError(f"{field} must be boolean")
        elif field in NUMBER_FIELDS:
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or value < 0
            ):
                raise EventError(f"{field} must be non-negative numeric")
        elif field in LIST_FIELDS:
            if (
                not isinstance(value, list)
                or len(value) > 16
                or len(set(value)) != len(value)
            ):
                raise EventError(f"{field} must be a unique list of at most 16 codes")
            for item in value:
                validate_code(item, field)
        elif field == "ts":
            if not isinstance(value, str) or not value.endswith("Z"):
                raise EventError("ts must be UTC ISO-8601")
        else:
            validate_code(value, field)
    return event


def project_id(home: Path, path: str) -> str:
    ensure_home(home)
    salt_path = home / ".project-id-salt"
    if not salt_path.exists():
        fd = os.open(salt_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(secrets.token_bytes(32))
    salt = salt_path.read_bytes()
    digest = hmac.new(
        salt, str(Path(path).expanduser().resolve()).encode(), hashlib.sha256
    ).hexdigest()
    return f"project-{digest[:16]}"


def append_event(home: Path, event: dict[str, object]) -> None:
    ensure_home(home)
    target = home / "events.jsonl"
    lock = home / ".events.lock"
    deadline = time.monotonic() + 5.0
    while True:
        try:
            lock_fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(lock_fd)
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > 30.0:
                    lock.unlink()
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() >= deadline:
                raise EventError("event store lock timed out") from None
            time.sleep(0.02)
    try:
        if target.exists():
            existing_ids = {item["event_id"] for item in read_events(home)}
            if event["event_id"] in existing_ids:
                raise EventError("duplicate event_id")
        fd = os.open(target, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
            )
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        lock.unlink(missing_ok=True)


def read_events(home: Path) -> list[dict[str, object]]:
    target = home / "events.jsonl"
    if not target.exists():
        return []
    events = []
    seen = set()
    for number, line in enumerate(target.read_text(encoding="utf-8").splitlines(), 1):
        try:
            event = validate_event(json.loads(line), fill_defaults=False)
        except (json.JSONDecodeError, EventError) as exc:
            raise EventError(f"line {number}: {exc}") from exc
        if event["event_id"] in seen:
            raise EventError(f"line {number}: duplicate event_id")
        seen.add(event["event_id"])
        events.append(event)
    return events


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def summarize(home: Path) -> dict[str, object]:
    events = read_events(home)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": utc_now(),
        "event_count": len(events),
        "run_count": len({event["run_id"] for event in events}),
        "by_event_type": dict(Counter(str(event["event_type"]) for event in events)),
        "by_disposition": dict(
            Counter(
                str(event["disposition"]) for event in events if "disposition" in event
            )
        ),
        "friction_codes": dict(
            Counter(
                code for event in events for code in event.get("friction_codes", [])
            )
        ),
        "retention_policy": "unset",
    }
    atomic_json(home / "status.json", summary)
    return summary


def _short_event(home: Path, project_path: str | None, event: dict[str, object]) -> dict[str, object]:
    event["project_id"] = project_id(home, project_path or str(Path.cwd()))
    return validate_event(event, fill_defaults=True)


def route_event(home: Path, args: argparse.Namespace) -> dict[str, object]:
    event: dict[str, object] = {
        "event_type": "route_planned",
        "run_id": args.run_id,
        "task_class": args.task_class,
        "closure_target": args.closure_target,
        "planned_role": args.planned_role,
        "planned_model": args.planned_model,
        "planned_effort": args.planned_effort,
        "requested_role": (
            args.requested_role
            if args.requested_role is not None
            else args.planned_role
        ),
        "requested_model": (
            args.requested_model
            if args.requested_model is not None
            else args.planned_model
        ),
        "requested_effort": (
            args.requested_effort
            if args.requested_effort is not None
            else args.planned_effort
        ),
        "nearest_alternative": args.nearest_alternative,
        "validation_oracle": args.validation_oracle,
        "falsifier_code": args.falsifier_code,
    }
    for field in (
        "consequence",
        "reversibility",
        "ambiguity",
        "expected_advantage_code",
        "packet_completeness_code",
        "write_scope_count",
    ):
        value = getattr(args, field)
        if value is not None:
            event[field] = value
    return _short_event(home, args.project_path, event)


def disposition_event(home: Path, args: argparse.Namespace) -> dict[str, object]:
    validator_outcome = args.validator_outcome
    if validator_outcome is None:
        validator_outcome = INFERRED_VALIDATOR_OUTCOMES.get(args.disposition)
    if validator_outcome is None:
        raise EventError(
            "validator outcome cannot be inferred; pass --validator-outcome"
        )
    event: dict[str, object] = {
        "event_type": "disposition",
        "run_id": args.run_id,
        "disposition": args.disposition,
        "validator_outcome": validator_outcome,
        "rework_count": args.rework_count,
        "friction_codes": args.friction_code,
        "confounder_codes": args.confounder_code,
        "observation_code": args.observation_code,
    }
    for field in (
        "observed_role",
        "observed_model",
        "observed_effort",
        "observed_identity_source",
        "elapsed_seconds",
        "input_tokens",
        "output_tokens",
        "total_tokens",
    ):
        value = getattr(args, field)
        if value is not None:
            event[field] = value
    return _short_event(home, args.project_path, event)


def _add_project_path(command: argparse.ArgumentParser) -> None:
    command.add_argument(
        "--project-path",
        help="project path used only to derive project_id; defaults to cwd",
    )


def _add_optional_route_fields(command: argparse.ArgumentParser) -> None:
    command.add_argument("--consequence")
    command.add_argument("--reversibility")
    command.add_argument("--ambiguity")
    command.add_argument("--expected-advantage-code")
    command.add_argument("--packet-completeness-code")
    command.add_argument("--write-scope-count", type=int)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--home")
    commands = result.add_subparsers(dest="command", required=True)
    project = commands.add_parser("project-id")
    project.add_argument("--path", required=True)
    record = commands.add_parser("record")
    record.add_argument("--file", help="read safe JSON from file; defaults to stdin")
    route = commands.add_parser("record-route")
    _add_project_path(route)
    route.add_argument("--run-id", required=True)
    route.add_argument("--task-class", required=True)
    route.add_argument("--closure-target", required=True)
    route.add_argument("--planned-role", required=True)
    route.add_argument("--planned-model", required=True)
    route.add_argument("--planned-effort", required=True)
    route.add_argument("--requested-role")
    route.add_argument("--requested-model")
    route.add_argument("--requested-effort")
    route.add_argument("--nearest-alternative", required=True)
    route.add_argument("--validation-oracle", required=True)
    route.add_argument("--falsifier-code", required=True)
    _add_optional_route_fields(route)
    disposition = commands.add_parser("record-disposition")
    _add_project_path(disposition)
    disposition.add_argument("--run-id", required=True)
    disposition.add_argument("--disposition", required=True)
    disposition.add_argument("--validator-outcome")
    disposition.add_argument("--rework-count", required=True, type=int)
    disposition.add_argument("--friction-code", action="append", default=[])
    disposition.add_argument("--confounder-code", action="append", default=[])
    disposition.add_argument("--observation-code", required=True)
    disposition.add_argument("--observed-role")
    disposition.add_argument("--observed-model")
    disposition.add_argument("--observed-effort")
    disposition.add_argument("--observed-identity-source")
    disposition.add_argument("--elapsed-seconds", type=float)
    disposition.add_argument("--input-tokens", type=int)
    disposition.add_argument("--output-tokens", type=int)
    disposition.add_argument("--total-tokens", type=int)
    commands.add_parser("audit")
    commands.add_parser("summarize")
    return result


def main() -> int:
    args = parser().parse_args()
    home = home_path(args.home)
    try:
        if args.command == "project-id":
            print(project_id(home, args.path))
        elif args.command == "record":
            source = (
                Path(args.file).read_text(encoding="utf-8")
                if args.file
                else sys.stdin.read()
            )
            event = validate_event(json.loads(source), fill_defaults=True)
            append_event(home, event)
            print(event["event_id"])
        elif args.command == "record-route":
            event = route_event(home, args)
            append_event(home, event)
            print(event["event_id"])
        elif args.command == "record-disposition":
            event = disposition_event(home, args)
            append_event(home, event)
            print(event["event_id"])
        elif args.command == "audit":
            events = read_events(home)
            print(json.dumps({"status": "ok", "events": len(events)}))
        elif args.command == "summarize":
            print(json.dumps(summarize(home), sort_keys=True))
    except (OSError, json.JSONDecodeError, EventError) as exc:
        print(f"delegate-learn: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
