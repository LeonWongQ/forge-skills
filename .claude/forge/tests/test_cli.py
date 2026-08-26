# -*- coding: utf-8 -*-
"""CLI command-layer tests for forge_cli.cli."""

import json
from pathlib import Path

from click.testing import CliRunner

from forge_cli.cli import cli


class TestCliVersion:
    def test_version_text_renders_project_name_and_version(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--root", str(populated_forge_root), "version"],
        )
        assert result.exit_code == 0
        assert result.output.strip() == "forge 1.1.1"

    def test_version_json_returns_project_metadata(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--root", str(populated_forge_root), "--format", "json", "version"],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["name"] == "forge"
        assert payload["version"] == "1.1.1"


class TestCliCompose:
    def test_compose_with_valid_skill(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--root", str(populated_forge_root), "compose", "--skill", "code-review"],
        )
        assert result.exit_code == 0
        assert "Compose: OK" in result.output
        assert "Skill: skill.code_review" in result.output

    def test_compose_warns_on_unknown_skill(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--root", str(populated_forge_root), "compose", "--skill", "nonexistent"],
        )
        assert result.exit_code == 0
        assert "Warnings:" in result.output
        assert "Requested skill not found: nonexistent" in result.output

    def test_compose_warns_on_unknown_pack(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--root", str(populated_forge_root), "compose", "--pack", "nonexistent"],
        )
        assert result.exit_code == 0
        assert "Warnings:" in result.output
        assert "Requested pack not found: nonexistent" in result.output

    def test_compose_json_includes_selection_and_sources(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--root",
                str(populated_forge_root),
                "--format",
                "json",
                "compose",
                "--skill",
                "code-review",
                "--domain",
                "domain.spring",
            ],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["mode"] == "compose"
        assert payload["matched"] is True
        assert payload["skill"] == "skill.code_review"
        assert "domain.java" in payload["domains"]
        assert "domain.spring" in payload["domains"]
        assert payload["sources"]["domains"] == "skill+cli"

    def test_compose_json_includes_unresolved_warning_metadata(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--root", str(populated_forge_root), "--format", "json", "compose", "--skill", "nonexistent"],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["warnings"]
        assert payload["unresolved"]["skill"] == "nonexistent"
        assert payload["skill"] is None


class TestRealRegistryCliSmoke:
    def test_route_json_uses_real_registry(self):
        real_forge_root = Path(__file__).resolve().parents[1]
        result = CliRunner().invoke(
            cli,
            [
                "--root",
                str(real_forge_root),
                "--format",
                "json",
                "route",
                "帮我 review 一个 spring service 改动",
            ],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["matched"] is True
        assert payload["skill"]["id"] == "skill.code_review"
        assert payload["pack"]["id"] == "pack.spring_review"

    def test_recommend_json_uses_real_registry(self):
        real_forge_root = Path(__file__).resolve().parents[1]
        result = CliRunner().invoke(
            cli,
            [
                "--root",
                str(real_forge_root),
                "--format",
                "json",
                "recommend",
                "生成测试报告",
            ],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["mode"] == "recommend"
        assert payload["matched"] is True
        assert payload["recommended"]["skill"] == "skill.report"
        assert payload["recommended"]["pack"] == "pack.general_test_report"


class TestCliRouting:
    def test_route_review_query_succeeds(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--root", str(populated_forge_root), "route", "帮我", "review"],
        )
        assert result.exit_code == 0
        assert "Route: MATCHED" in result.output
        assert "skill.code_review" in result.output

    def test_route_json_includes_candidates_and_pack(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--root",
                str(populated_forge_root),
                "--format",
                "json",
                "route",
                "review",
                "spring",
                "service",
            ],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["matched"] is True
        assert payload["skill"]["id"] == "skill.code_review"
        assert payload["pack"]["id"] == "pack.test_pack"
        assert "candidates" in payload
        assert "strategy" in payload

    def test_route_json_unmatched_returns_reason(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--root", str(populated_forge_root), "--format", "json", "route", "xyzzy", "nothing"],
        )
        assert result.exit_code != 0
        payload = json.loads(result.output)
        assert payload["matched"] is False
        assert payload["confidence"] == "low"
        assert payload["reason"]
        assert payload["skill"] is None

    def test_route_prefer_fallback_returns_match(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--root",
                str(populated_forge_root),
                "--format",
                "json",
                "route",
                "--prefer",
                "code-review",
                "xyzzy",
                "nothing",
            ],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["matched"] is True
        assert payload["skill"]["id"] == "skill.code_review"
        assert payload["confidence"] == "low"
        assert payload["confidence_diagnostics"]["selection_mode"] == "prefer_fallback"
        assert payload["confidence_diagnostics"]["caps"] == ["fallback"]
        assert payload["matched_triggers"] == ["--prefer code-review"]

    def test_route_invalid_prefer_keeps_unmatched(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--root",
                str(populated_forge_root),
                "--format",
                "json",
                "route",
                "--prefer",
                "nonexistent",
                "xyzzy",
                "nothing",
            ],
        )
        assert result.exit_code != 0
        payload = json.loads(result.output)
        assert payload["matched"] is False
        assert payload["skill"] is None

    def test_recommend_review_query_succeeds(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--root", str(populated_forge_root), "recommend", "review", "spring", "service"],
        )
        assert result.exit_code == 0
        assert "Recommend: OK" in result.output
        assert "Skill: skill.code_review" in result.output

    def test_recommend_json_includes_recommended_modules(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--root",
                str(populated_forge_root),
                "--format",
                "json",
                "recommend",
                "review",
                "spring",
                "service",
            ],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["mode"] == "recommend"
        assert payload["matched"] is True
        assert payload["recommended"]["skill"] == "skill.code_review"
        assert payload["recommended"]["pack"] == "pack.test_pack"
        assert "domain.java" in payload["recommended"]["domains"]

    def test_recommend_json_unmatched_returns_null_recommendation(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--root", str(populated_forge_root), "--format", "json", "recommend", "xyzzy", "nothing"],
        )
        assert result.exit_code != 0
        payload = json.loads(result.output)
        assert payload["mode"] == "recommend"
        assert payload["matched"] is False
        assert payload["recommended"] is None
        assert payload["reason"]

    def test_recommend_prefer_fallback_returns_recommendation(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--root",
                str(populated_forge_root),
                "--format",
                "json",
                "recommend",
                "--prefer",
                "code-review",
                "xyzzy",
                "nothing",
            ],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["matched"] is True
        assert payload["recommended"]["skill"] == "skill.code_review"
        assert payload["confidence"] == "low"
        assert payload["confidence_diagnostics"]["selection_mode"] == "prefer_fallback"


class TestCliStatus:
    def test_status_json_counts_present(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--root", str(populated_forge_root), "--format", "json", "status"],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["project"]["source"] == "registry/project.json"
        assert "skills" in payload
        assert "packs" in payload
        assert "workflows" in payload

    def test_status_json_reports_semantic_fields(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--root", str(populated_forge_root), "--format", "json", "status"],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["project"]["name"] == "forge"
        assert payload["project"]["version"] == "1.1.1"
        assert payload["registry_files"] >= 1
        assert payload["schema_files"] >= 1
        assert payload["registered_modules"] >= 1
        assert isinstance(payload["quick_path_check_passed"], bool)
        assert isinstance(payload["missing_paths"], int)

    def test_status_text_reports_summary_lines(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--root", str(populated_forge_root), "status"],
        )
        assert result.exit_code == 0
        assert "forge 1.1.1" in result.output
        assert "Root:" in result.output

    def test_status_explain_root_keeps_link_target_hidden(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(cli, ["--root", str(populated_forge_root), "status", "--explain-root"])

        assert result.exit_code == 0
        assert "Root diagnostic:" in result.output
        assert f"Logical root: {populated_forge_root}" in result.output
        assert "Link target: intentionally not resolved or reported" in result.output
        assert "Registry files:" in result.output
        assert "Schema files:" in result.output
        assert "Quick path check:" in result.output
        assert "Missing paths:" in result.output


class TestCliShow:
    def test_show_skill_renders_registry_fields(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--root", str(populated_forge_root), "show", "skill", "code-review"],
        )
        assert result.exit_code == 0
        assert "id: skill.code_review" in result.output
        assert "name: code-review" in result.output
        assert "behavior: behavior.review" in result.output

    def test_show_missing_item_returns_error(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--root", str(populated_forge_root), "show", "skill", "nonexistent"],
        )
        assert result.exit_code != 0
        assert "Item not found: type=skill, query=nonexistent" in result.output


class TestCliList:
    def test_list_skills_renders_known_item(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--root", str(populated_forge_root), "list", "skills"],
        )
        assert result.exit_code == 0
        assert "skill.code_review" in result.output
        assert "code-review" in result.output


class TestCliValidate:
    def test_validate_quick_reports_failure_for_incomplete_fixture(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--root", str(populated_forge_root), "validate", "--quick"],
        )
        assert result.exit_code != 0
        assert "Command: validate" in result.output
        assert "Summary:" in result.output
        assert "FAIL" in result.output

    def test_validate_quick_writes_report_file(self, populated_forge_root, tmp_path):
        runner = CliRunner()
        report_path = tmp_path / "validate-report.json"
        result = runner.invoke(
            cli,
            ["--root", str(populated_forge_root), "validate", "--quick", "--report", str(report_path)],
        )
        assert result.exit_code != 0
        assert report_path.exists()
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        assert payload["command"] == "validate"
        assert payload["root"] == str(populated_forge_root)
        assert "checks" in payload
        assert "summary" in payload
        assert payload["summary"]["ok"] is False

    def test_validate_rejects_quick_with_check(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--root", str(populated_forge_root), "validate", "--quick", "--check", "paths"],
        )
        assert result.exit_code != 0
        assert "Error: --quick cannot be used together with --check" in result.output


class TestCliDoctor:
    def test_doctor_json_reports_failure_for_incomplete_fixture(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--root", str(populated_forge_root), "--format", "json", "doctor"],
        )
        assert result.exit_code != 0
        payload = json.loads(result.output)
        assert payload["command"] == "doctor"
        assert "summary" in payload
        assert "checks" in payload
        assert payload["summary"]["ok"] is False

    def test_doctor_writes_report_file(self, populated_forge_root, tmp_path):
        runner = CliRunner()
        report_path = tmp_path / "doctor-report.json"
        result = runner.invoke(
            cli,
            ["--root", str(populated_forge_root), "doctor", "--report", str(report_path)],
        )
        assert result.exit_code != 0
        assert report_path.exists()
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        assert payload["command"] == "doctor"
        assert payload["root"] == str(populated_forge_root)
        assert "checks" in payload
        assert "summary" in payload


class TestCliAsk:
    def test_ask_json_includes_mode_and_input(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--root", str(populated_forge_root), "--format", "json", "ask", "review", "spring", "service"],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["mode"] == "ask"
        assert payload["decision"] == "forge_route"
        assert payload["execution"] == "not_executed"
        assert payload["matched"] is True
        assert payload["recommended"]["skill"] == "skill.code_review"

    def test_ask_json_unmatched_returns_null_recommendation(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--root", str(populated_forge_root), "--format", "json", "ask", "xyzzy", "nothing"],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["mode"] == "ask"
        assert payload["decision"] == "native_fallback"
        assert payload["host_action"] == "use_native_claude"
        assert payload["matched"] is False
        assert payload["recommended"] is None
        assert payload["reason"]

    def test_ask_text_unmatched_explains_native_handoff(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(cli, ["--root", str(populated_forge_root), "ask", "xyzzy", "nothing"])

        assert result.exit_code == 0
        assert "no Forge route matched" in result.output
        assert "native assistant" in result.output
        assert "not executed" in result.output

    def test_ask_explicit_skill_is_host_passthrough(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--root", str(populated_forge_root), "--format", "json", "ask", "/review", "spring", "service"],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["decision"] == "explicit_skill_passthrough"
        assert payload["host_action"] == "use_native_claude"
        assert payload["execution"] == "not_executed"
        assert payload["recommended"] is None
        assert payload["reason"]["code"] == "explicit_skill"

    def test_ask_native_specialist_wins_for_github_pr(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--root", str(populated_forge_root), "--format", "json", "ask", "review", "this", "pull", "request"],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["decision"] == "native_route"
        assert payload["native"]["id"] == "native.review"
        assert payload["recommended"] is None
        assert payload["execution"] == "not_executed"

    def test_ask_every_endpoint_does_not_route_to_native_loop(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--root", str(populated_forge_root), "--format", "json", "ask", "write", "tests", "for", "every", "endpoint"],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["decision"] != "native_route"
        assert (payload.get("native") or {}).get("id") != "native.loop"

    def test_ask_mcp_routes_to_native_claude_api(self, populated_forge_root):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--root", str(populated_forge_root), "--format", "json", "ask", "help", "me", "build", "an", "MCP", "server"],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["decision"] == "native_route"
        assert payload["native"]["id"] == "native.claude_api"


        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--root", str(populated_forge_root), "--format", "json", "ask", "review", "spring", "service"],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["decision"] == "forge_route"
        assert payload["recommended"]["skill"] == "skill.code_review"


        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--root",
                str(populated_forge_root),
                "--format",
                "json",
                "ask",
                "--prefer",
                "code-review",
                "xyzzy",
                "nothing",
            ],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["mode"] == "ask"
        assert payload["matched"] is True
        assert payload["recommended"]["skill"] == "skill.code_review"
        assert payload["input"] == "xyzzy nothing"
