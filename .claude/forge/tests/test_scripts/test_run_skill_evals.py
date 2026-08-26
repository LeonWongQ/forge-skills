# -*- coding: utf-8 -*-
"""Tests for disposable skill evaluation fixtures and selection."""

import importlib.util
import os
import sys
import json
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "run-skill-evals.py"
SPEC = importlib.util.spec_from_file_location("run_skill_evals", SCRIPT_PATH)
run_skill_evals = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(run_skill_evals)


def test_all_declared_fixtures_build_inside_disposable_root(tmp_path):
    for name, builder in run_skill_evals.FIXTURES.items():
        root = tmp_path / name
        root.mkdir()
        substitutions = builder(root)

        assert any(root.rglob("*"))
        assert all(path.is_relative_to(root) for path in root.rglob("*"))
        assert isinstance(substitutions, dict)


def test_default_selection_excludes_environment_gated_cases():
    cases = run_skill_evals.load_cases()

    selected = run_skill_evals.select_cases(cases, [], include_gated=False)

    assert selected
    assert all(case["execution"]["mode"] == "automated" for case in selected)
    assert len(selected) == len(cases) - 1


def test_explicit_unknown_case_is_rejected():
    with pytest.raises(ValueError, match="unknown case id"):
        run_skill_evals.select_cases(run_skill_evals.load_cases(), ["missing"], False)


def test_explicit_gated_case_requires_opt_in():
    cases = run_skill_evals.load_cases()
    gated = next(case for case in cases if case["execution"]["mode"] == "environment_gated")

    with pytest.raises(ValueError, match="require --include-gated"):
        run_skill_evals.select_cases(cases, [gated["id"]], False)


def test_claude_filters_browser_case_without_treating_it_as_failure():
    cases = run_skill_evals.select_cases(run_skill_evals.load_cases(), [], False)

    runnable, excluded = run_skill_evals.classify_cases_for_backend(cases, "claude")

    assert "skill-eval.page-test.extract-content" not in {case["id"] for case in runnable}
    browser = next(result for result in excluded if result["case_id"] == "skill-eval.page-test.extract-content")
    assert browser["status"] == "unsupported_backend"
    assert browser["missing_capabilities"] == ["browser", "shell"]


def test_environment_gate_is_recorded_when_host_condition_is_not_satisfied(monkeypatch):
    cases = run_skill_evals.select_cases(run_skill_evals.load_cases(), [], True)
    monkeypatch.setattr(run_skill_evals, "supported_browser_available", lambda: True)

    runnable, excluded = run_skill_evals.classify_cases_for_backend(cases, "codex")

    gated = next(result for result in excluded if result["case_id"] == "skill-eval.page-test.browser-missing")
    assert gated["status"] == "environment_gated_not_run"
    assert gated["reason"] == "host condition not satisfied: no_supported_browser"
    assert gated["case_id"] not in {case["id"] for case in runnable}


def test_environment_gated_case_runs_when_host_condition_is_satisfied(monkeypatch):
    cases = run_skill_evals.select_cases(run_skill_evals.load_cases(), [], True)
    monkeypatch.setattr(run_skill_evals, "supported_browser_available", lambda: False)

    runnable, excluded = run_skill_evals.classify_cases_for_backend(cases, "claude")

    assert "skill-eval.page-test.browser-missing" in {case["id"] for case in runnable}
    assert "skill-eval.page-test.browser-missing" not in {result["case_id"] for result in excluded}


def test_read_only_fixture_snapshot_detects_changes(tmp_path):
    (tmp_path / "one.txt").write_text("before", encoding="utf-8")
    before = run_skill_evals.snapshot(tmp_path)
    (tmp_path / "one.txt").write_text("after", encoding="utf-8")
    (tmp_path / "two.txt").write_text("new", encoding="utf-8")
    after = run_skill_evals.snapshot(tmp_path)

    changed = sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))
    assert changed == ["one.txt", "two.txt"]


def test_prepare_case_writes_prompt_without_rubric(tmp_path):
    case = next(case for case in run_skill_evals.load_cases() if case["execution"]["fixture"] == "empty")

    prepared = run_skill_evals.prepare_case(case, tmp_path)
    prompt = Path(prepared["prompt"]).read_text(encoding="utf-8")

    assert f"Use ${case['skill']}" in prompt
    assert "Inspect the relevant fixture files before responding" in prompt
    assert "hard_requirements" not in prompt
    assert "forbidden_behaviors" not in prompt
    assert (tmp_path / case["id"] / "fixture" / ".claude" / "skills" / case["skill"] / "SKILL.md").is_file()
    assert str(tmp_path / case["id"] / "fixture" / ".claude" / "skills") in prompt


def test_stage_skill_copies_only_selected_skill_into_fixture(tmp_path):
    case = run_skill_evals.load_cases()[0]

    target = run_skill_evals.stage_skill(case, tmp_path)

    assert target.read_bytes() == (run_skill_evals.TOOL_ROOT / "skills" / case["skill"] / "SKILL.md").read_bytes()
    assert list((tmp_path / ".claude" / "skills").rglob("SKILL.md")) == [target]
    assert (tmp_path / ".claude" / "forge" / "CLAUDE.md").is_file()
    assert not (tmp_path / ".claude" / "forge" / "evals").exists()


def test_stage_skill_includes_references_but_excludes_agents_and_node_modules(tmp_path):
    case = next(case for case in run_skill_evals.load_cases() if case["skill"] == "debug")

    run_skill_evals.stage_skill(case, tmp_path)

    skill_root = tmp_path / ".claude" / "skills" / "debug"
    assert (skill_root / "references" / "hypothesis-checklist.md").is_file()
    assert not (skill_root / "agents").exists()
    assert not (skill_root / "node_modules").exists()


def test_stage_browser_case_includes_existing_playwright_runtime_only(tmp_path):
    case = next(case for case in run_skill_evals.load_cases() if "browser" in case["execution"]["requires_capabilities"])

    run_skill_evals.stage_skill(case, tmp_path)

    skill_root = tmp_path / ".claude" / "skills" / case["skill"]
    assert (skill_root / "node_modules" / "playwright-core" / "index.js").is_file()
    assert not (skill_root / "node_modules" / ".package-lock.json").exists()


def test_stage_browser_case_fails_closed_when_runtime_is_missing(tmp_path, monkeypatch):
    case = next(case for case in run_skill_evals.load_cases() if "browser" in case["execution"]["requires_capabilities"])
    original_root = run_skill_evals.TOOL_ROOT
    fake_root = tmp_path / "tool"
    source = fake_root / "skills" / case["skill"]
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("# Page Test\n", encoding="utf-8")
    forge = fake_root / "forge"
    forge.mkdir()
    for name in ("CLAUDE.md", "AUTOLOAD.md"):
        (forge / name).write_text("# Guidance\n", encoding="utf-8")
    for directory in ("behaviors", "domains", "templates", "checklists"):
        (forge / directory).mkdir()
    monkeypatch.setattr(run_skill_evals, "TOOL_ROOT", fake_root)
    monkeypatch.setattr(run_skill_evals, "FORGE_ROOT", forge)

    with pytest.raises(ValueError, match="existing skill-owned playwright-core"):
        run_skill_evals.stage_skill(case, tmp_path / "fixture")

    monkeypatch.setattr(run_skill_evals, "TOOL_ROOT", original_root)


@pytest.mark.parametrize("message", [
    "ERROR: Missing environment variable: CODEX_RELAY_API_KEY",
    "HTTP 403: Forbidden",
    "Authentication required: not logged in",
])
def test_backend_failures_are_classified_separately(message):
    assert run_skill_evals.classify_execution_status(1, "", message) == "backend_unavailable"


def test_other_nonzero_exit_is_a_runner_error():
    assert run_skill_evals.classify_execution_status(1, "", "unexpected CLI failure") == "runner_error"


def test_decision_template_matches_each_case_rubric():
    cases = run_skill_evals.load_cases()[:2]

    template = run_skill_evals.decision_template(cases)

    assert len(template["scores"]) == 2
    assert len(template["scores"][0]["hard_requirements"]) == len(cases[0]["hard_requirements"])
    assert len(template["scores"][0]["forbidden_behaviors"]) == len(cases[0]["forbidden_behaviors"])


def test_preflight_fails_when_codex_command_is_missing():
    ok, messages = run_skill_evals.preflight("codex", "definitely-missing-codex-command", False)

    assert not ok
    assert "unavailable" in messages[0]


def test_preflight_checks_declared_env_key_without_exposing_value(tmp_path, monkeypatch):
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text(
        'model_provider = "test"\n[model_providers.test]\nenv_key = "FORGE_TEST_API_KEY"\n',
        encoding="utf-8",
    )
    fake_codex = tmp_path / "codex.exe"
    fake_codex.write_text("", encoding="utf-8")
    (tmp_path / "codex-windows-sandbox-setup.exe").write_text("", encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("FORGE_TEST_API_KEY", "super-secret-value")
    monkeypatch.setattr(
        run_skill_evals.subprocess,
        "run",
        lambda *args, **kwargs: run_skill_evals.subprocess.CompletedProcess(
            args[0],
            0,
            "codex-cli test\n",
            "",
        ),
    )

    ok, messages = run_skill_evals.preflight("codex", str(fake_codex), False)

    assert ok
    assert "FORGE_TEST_API_KEY" in " ".join(messages)
    assert os.environ["FORGE_TEST_API_KEY"] not in " ".join(messages)


def test_main_reports_selection_error_without_traceback(capsys):
    with pytest.raises(SystemExit, match="error: unknown case id"):
        run_skill_evals.main(["--case", "missing", "--prepare", "unused"])

    assert "Traceback" not in capsys.readouterr().err


def test_execution_requires_explicit_backend(tmp_path):
    with pytest.raises(SystemExit, match="user-selected --backend"):
        run_skill_evals.main(["--output", str(tmp_path / "run"), "--confirm-llm-evaluation"])


def test_execution_requires_explicit_user_acknowledgement(tmp_path):
    with pytest.raises(SystemExit, match="explicit user acknowledgement"):
        run_skill_evals.main(["--output", str(tmp_path / "run"), "--backend", "claude"])


def test_claude_execution_requires_unisolated_filesystem_acknowledgement(tmp_path):
    with pytest.raises(SystemExit, match="no OS-level read isolation"):
        run_skill_evals.main([
            "--output",
            str(tmp_path / "run"),
            "--backend",
            "claude",
            "--confirm-llm-evaluation",
        ])


def test_prepare_rejects_backend_options(tmp_path):
    with pytest.raises(SystemExit, match="does not use an LLM backend"):
        run_skill_evals.main(["--prepare", str(tmp_path / "prepared"), "--backend", "claude"])


def test_preflight_requires_explicit_backend():
    with pytest.raises(SystemExit, match="requires explicit --backend"):
        run_skill_evals.main(["--preflight"])


def test_claude_read_only_command_disables_write_tools(tmp_path):
    case = next(case for case in run_skill_evals.load_cases() if case["execution"]["sandbox"] == "read-only")

    command = run_skill_evals.build_backend_command(
        "claude", "claude", case, tmp_path, tmp_path / "response.md", "prompt", None, False
    )

    assert "--tools=Read,Glob,Grep" in command
    assert "--allowedTools=Read,Glob,Grep" in command
    assert "--append-system-prompt-file" in command
    assert "--no-session-persistence" in command
    assert "--permission-mode" in command
    assert command[command.index("--permission-mode") + 1] == "dontAsk"


def test_claude_tools_option_cannot_consume_prompt(tmp_path):
    case = next(case for case in run_skill_evals.load_cases() if case["execution"]["sandbox"] == "workspace-write")

    command = run_skill_evals.build_backend_command(
        "claude", "claude", case, tmp_path, tmp_path / "response.md", "the prompt", None, False
    )

    assert "--tools=Read,Glob,Grep,Edit,Write" in command
    assert "--allowedTools=Read,Glob,Grep,Edit,Write" in command
    assert command[command.index("--permission-mode") + 1] == "acceptEdits"
    assert command[-1] == "the prompt"


def test_codex_command_preserves_native_sandbox(tmp_path):
    case = next(case for case in run_skill_evals.load_cases() if case["execution"]["sandbox"] == "workspace-write")

    command = run_skill_evals.build_backend_command(
        "codex", "codex", case, tmp_path, tmp_path / "response.md", "prompt", None, False
    )

    assert command[command.index("--sandbox") + 1] == "workspace-write"
    assert "--ephemeral" in command


def test_cursor_preflight_fails_closed_when_command_exists(tmp_path):
    fake_cursor = tmp_path / "cursor-agent.exe"
    fake_cursor.write_text("", encoding="utf-8")

    ok, messages = run_skill_evals.preflight("cursor", str(fake_cursor), False)

    assert not ok
    assert "unsupported" in " ".join(messages)


def test_claude_resolves_native_windows_binary_from_cmd_install(tmp_path, monkeypatch):
    shim = tmp_path / "claude.cmd"
    shim.write_text("", encoding="utf-8")
    native = tmp_path / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    native.parent.mkdir(parents=True)
    native.write_text("", encoding="utf-8")
    monkeypatch.setattr(run_skill_evals.os, "name", "nt")
    monkeypatch.setattr(run_skill_evals.shutil, "which", lambda command: str(shim) if command == "claude" else None)

    assert run_skill_evals.resolve_backend_command("claude") == str(native)


def test_non_codex_backend_rejects_codex_config_flag(tmp_path):
    with pytest.raises(SystemExit, match="only by the Codex backend"):
        run_skill_evals.main([
            "--output",
            str(tmp_path / "run"),
            "--backend",
            "claude",
            "--confirm-llm-evaluation",
            "--ignore-user-config",
        ])


def test_run_case_starts_backend_inside_disposable_fixture(tmp_path, monkeypatch):
    case = next(case for case in run_skill_evals.load_cases() if case["execution"]["sandbox"] == "read-only")
    observed = {}

    class CompletedProcess:
        returncode = 0

        def communicate(self, timeout=None):
            return "response", ""

        def poll(self):
            return self.returncode

    def fake_popen(command, **kwargs):
        observed["cwd"] = kwargs["cwd"]
        return CompletedProcess()

    monkeypatch.setattr(run_skill_evals.subprocess, "Popen", fake_popen)
    result = run_skill_evals.run_case(
        case,
        tmp_path / "output",
        "claude",
        sys.executable,
        None,
    )

    assert observed["cwd"].name.startswith("forge-skill-eval-")
    assert observed["cwd"].parent == tmp_path / "output" / ".fixtures"
    assert result["status"] == "completed_unscored"


def test_codex_usage_parser_accepts_backend_reported_total():
    usage = run_skill_evals.parse_codex_token_usage("tokens used: 12,345", "")

    assert usage == {"status": "reported", "total_tokens": 12345}


def test_codex_usage_parser_marks_malformed_and_missing_reports():
    assert run_skill_evals.parse_codex_token_usage("token usage: unknown", "")["reason"] == "malformed_report"
    assert run_skill_evals.parse_codex_token_usage("tokens used: 12.5", "")["reason"] == "malformed_report"
    assert run_skill_evals.parse_codex_token_usage("ordinary stderr", "")["reason"] == "not_reported"


def test_codex_run_case_uses_output_local_fixture_and_records_usage(tmp_path, monkeypatch):
    case = next(case for case in run_skill_evals.load_cases() if case["execution"]["sandbox"] == "workspace-write")
    observed = {}

    class CompletedProcess:
        returncode = 0

        def communicate(self, timeout=None):
            return "response", "tokens used: 42"

        def poll(self):
            return self.returncode

    def fake_popen(command, **kwargs):
        observed["cwd"] = kwargs["cwd"]
        return CompletedProcess()

    monkeypatch.setattr(run_skill_evals.subprocess, "Popen", fake_popen)
    output = tmp_path / "output"
    result = run_skill_evals.run_case(case, output, "codex", sys.executable, None)

    assert observed["cwd"].parent == output / ".fixtures"
    assert result["token_usage"] == {"status": "reported", "total_tokens": 42}
    assert result["cost"]["status"] == "cost_unavailable"


def test_collect_after_timeout_is_bounded_when_descendant_holds_pipes(monkeypatch):
    calls = []

    class Stream:
        def close(self):
            calls.append("closed")

    class StuckProcess:
        pid = 123
        stdout = Stream()
        stderr = Stream()

        def communicate(self, timeout=None):
            assert timeout == 5
            raise run_skill_evals.subprocess.TimeoutExpired("claude", timeout)

    monkeypatch.setattr(run_skill_evals, "terminate_process", lambda process: calls.append(process.pid))

    stdout, stderr = run_skill_evals.collect_after_timeout(StuckProcess())

    assert stdout == ""
    assert "kept output pipes open" in stderr
    assert calls == [123, "closed", "closed"]


def test_backend_inventory_reports_portable_capabilities(monkeypatch):
    monkeypatch.setattr(run_skill_evals.shutil, "which", lambda command: f"/bin/{command}" if command != "cursor-agent" else None)

    items = {item["backend"]: item for item in run_skill_evals.backend_inventory()}

    assert items["codex"]["available"] is True
    assert "native" in items["codex"]["containment"]
    assert items["claude"]["automation_supported"] is True
    assert items["claude"]["capabilities"] == ["filesystem_read", "filesystem_write"]
    assert items["cursor"]["available"] is False
    assert items["cursor"]["automation_supported"] is False


def test_list_backends_json_is_read_only_and_machine_readable(capsys):
    assert run_skill_evals.main(["--list-backends", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert [item["backend"] for item in payload["backends"]] == list(run_skill_evals.SUPPORTED_BACKENDS)


def test_legacy_codex_command_still_requires_backend_and_consent(tmp_path):
    with pytest.raises(SystemExit, match="user-selected --backend"):
        run_skill_evals.main([
            "--output",
            str(tmp_path / "run"),
            "--codex-command",
            "custom-codex",
            "--confirm-llm-evaluation",
        ])


def test_legacy_codex_command_maps_to_backend_override(tmp_path, monkeypatch):
    observed = {}

    def fake_preflight(backend, command, ignore_user_config):
        observed.update({"backend": backend, "command": command})
        return False, ["expected stop"]

    monkeypatch.setattr(run_skill_evals, "preflight", fake_preflight)
    result = run_skill_evals.main([
        "--output",
        str(tmp_path / "run"),
        "--backend",
        "codex",
        "--codex-command",
        "custom-codex",
        "--confirm-llm-evaluation",
    ])

    assert result == 1
    assert observed == {"backend": "codex", "command": "custom-codex"}


def test_main_records_backend_exclusions_and_scores_only_runnable_cases(tmp_path, monkeypatch):
    monkeypatch.setattr(run_skill_evals, "preflight", lambda *args: (True, ["ready"]))
    monkeypatch.setattr(
        run_skill_evals,
        "run_case",
        lambda case, *args: {
            "case_id": case["id"],
            "skill": case["skill"],
            "status": "completed_unscored",
            "duration_ms": 1,
        },
    )
    output = tmp_path / "run"

    result = run_skill_evals.main([
        "--output", str(output),
        "--backend", "claude",
        "--confirm-claude-unisolated-filesystem",
        "--backend-command", sys.executable,
        "--confirm-llm-evaluation",
    ])

    run = json.loads((output / "run.json").read_text(encoding="utf-8"))
    decisions = json.loads((output / "decisions.template.json").read_text(encoding="utf-8"))
    excluded = next(item for item in run["results"] if item["case_id"] == "skill-eval.page-test.extract-content")
    assert result == 0
    assert excluded["status"] == "unsupported_backend"
    assert "skill-eval.page-test.extract-content" in run["selection"]["excluded_case_ids"]
    assert "skill-eval.page-test.extract-content" not in {score["case_id"] for score in decisions["scores"]}
    assert run["candidate"]["filesystem_read_isolation"] == "read_scope_not_verified"
    assert run["scoring_eligibility"]["trusted_isolated_evaluation"] is False


def test_codex_run_does_not_claim_verified_fixture_read_isolation(tmp_path, monkeypatch):
    monkeypatch.setattr(run_skill_evals, "preflight", lambda *args: (True, ["ready"]))
    monkeypatch.setattr(
        run_skill_evals,
        "run_case",
        lambda case, *args: {
            "case_id": case["id"],
            "skill": case["skill"],
            "status": "completed_unscored",
            "duration_ms": 1,
        },
    )
    output = tmp_path / "run"

    assert run_skill_evals.main([
        "--output", str(output),
        "--backend", "codex",
        "--backend-command", sys.executable,
        "--confirm-llm-evaluation",
        "--case", "skill-eval.debug.confirm-user-assumption",
    ]) == 0

    run = json.loads((output / "run.json").read_text(encoding="utf-8"))
    assert run["candidate"]["filesystem_read_isolation"] == "read_scope_not_verified"
    assert run["scoring_eligibility"]["trusted_isolated_evaluation"] is False
