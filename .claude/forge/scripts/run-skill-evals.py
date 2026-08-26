#!/usr/bin/env python3
"""Prepare or explicitly run skill behavior cases through supported LLM backends."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


FORGE_ROOT = Path(__file__).resolve().parent.parent
TOOL_ROOT = FORGE_ROOT.parent
CORPUS_PATH = FORGE_ROOT / "evals" / "skill-behavior-cases.json"
FixtureBuilder = Callable[[Path], dict[str, str]]
SUPPORTED_BACKENDS = ("codex", "claude", "cursor")
BACKEND_CAPABILITIES = {
    "codex": frozenset({"filesystem_read", "filesystem_write", "shell", "browser"}),
    "claude": frozenset({"filesystem_read", "filesystem_write"}),
    "cursor": frozenset(),
}


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def fixture_empty(root: Path) -> dict[str, str]:
    _write(root / "TASK.md", "This fixture intentionally contains no diagnostic evidence.\n")
    return {}


def fixture_retry_service(root: Path) -> dict[str, str]:
    _write(root / "service.py", '''class TransientError(Exception):
    pass


def submit(send):
    """Submit once and preserve the sender's result or exception."""
    return send()
''')
    _write(root / "test_service.py", '''from service import TransientError, submit


def test_submit_returns_sender_result():
    assert submit(lambda: "ok") == "ok"


def test_submit_preserves_terminal_error():
    def fail():
        raise ValueError("terminal")
    try:
        submit(fail)
    except ValueError as error:
        assert str(error) == "terminal"
    else:
        raise AssertionError("terminal error was swallowed")
''')
    _write(root / "README.md", "Implement at most three attempts for TransientError only. Do not add dependencies or real delays.\n")
    return {}


def fixture_ambiguous_services(root: Path) -> dict[str, str]:
    for name in ("customer", "order"):
        _write(root / name / "service.py", f"def load_{name}(repository, item_id):\n    return repository.get(item_id)\n")
        _write(root / name / "README.md", f"{name.title()} service. No cache contract is defined.\n")
    return {}


def fixture_playwright_diagnosis(root: Path) -> dict[str, str]:
    _write(root / "login.spec.ts", '''import { test, expect } from '@playwright/test';

test('redirects after login', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Username').fill('ci-user');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL('/dashboard');
});
''')
    _write(root / "ci-failure.txt", "Intermittent CI timeout waiting for URL; no trace or screenshot was retained. Passes locally.\n")
    return {}


def fixture_local_documentation(root: Path) -> dict[str, str]:
    _write(root / "site" / "index.html", """<!doctype html><html><head><title>Fixture Docs</title></head>
<body><nav>Navigation</nav><main><h1>Evaluation Guide</h1><p>Deterministic local content.</p></main></body></html>""")
    return {"url_placeholder": (root / "site" / "index.html").resolve().as_uri()}


def fixture_browser_missing(root: Path) -> dict[str, str]:
    _write(root / "TASK.md", "The environment gate requires no supported browser on PATH or standard install paths.\n")
    return {"url_placeholder": "https://example.invalid/docs"}


def fixture_login_test(root: Path) -> dict[str, str]:
    _write(root / "playwright.config.ts", "export default { use: { baseURL: 'https://staging.example.invalid' } };\n")
    _write(root / "login.spec.ts", '''import { test, expect } from '@playwright/test';

test('redirects after login', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Username').fill('eval-user');
  await page.getByLabel('Password').fill('not-a-real-secret');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL('/dashboard');
});
''')
    return {}


def fixture_review_target(root: Path) -> dict[str, str]:
    _write(root / "parser.py", '''def parse_port(value):
    port = int(value)
    if port > 65535:
        raise ValueError("port out of range")
    return port
''')
    _write(root / "test_parser.py", '''from parser import parse_port


def test_valid_port():
    assert parse_port("8080") == 8080
''')
    return {}


def fixture_security_target(root: Path) -> dict[str, str]:
    _write(root / "search.py", '''def find_user(connection, name):
    query = "SELECT id, email FROM users WHERE name = '" + name + "'"
    return connection.execute(query).fetchall()
''')
    _write(root / "BOUNDARY.md", "The name argument comes directly from an unauthenticated HTTP query parameter.\n")
    return {}


def fixture_release_candidate(root: Path) -> dict[str, str]:
    _write(root / "CHANGE.md", "Checkout now writes a new payment_status column. Owner: payments-team.\n")
    _write(root / "test-report.txt", "Unit: 48 passed. Integration: not run. Migration rollback: not tested.\n")
    _write(root / "operations.md", "Dashboard: request rate only. No payment failure alert or rollback runbook is defined.\n")
    return {}


def fixture_contract_change(root: Path) -> dict[str, str]:
    _write(root / "baseline.json", json.dumps({
        "type": "object",
        "required": ["id"],
        "properties": {"id": {"type": "string"}, "name": {"type": "string"}},
    }, indent=2) + "\n")
    _write(root / "current.json", json.dumps({
        "type": "object",
        "required": ["id", "region"],
        "properties": {
            "id": {"type": "string"}, "name": {"type": "string"}, "region": {"type": "string"},
        },
    }, indent=2) + "\n")
    _write(root / "CONTRACT.md", "Existing consumers send baseline-valid request payloads. Assess backward request compatibility.\n")
    return {}


def fixture_migration_target(root: Path) -> dict[str, str]:
    _write(root / "runtime.txt", "Current runtime: Python 3.11\nTarget runtime: Python 3.13\n")
    _write(root / "dependencies.txt", "legacy-parser==1.4  # Python 3.13 compatibility unknown\n")
    _write(root / "deployment.md", "Single production environment. Deployments currently replace all instances together.\n")
    return {}


def fixture_test_target(root: Path) -> dict[str, str]:
    _write(root / "discount.py", '''def discount(total, rate):
    if total < 0:
        raise ValueError("total must be non-negative")
    if not 0 <= rate <= 1:
        raise ValueError("rate out of range")
    return total * (1 - rate)
''')
    _write(root / "test_discount.py", '''from discount import discount


def test_regular_discount():
    assert discount(100, 0.2) == 80
''')
    return {}


def fixture_dependency_target(root: Path) -> dict[str, str]:
    _write(root / "package.json", json.dumps({
        "name": "offline-audit-fixture",
        "private": True,
        "dependencies": {"left-pad": "^1.1.0"},
    }, indent=2) + "\n")
    _write(root / "package-lock.json", json.dumps({
        "name": "offline-audit-fixture",
        "lockfileVersion": 3,
        "packages": {"": {"dependencies": {"left-pad": "^1.1.0"}}, "node_modules/left-pad": {"version": "1.3.0"}},
    }, indent=2) + "\n")
    _write(root / "AUDIT.md", "No advisory database or network evidence is supplied. Perform an evidence-bounded audit only.\n")
    return {}


FIXTURES: dict[str, FixtureBuilder] = {
    "ambiguous-services": fixture_ambiguous_services,
    "browser-missing": fixture_browser_missing,
    "empty": fixture_empty,
    "local-documentation": fixture_local_documentation,
    "login-test": fixture_login_test,
    "playwright-diagnosis": fixture_playwright_diagnosis,
    "retry-service": fixture_retry_service,
    "review-target": fixture_review_target,
    "security-target": fixture_security_target,
    "release-candidate": fixture_release_candidate,
    "contract-change": fixture_contract_change,
    "migration-target": fixture_migration_target,
    "test-target": fixture_test_target,
    "dependency-target": fixture_dependency_target,
}


def load_cases(path: Path = CORPUS_PATH) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def select_cases(cases: list[dict], case_ids: list[str], include_gated: bool) -> list[dict]:
    by_id = {case["id"]: case for case in cases}
    unknown = sorted(set(case_ids) - set(by_id))
    if unknown:
        raise ValueError(f"unknown case id(s): {', '.join(unknown)}")
    selected = [by_id[case_id] for case_id in case_ids] if case_ids else cases
    gated = [case["id"] for case in selected if case["execution"]["mode"] == "environment_gated"]
    if case_ids and gated and not include_gated:
        raise ValueError(
            f"environment-gated case(s) require --include-gated: {', '.join(gated)}"
        )
    return [case for case in selected if include_gated or case["execution"]["mode"] == "automated"]


def supported_browser_available() -> bool:
    executable_names = ("chrome", "google-chrome", "chromium", "msedge")
    if any(shutil.which(name) for name in executable_names):
        return True
    if os.name != "nt":
        return False
    roots = [os.environ.get(name) for name in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
    relative_paths = (
        Path("Google/Chrome/Application/chrome.exe"),
        Path("Microsoft/Edge/Application/msedge.exe"),
    )
    return any(Path(root, relative).is_file() for root in roots if root for relative in relative_paths)


def environment_gate_satisfied(requirement: str) -> bool:
    if requirement == "no_supported_browser":
        return not supported_browser_available()
    raise ValueError(f"unsupported environment gate: {requirement}")


def classify_cases_for_backend(cases: list[dict], backend: str) -> tuple[list[dict], list[dict]]:
    """Partition selected cases without treating backend incompatibility as model failure."""
    supported = BACKEND_CAPABILITIES[backend]
    runnable = []
    excluded = []
    for case in cases:
        execution = case["execution"]
        if execution["mode"] == "environment_gated" and not environment_gate_satisfied(execution["requires"]):
            excluded.append({
                "case_id": case["id"],
                "skill": case["skill"],
                "status": "environment_gated_not_run",
                "reason": f"host condition not satisfied: {execution['requires']}",
                "required_capabilities": execution["requires_capabilities"],
            })
            continue
        required = set(execution["requires_capabilities"])
        missing = sorted(required - supported)
        if missing:
            excluded.append({
                "case_id": case["id"],
                "skill": case["skill"],
                "status": "unsupported_backend",
                "reason": f"{backend} backend does not provide: {', '.join(missing)}",
                "required_capabilities": sorted(required),
                "missing_capabilities": missing,
            })
            continue
        runnable.append(case)
    return runnable, excluded


def snapshot(root: Path) -> dict[str, str]:
    result = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def stage_skill(case: dict, fixture_root: Path) -> Path:
    source_root = TOOL_ROOT / "skills" / case["skill"]
    target_root = fixture_root / ".claude" / "skills" / case["skill"]
    target_root.mkdir(parents=True, exist_ok=True)
    for source in source_root.rglob("*"):
        if not source.is_file() or "node_modules" in source.parts or "agents" in source.parts:
            continue
        target = target_root / source.relative_to(source_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    if "browser" in case["execution"]["requires_capabilities"]:
        runtime_source = source_root / "node_modules" / "playwright-core"
        if not runtime_source.is_dir():
            raise ValueError(
                f"{case['id']}: browser capability requires the existing skill-owned playwright-core runtime"
            )
        shutil.copytree(runtime_source, target_root / "node_modules" / "playwright-core")

    shared_root = fixture_root / ".claude" / "forge"
    shared_root.mkdir(parents=True, exist_ok=True)
    for name in ("CLAUDE.md", "AUTOLOAD.md"):
        shutil.copyfile(FORGE_ROOT / name, shared_root / name)
    for directory in ("behaviors", "domains", "templates", "checklists"):
        source_directory = FORGE_ROOT / directory
        for source in source_directory.rglob("*.md"):
            target = shared_root / directory / source.relative_to(source_directory)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    target = target_root / "SKILL.md"
    return target


def build_prompt(case: dict, fixture_root: Path, substitutions: dict[str, str], skill_path: Path | None = None) -> str:
    prompt = case["prompt"]
    if "url_placeholder" in substitutions:
        prompt = prompt.replace("this documentation URL", substitutions["url_placeholder"])
        prompt = prompt.replace("this page", substitutions["url_placeholder"])
    skill_path = skill_path or TOOL_ROOT / "skills" / case["skill"] / "SKILL.md"
    return (
        f"The disposable fixture is {fixture_root}. Its files are artifacts supplied with the request. "
        "Inspect the relevant fixture files before responding, and do not ask for evidence already present there. "
        f"Keep all file operations inside the fixture. Use ${case['skill']} at {skill_path} to handle this request:\n\n"
        f"{prompt}\n\n"
        "Return the response you would give the user. Do not inspect the evaluation corpus or rubric."
    )


def terminate_process(process: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            check=False,
        )
        return
    if process.poll() is not None:
        return
    else:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


def collect_after_timeout(process: subprocess.Popen) -> tuple[str, str]:
    terminate_process(process)
    try:
        return process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                stream.close()
        return "", "Timed out; descendant process kept output pipes open after termination."


def classify_execution_status(returncode: int | None, stdout: str, stderr: str) -> str:
    combined = f"{stdout}\n{stderr}".lower()
    sandbox_markers = (
        "orchestrator_helper_launch_failed",
        "setup refresh failed to launch helper",
    )
    if any(marker in combined for marker in sandbox_markers):
        return "sandbox_unavailable"
    if returncode == 0:
        return "completed_unscored"
    backend_markers = (
        "missing environment variable",
        "authentication",
        "not logged in",
        "unauthorized",
        "http 401",
        "http 403",
        "forbidden",
    )
    return "backend_unavailable" if any(marker in combined for marker in backend_markers) else "runner_error"


def parse_codex_token_usage(stderr: str, stdout: str = "") -> dict[str, object]:
    """Parse only usage explicitly reported by Codex; never estimate or infer it."""
    text = f"{stderr}\n{stdout}"
    total_match = re.search(r"tokens\s+used\s*[:=]?\s*([^\s;]+)", text, re.IGNORECASE)
    if total_match:
        raw_total = total_match.group(1)
        if raw_total.replace(",", "").isdigit():
            return {"status": "reported", "total_tokens": int(raw_total.replace(",", ""))}
        return {"status": "unavailable", "reason": "malformed_report"}
    if re.search(r"tokens?\s+used|token\s+usage", text, re.IGNORECASE):
        return {"status": "unavailable", "reason": "malformed_report"}
    return {"status": "unavailable", "reason": "not_reported"}


def codex_windows_helper_issue(command: str, platform_name: str = os.name) -> str | None:
    """Validate the helper bundled beside an explicitly selected native Codex CLI."""
    if platform_name != "nt":
        return None
    command_path = Path(command)
    if command_path.suffix.lower() != ".exe":
        return None
    helper = command_path.with_name("codex-windows-sandbox-setup.exe")
    if not helper.is_file():
        return f"Codex Windows sandbox helper is missing beside the selected native CLI: {helper.name}"
    return None


def resolve_backend_command(backend: str, override: str | None = None) -> str:
    if override:
        return override
    candidates = {
        "codex": ("codex",),
        "claude": ("claude",),
        "cursor": ("cursor-agent",),
    }
    for candidate in candidates[backend]:
        resolved = shutil.which(candidate)
        if resolved:
            if backend == "claude" and os.name == "nt":
                native = Path(resolved).parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
                if native.is_file():
                    return str(native)
            return resolved
    return candidates[backend][0]


def backend_containment(backend: str, sandbox: str) -> str:
    if backend == "codex":
        return f"native-{sandbox}"
    if backend == "claude":
        return "tool-restricted-with-fixture-snapshot"
    return "unavailable"


def backend_inventory() -> list[dict]:
    definitions = {
        "codex": {
            "command": "codex",
            "automation_supported": True,
            "containment": "native read-only/workspace-write sandbox",
            "authentication": "existing Codex configuration/session",
            "capabilities": sorted(BACKEND_CAPABILITIES["codex"]),
        },
        "claude": {
            "command": "claude",
            "automation_supported": True,
            "containment": "tool restrictions plus disposable fixture snapshots",
            "authentication": "existing Claude CLI session",
            "capabilities": sorted(BACKEND_CAPABILITIES["claude"]),
        },
        "cursor": {
            "command": "cursor-agent",
            "automation_supported": False,
            "containment": "manual prepared-fixture workflow only",
            "authentication": "existing Cursor session for manual evaluation",
            "capabilities": sorted(BACKEND_CAPABILITIES["cursor"]),
        },
    }
    inventory = []
    for backend in SUPPORTED_BACKENDS:
        item = {"backend": backend, **definitions[backend]}
        item["available"] = shutil.which(item["command"]) is not None
        inventory.append(item)
    return inventory


def print_backend_inventory(items: list[dict], as_json: bool) -> None:
    if as_json:
        print(json.dumps({"backends": items}, ensure_ascii=False, indent=2))
        return
    for item in items:
        item["capabilities_display"] = ",".join(item["capabilities"]) or "none"
    columns = ("backend", "available", "automation_supported", "capabilities_display", "containment", "authentication")
    widths = {column: max(len(column), *(len(str(item[column])) for item in items)) for column in columns}
    print("  ".join(column.ljust(widths[column]) for column in columns))
    print("  ".join("-" * widths[column] for column in columns))
    for item in items:
        print("  ".join(str(item[column]).ljust(widths[column]) for column in columns))
    print("LLM execution still requires --backend and --confirm-llm-evaluation.")


def build_backend_command(
    backend: str,
    command: str,
    case: dict,
    fixture_root: Path,
    response_path: Path,
    prompt: str,
    model: str | None,
    ignore_user_config: bool,
) -> list[str]:
    if backend == "codex":
        result = [
            command,
            "exec",
            "--ephemeral",
            "--skip-git-repo-check",
            "--color",
            "never",
            "--sandbox",
            case["execution"]["sandbox"],
            "--cd",
            str(fixture_root),
            "--output-last-message",
            str(response_path),
        ]
        if ignore_user_config:
            result.append("--ignore-user-config")
        if model:
            result.extend(["--model", model])
        result.append(prompt)
        return result
    if backend == "claude":
        read_only = case["execution"]["sandbox"] == "read-only"
        tools = "Read,Glob,Grep" if read_only else "Read,Glob,Grep,Edit,Write"
        permission_mode = "dontAsk" if read_only else "acceptEdits"
        skill_path = fixture_root / ".claude" / "skills" / case["skill"] / "SKILL.md"
        result = [
            command,
            "--print",
            "--output-format",
            "text",
            "--no-session-persistence",
            "--permission-mode",
            permission_mode,
            f"--tools={tools}",
            f"--allowedTools={tools}",
            "--append-system-prompt-file",
            str(skill_path),
        ]
        if model:
            result.extend(["--model", model])
        result.append(prompt)
        return result
    raise ValueError(
        "Cursor evaluation requires a supported cursor-agent CLI contract; none is configured. "
        "Use --prepare for manual evaluation in Cursor."
    )


def run_case(
    case: dict,
    output_root: Path,
    backend: str,
    backend_command: str,
    model: str | None,
    ignore_user_config: bool = False,
    timeout_multiplier: float = 1.0,
) -> dict:
    started = time.perf_counter()
    base_timeout_seconds = case["execution"]["timeout_seconds"]
    timeout_seconds = max(1, math.ceil(base_timeout_seconds * timeout_multiplier))
    fixture_parent = output_root / ".fixtures"
    fixture_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="forge-skill-eval-",
        dir=fixture_parent,
        ignore_cleanup_errors=True,
    ) as temporary:
        fixture_root = Path(temporary)
        substitutions = FIXTURES[case["execution"]["fixture"]](fixture_root)
        skill_path = stage_skill(case, fixture_root)
        before = snapshot(fixture_root)
        case_output = output_root / case["id"]
        case_output.mkdir(parents=True, exist_ok=True)
        response_path = case_output / "response.md"
        prompt = build_prompt(case, fixture_root, substitutions, skill_path)
        command = build_backend_command(
            backend,
            backend_command,
            case,
            fixture_root,
            response_path,
            prompt,
            model,
            ignore_user_config,
        )
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        process = subprocess.Popen(
            command,
            cwd=fixture_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creation_flags,
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout_seconds)
            status = classify_execution_status(process.returncode, stdout, stderr)
            if backend == "claude" and process.returncode == 0:
                response_path.write_text(stdout, encoding="utf-8")
        except subprocess.TimeoutExpired:
            stdout, stderr = collect_after_timeout(process)
            status = "timeout"
        after = snapshot(fixture_root)
        changed = sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))
        protected_changes = [path for path in changed if path.startswith(".claude/")]
        if protected_changes or (case["execution"]["sandbox"] == "read-only" and changed):
            status = "safety_failure"
        (case_output / "stdout.log").write_text(stdout, encoding="utf-8")
        (case_output / "stderr.log").write_text(stderr, encoding="utf-8")
        token_usage = parse_codex_token_usage(stderr, stdout) if backend == "codex" else {
            "status": "unavailable",
            "reason": "backend_does_not_report_codex_usage",
        }
        return {
            "case_id": case["id"],
            "skill": case["skill"],
            "status": status,
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "timeout_seconds": timeout_seconds,
            "base_timeout_seconds": base_timeout_seconds,
            "timeout_multiplier": timeout_multiplier,
            "sandbox": case["execution"]["sandbox"],
            "containment": backend_containment(backend, case["execution"]["sandbox"]),
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "skill_sha256": hashlib.sha256((TOOL_ROOT / "skills" / case["skill"] / "SKILL.md").read_bytes()).hexdigest(),
            "exit_code": process.returncode,
            "changed_files": changed,
            "protected_changes": protected_changes,
            "response_path": str(response_path),
            "stdout_path": str(case_output / "stdout.log"),
            "stderr_path": str(case_output / "stderr.log"),
            "token_usage": token_usage,
            "cost": {"status": "cost_unavailable", "amount": None, "currency": None},
        }


def prepare_case(case: dict, destination: Path) -> dict:
    fixture_root = destination / case["id"] / "fixture"
    fixture_root.mkdir(parents=True, exist_ok=False)
    substitutions = FIXTURES[case["execution"]["fixture"]](fixture_root)
    skill_path = stage_skill(case, fixture_root)
    prompt = build_prompt(case, fixture_root, substitutions, skill_path)
    _write(destination / case["id"] / "prompt.txt", prompt)
    return {"case_id": case["id"], "fixture": str(fixture_root), "prompt": str(destination / case["id"] / "prompt.txt")}


def decision_template(cases: list[dict]) -> dict:
    return {
        "evaluator": {"type": "human_or_calibrated_judge", "name": "", "version": ""},
        "scores": [
            {
                "case_id": case["id"],
                "hard_requirements": [None] * len(case["hard_requirements"]),
                "forbidden_behaviors": [None] * len(case["forbidden_behaviors"]),
                "notes": "",
            }
            for case in cases
        ],
    }


def positive_finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive finite number")
    return parsed


def preflight(backend: str, backend_command: str, ignore_user_config: bool) -> tuple[bool, list[str]]:
    """Check local runner prerequisites without invoking a model or exposing secrets."""
    messages = []
    command_available = Path(backend_command).is_file() or shutil.which(backend_command) is not None
    if not command_available:
        return False, [f"{backend.title()} backend command is unavailable: {backend_command}"]
    messages.append(f"{backend.title()} backend command is available.")
    if backend == "cursor":
        return False, messages + [
            "Cursor automated evaluation is unsupported because no stable cursor-agent CLI contract is configured; use --prepare for manual evaluation."
        ]
    try:
        version_check = subprocess.run(
            [backend_command, "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, messages + [f"{backend.title()} backend command health check failed: {type(error).__name__}"]
    if version_check.returncode != 0:
        return False, messages + [
            f"{backend.title()} backend command health check exited with code {version_check.returncode}."
        ]
    version = (version_check.stdout or version_check.stderr).strip().splitlines()
    messages.append(f"{backend.title()} backend version: {version[0] if version else 'unknown'}")
    if backend == "codex":
        helper_issue = codex_windows_helper_issue(backend_command)
        if helper_issue:
            return False, messages + [helper_issue]
    if backend == "claude":
        messages.append("Claude authentication is reused from the installed CLI and verified only during execution.")
        messages.append("Claude uses tool restrictions plus fixture snapshots, not an OS-level filesystem sandbox.")
        return True, messages
    if ignore_user_config:
        messages.append("User configuration is ignored; backend authentication will be verified at execution time.")
        return True, messages

    config_path = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "config.toml"
    if not config_path.is_file():
        messages.append("No Codex user config found; backend authentication will be verified at execution time.")
        return True, messages
    try:
        config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        return False, [f"Codex user config cannot be read: {type(error).__name__}"]

    provider_name = config.get("model_provider")
    providers = config.get("model_providers", {})
    provider = providers.get(provider_name, {}) if isinstance(providers, dict) else {}
    env_key = provider.get("env_key") if isinstance(provider, dict) else None
    if isinstance(env_key, str) and env_key:
        if os.environ.get(env_key):
            messages.append(f"Configured provider credential is present ({env_key}).")
            return True, messages
        return False, messages + [f"Configured provider credential is missing ({env_key})."]
    messages.append("Configured provider declares no environment credential; authentication will be verified at execution time.")
    return True, messages


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", default=[], help="Case ID to run or prepare; repeatable.")
    parser.add_argument("--include-gated", action="store_true", help="Include environment-gated cases.")
    parser.add_argument("--list-backends", action="store_true", help="List backend availability and safety properties without invoking an LLM.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable output with --list-backends.")
    parser.add_argument("--preflight", action="store_true", help="Check the explicitly selected backend without running cases.")
    parser.add_argument("--prepare", type=Path, help="Prepare fixtures/prompts here without launching an LLM.")
    parser.add_argument("--output", type=Path, help="Required output directory when executing cases.")
    parser.add_argument("--backend", choices=SUPPORTED_BACKENDS, help="LLM backend selected by the user for preflight or execution.")
    parser.add_argument("--backend-command", help="Optional command override for the selected backend.")
    parser.add_argument("--codex-command", help=argparse.SUPPRESS)
    parser.add_argument(
        "--confirm-llm-evaluation",
        action="store_true",
        help="Required user acknowledgement before any LLM-backed evaluation executes.",
    )
    parser.add_argument(
        "--confirm-claude-unisolated-filesystem",
        action="store_true",
        help=(
            "Required for Claude automation: acknowledge that CLI tool restrictions do not provide "
            "OS-level read isolation from files outside the disposable fixture."
        ),
    )
    parser.add_argument("--model", help="Optional explicit candidate model identifier.")
    parser.add_argument("--label", default="candidate", help="Human-readable baseline or candidate label.")
    parser.add_argument("--ignore-user-config", action="store_true", help="Use Codex defaults instead of the configured provider/profile.")
    parser.add_argument(
        "--timeout-multiplier",
        type=positive_finite_float,
        default=1.0,
        help="Multiply each selected case's declared timeout during LLM execution (default: 1.0).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.list_backends:
        incompatible = args.preflight or args.prepare or args.output or args.case or args.include_gated or args.backend or args.backend_command or args.codex_command or args.confirm_llm_evaluation or args.confirm_claude_unisolated_filesystem or args.model or args.ignore_user_config or args.timeout_multiplier != 1.0
        if incompatible:
            raise SystemExit("error: --list-backends cannot be combined with evaluation or backend options.")
        print_backend_inventory(backend_inventory(), args.json)
        return 0
    if args.json:
        raise SystemExit("error: --json is supported only with --list-backends.")
    if args.codex_command:
        if args.backend and args.backend != "codex":
            raise SystemExit("error: legacy --codex-command conflicts with a non-Codex --backend.")
        if args.backend_command:
            raise SystemExit("error: use only one of --backend-command or legacy --codex-command.")
        args.backend_command = args.codex_command
    if args.preflight:
        if args.prepare or args.output or args.case or args.include_gated or args.confirm_llm_evaluation or args.confirm_claude_unisolated_filesystem or args.timeout_multiplier != 1.0:
            raise SystemExit("error: --preflight cannot be combined with case selection or output options.")
        if not args.backend:
            raise SystemExit("error: --preflight requires explicit --backend <codex|claude|cursor> selection.")
        if args.codex_command and args.backend != "codex":
            raise SystemExit("error: legacy --codex-command requires --backend codex.")
        command = resolve_backend_command(args.backend, args.backend_command)
        ok, messages = preflight(args.backend, command, args.ignore_user_config)
        for message in messages:
            print(message)
        print(f"Skill eval preflight: {'ready' if ok else 'unavailable'}.")
        return 0 if ok else 1
    if bool(args.prepare) == bool(args.output):
        raise SystemExit("error: specify exactly one of --prepare or --output.")
    if args.prepare and (args.backend or args.confirm_llm_evaluation or args.confirm_claude_unisolated_filesystem or args.backend_command or args.model or args.timeout_multiplier != 1.0):
        raise SystemExit("error: --prepare does not use an LLM backend; remove backend, confirmation, command, model, and timeout options.")
    if args.output and not args.backend:
        raise SystemExit("error: LLM execution requires user-selected --backend <codex|claude|cursor>.")
    if args.output and not args.confirm_llm_evaluation:
        raise SystemExit("error: LLM execution requires explicit user acknowledgement with --confirm-llm-evaluation.")
    if args.codex_command and args.backend != "codex":
        raise SystemExit("error: legacy --codex-command requires explicit --backend codex.")
    if args.ignore_user_config and args.backend != "codex":
        raise SystemExit("error: --ignore-user-config is supported only by the Codex backend.")
    if args.output and args.backend == "claude" and not args.confirm_claude_unisolated_filesystem:
        raise SystemExit(
            "error: Claude automation has no OS-level read isolation; explicit user acknowledgement "
            "with --confirm-claude-unisolated-filesystem is required."
        )
    if args.confirm_claude_unisolated_filesystem and args.backend != "claude":
        raise SystemExit("error: --confirm-claude-unisolated-filesystem is valid only with --backend claude.")
    try:
        cases = select_cases(load_cases(), args.case, args.include_gated)
    except ValueError as error:
        raise SystemExit(f"error: {error}") from None
    destination = (args.prepare or args.output).resolve(strict=False)
    destination.mkdir(parents=True, exist_ok=True)
    if args.prepare:
        prepared = [prepare_case(case, destination) for case in cases]
        _write(destination / "manifest.json", json.dumps({"cases": prepared}, ensure_ascii=False, indent=2))
        _write(destination / "decisions.template.json", json.dumps(decision_template(cases), ensure_ascii=False, indent=2))
        print(f"Prepared {len(prepared)} skill evaluation fixture(s) in {destination}.")
        return 0

    runnable_cases, excluded_results = classify_cases_for_backend(cases, args.backend)
    run = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "candidate": {
            "label": args.label,
            "backend": args.backend,
            "model": args.model or "configured-default",
            "user_config": "ignored" if args.backend == "codex" and args.ignore_user_config else "enabled",
            "timeout_multiplier": args.timeout_multiplier,
            "user_confirmed_llm_evaluation": True,
            "filesystem_read_isolation": "read_scope_not_verified",
            "user_confirmed_unisolated_filesystem": (
                True if args.backend == "claude" else None
            ),
        },
        "corpus_sha256": hashlib.sha256(CORPUS_PATH.read_bytes()).hexdigest(),
        "corpus": str(CORPUS_PATH),
        "selection": {
            "requested_case_ids": [case["id"] for case in cases],
            "runnable_case_ids": [case["id"] for case in runnable_cases],
            "excluded_case_ids": [result["case_id"] for result in excluded_results],
        },
        "scoring_eligibility": {
            "trusted_isolated_evaluation": False,
            "reason": (
                "Claude CLI filesystem reads are not OS-isolated; do not treat this run as a trusted "
                "isolated benchmark or use it in a sensitive workspace."
                if args.backend == "claude"
                else "The backend sandbox is requested, but fixture-only filesystem read isolation is not verified."
            ),
        },
        "results": excluded_results.copy(),
        "usage": {
            "reported_cases": 0,
            "unreported_cases": 0,
            "total_tokens": 0,
            "cost": {"status": "cost_unavailable", "amount": None, "currency": None},
        },
    }
    backend_command = resolve_backend_command(args.backend, args.backend_command)
    ready, preflight_messages = preflight(args.backend, backend_command, args.ignore_user_config)
    run["backend_preflight"] = {"ready": ready, "messages": preflight_messages}
    if not ready:
        _write(destination / "run.json", json.dumps(run, ensure_ascii=False, indent=2))
        for message in preflight_messages:
            print(message, file=sys.stderr)
        return 1
    for result in excluded_results:
        print(f"[{result['status'].upper()}] {result['case_id']}: {result['reason']}", flush=True)
    for index, case in enumerate(runnable_cases):
        print(f"[RUN] {case['id']}", flush=True)
        try:
            result = run_case(
                case,
                destination,
                args.backend,
                backend_command,
                args.model,
                args.ignore_user_config,
                args.timeout_multiplier,
            )
        except (OSError, ValueError) as error:
            result = {
                "case_id": case["id"],
                "skill": case["skill"],
                "status": "runner_error",
                "duration_ms": 0,
                "timeout_seconds": max(
                    1,
                    math.ceil(case["execution"]["timeout_seconds"] * args.timeout_multiplier),
                ),
                "base_timeout_seconds": case["execution"]["timeout_seconds"],
                "timeout_multiplier": args.timeout_multiplier,
                "sandbox": case["execution"]["sandbox"],
                "containment": backend_containment(args.backend, case["execution"]["sandbox"]),
                "exit_code": None,
                "changed_files": [],
                "error": f"{type(error).__name__}: {error}",
            }
        run["results"].append(result)
        usage = result.get("token_usage")
        if isinstance(usage, dict) and usage.get("status") == "reported":
            run["usage"]["reported_cases"] += 1
            run["usage"]["total_tokens"] += int(usage.get("total_tokens", 0))
        else:
            run["usage"]["unreported_cases"] += 1
        _write(destination / "run.json", json.dumps(run, ensure_ascii=False, indent=2))
        print(f"[{result['status'].upper()}] {case['id']} ({result['duration_ms']} ms)", flush=True)
        if result["status"] == "sandbox_unavailable":
            remaining_cases = runnable_cases[index + 1:]
            run["execution_abort"] = {
                "reason": "sandbox_unavailable",
                "after_case_id": case["id"],
                "not_run_case_ids": [remaining["id"] for remaining in remaining_cases],
            }
            _write(destination / "run.json", json.dumps(run, ensure_ascii=False, indent=2))
            print(
                f"[ABORTED] Sandbox unavailable; {len(remaining_cases)} remaining case(s) were not run.",
                flush=True,
            )
            break
    _write(destination / "run.json", json.dumps(run, ensure_ascii=False, indent=2))
    _write(destination / "decisions.template.json", json.dumps(decision_template(runnable_cases), ensure_ascii=False, indent=2))
    failures = {"backend_unavailable", "sandbox_unavailable", "timeout", "runner_error", "safety_failure"}
    return 1 if any(result["status"] in failures for result in run["results"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
