# -*- coding: utf-8 -*-
"""Forge CLI — modular AI Engineering Operating System."""

import hashlib
from importlib.util import find_spec
import json
import re
import sys
from pathlib import Path
from typing import Optional

import click

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from .constants import (
    ALL_CHECKS,
    CHECK_PATHS,
    CHECK_REGISTRY,
    CHECK_REFS,
    EXIT_GENERAL_ERROR,
    EXIT_OK,
    EXIT_PATH_ERROR,
    EXIT_USAGE_ERROR,
    EXIT_VALIDATION_FAILED,
)
from .helpers import env_verbose, resolve_root
from .context_bundle import DEFAULT_MAX_BUNDLE_BYTES, DEFAULT_MAX_MODULE_BYTES, build_context_bundle
from .claude_code_adapter import build_claude_code_host_request, validate_and_normalize_claude_code_host_result
from .runtime_discovery import discover_resumable_runtimes
from .runtime_lifecycle import consume_paused_runtime
from .runtime_paths import (
    migrate_legacy_runtime_directory,
    project_runtime_directory,
    validate_project_runtime_directory,
)
from .routing_config import get_effective_skill_routing_config
from .query_helpers import find_item, list_modules_by_kind
from .renderers import (
    build_check_results_payload,
    render_ask_text,
    render_check_results_text,
    render_compose_text,
    render_output_validation_text,
    render_recommend_text,
    render_resolved_context_text,
    write_report_file,
    write_report_file_exclusive,
)
from .routing_engine import (
    _build_prefer_fallback,
    build_recommendation_from_route,
    compose_selection,
    merge_skill_and_pack_route,
    render_route_text,
    route_by_skill_triggers,
    route_pack,
)


def _runtime_suspend_intent(text: str) -> tuple[str, str] | None:
    patterns = (
        ("suspend", r"^\s*runtime-suspend\s+--task\s+(?P<task>.+?)\s*$"),
        ("suspend", r"^\s*用\s*Forge\s*Runtime\s*挂起[“\"](?P<task>.+?)[”\"]这个任务\s*$"),
        ("suspend", r"^\s*确认\s*(?:挂起|暂停)\s*Forge\s*Runtime\s*任务\s*[“\"](?P<task>.+?)[”\"]\s*$"),
        ("suspend_confirmation_required", r"^\s*将\s*(?P<task>.+?)\s*持久化(?:挂起|暂停)\s*$"),
        ("suspend_confirmation_required", r"^\s*(?:挂起|暂停)\s*Forge\s*Runtime\s*任务\s*[“\"](?P<task>.+?)[”\"]\s*$"),
    )
    for action, pattern in patterns:
        match = re.match(pattern, text, flags=re.IGNORECASE)
        if match:
            task = match.group("task").strip().strip('“”"')
            if task:
                return action, task
    return None


def _runtime_ask_intent(text: str) -> tuple[str, str | None] | None:
    suspend_intent = _runtime_suspend_intent(text)
    if suspend_intent:
        return suspend_intent
    list_patterns = (
        r"^\s*runtime-list-paused\s*$",
        r"^\s*(?:查看|列出)\s*(?:(?:暂停|挂起)(?:的)?\s*)?(?:Forge\s*Runtime\s*)?(?:(?:暂停|挂起)(?:的)?\s*)?任务(?:项)?(?:有哪些)?\s*$",
        r"^\s*(?:我\s*)?有哪些\s*(?:暂停|挂起)(?:的)?\s*(?:Forge\s*Runtime\s*)?任务(?:项)?\s*$",
    )
    if any(re.match(pattern, text, flags=re.IGNORECASE) for pattern in list_patterns):
        return "list", None
    candidate_match = re.match(
        r"^\s*(?:runtime-consume-paused\s+--path\s+|继续(?:\s*Forge\s*Runtime(?:任务)?)?\s+)(?P<path>[^\s/\\]+\.json)\s*$",
        text,
        flags=re.IGNORECASE,
    )
    if candidate_match:
        return "consume", candidate_match.group("path")
    if re.match(r"^\s*(runtime-consume-paused|继续.*Forge\s*Runtime.*|continue(?:\s+forge\s+runtime)?(?:\s+task)?)\s*$", text, flags=re.IGNORECASE):
        return "list", None
    return None


def _learning_review_intent(text: str) -> str | None:
    compact = re.sub(r"\s+", "", text).lower()
    if compact in {"结束这个服务", "关闭这个服务", "停止这个服务"}:
        return "stop"
    if "8765" in compact and any(value in compact for value in ("加载", "监听", "打开", "启动")):
        return "start"
    subject = any(value in compact for value in ("学习审核", "学习数据审核", "learningreview"))
    if not subject:
        return None
    if any(value in compact for value in ("关闭", "停止", "结束", "退出")):
        return "stop"
    if any(value in compact for value in ("启动", "打开", "加载", "监听", "运行")):
        return "start"
    return None


def _render_learning_review(payload: dict, output_format: str) -> None:
    if output_format == "json":
        click.echo(json.dumps({key: value for key, value in payload.items() if key != "token"}, ensure_ascii=False, indent=2))
        return
    status = payload.get("status")
    if status in {"started", "already_running"}:
        click.echo(f"Learning review {status}: {payload['url']} (PID {payload['pid']})")
    elif status == "stopped":
        click.echo(f"Learning review stopped: {payload['url']} (PID {payload['pid']})")
    elif status == "stale_state_removed":
        click.echo("Learning review was not running; removed stale service state")
    else:
        click.echo("Learning review is not running")


def _project_directory(root: Path) -> Path:
    """Return the caller-owned project, independent from Forge's install root.

    A Forge root may be globally installed or be a Junction to shared source.
    Runtime state is user work, so it must always remain in the current
    project's directory rather than beside either installation.
    """
    return Path.cwd()


def _project_runtime_directory(root: Path) -> Path:
    return project_runtime_directory(_project_directory(root))


def _render_runtime_list(result: dict, output_format: str) -> None:
    if output_format == "json":
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["candidates"]:
        click.echo("Resumable Forge runtimes:")
        for candidate in result["candidates"]:
            click.echo(f"- {candidate['path']}: {candidate['status']} / {candidate['current_stage_id']}")
    else:
        summary = result["summary"]
        click.echo(
            "Resumable Forge runtimes: none "
            f"(scanned {summary['scanned']}; terminal {summary['terminal']}; invalid {summary['invalid']})"
        )


def _render_consumed_runtime(result: dict, output_format: str) -> None:
    if output_format == "json":
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))
        return
    click.echo(f"Forge Runtime: CONSUMED ({result['runtime_id']})")
    click.echo(f"Task: {result['task_statement']}")
    click.echo(f"Stage: {result['current_stage_id']}")


def _runtime_suspend_output(root: Path, task: str) -> Path:
    project = _project_directory(root)
    migrate_legacy_runtime_directory(project)
    runtime_directory = project_runtime_directory(project)
    normalized = re.sub(r"[^a-z0-9]+", "-", task.lower()).strip("-")
    if not normalized:
        normalized = f"task-{hashlib.sha256(task.encode('utf-8')).hexdigest()[:12]}"
    return runtime_directory / f"{normalized[:64]}.json"


def _project_relative_path(path: Path) -> str:
    """Render a project-owned path without leaking a global/source location."""
    return path.relative_to(Path.cwd()).as_posix()


def _create_suspended_runtime(root: Path, task: str, preferred_skill: str = "skill.plan") -> dict:
    """Persist an explicit task even when its free-text route has no match."""
    output_path = _runtime_suspend_output(root, task)
    if output_path.exists():
        raise click.UsageError(
            f"runtime already exists: {_project_relative_path(output_path)}; "
            "choose a different task name or handle the existing runtime explicitly"
        )
    manifest, _ = _runtime_manifest_from_inputs(root, (task,), preferred_skill, None, None, None, None, None, (), ())
    try:
        from .runtime_composition import initialize_runtime

        envelope = initialize_runtime(root, manifest, task_statement=task)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        write_report_file_exclusive(output_path, envelope)
    except FileExistsError as error:
        raise click.UsageError(
            f"runtime already exists: {_project_relative_path(output_path)}; "
            "choose a different task name or handle the existing runtime explicitly"
        ) from error
    except ValueError as error:
        raise click.UsageError(str(error)) from error
    return {
        "mode": "runtime-suspended",
        "runtime_path": _project_relative_path(output_path),
        "runtime_id": envelope["runtime_id"],
        "status": envelope["status"],
        "current_stage_id": envelope["stage_progress"]["workflow_stages"][0],
    }


def _render_suspended_runtime(payload: dict, output_format: str) -> None:
    if output_format == "json":
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    click.echo("Forge Runtime: SAVED")
    click.echo(f"Path: {payload['runtime_path']}")
    click.echo(f"Runtime ID: {payload['runtime_id']}")
    click.echo(f"Status: {payload['status']}")
    click.echo(f"Current stage: {payload['current_stage_id']}")


def _render_suspend_confirmation(task: str, output_format: str) -> None:
    confirmation = f'确认挂起 Forge Runtime 任务“{task}”'
    persistence_question = f'是否需要将 Forge Runtime 任务“{task}”持久化保存到当前项目？'
    payload = {
        "mode": "runtime-suspend-confirmation-required",
        "task_statement": task,
        "mutated": False,
        "persistence_question": persistence_question,
        "confirmation": confirmation,
    }
    if output_format == "json":
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    click.echo("Forge Runtime: CONFIRM SUSPEND")
    click.echo(f"Task: {task}")
    click.echo(persistence_question)


def _execute_route(root: Path, text: str, preferred_skill: Optional[str] = None) -> dict:
    """Shared routing pipeline: skill match → pack match → merge → prefer fallback."""
    skill_route = route_by_skill_triggers(root, text)
    chosen_skill_id = None
    if skill_route.get("matched") and skill_route.get("skill"):
        chosen_skill_id = skill_route["skill"].get("id")

    pack_route = route_pack(root, text, chosen_skill_id=chosen_skill_id)
    route_result = merge_skill_and_pack_route(skill_route, pack_route)

    if not route_result.get("matched") and preferred_skill:
        fallback = _build_prefer_fallback(root, text, preferred_skill)
        if fallback:
            route_result = fallback

    return route_result


def _match_native_first(root: Path, text: str) -> dict | None:
    policy = get_effective_skill_routing_config(root).get("ask_policy", {})
    native_entries = policy.get("native_first", []) if isinstance(policy, dict) else []
    normalized = text.strip().casefold()
    for entry in native_entries:
        if not isinstance(entry, dict):
            continue
        triggers = entry.get("triggers", [])
        if any(isinstance(trigger, str) and trigger.casefold() in normalized for trigger in triggers):
            return entry
    return None


def _is_forge_first_skill(root: Path, route_result: dict) -> bool:
    skill_id = ((route_result.get("skill") or {}).get("id"))
    policy = get_effective_skill_routing_config(root).get("ask_policy", {})
    forge_skills = policy.get("forge_first_skills", []) if isinstance(policy, dict) else []
    return isinstance(skill_id, str) and skill_id in forge_skills


def _build_ask_decision(text: str, route_result: dict | None = None, *, reason_code: str, reason_detail: str | None = None, native: dict | None = None, decision: str | None = None) -> dict:
    if route_result and route_result.get("matched"):
        recommendation = build_recommendation_from_route(route_result)
        return {
            **recommendation,
            "schema_version": "forge.ask-decision/v1",
            "mode": "ask",
            "input": text,
            "decision": "forge_route",
            "host_action": "use_forge_composition",
            "execution": "not_executed",
            "reason": {"code": reason_code, "detail": reason_detail},
        }
    native_payload = None
    if native:
        native_payload = {
            "id": native.get("id"),
            "skill": native.get("skill"),
            "invocation": native.get("invocation"),
            "selection_source": "ask_policy",
        }
    return {
        "schema_version": "forge.ask-decision/v1",
        "mode": "ask",
        "input": text,
        "decision": decision or ("native_route" if native else "native_fallback"),
        "host_action": "use_native_claude",
        "execution": "not_executed",
        "reason": {"code": reason_code, "detail": reason_detail},
        "matched": bool(native),
        "recommended": None,
        "native": native_payload,
        "confidence": "medium" if native else "low",
    }


def _render_ask_decision(result: dict, output_format: str) -> None:
    if output_format == "json":
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["decision"] == "forge_route":
        render_ask_text(result)
    elif result["decision"] == "explicit_skill_passthrough":
        click.echo("Forge ask: explicit skill passthrough (host-owned; not executed)")
    elif result["decision"] == "native_route":
        native = result.get("native") or {}
        click.echo(f"Forge ask: native handoff to {native.get('skill') or native.get('id')} (not executed)")
    else:
        click.echo("Forge ask: no Forge route matched; hand off to the native assistant (not executed)")


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--root", type=click.Path(file_okay=False, dir_okay=True), default=None, help="Forge root path")
@click.option("--verbose", is_flag=True, default=False, help="Enable verbose output")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
@click.pass_context
def cli(ctx, root, verbose, output_format):
    """
    forge — Modular AI Engineering Operating System CLI
    """
    ctx.ensure_object(dict)
    ctx.obj["root"] = resolve_root(root)
    ctx.obj["verbose"] = verbose or env_verbose()
    ctx.obj["format"] = output_format


@cli.command()
@click.pass_context
def version(ctx):
    """Show forge version"""
    root: Path = ctx.obj["root"]
    output_format: str = ctx.obj["format"]

    from .registry_discovery import load_project_metadata

    meta = load_project_metadata(root)
    if output_format == "json":
        click.echo(json.dumps(meta, ensure_ascii=False, indent=2))
    else:
        click.echo(f"{meta['name']} {meta['version']}")


@cli.command()
@click.option("--explain-root", is_flag=True, default=False, help="Explain the active logical Forge root without resolving a link target")
@click.pass_context
def status(ctx, explain_root):
    """Show forge health summary"""
    root: Path = ctx.obj["root"]
    output_format: str = ctx.obj["format"]

    from .registry_discovery import get_registry_json_files, get_schema_files, load_project_metadata

    meta = load_project_metadata(root)
    registry_files = get_registry_json_files(root)
    schema_files = get_schema_files(root)

    modules = list_modules_by_kind(root, "modules")
    skills = list_modules_by_kind(root, "skills")
    packs = list_modules_by_kind(root, "packs")
    workflows = list_modules_by_kind(root, "workflows")
    compositions = list_modules_by_kind(root, "compositions")

    from .checks import check_paths as _check_paths
    path_check = _check_paths(root, ctx)
    missing_count = sum(1 for m in path_check["messages"] if m["code"] == "PATH_MISSING")

    jsonschema_available = find_spec("jsonschema") is not None

    payload = {
        "project": meta,
        "root": str(root),
        "registry_files": len(registry_files),
        "registry_filenames": [p.name for p in registry_files],
        "schema_files": len(schema_files),
        "schema_filenames": [p.name for p in schema_files],
        "jsonschema_available": jsonschema_available,
        "registered_modules": len(modules),
        "skills": len(skills),
        "packs": len(packs),
        "workflows": len(workflows),
        "compositions": len(compositions),
        "quick_path_check_passed": path_check["passed"],
        "missing_paths": missing_count,
    }

    if output_format == "json":
        if explain_root:
            payload["root_diagnostic"] = {
                "logical_root": str(root),
                "link_target_reported": False,
                "guidance": "Use the linked consumer root passed through --root; Forge does not report or derive a shared source target.",
            }
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        click.echo(f"{meta['name']} {meta['version']}")
        click.echo(f"Root: {payload['root']}")
        click.echo(f"Registry files: {payload['registry_files']}")
        click.echo(f"Schema files: {payload['schema_files']}")
        click.echo(f"jsonschema available: {payload['jsonschema_available']}")
        click.echo(f"Registered modules: {payload['registered_modules']}")
        click.echo(f"Skills: {payload['skills']}")
        click.echo(f"Packs: {payload['packs']}")
        click.echo(f"Workflows: {payload['workflows']}")
        click.echo(f"Compositions: {payload['compositions']}")
        if explain_root:
            click.echo("Root diagnostic:")
            click.echo(f"  Logical root: {payload['root']}")
            click.echo("  Link target: intentionally not resolved or reported")
            click.echo("  Use the linked consumer root passed through --root")
        click.echo(f"Quick path check: {'PASS' if payload['quick_path_check_passed'] else 'FAIL'}")
        click.echo(f"Missing paths: {payload['missing_paths']}")


@cli.command()
@click.option("--quick", is_flag=True, default=False, help="Run only quick path check")
@click.option("--check", "checks", multiple=True, type=click.Choice(ALL_CHECKS), help="Run selected checks only")
@click.option("--strict", is_flag=True, default=False, help="Treat warnings as failure")
@click.option("--report", "report_path", default=None, help="Write validation report to JSON file")
@click.pass_context
def validate(ctx, quick, checks, strict, report_path):
    """Run forge validation checks"""
    root: Path = ctx.obj["root"]
    output_format: str = ctx.obj["format"]

    if quick and checks:
        raise click.UsageError("--quick cannot be used together with --check")

    if quick:
        selected_checks = [CHECK_PATHS]
    elif checks:
        selected_checks = list(checks)
    else:
        selected_checks = ALL_CHECKS

    from .checks import CHECK_RUNNERS

    results = []
    for name in selected_checks:
        runner = CHECK_RUNNERS[name]
        results.append(runner(root, ctx))

    payload = build_check_results_payload("validate", root, results, strict)
    if output_format == "json":
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        render_check_results_text("validate", root, results, strict)

    if report_path:
        write_report_file(report_path, payload)

    summary = payload["summary"]
    raise SystemExit(EXIT_OK if summary["ok"] else EXIT_VALIDATION_FAILED)


@cli.command("list")
@click.argument(
    "kind",
    type=click.Choice([
        "modules",
        "skills",
        "packs",
        "workflows",
        "compositions",
        "kernel",
        "engine",
        "runtime",
        "behaviors",
        "domains",
        "templates",
        "checklists",
        "reports",
    ]),
)
@click.pass_context
def list_cmd(ctx, kind):
    """List registry items by kind"""
    root: Path = ctx.obj["root"]
    output_format: str = ctx.obj["format"]

    items = list_modules_by_kind(root, kind)

    if output_format == "json":
        click.echo(json.dumps(items, ensure_ascii=False, indent=2))
        return

    if not items:
        click.echo(f"No items found for kind: {kind}")
        return

    for item in items:
        if isinstance(item, dict):
            item_id = item.get("id", "<no-id>")
            name = item.get("name", "")
            path = item.get("path", "")
            click.echo(f"{item_id}\t{name}\t{path}")


@cli.command("validate-output")
@click.option("--template", "template_id", required=True, help="Canonical template id, e.g. template.review_report")
@click.option("--input", "input_path", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path), help="Structured JSON output file")
@click.pass_context
def validate_output(ctx, template_id: str, input_path: Path):
    """Validate structured JSON output against a registered template contract."""
    root: Path = ctx.obj["root"]
    output_format: str = ctx.obj["format"]

    if not template_id.startswith("template."):
        raise click.UsageError("--template must use a canonical template.* id")

    from .output_validation import validate_template_output

    result = validate_template_output(root, template_id, input_path)
    if output_format == "json":
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        render_output_validation_text(result)

    raise SystemExit(EXIT_OK if result["valid"] else EXIT_VALIDATION_FAILED)




def _load_json_option(path: Path, option_name: str):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as error:
        raise click.UsageError(f"Cannot load {option_name} JSON: {path}: {error}") from error


def _runtime_manifest_from_inputs(root: Path, user_input, preferred_skill, skill_query, pack_query, behavior, workflow, template, domains, checklists):
    from .resolved_context import build_context_from_compose, build_context_from_route

    text = " ".join(user_input).strip()
    explicit_values = (skill_query, pack_query, behavior, workflow, template, *domains, *checklists)
    explicit_mode = any(value for value in explicit_values)
    if explicit_mode and text:
        raise click.UsageError("user input cannot be combined with explicit selection options")
    if preferred_skill and explicit_mode:
        raise click.UsageError("--prefer is only available when resolving user input")
    if not explicit_mode and not text:
        raise click.UsageError("provide user input or at least one explicit selection option")
    if explicit_mode:
        composed = compose_selection(root, skill_query, pack_query, behavior, workflow, template, list(domains), list(checklists))
        return build_context_from_compose(root, composed), text
    return build_context_from_route(root, _execute_route(root, text, preferred_skill)), text


@cli.command("context-bundle")
@click.option("--runtime", "runtime_path", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--bundle-id", default=None, help="Optional caller-provided Context Bundle ID")
@click.option("--max-module-bytes", default=DEFAULT_MAX_MODULE_BYTES, type=click.IntRange(min=1), show_default=True)
@click.option("--max-bundle-bytes", default=DEFAULT_MAX_BUNDLE_BYTES, type=click.IntRange(min=1), show_default=True)
@click.option("--max-estimated-tokens", default=None, type=click.IntRange(min=1), help="Optional provider-neutral token-estimate budget")
@click.option("--output", "output_path", default=None, help="Explicit JSON output path")
@click.pass_context
def context_bundle(ctx, runtime_path, bundle_id, max_module_bytes, max_bundle_bytes, max_estimated_tokens, output_path):
    """Materialize selected Markdown modules into a portable Context Bundle."""
    try:
        bundle = build_context_bundle(
            ctx.obj["root"],
            _load_json_option(runtime_path, "--runtime"),
            bundle_id=bundle_id,
            max_module_bytes=max_module_bytes,
            max_bundle_bytes=max_bundle_bytes,
            max_estimated_tokens=max_estimated_tokens,
        )
    except ValueError as error:
        raise click.UsageError(str(error)) from error
    if ctx.obj["format"] == "json":
        click.echo(json.dumps(bundle, ensure_ascii=False, indent=2))
    else:
        module_count = sum(len(layer["modules"]) for layer in bundle["layers"])
        byte_count = sum(module["byte_size"] for layer in bundle["layers"] for module in layer["modules"])
        click.echo("Context Bundle: READY")
        click.echo(f"Bundle ID: {bundle['bundle_id']}")
        click.echo(f"Runtime ID: {bundle['runtime_id']}")
        click.echo(f"Workflow: {bundle['workflow']['id']}")
        click.echo(f"Layers: {len(bundle['layers'])}")
        click.echo(f"Modules: {module_count}")
        click.echo(f"UTF-8 bytes: {byte_count}")
        if "budget" in bundle:
            budget = bundle["budget"]
            click.echo(f"Estimated tokens: {budget['included_estimated_tokens']} / {budget['max_estimated_tokens']}")
            click.echo(f"Skipped modules: {len(budget['skipped_modules'])}")
        click.echo(f"Digest: {bundle['bundle_digest']}")
    if output_path:
        write_report_file(output_path, bundle)


@cli.command("claude-code-prepare")
@click.option("--runtime", "runtime_path", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--bundle", "bundle_path", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--stage", "stage_id", default=None)
@click.option("--request-id", default=None, help="Optional caller-provided Claude Code host request ID")
@click.option("--output", "output_path", default=None, help="Explicit JSON output path")
@click.pass_context
def claude_code_prepare(ctx, runtime_path, bundle_path, stage_id, request_id, output_path):
    """Prepare an SDK-free caller-managed Claude Code host request."""
    try:
        request = build_claude_code_host_request(
            ctx.obj["root"],
            _load_json_option(runtime_path, "--runtime"),
            _load_json_option(bundle_path, "--bundle"),
            stage_id=stage_id,
            request_id=request_id,
        )
    except ValueError as error:
        raise click.UsageError(str(error)) from error
    if ctx.obj["format"] == "json":
        click.echo(json.dumps(request, ensure_ascii=False, indent=2))
    else:
        module_count = sum(1 for segment in request["prompt"]["segments"] if segment["kind"] == "stable_instruction")
        click.echo("Claude Code Host Request: READY")
        click.echo(f"Request ID: {request['request_id']}")
        click.echo(f"Runtime ID: {request['runtime']['runtime_id']}")
        click.echo(f"Stage: {request['runtime']['stage_id']}")
        click.echo(f"Prompt segments: {len(request['prompt']['segments'])}")
        click.echo(f"Stable instruction segments: {module_count}")
        click.echo(f"Prompt digest: {request['prompt']['task_prompt_digest']}")
        click.echo(f"Request digest: {request['request_digest']}")
    if output_path:
        write_report_file(output_path, request)


@cli.command("claude-code-validate-result")
@click.option("--request", "request_path", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--result", "result_path", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--output", "output_path", default=None, help="Explicit JSON output path")
@click.pass_context
def claude_code_validate_result(ctx, request_path, result_path, output_path):
    """Validate and normalize a caller-managed Claude Code host result."""
    try:
        normalized = validate_and_normalize_claude_code_host_result(
            ctx.obj["root"],
            _load_json_option(request_path, "--request"),
            _load_json_option(result_path, "--result"),
        )
    except ValueError as error:
        payload = {"command": "claude-code-validate-result", "valid": False, "errors": [str(error)]}
        if ctx.obj["format"] == "json":
            click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            click.echo(f"Claude Code Host Result: INVALID\nReason: {error}")
        raise SystemExit(EXIT_VALIDATION_FAILED)
    if ctx.obj["format"] == "json":
        click.echo(json.dumps(normalized, ensure_ascii=False, indent=2))
    else:
        click.echo("Claude Code Host Result: VALID")
        click.echo(f"Runtime ID: {normalized['runtime_id']}")
        click.echo(f"Stage: {normalized['stage_id']}")
        click.echo(f"Status: {normalized['status']}")
    if output_path:
        write_report_file(output_path, normalized)


@cli.command("runtime-init")
@click.argument("user_input", nargs=-1, required=False)
@click.option("--prefer", "preferred_skill", default=None)
@click.option("--skill", "skill_query", default=None)
@click.option("--pack", "pack_query", default=None)
@click.option("--behavior", default=None)
@click.option("--workflow", default=None)
@click.option("--template", default=None)
@click.option("--domain", "domains", multiple=True)
@click.option("--checklist", "checklists", multiple=True)
@click.option("--manifest", "manifest_path", type=click.Path(exists=True, dir_okay=False, path_type=Path), default=None)
@click.option("--task", "task_statement", default=None, help="Task statement; defaults to routed input")
@click.option("--goal", "user_goal", default=None)
@click.option("--artifact-evidence", type=click.Path(exists=True, dir_okay=False, path_type=Path), default=None)
@click.option("--output", "output_path", default=None, help="Explicit JSON output path")
@click.pass_context
def runtime_init(ctx, user_input, preferred_skill, skill_query, pack_query, behavior, workflow, template, domains, checklists, manifest_path, task_statement, user_goal, artifact_evidence, output_path):
    """Initialize a portable runtime envelope without invoking a provider."""
    root = ctx.obj["root"]
    if manifest_path:
        if any((user_input, preferred_skill, skill_query, pack_query, behavior, workflow, template, domains, checklists)):
            raise click.UsageError("--manifest cannot be combined with route or composition inputs")
        manifest = _load_json_option(manifest_path, "--manifest")
        text = ""
    else:
        manifest, text = _runtime_manifest_from_inputs(root, user_input, preferred_skill, skill_query, pack_query, behavior, workflow, template, domains, checklists)
    if not task_statement:
        task_statement = text or manifest.get("selection", {}).get("input")
    if not isinstance(task_statement, str) or not task_statement.strip():
        raise click.UsageError("--task is required when the manifest has no routed input")
    artifacts = _load_json_option(artifact_evidence, "--artifact-evidence") if artifact_evidence else None
    try:
        from .runtime_composition import initialize_runtime

        envelope = initialize_runtime(root, manifest, task_statement=task_statement, user_goal=user_goal, artifact_evidence=artifacts)
    except ValueError as error:
        raise click.UsageError(str(error)) from error
    if ctx.obj["format"] == "json":
        click.echo(json.dumps(envelope, ensure_ascii=False, indent=2))
    else:
        click.echo(f"Runtime: {envelope['status']}")
        click.echo(f"Runtime ID: {envelope['runtime_id']}")
        click.echo(f"Domains: {', '.join(envelope['runtime_state']['active_domains']) or '-'}")
    if output_path:
        write_report_file(output_path, envelope)


@cli.command("runtime-suspend")
@click.option("--task", required=True)
@click.pass_context
def runtime_suspend(ctx, task):
    """Persist one explicit project-local Forge Runtime Envelope."""
    payload = _create_suspended_runtime(ctx.obj["root"], task.strip())
    _render_suspended_runtime(payload, ctx.obj["format"])


@cli.command("runtime-consume-paused")
@click.option("--directory", "runtime_directory", required=True, type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--path", "candidate", required=True)
@click.pass_context
def runtime_consume_paused(ctx, runtime_directory, candidate):
    """Consume one user-selected current-project Runtime after handoff."""
    try:
        result = consume_paused_runtime(ctx.obj["root"], runtime_directory, candidate)
    except (ValueError, RuntimeError) as error:
        raise click.UsageError(str(error)) from error
    _render_consumed_runtime(result, ctx.obj["format"])


@cli.command("runtime-list-paused")
@click.option("--directory", "runtime_directory", required=True, type=click.Path(exists=False, file_okay=False, path_type=Path))
@click.pass_context
def runtime_list_paused(ctx, runtime_directory):
    """List resumable caller-owned Runtime Envelopes without changing them."""
    project = _project_directory(ctx.obj["root"])
    try:
        validate_project_runtime_directory(runtime_directory, project)
    except ValueError as error:
        raise click.UsageError(str(error)) from error
    migration_diagnostics = migrate_legacy_runtime_directory(project)
    result = discover_resumable_runtimes(ctx.obj["root"], runtime_directory)
    result["diagnostics"] = migration_diagnostics + result["diagnostics"]
    _render_runtime_list(result, ctx.obj["format"])


@cli.command("runtime-prepare")
@click.option("--runtime", "runtime_path", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--stage", "stage_id", default=None)
@click.option("--output", "output_path", default=None)
@click.pass_context
def runtime_prepare(ctx, runtime_path, stage_id, output_path):
    """Prepare one provider-neutral adapter request without executing it."""
    envelope = _load_json_option(runtime_path, "--runtime")
    try:
        from .runtime_composition import prepare_adapter_request

        updated = prepare_adapter_request(ctx.obj["root"], envelope, stage_id)
    except ValueError as error:
        raise click.UsageError(str(error)) from error
    if ctx.obj["format"] == "json":
        click.echo(json.dumps(updated, ensure_ascii=False, indent=2))
    else:
        click.echo(f"Runtime: {updated['status']}")
        click.echo(f"Stage: {updated['adapter_request']['stage_id']}")
    if output_path:
        write_report_file(output_path, updated)


@cli.command("runtime-import-result")
@click.option("--runtime", "runtime_path", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--result", "result_path", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--output", "output_path", default=None)
@click.pass_context
def runtime_import_result(ctx, runtime_path, result_path, output_path):
    """Import a normalized external adapter result without provider execution."""
    try:
        from .runtime_composition import import_adapter_result

        updated = import_adapter_result(ctx.obj["root"], _load_json_option(runtime_path, "--runtime"), _load_json_option(result_path, "--result"))
    except ValueError as error:
        raise click.UsageError(str(error)) from error
    if ctx.obj["format"] == "json":
        click.echo(json.dumps(updated, ensure_ascii=False, indent=2))
    else:
        click.echo(f"Runtime: {updated['status']}")
    if output_path:
        write_report_file(output_path, updated)


@cli.command("runtime-advance")
@click.option("--runtime", "runtime_path", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--action", required=True, type=click.Choice(["next", "retry", "abort"], case_sensitive=False))
@click.option("--output", "output_path", default=None)
@click.pass_context
def runtime_advance(ctx, runtime_path, action, output_path):
    """Explicitly advance, retry, or abort after an imported adapter result."""
    try:
        from .runtime_composition import advance_runtime

        updated = advance_runtime(ctx.obj["root"], _load_json_option(runtime_path, "--runtime"), action)
    except ValueError as error:
        raise click.UsageError(str(error)) from error
    if ctx.obj["format"] == "json":
        click.echo(json.dumps(updated, ensure_ascii=False, indent=2))
    else:
        click.echo(f"Runtime: {updated['status']}")
        if updated["status"] == "ready":
            click.echo(f"Next stage: {updated['stage_progress']['workflow_stages'][updated['stage_progress']['current_stage_index']]}")
    if output_path:
        write_report_file(output_path, updated)

@cli.command("validate-runtime-output")
@click.option("--runtime", "runtime_path", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--input", "input_path", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--output", "output_path", default=None)
@click.pass_context
def validate_runtime_output_cmd(ctx, runtime_path, input_path, output_path):
    """Validate structured output against the runtime-selected template."""
    from .runtime_output_validation import validate_runtime_output

    result = validate_runtime_output(ctx.obj["root"], _load_json_option(runtime_path, "--runtime"), _load_json_option(input_path, "--input"))
    if ctx.obj["format"] == "json":
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        render_output_validation_text(result)
    if output_path:
        write_report_file(output_path, result)
    raise SystemExit(EXIT_OK if result["valid"] else EXIT_VALIDATION_FAILED)


@cli.command()
@click.argument(
    "item_type",
    type=click.Choice([
        "skill",
        "pack",
        "workflow",
        "composition",
        "module",
        "behavior",
        "domain",
        "template",
        "checklist",
        "report",
    ]),
)
@click.argument("query")
@click.pass_context
def show(ctx, item_type, query):
    """Show one registry item"""
    root: Path = ctx.obj["root"]
    output_format: str = ctx.obj["format"]

    mapping = {
        "skill": "skills",
        "pack": "packs",
        "workflow": "workflows",
        "composition": "compositions",
        "module": "modules",
        "behavior": "behaviors",
        "domain": "domains",
        "template": "templates",
        "checklist": "checklists",
        "report": "reports",
    }

    kind = mapping[item_type]
    item = find_item(root, kind, query)

    if not item:
        click.echo(f"Item not found: type={item_type}, query={query}", err=True)
        raise SystemExit(EXIT_GENERAL_ERROR)

    if output_format == "json":
        click.echo(json.dumps(item, ensure_ascii=False, indent=2))
    else:
        # Render every field present in the entry, one per line, so `show`
        # actually surfaces what the registry declares (behavior, workflow,
        # triggers, routing, etc.) — not just id/name/path. Keys are sorted
        # for stable, diff-friendly output; values are JSON-encoded so lists
        # and nested objects stay on one readable line.
        if not isinstance(item, dict):
            click.echo(str(item))
        else:
            for key in sorted(item.keys()):
                value = item.get(key)
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)
                click.echo(f"{key}: {value if value is not None else '-'}")


@cli.command()
@click.argument("user_input", nargs=-1, required=True)
@click.option("--prefer", "preferred_skill", default=None, help="Preferred skill to fallback when routing fails")
@click.pass_context
def route(ctx, user_input, preferred_skill):
    """Route user input to the best matching skill/pack"""
    output_format: str = ctx.obj["format"]
    root: Path = ctx.obj["root"]

    text = " ".join(user_input).strip()
    if not text:
        raise click.UsageError("user_input cannot be empty")

    route_result = _execute_route(root, text, preferred_skill)

    if output_format == "json":
        click.echo(json.dumps(route_result, ensure_ascii=False, indent=2))
    else:
        render_route_text(route_result)

    raise SystemExit(EXIT_OK if route_result.get("matched") else EXIT_GENERAL_ERROR)


@cli.command()
@click.option("--skill", "skill_query", default=None, help="Skill id or name")
@click.option("--pack", "pack_query", default=None, help="Pack id or name")
@click.option("--behavior", default=None, help="Override behavior id")
@click.option("--workflow", default=None, help="Override workflow id")
@click.option("--template", default=None, help="Override template id")
@click.option("--domain", "domains", multiple=True, help="Additional domain ids")
@click.option("--checklist", "checklists", multiple=True, help="Additional checklist ids")
@click.pass_context
def compose(ctx, skill_query, pack_query, behavior, workflow, template, domains, checklists):
    """Compose a final module selection explicitly"""
    output_format: str = ctx.obj["format"]
    root: Path = ctx.obj["root"]

    result = compose_selection(
        root=root,
        skill_query=skill_query,
        pack_query=pack_query,
        behavior=behavior,
        workflow=workflow,
        template=template,
        domains=list(domains),
        checklists=list(checklists),
    )

    if output_format == "json":
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        render_compose_text(result)


@cli.command("registry-sync")
@click.option("--check", "check_only", is_flag=True, default=False, help="Check derived module registry identities without writing")
@click.option("--write", "write", is_flag=True, default=False, help="Write synchronized modules.json identities")
@click.pass_context
def registry_sync(ctx, check_only, write):
    """Check or explicitly synchronize derived modules.json layer identities."""
    from .registry_generation import derived_registry_issues, write_synced_modules

    if check_only == write:
        raise click.UsageError("provide exactly one of --check or --write")
    root: Path = ctx.obj["root"]
    output_format: str = ctx.obj["format"]
    issues = derived_registry_issues(root) if check_only else write_synced_modules(root)
    payload = {"mode": "registry-sync", "action": "check" if check_only else "write", "ok": not issues, "issues": issues}

    if output_format == "json":
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    elif issues:
        click.echo("Registry sync: DRIFT")
        for issue in issues:
            click.echo(f"- {issue['code']}: {issue['message']}")
    else:
        click.echo("Registry sync: OK")

    raise SystemExit(EXIT_OK if not issues else EXIT_VALIDATION_FAILED)


@cli.command()
@click.argument("user_input", nargs=-1, required=False)
@click.option("--prefer", "preferred_skill", default=None, help="Preferred skill to fallback when routing fails")
@click.option("--skill", "skill_query", default=None, help="Explicit skill id or name")
@click.option("--pack", "pack_query", default=None, help="Explicit pack id or name")
@click.option("--behavior", default=None, help="Explicit behavior override")
@click.option("--workflow", default=None, help="Explicit workflow override")
@click.option("--template", default=None, help="Explicit template override")
@click.option("--domain", "domains", multiple=True, help="Additional domain ids")
@click.option("--checklist", "checklists", multiple=True, help="Additional checklist ids")
@click.pass_context
def resolve(ctx, user_input, preferred_skill, skill_query, pack_query, behavior, workflow, template, domains, checklists):
    """Resolve routed or explicit selection into a read-only context manifest."""
    from .resolved_context import build_context_from_compose, build_context_from_route

    root: Path = ctx.obj["root"]
    output_format: str = ctx.obj["format"]
    text = " ".join(user_input).strip()
    explicit_values = (skill_query, pack_query, behavior, workflow, template, *domains, *checklists)
    explicit_mode = any(value for value in explicit_values)

    if explicit_mode and text:
        raise click.UsageError("user input cannot be combined with explicit selection options")
    if preferred_skill and explicit_mode:
        raise click.UsageError("--prefer is only available when resolving user input")
    if not explicit_mode and not text:
        raise click.UsageError("provide user input or at least one explicit selection option")

    if explicit_mode:
        compose_result = compose_selection(
            root=root,
            skill_query=skill_query,
            pack_query=pack_query,
            behavior=behavior,
            workflow=workflow,
            template=template,
            domains=list(domains),
            checklists=list(checklists),
        )
        result = build_context_from_compose(root, compose_result)
    else:
        result = build_context_from_route(root, _execute_route(root, text, preferred_skill))

    if output_format == "json":
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        render_resolved_context_text(result)

    raise SystemExit(EXIT_OK if result["resolution"]["ok"] else EXIT_GENERAL_ERROR)


@cli.command()
@click.argument("user_input", nargs=-1, required=True)
@click.option("--prefer", "preferred_skill", default=None, help="Preferred skill to fallback when routing fails")
@click.pass_context
def recommend(ctx, user_input, preferred_skill):
    """Recommend a final composition from natural language input"""
    output_format: str = ctx.obj["format"]
    root: Path = ctx.obj["root"]

    text = " ".join(user_input).strip()
    if not text:
        raise click.UsageError("user_input cannot be empty")

    route_result = _execute_route(root, text, preferred_skill)
    result = build_recommendation_from_route(route_result)

    if output_format == "json":
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        render_recommend_text(result)

    raise SystemExit(EXIT_OK if result.get("matched") else EXIT_GENERAL_ERROR)


@cli.command()
@click.argument("user_input", nargs=-1, required=True)
@click.option("--prefer", "preferred_skill", default=None, help="Preferred skill to fallback when routing fails")
@click.pass_context
def ask(ctx, user_input, preferred_skill):
    """Lightweight natural-language entrypoint — route + recommend in one step"""
    output_format: str = ctx.obj["format"]
    root: Path = ctx.obj["root"]

    text = " ".join(user_input).strip()
    if not text:
        raise click.UsageError("user_input cannot be empty")

    learning_intent = _learning_review_intent(text)
    if learning_intent:
        from .learning_review_service import start_review_service, stop_review_service
        try:
            payload = start_review_service(root) if learning_intent == "start" else stop_review_service(root)
        except RuntimeError as error:
            raise click.UsageError(str(error)) from error
        _render_learning_review(payload, output_format)
        raise SystemExit(EXIT_OK)

    intent = _runtime_ask_intent(text)
    if intent:
        action, value = intent
        runtime_directory = _project_runtime_directory(root)
        if action == "suspend_confirmation_required":
            _render_suspend_confirmation(value or "", output_format)
        elif action == "suspend":
            payload = _create_suspended_runtime(root, value or "")
            _render_suspended_runtime(payload, output_format)
        elif action == "list":
            _render_runtime_list(discover_resumable_runtimes(root, runtime_directory), output_format)
        elif action == "consume":
            try:
                payload = consume_paused_runtime(root, runtime_directory, value or "")
            except (ValueError, RuntimeError) as error:
                raise click.UsageError(str(error)) from error
            _render_consumed_runtime(payload, output_format)
        else:
            raise click.UsageError(f"unsupported Runtime intent: {action}")
        raise SystemExit(EXIT_OK)

    stripped = text.strip()
    if stripped.startswith("/"):
        result = _build_ask_decision(
            text,
            reason_code="explicit_skill",
            decision="explicit_skill_passthrough",
        )
        _render_ask_decision(result, output_format)
        raise SystemExit(EXIT_OK)

    native = _match_native_first(root, text)
    if native:
        result = _build_ask_decision(
            text,
            reason_code=native.get("reason_code", "native_specialist_matched"),
            reason_detail=native.get("id"),
            native=native,
        )
        _render_ask_decision(result, output_format)
        raise SystemExit(EXIT_OK)

    route_result = _execute_route(root, text, preferred_skill)
    if route_result.get("matched") and _is_forge_first_skill(root, route_result):
        result = _build_ask_decision(text, route_result, reason_code="forge_skill_matched")
    else:
        result = _build_ask_decision(
            text,
            reason_code="no_forge_match",
            reason_detail="No registered Forge skill matched this request; the native assistant should handle it.",
        )
    _render_ask_decision(result, output_format)
    raise SystemExit(EXIT_OK)


@cli.command()
@click.option("--report", "report_path", default=None, help="Write doctor report to JSON file")
@click.pass_context
def doctor(ctx, report_path):
    """Run a health-oriented validation summary"""
    root: Path = ctx.obj["root"]
    output_format: str = ctx.obj["format"]

    from .checks import CHECK_RUNNERS

    selected_checks = [CHECK_REGISTRY, CHECK_PATHS, CHECK_REFS]
    results = [CHECK_RUNNERS[name](root, ctx) for name in selected_checks]

    payload = build_check_results_payload("doctor", root, results, strict=False)
    if output_format == "json":
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        render_check_results_text("doctor", root, results, strict=False)

    if report_path:
        write_report_file(report_path, payload)

    summary = payload["summary"]
    raise SystemExit(EXIT_OK if summary["ok"] else EXIT_VALIDATION_FAILED)


def main():
    try:
        cli(obj={})
    except click.UsageError as e:
        click.echo(f"Usage error: {e}", err=True)
        raise SystemExit(EXIT_USAGE_ERROR)
