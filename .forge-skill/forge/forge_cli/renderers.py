# -*- coding: utf-8 -*-
"""Forge CLI — output renderers for text and JSON formats."""

import json
from pathlib import Path
from typing import Any, Dict, List

import click

from .result_builders import summarize_checks


def render_check_results_text(command: str, root: Path, checks: List[Dict[str, Any]], strict: bool):
    summary = summarize_checks(checks, strict=strict)

    click.echo(f"Command: {command}")
    click.echo(f"Root: {root}")
    click.echo("")

    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        click.echo(f"[{status}] {check['name']} ({check['duration_ms']} ms)")
        for msg in check["messages"]:
            line = f"  - {msg['level'].upper()} {msg['code']}: {msg['message']}"
            click.echo(line)
            if msg.get("details") and msg["level"] in ("error", "warning"):
                click.echo(f"      details: {msg['details']}")

    click.echo("")
    click.echo(
        f"Summary: ok={summary['ok']}, total_checks={summary['total_checks']}, "
        f"warnings={summary['warning_count']}, errors={summary['error_count']}, strict={summary['strict']}"
    )
    return summary


def build_check_results_payload(command: str, root: Path, checks: List[Dict[str, Any]], strict: bool) -> Dict[str, Any]:
    summary = summarize_checks(checks, strict=strict)
    return {
        "command": command,
        "root": str(root),
        "checks": checks,
        "summary": summary,
    }


def write_report_file(path: str, payload: Dict[str, Any]) -> None:
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def write_report_file_exclusive(path: str | Path, payload: Dict[str, Any]) -> None:
    """Create a JSON report once without overwriting a concurrent writer."""
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "x", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)



def render_output_validation_text(result: Dict[str, Any]):
    status = "VALID" if result.get("valid") else "INVALID"
    click.echo(f"Output contract: {status}")
    click.echo(f"Template: {result.get('template_id')}")
    click.echo(f"Input: {result.get('input_path')}")
    click.echo(f"Schema: {result.get('schema_path') or '-'}")
    for error in result.get("errors", []):
        click.echo(f"  - {error.get('code')}: {error.get('message')}")
        details = error.get("details")
        if details:
            click.echo(f"      details: {details}")
        if error.get("path") or error.get("schema_path"):
            click.echo(f"      path: {error.get('path', '$')} schema: {error.get('schema_path', '$')}")


def render_compose_text(result: Dict[str, Any]):
    click.echo("Compose: OK")
    click.echo(f"Skill: {result.get('skill')}")
    click.echo(f"Pack: {result.get('pack')}")
    click.echo(f"Behavior: {result.get('behavior')}")
    click.echo(f"Workflow: {result.get('workflow')}")
    click.echo(f"Template: {result.get('template')}")
    click.echo(f"Domains: {', '.join(result.get('domains', [])) if result.get('domains') else '-'}")
    click.echo(f"Checklists: {', '.join(result.get('checklists', [])) if result.get('checklists') else '-'}")

    warnings = result.get("warnings", [])
    if warnings:
        click.echo("Warnings:")
        for warning in warnings:
            click.echo(f"  - {warning}")

    sources = result.get("sources", {})
    if sources:
        click.echo("Sources:")
        for k, v in sources.items():
            click.echo(f"  - {k}: {v}")


def render_recommend_text(result: Dict[str, Any]):
    if not result.get("matched"):
        click.echo("Recommend: NO MATCH")
        click.echo(f"Input: {result.get('input')}")
        click.echo(f"Reason: {result.get('reason')}")
        click.echo(f"Confidence: {result.get('confidence')}")
        return

    rec = result.get("recommended") or {}
    click.echo("Recommend: OK")
    click.echo(f"Input: {result.get('input')}")
    click.echo(f"Confidence: {result.get('confidence')}")
    click.echo(f"Strategy: {result.get('strategy')}")
    click.echo(f"Skill: {rec.get('skill')}")
    click.echo(f"Variant: {rec.get('variant') or '-'}")
    click.echo(f"Pack: {rec.get('pack')}")
    click.echo(f"Behavior: {rec.get('behavior')}")
    click.echo(f"Workflow: {rec.get('workflow')}")
    click.echo(f"Template: {rec.get('template')}")
    click.echo(f"Domains: {', '.join(rec.get('domains', [])) if rec.get('domains') else '-'}")
    click.echo(f"Checklists: {', '.join(rec.get('checklists', [])) if rec.get('checklists') else '-'}")


def render_resolved_context_text(result: Dict[str, Any]):
    status = "RESOLVED" if result.get("resolution", {}).get("ok") else "INCOMPLETE"
    click.echo(f"Context: {status}")
    click.echo(f"Mode: {result.get('mode')}")
    selection = result.get("selection", {})
    click.echo(f"Skill: {selection.get('skill') or '-'}")
    click.echo(f"Pack: {selection.get('pack') or '-'}")
    click.echo(f"Workflow: {selection.get('workflow') or '-'}")

    for layer, items in result.get("context", {}).items():
        if not items:
            continue
        click.echo(f"{layer.title()}:")
        for item in items:
            path = item.get("resolved_path") or item.get("declared_path") or "-"
            click.echo(f"  - {item.get('id')} — {path}")

    resolution = result.get("resolution", {})
    for error in resolution.get("errors", []):
        click.echo(f"Error: {error.get('code')}: {error.get('message')}")
    for warning in resolution.get("warnings", []):
        click.echo(f"Warning: {warning}")


def render_ask_text(result: Dict[str, Any]):
    if not result.get("matched"):
        click.echo("No clear handling suggestion.")
        click.echo(f"Input: {result.get('input')}")
        click.echo(f"Reason: {result.get('reason')}")
        click.echo(f"Confidence: {result.get('confidence')}")
        return

    rec = result.get("recommended") or {}

    click.echo("Suggested handling:")
    click.echo(f"- Skill: {rec.get('skill')}")
    click.echo(f"- Variant: {rec.get('variant') or '-'}")
    click.echo(f"- Pack: {rec.get('pack') or '-'}")
    click.echo(f"- Behavior: {rec.get('behavior') or '-'}")
    click.echo(f"- Workflow: {rec.get('workflow') or '-'}")
    click.echo(f"- Template: {rec.get('template') or '-'}")

    domains = rec.get("domains", [])
    checklists = rec.get("checklists", [])

    click.echo(f"- Domains: {', '.join(domains) if domains else '-'}")
    click.echo(f"- Checklists: {', '.join(checklists) if checklists else '-'}")

    click.echo("")
    click.echo("Why:")
    click.echo(f"- strategy: {result.get('strategy')}")
    click.echo(f"- confidence: {result.get('confidence')}")

    evidence = result.get("evidence", [])
    pack_evidence = result.get("pack_evidence", [])

    if evidence:
        for e in evidence[:5]:
            click.echo(f"- evidence: {e.get('type')} = {e.get('value')}")

    if pack_evidence:
        for e in pack_evidence[:5]:
            click.echo(f"- pack evidence: {e.get('type')} = {e.get('value')}")
