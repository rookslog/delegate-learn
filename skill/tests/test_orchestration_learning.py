from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SKILL_ROOT = Path(__file__).parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "orchestration_learning.py"


class OrchestrationLearningCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.home = self.base / "telemetry"
        self.project = self.base / "project"
        self.project.mkdir()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_cli(
        self,
        *arguments: str,
        input_text: str | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--home", str(self.home), *arguments],
            cwd=self.project,
            input=input_text,
            text=True,
            capture_output=True,
            check=check,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )

    def events(self) -> list[dict[str, object]]:
        path = self.home / "events.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def test_record_route_derives_envelope_project_and_requested_route_defaults(self) -> None:
        self.run_cli(
            "record-route",
            "--run-id", "task-1",
            "--task-class", "bounded-implementation",
            "--closure-target", "reviewed-software-slice",
            "--planned-role", "worker",
            "--planned-model", "gpt-5.6-terra",
            "--planned-effort", "high",
            "--nearest-alternative", "root-local-implementation",
            "--validation-oracle", "focused-and-full-tests",
            "--falsifier-code", "test-failure",
        )

        event = self.events()[0]
        self.assertEqual(event["schema_version"], 1)
        self.assertEqual(event["event_type"], "route_planned")
        self.assertRegex(str(event["event_id"]), r"^[0-9a-f-]{36}$")
        self.assertTrue(str(event["ts"]).endswith("Z"))
        self.assertRegex(str(event["project_id"]), r"^project-[0-9a-f]{16}$")
        self.assertEqual(event["requested_role"], "worker")
        self.assertEqual(event["requested_model"], "gpt-5.6-terra")
        self.assertEqual(event["requested_effort"], "high")
        self.assertNotIn(str(self.project), json.dumps(event))

    def test_record_route_accepts_requested_route_overrides(self) -> None:
        self.run_cli(
            "record-route",
            "--run-id", "task-2",
            "--task-class", "independent-review",
            "--closure-target", "reviewed-software-slice",
            "--planned-role", "reviewer",
            "--planned-model", "gpt-5.6-terra",
            "--planned-effort", "high",
            "--requested-role", "cold-reviewer",
            "--requested-model", "terra-high",
            "--requested-effort", "xhigh",
            "--nearest-alternative", "root-self-review",
            "--validation-oracle", "source-and-tests",
            "--falsifier-code", "reproducible-finding",
            "--write-scope-count", "0",
        )

        event = self.events()[0]
        self.assertEqual(event["requested_role"], "cold-reviewer")
        self.assertEqual(event["requested_model"], "terra-high")
        self.assertEqual(event["requested_effort"], "xhigh")
        self.assertEqual(event["write_scope_count"], 0)

    def test_record_route_does_not_treat_an_empty_override_as_absent(self) -> None:
        result = self.run_cli(
            "record-route",
            "--run-id", "task-empty",
            "--task-class", "independent-review",
            "--closure-target", "reviewed-software-slice",
            "--planned-role", "reviewer",
            "--planned-model", "gpt-5.6-terra",
            "--planned-effort", "high",
            "--requested-role", "",
            "--nearest-alternative", "root-self-review",
            "--validation-oracle", "source-and-tests",
            "--falsifier-code", "reproducible-finding",
            check=False,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("requested_role", result.stderr)

    def test_record_disposition_defaults_lists_and_infers_validator_outcome(self) -> None:
        self.run_cli(
            "record-disposition",
            "--run-id", "task-1",
            "--disposition", "accept-after-revision",
            "--rework-count", "2",
            "--observation-code", "findings-resolved",
            "--friction-code", "validator-gap",
            "--confounder-code", "read-only-reviewer",
        )

        event = self.events()[0]
        self.assertEqual(event["event_type"], "disposition")
        self.assertEqual(event["validator_outcome"], "approved")
        self.assertEqual(event["rework_count"], 2)
        self.assertEqual(event["friction_codes"], ["validator-gap"])
        self.assertEqual(event["confounder_codes"], ["read-only-reviewer"])

    def test_record_disposition_rejects_ambiguous_validator_inference(self) -> None:
        result = self.run_cli(
            "record-disposition",
            "--run-id", "task-3",
            "--disposition", "park",
            "--rework-count", "0",
            "--observation-code", "awaiting-authority",
            check=False,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("validator outcome", result.stderr.lower())
        self.assertFalse((self.home / "events.jsonl").exists())

    def test_raw_record_stdin_remains_compatible(self) -> None:
        project_id = self.run_cli("project-id", "--path", str(self.project)).stdout.strip()
        raw = {
            "event_type": "checkpoint",
            "project_id": project_id,
            "run_id": "task-4",
            "checkpoint_code": "first-validation",
            "checkpoint_outcome": "passed",
        }

        self.run_cli("record", input_text=json.dumps(raw))

        self.assertEqual(self.events()[0]["checkpoint_outcome"], "passed")

    def test_skill_guidance_prefers_short_form_for_recurring_events(self) -> None:
        guidance = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("record-route", guidance)
        self.assertIn("record-disposition", guidance)
        self.assertIn("requested role/model/effort", guidance)


if __name__ == "__main__":
    unittest.main()
