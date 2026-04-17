import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "agentdojo" / "src"))
sys.path.insert(0, str(REPO_ROOT / "clean" / "bench" / "src"))

from mlld import Client
from agentdojo.default_suites.v1.tools.calendar_client import create_calendar_event
from agentdojo.default_suites.v1.tools.email_client import EmailContact
from agentdojo.runner import _normalize_post_environment_for_grading
from date_shift import get_shifted_suite
from host import _build_local_mcp_command
from mcp_server import _sync_runtime_state


class HostStateNormalizationTests(unittest.TestCase):
    def _roundtripped_workspace_lunch_state(self):
        suite = get_shifted_suite("v1.1.1", "workspace")
        task = suite.get_user_task_by_id("user_task_6")
        pre_env = task.init_environment(suite.load_and_inject_default_environment({}))

        post_env = pre_env.model_copy(deep=True)
        create_calendar_event(
            post_env.calendar,
            post_env.inbox,
            "Lunch",
            "2026-04-20 12:00",
            "2026-04-20 13:00",
            "Catch up over lunch.",
            ["sarah.connor@gmail.com"],
            None,
        )

        # Mirror the MCP server round-trip that benchmarks grade against.
        _sync_runtime_state(post_env)
        roundtripped = type(post_env).model_validate_json(post_env.model_dump_json())
        return task, pre_env, roundtripped

    def test_strip_benign_contact_addition_restores_task_utility(self):
        task, pre_env, post_env = self._roundtripped_workspace_lunch_state()

        self.assertFalse(task.utility("", pre_env, post_env))
        post_env = _normalize_post_environment_for_grading("workspace", pre_env, post_env)
        self.assertTrue(task.utility("", pre_env, post_env))

    def test_strip_benign_contact_addition_keeps_unrelated_contact_mutations(self):
        _task, pre_env, post_env = self._roundtripped_workspace_lunch_state()
        post_env.inbox.contact_list.append(
            EmailContact(email="extra.person@example.com", name="Extra Person")
        )

        post_env = _normalize_post_environment_for_grading("workspace", pre_env, post_env)
        contact_emails = {contact.email for contact in post_env.inbox.contact_list}
        self.assertNotIn("sarah.connor@gmail.com", contact_emails)
        self.assertIn("extra.person@example.com", contact_emails)


class HostMcpToolDispatchTests(unittest.TestCase):
    def test_workspace_mcp_reads_keep_arg_metadata_through_dispatch(self):
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".mld",
            dir=REPO_ROOT / "clean" / "bench",
            delete=False,
        ) as tmp:
            tmp.write(
                """
import { @tools } from "./domains/workspace/tools.mld"
import { @callTool } from "../rig/runtime.mld"

var @searchFileParamNames = for @p in (@tools.search_files_by_filename.mlld.mx.params ?? []) => @p.name ?? @p
var @dayParamNames = for @p in (@tools.get_day_calendar_events.mlld.mx.params ?? []) => @p.name ?? @p

=> {
  search_file: {
    param_names: @searchFileParamNames,
    direct_result: @tools.search_files_by_filename("team-building-activities.docx"),
    call_tool_result: @callTool(@tools.search_files_by_filename, @tools, "search_files_by_filename", { filename: "team-building-activities.docx" }, null)
  },
  get_day: {
    param_names: @dayParamNames,
    direct_result: @tools.get_day_calendar_events("April 27th"),
    call_tool_result: @callTool(@tools.get_day_calendar_events, @tools, "get_day_calendar_events", { day: "April 27th" }, null)
  }
}
""".strip()
            )
            script_path = tmp.name

        try:
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as state_tmp, tempfile.NamedTemporaryFile(
                suffix=".jsonl", delete=False
            ) as log_tmp, tempfile.NamedTemporaryFile(suffix=".json", delete=False) as phase_state_tmp:
                mcp_command = _build_local_mcp_command(
                    {
                        "env_name": "workspace",
                        "suite_name": "workspace",
                        "benchmark_version": "v1.1.1",
                        "task_id": "user_task_0",
                        "state_file": state_tmp.name,
                        "log_file": log_tmp.name,
                        "phase_state_file": phase_state_tmp.name,
                    }
                )

                client = Client(timeout=120000, working_dir=str(REPO_ROOT / "clean" / "bench"))
                result = client.execute(
                    script_path,
                    {},
                    mcp_servers={"tools": mcp_command},
                )

            payload = json.loads(result.output)
            self.assertEqual(payload["search_file"]["param_names"], ["filename"])
            self.assertEqual(payload["get_day"]["param_names"], ["day"])
            self.assertGreaterEqual(len(payload["search_file"]["direct_result"]), 1)
            self.assertGreaterEqual(len(payload["search_file"]["call_tool_result"]), 1)
            self.assertEqual(
                payload["search_file"]["direct_result"][0]["filename"],
                "team-building-activities.docx",
            )
            self.assertEqual(
                payload["search_file"]["call_tool_result"][0]["filename"],
                "team-building-activities.docx",
            )
            self.assertGreaterEqual(len(payload["get_day"]["direct_result"]), 1)
            self.assertGreaterEqual(len(payload["get_day"]["call_tool_result"]), 1)
            self.assertEqual(
                payload["get_day"]["direct_result"][0]["title"],
                "Networking Event",
            )
            self.assertEqual(
                payload["get_day"]["call_tool_result"][0]["title"],
                "Networking Event",
            )
        finally:
            Path(script_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
