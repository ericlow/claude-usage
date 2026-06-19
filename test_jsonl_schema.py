"""
Schema validation tests for Claude Code JSONL transcript files.

These tests read REAL data from ~/.claude/projects/ and assert the exact
structure that claude_usage.py depends on. If Anthropic changes the
format, these tests fail loudly instead of the tool silently producing wrong numbers.

Run with:
    python3 -m pytest test_jsonl_schema.py -v
"""

import json
import os
from pathlib import Path
import pytest

PROJECTS_DIR = Path.home() / '.claude' / 'projects'


# ── Fixtures ──────────────────────────────────────────────────────────────────

def load_all_entries() -> list[dict]:
    entries = []
    for path in PROJECTS_DIR.rglob('*.jsonl'):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    return entries


@pytest.fixture(scope='module')
def all_entries():
    entries = load_all_entries()
    assert entries, "No JSONL entries found — is ~/.claude/projects/ populated?"
    return entries


@pytest.fixture(scope='module')
def assistant_entries(all_entries):
    entries = [e for e in all_entries if e.get('type') == 'assistant']
    assert entries, "No assistant entries found in JSONL files"
    return entries


@pytest.fixture(scope='module')
def entries_with_usage(assistant_entries):
    entries = [e for e in assistant_entries if e.get('message', {}).get('usage')]
    assert entries, "No assistant entries with usage data found"
    return entries


@pytest.fixture(scope='module')
def entries_with_tools(assistant_entries):
    def has_tool(e):
        return any(
            b.get('type') == 'tool_use'
            for b in e.get('message', {}).get('content', [])
        )
    entries = [e for e in assistant_entries if has_tool(e)]
    assert entries, "No assistant entries with tool calls found"
    return entries


@pytest.fixture(scope='module')
def entries_with_cache_breakdown(entries_with_usage):
    entries = [
        e for e in entries_with_usage
        if e['message']['usage'].get('cache_creation')
    ]
    assert entries, "No entries with cache_creation breakdown found"
    return entries


# ── Top-level entry structure ─────────────────────────────────────────────────

def test_assistant_entries_have_type_field(assistant_entries):
    for e in assistant_entries:
        assert e['type'] == 'assistant'

def test_assistant_entries_have_timestamp(assistant_entries):
    missing = [e for e in assistant_entries if not e.get('timestamp')]
    assert not missing, f"{len(missing)} assistant entries missing 'timestamp'"

def test_timestamp_is_iso8601_with_z(assistant_entries):
    from datetime import datetime
    bad = []
    for e in assistant_entries:
        ts = e.get('timestamp', '')
        try:
            datetime.fromisoformat(ts.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            bad.append(ts)
    assert not bad, f"Non-ISO timestamps found: {bad[:5]}"

def test_assistant_entries_have_message(assistant_entries):
    missing = [e for e in assistant_entries if 'message' not in e]
    assert not missing, f"{len(missing)} assistant entries missing 'message'"

def test_assistant_entries_have_cwd(assistant_entries):
    """cwd is used for project name extraction — must be present."""
    missing = [e for e in assistant_entries if not e.get('cwd')]
    pct = len(missing) / len(assistant_entries) * 100
    assert pct < 5, f"{pct:.1f}% of assistant entries missing 'cwd' (threshold: 5%)"


# ── message object ────────────────────────────────────────────────────────────

def test_message_has_model(entries_with_usage):
    missing = [e for e in entries_with_usage if not e['message'].get('model')]
    assert not missing, f"{len(missing)} entries missing message.model"

def test_message_model_is_string(entries_with_usage):
    bad = [e for e in entries_with_usage if not isinstance(e['message'].get('model'), str)]
    assert not bad, f"{len(bad)} entries where message.model is not a string"

def test_message_has_content_list(assistant_entries):
    bad = [e for e in assistant_entries if not isinstance(e['message'].get('content'), list)]
    assert not bad, f"{len(bad)} entries where message.content is not a list"

def test_message_has_usage(entries_with_usage):
    bad = [e for e in entries_with_usage if not isinstance(e['message'].get('usage'), dict)]
    assert not bad, f"{len(bad)} entries where message.usage is not a dict"


# ── usage fields ──────────────────────────────────────────────────────────────

REQUIRED_USAGE_FIELDS = [
    'input_tokens',
    'output_tokens',
    'cache_read_input_tokens',
    'cache_creation_input_tokens',
]

@pytest.mark.parametrize("field", REQUIRED_USAGE_FIELDS)
def test_usage_has_required_field(entries_with_usage, field):
    missing = [e for e in entries_with_usage if field not in e['message']['usage']]
    assert not missing, f"{len(missing)} entries missing usage.{field}"

@pytest.mark.parametrize("field", REQUIRED_USAGE_FIELDS)
def test_usage_field_is_non_negative_int(entries_with_usage, field):
    bad = [
        e for e in entries_with_usage
        if not isinstance(e['message']['usage'].get(field), int)
        or e['message']['usage'][field] < 0
    ]
    assert not bad, f"{len(bad)} entries where usage.{field} is not a non-negative int"

def test_cache_creation_is_dict_when_present(entries_with_cache_breakdown):
    bad = [
        e for e in entries_with_cache_breakdown
        if not isinstance(e['message']['usage']['cache_creation'], dict)
    ]
    assert not bad, f"{len(bad)} entries where cache_creation is not a dict"

def test_cache_creation_has_5m_field(entries_with_cache_breakdown):
    bad = [
        e for e in entries_with_cache_breakdown
        if 'ephemeral_5m_input_tokens' not in e['message']['usage']['cache_creation']
    ]
    assert not bad, f"{len(bad)} entries missing cache_creation.ephemeral_5m_input_tokens"

def test_cache_creation_has_1h_field(entries_with_cache_breakdown):
    bad = [
        e for e in entries_with_cache_breakdown
        if 'ephemeral_1h_input_tokens' not in e['message']['usage']['cache_creation']
    ]
    assert not bad, f"{len(bad)} entries missing cache_creation.ephemeral_1h_input_tokens"

def test_cache_creation_tiers_sum_to_total(entries_with_cache_breakdown):
    """5m + 1h tokens must equal cache_creation_input_tokens."""
    bad = []
    for e in entries_with_cache_breakdown:
        usage = e['message']['usage']
        cc = usage['cache_creation']
        tier_sum = cc.get('ephemeral_5m_input_tokens', 0) + cc.get('ephemeral_1h_input_tokens', 0)
        total = usage['cache_creation_input_tokens']
        if tier_sum != total:
            bad.append({'tier_sum': tier_sum, 'total': total})
    assert not bad, f"{len(bad)} entries where cache tier sum != cache_creation_input_tokens: {bad[:3]}"


# ── tool_use content blocks ───────────────────────────────────────────────────

def test_tool_use_blocks_have_type(entries_with_tools):
    for e in entries_with_tools:
        for block in e['message']['content']:
            if block.get('type') == 'tool_use':
                assert 'type' in block

def test_tool_use_blocks_have_name(entries_with_tools):
    bad = []
    for e in entries_with_tools:
        for block in e['message']['content']:
            if block.get('type') == 'tool_use' and not block.get('name'):
                bad.append(block)
    assert not bad, f"{len(bad)} tool_use blocks missing 'name'"

def test_tool_use_name_is_string(entries_with_tools):
    bad = []
    for e in entries_with_tools:
        for block in e['message']['content']:
            if block.get('type') == 'tool_use':
                if not isinstance(block.get('name'), str):
                    bad.append(block)
    assert not bad, f"{len(bad)} tool_use blocks where name is not a string"

def test_tool_use_blocks_have_id(entries_with_tools):
    bad = []
    for e in entries_with_tools:
        for block in e['message']['content']:
            if block.get('type') == 'tool_use' and not block.get('id'):
                bad.append(block)
    assert not bad, f"{len(bad)} tool_use blocks missing 'id'"


# ── cwd-based project extraction ──────────────────────────────────────────────

def test_cwd_is_absolute_path(assistant_entries):
    bad = [
        e for e in assistant_entries
        if e.get('cwd') and not e['cwd'].startswith('/')
    ]
    assert not bad, f"{len(bad)} entries where cwd is not an absolute path: {[e['cwd'] for e in bad[:3]]}"

def test_cwd_project_name_extractable(assistant_entries):
    """Project name = Path(cwd).name — must be non-empty."""
    bad = [
        e for e in assistant_entries
        if e.get('cwd') and not Path(e['cwd']).name
    ]
    assert not bad, f"{len(bad)} entries where Path(cwd).name is empty"
