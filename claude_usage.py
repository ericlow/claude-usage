#!/usr/bin/env python3
"""
claude_usage.py — Break down Claude Code cost by tool call.

Usage:
    claude-usage-tool today        # current day
    claude-usage-tool week         # last 7 days
    claude-usage-tool month        # last 30 days
    claude-usage-tool 3months      # last 3 months
    claude-usage-tool session      # most recent session only
    claude-usage-tool path/to/session.jsonl  # specific session file

Output: overview (by model + by project), then detail blocks for each.
Prices are per million tokens (API-equivalent rates, not subscription cost).
"""

import json
import os
import sys

if sys.version_info < (3, 10):
    sys.exit("claude_usage_by_tool requires Python 3.10 or later.")

from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Per-model pricing ($/million tokens). Cache write has 5-min and 1-hour tiers.
# Source: platform.claude.com/docs/en/about-claude/pricing (June 2026)
MODEL_PRICES = {
    'claude-haiku-4-5':  {'input': 1.00,  'output': 5.00,  'cache_read': 0.10,  'cache_write_5m': 1.25,  'cache_write_1h': 2.00},
    'claude-sonnet-4-6': {'input': 3.00,  'output': 15.00, 'cache_read': 0.30,  'cache_write_5m': 3.75,  'cache_write_1h': 6.00},
    'claude-opus-4-7':   {'input': 5.00,  'output': 25.00, 'cache_read': 0.50,  'cache_write_5m': 6.25,  'cache_write_1h': 10.00},
    'claude-opus-4-8':   {'input': 5.00,  'output': 25.00, 'cache_read': 0.50,  'cache_write_5m': 6.25,  'cache_write_1h': 10.00},
}
DEFAULT_PRICES = MODEL_PRICES['claude-sonnet-4-6']

PERIODS = {
    'today':   0,
    'week':    6,
    'month':  29,
    '3months': 89,
}

BAR_WIDTH = 20
MIN_PROJECT_PCT = 1.0


def trunc(name: str, max_len: int) -> str:
    return name if len(name) <= max_len else name[:max_len - 3] + '...'


def get_prices(model: str) -> dict:
    if model in MODEL_PRICES:
        return MODEL_PRICES[model]
    for key in MODEL_PRICES:
        if key in model:
            return MODEL_PRICES[key]
    return DEFAULT_PRICES


def entry_cost(usage: dict, prices: dict) -> float:
    cache_creation = usage.get('cache_creation', {})
    cache_5m = cache_creation.get('ephemeral_5m_input_tokens', 0)
    cache_1h = cache_creation.get('ephemeral_1h_input_tokens', 0)
    if not cache_5m and not cache_1h:
        cache_5m = usage.get('cache_creation_input_tokens', 0)
    return (
        usage.get('input_tokens', 0) / 1e6 * prices['input'] +
        usage.get('output_tokens', 0) / 1e6 * prices['output'] +
        usage.get('cache_read_input_tokens', 0) / 1e6 * prices['cache_read'] +
        cache_5m / 1e6 * prices['cache_write_5m'] +
        cache_1h / 1e6 * prices['cache_write_1h']
    )


def extract_project_name(cwd: str) -> str:
    """Extract project name from the cwd field in a JSONL entry."""
    return Path(cwd).name if cwd else 'unknown'


def parse_entries(path: str) -> list[dict]:
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


def _empty_bucket() -> dict:
    return {
        'tool_costs': defaultdict(lambda: {'calls': 0, 'cost': 0.0, 'cache_created': 0}),
        'no_tool_cost': 0.0,
        'total_cost': 0.0,
    }


def analyze_entries(entries: list[dict], since: datetime | None) -> tuple[dict, dict]:
    """
    Returns (by_model, by_project).
    Each is a dict keyed by name → { tool_costs, no_tool_cost, total_cost }.
    by_project additionally has a 'models' sub-dict: { model_name: cost }.
    """
    by_model: dict[str, dict] = {}
    by_project: dict[str, dict] = {}

    for entry in entries:
        if entry.get('type') != 'assistant':
            continue
        msg = entry.get('message', {})
        usage = msg.get('usage', {})
        if not usage:
            continue

        if since:
            ts = entry.get('timestamp')
            if ts:
                try:
                    entry_time = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    if entry_time < since:
                        continue
                except (ValueError, AttributeError):
                    pass

        model = msg.get('model', 'unknown')
        project = extract_project_name(entry.get('cwd', ''))
        prices = get_prices(model)

        if model not in by_model:
            by_model[model] = _empty_bucket()
        if project not in by_project:
            by_project[project] = {**_empty_bucket(), 'models': defaultdict(float)}

        tools_called = [
            b['name'] for b in msg.get('content', [])
            if isinstance(b, dict) and b.get('type') == 'tool_use'
        ]

        c = entry_cost(usage, prices)
        cc = usage.get('cache_creation_input_tokens', 0)

        by_model[model]['total_cost'] += c
        by_project[project]['total_cost'] += c
        by_project[project]['models'][model] += c

        if tools_called:
            split = c / len(tools_called)
            cc_split = cc // len(tools_called)
            for t in tools_called:
                for bucket in (by_model[model], by_project[project]):
                    bucket['tool_costs'][t]['calls'] += 1
                    bucket['tool_costs'][t]['cost'] += split
                    bucket['tool_costs'][t]['cache_created'] += cc_split
        else:
            by_model[model]['no_tool_cost'] += c
            by_project[project]['no_tool_cost'] += c

    return by_model, by_project


def bar(pct: float) -> str:
    filled = round(pct / 100 * BAR_WIDTH)
    return '█' * filled + '░' * (BAR_WIDTH - filled)


def print_overview(by_model: dict, by_project: dict, label: str) -> None:
    grand_total = sum(m['total_cost'] for m in by_model.values())

    print(f"\n{'━' * 72}")
    print(f"  {label}  —  Total: ${grand_total:.4f}  (API-equivalent)")
    print(f"{'━' * 72}")

    print(f"\n  BY MODEL")
    print(f"  {'─' * 60}")
    print(f"  {'Model':<30} {'Cost':>9}  {'%':>5}")
    for model, data in sorted(by_model.items(), key=lambda x: -x[1]['total_cost']):
        pct = data['total_cost'] / grand_total * 100 if grand_total else 0
        print(f"  {trunc(model, 30):<30} ${data['total_cost']:>8.4f}  {pct:>4.1f}%  {bar(pct)}")

    print(f"\n  BY PROJECT")
    print(f"  {'─' * 60}")
    print(f"  {'Project':<30} {'Cost':>9}  {'%':>5}")
    hidden = 0
    for project, data in sorted(by_project.items(), key=lambda x: -x[1]['total_cost']):
        pct = data['total_cost'] / grand_total * 100 if grand_total else 0
        if pct < MIN_PROJECT_PCT:
            hidden += 1
            continue
        model_hints = ', '.join(
            m.replace('claude-', '').replace('-4-8', '').replace('-4-7', '')
             .replace('-4-6', '').replace('-4-5', '')
            for m in sorted(data['models'], key=lambda m: -data['models'][m])
        )
        print(f"  {trunc(project, 30):<30} ${data['total_cost']:>8.4f}  {pct:>4.1f}%  {bar(pct)}  [{model_hints}]")
    if hidden:
        print(f"  {'(< 1% hidden)':<30}  {hidden} project{'s' if hidden > 1 else ''}")
    print()


def _print_tool_rows(tool_costs: dict, no_tool_cost: float, total: float) -> None:
    for name, d in sorted(tool_costs.items(), key=lambda x: -x[1]['cost']):
        marker = " *" if name.startswith('mcp__') else ""
        tool_pct = d['cost'] / total * 100 if total else 0
        print(f"  │  {trunc(name+marker, 36):<36} {d['calls']:>5} {d['cache_created']:>12,}  ${d['cost']:.4f}  {tool_pct:>4.1f}%")
    print(f"  │  {'-' * 68}")
    no_pct = no_tool_cost / total * 100 if total else 0
    print(f"  │  {'(text responses)':<36} {'':>5} {'':>14} ${no_tool_cost:.4f}  {no_pct:>4.1f}%")


def print_model_detail(model: str, data: dict, grand_total: float) -> None:
    tool_costs = data['tool_costs']
    model_total = data['total_cost']
    pct = model_total / grand_total * 100 if grand_total else 0
    mcp_cost = sum(d['cost'] for n, d in tool_costs.items() if n.startswith('mcp__'))

    print(f"  ┌─ {model}  ${model_total:.4f}  ({pct:.1f}% of total)")
    print(f"  │")
    print(f"  │  {'Tool':<36} {'Calls':>5} {'Cache created':>14} {'Cost':>8}")
    print(f"  │  {'-' * 68}")
    _print_tool_rows(tool_costs, data['no_tool_cost'], model_total)
    if mcp_cost:
        print(f"  │")
        print(f"  │  * MCP tools: ${mcp_cost:.4f}  ({mcp_cost/model_total*100:.1f}% of this model)")
    print(f"  └{'─' * 70}")
    print()


def print_project_detail(project: str, data: dict, grand_total: float) -> None:
    tool_costs = data['tool_costs']
    project_total = data['total_cost']
    pct = project_total / grand_total * 100 if grand_total else 0
    mcp_cost = sum(d['cost'] for n, d in tool_costs.items() if n.startswith('mcp__'))

    print(f"  ┌─ {project}  ${project_total:.4f}  ({pct:.1f}% of total)")
    print(f"  │")

    # Mini model bar chart
    print(f"  │  {'Model':<28} {'Cost':>9}  {'%':>5}")
    print(f"  │  {'─' * 50}")
    for model, mcost in sorted(data['models'].items(), key=lambda x: -x[1]):
        mpct = mcost / project_total * 100 if project_total else 0
        short = model.replace('claude-', '')
        print(f"  │  {trunc(short, 28):<28} ${mcost:>8.4f}  {mpct:>4.1f}%  {bar(mpct)}")

    print(f"  │")
    print(f"  │  {'Tool':<36} {'Calls':>5} {'Cache created':>14} {'Cost':>8}")
    print(f"  │  {'-' * 68}")
    _print_tool_rows(tool_costs, data['no_tool_cost'], project_total)
    if mcp_cost:
        print(f"  │")
        print(f"  │  * MCP tools: ${mcp_cost:.4f}  ({mcp_cost/project_total*100:.1f}% of this project)")
    print(f"  └{'─' * 70}")
    print()


def print_report(by_model: dict, by_project: dict, label: str, view: str = 'model') -> None:
    if not by_model:
        print(f"\n{label}\n  No data found.")
        return

    grand_total = sum(m['total_cost'] for m in by_model.values())
    print_overview(by_model, by_project, label)

    if view == 'project':
        print(f"  {'─' * 70}")
        print(f"  Detail by project")
        print(f"  {'─' * 70}\n")
        for project, data in sorted(by_project.items(), key=lambda x: -x[1]['total_cost']):
            pct = data['total_cost'] / grand_total * 100 if grand_total else 0
            if pct < MIN_PROJECT_PCT:
                continue
            print_project_detail(project, data, grand_total)
    else:
        print(f"  {'─' * 70}")
        print(f"  Detail by model")
        print(f"  {'─' * 70}\n")
        for model, data in sorted(by_model.items(), key=lambda x: -x[1]['total_cost']):
            print_model_detail(model, data, grand_total)

    print(f"  Note: costs are API-equivalent estimates. Pro/Max users pay a flat monthly fee.")


def all_jsonl_files() -> list[str]:
    projects_dir = Path.home() / '.claude' / 'projects'
    return list(str(p) for p in projects_dir.rglob('*.jsonl'))


def latest_session() -> str:
    files = all_jsonl_files()
    if not files:
        print("No session files found in ~/.claude/projects/", file=sys.stderr)
        sys.exit(1)
    return max(files, key=os.path.getmtime)


def run_period(period_days: int | None, label: str, view: str = 'model') -> None:
    since = None
    if period_days is not None:
        local_midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        since = local_midnight.astimezone(timezone.utc) - timedelta(days=period_days)

    all_entries = []
    for path in all_jsonl_files():
        try:
            all_entries.extend(parse_entries(path))
        except Exception:
            pass

    by_model, by_project = analyze_entries(all_entries, since)
    print_report(by_model, by_project, label, view)


def run_file(path: str, view: str = 'model') -> None:
    try:
        entries = parse_entries(path)
    except FileNotFoundError:
        print(f"File not found: {path}", file=sys.stderr)
        sys.exit(1)
    by_model, by_project = analyze_entries(entries, since=None)
    print_report(by_model, by_project, f"Session: {path}", view)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: claude-usage-tool <period> [project]  or  claude-usage-tool <path/to/session.jsonl> [project]")
        print()
        print("  Periods:")
        print("    today    — current day")
        print("    week     — last 7 days")
        print("    month    — last 30 days")
        print("    3months  — last 3 months")
        print("    session  — most recent session only")
        print()
        print("  Views (optional second argument):")
        print("    model    — detail by model, tools per model (default)")
        print("    project  — detail by project, with per-project model + tool breakdown")
        print()
        print("Examples:")
        print("  claude-usage-tool week")
        print("  claude-usage-tool month project")
        sys.exit(0)

    arg = sys.argv[1]
    view = sys.argv[2] if len(sys.argv) > 2 else 'model'
    if view not in ('model', 'project'):
        print(f"Unknown view: {view!r}  (expected 'model' or 'project')")
        sys.exit(1)

    if arg == 'session':
        run_file(latest_session(), view)
    elif arg in PERIODS:
        days = PERIODS[arg]
        label = {'today': 'Today', 'week': 'Last 7 days', 'month': 'Last 30 days', '3months': 'Last 3 months'}[arg]
        run_period(days, label, view)
    elif os.path.exists(arg):
        run_file(arg, view)
    else:
        print(f"Unknown argument: {arg!r}")
        print("Run claude-usage-tool with no arguments for usage info.")
        sys.exit(1)
