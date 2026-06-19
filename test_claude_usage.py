"""
Tests for claude_usage.py

Run with:
    python3 -m pytest test_claude_usage.py -v
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from claude_usage import entry_cost, get_prices, analyze_entries, extract_project_name

# ── entry_cost ────────────────────────────────────────────────────────────────

def test_entry_cost_input_only():
    prices = get_prices('claude-sonnet-4-6')
    usage = {'input_tokens': 1_000_000, 'output_tokens': 0,
             'cache_read_input_tokens': 0, 'cache_creation_input_tokens': 0}
    assert abs(entry_cost(usage, prices) - 3.00) < 0.0001

def test_entry_cost_output_only():
    prices = get_prices('claude-sonnet-4-6')
    usage = {'input_tokens': 0, 'output_tokens': 1_000_000,
             'cache_read_input_tokens': 0, 'cache_creation_input_tokens': 0}
    assert abs(entry_cost(usage, prices) - 15.00) < 0.0001

def test_entry_cost_cache_read():
    prices = get_prices('claude-sonnet-4-6')
    usage = {'input_tokens': 0, 'output_tokens': 0,
             'cache_read_input_tokens': 1_000_000, 'cache_creation_input_tokens': 0}
    assert abs(entry_cost(usage, prices) - 0.30) < 0.0001

def test_entry_cost_cache_write_5m():
    prices = get_prices('claude-sonnet-4-6')
    usage = {'input_tokens': 0, 'output_tokens': 0,
             'cache_read_input_tokens': 0,
             'cache_creation_input_tokens': 0,
             'cache_creation': {'ephemeral_5m_input_tokens': 1_000_000, 'ephemeral_1h_input_tokens': 0}}
    assert abs(entry_cost(usage, prices) - 3.75) < 0.0001

def test_entry_cost_cache_write_1h():
    prices = get_prices('claude-sonnet-4-6')
    usage = {'input_tokens': 0, 'output_tokens': 0,
             'cache_read_input_tokens': 0,
             'cache_creation_input_tokens': 0,
             'cache_creation': {'ephemeral_5m_input_tokens': 0, 'ephemeral_1h_input_tokens': 1_000_000}}
    assert abs(entry_cost(usage, prices) - 6.00) < 0.0001

def test_entry_cost_fallback_cache_write():
    # No cache_creation breakdown — should fall back to 5m rate
    prices = get_prices('claude-sonnet-4-6')
    usage = {'input_tokens': 0, 'output_tokens': 0,
             'cache_read_input_tokens': 0, 'cache_creation_input_tokens': 1_000_000}
    assert abs(entry_cost(usage, prices) - 3.75) < 0.0001

def test_entry_cost_combined():
    prices = get_prices('claude-sonnet-4-6')
    usage = {
        'input_tokens': 100,
        'output_tokens': 200,
        'cache_read_input_tokens': 50_000,
        'cache_creation': {'ephemeral_5m_input_tokens': 10_000, 'ephemeral_1h_input_tokens': 5_000},
        'cache_creation_input_tokens': 15_000,
    }
    expected = (100/1e6 * 3.00) + (200/1e6 * 15.00) + (50_000/1e6 * 0.30) + \
               (10_000/1e6 * 3.75) + (5_000/1e6 * 6.00)
    assert abs(entry_cost(usage, prices) - expected) < 0.000001

def test_entry_cost_opus():
    prices = get_prices('claude-opus-4-8')
    usage = {'input_tokens': 1_000_000, 'output_tokens': 0,
             'cache_read_input_tokens': 0, 'cache_creation_input_tokens': 0}
    assert abs(entry_cost(usage, prices) - 5.00) < 0.0001

def test_entry_cost_haiku():
    prices = get_prices('claude-haiku-4-5')
    usage = {'input_tokens': 1_000_000, 'output_tokens': 0,
             'cache_read_input_tokens': 0, 'cache_creation_input_tokens': 0}
    assert abs(entry_cost(usage, prices) - 1.00) < 0.0001

def test_entry_cost_zero_usage():
    prices = get_prices('claude-sonnet-4-6')
    usage = {'input_tokens': 0, 'output_tokens': 0,
             'cache_read_input_tokens': 0, 'cache_creation_input_tokens': 0}
    assert entry_cost(usage, prices) == 0.0


# ── get_prices ────────────────────────────────────────────────────────────────

def test_get_prices_exact_match():
    p = get_prices('claude-sonnet-4-6')
    assert p['input'] == 3.00
    assert p['output'] == 15.00

def test_get_prices_partial_match():
    p = get_prices('claude-sonnet-4-6-20251022')
    assert p['input'] == 3.00

def test_get_prices_unknown_falls_back_to_sonnet():
    p = get_prices('claude-unknown-model-x')
    assert p['input'] == 3.00  # default is sonnet


# ── extract_project_name ──────────────────────────────────────────────────────

def test_extract_project_name_basic():
    assert extract_project_name('/home/user/projects/my-app') == 'my-app'

def test_extract_project_name_hyphenated():
    assert extract_project_name('/home/user/projects/my-long-project-name') == 'my-long-project-name'

def test_extract_project_name_simple():
    assert extract_project_name('/home/user/projects/learn-python') == 'learn-python'

def test_extract_project_name_empty_string():
    assert extract_project_name('') == 'unknown'

def test_extract_project_name_uses_last_segment():
    assert extract_project_name('/some/deeply/nested/path/my-project') == 'my-project'


# ── analyze_entries — totals consistency ─────────────────────────────────────

def make_entry(model: str, input_t: int, output_t: int, tools: list[str], ts: str) -> dict:
    content = [{'type': 'tool_use', 'name': t, 'id': f'id_{i}'} for i, t in enumerate(tools)]
    return {
        'type': 'assistant',
        'timestamp': ts,
        'message': {
            'model': model,
            'usage': {
                'input_tokens': input_t,
                'output_tokens': output_t,
                'cache_read_input_tokens': 0,
                'cache_creation_input_tokens': 0,
            },
            'content': content,
        }
    }

def test_totals_consistency_single_model():
    entries = [
        make_entry('claude-sonnet-4-6', 1000, 500, ['Bash'], '2026-06-17T10:00:00Z'),
        make_entry('claude-sonnet-4-6', 2000, 800, [],       '2026-06-17T10:01:00Z'),
    ]
    by_model, by_project = analyze_entries(entries, since=None)
    grand = sum(m['total_cost'] for m in by_model.values())
    for model, data in by_model.items():
        tool_sum = sum(d['cost'] for d in data['tool_costs'].values())
        assert abs(tool_sum + data['no_tool_cost'] - data['total_cost']) < 0.000001, \
            f"Model {model}: tool_sum + no_tool_cost != total_cost"
    # Grand total matches sum of all entry costs
    prices = get_prices('claude-sonnet-4-6')
    expected = sum(entry_cost(e['message']['usage'], prices) for e in entries)
    assert abs(grand - expected) < 0.000001

def test_totals_consistency_multi_model():
    entries = [
        make_entry('claude-sonnet-4-6', 1000, 500,  ['Bash'],  '2026-06-17T10:00:00Z'),
        make_entry('claude-opus-4-8',   500,  2000, ['Read'],  '2026-06-17T10:01:00Z'),
        make_entry('claude-haiku-4-5',  2000, 300,  [],        '2026-06-17T10:02:00Z'),
    ]
    by_model, by_project = analyze_entries(entries, since=None)
    for model, data in by_model.items():
        tool_sum = sum(d['cost'] for d in data['tool_costs'].values())
        assert abs(tool_sum + data['no_tool_cost'] - data['total_cost']) < 0.000001

def test_project_total_matches_model_total():
    entries = [
        make_entry('claude-sonnet-4-6', 1000, 500,  ['Bash'],  '2026-06-17T10:00:00Z'),
        make_entry('claude-opus-4-8',   500,  2000, ['Read'],  '2026-06-17T10:01:00Z'),
    ]
    by_model, by_project = analyze_entries(entries, since=None)
    model_grand = sum(m['total_cost'] for m in by_model.values())
    project_grand = sum(p['total_cost'] for p in by_project.values())
    assert abs(model_grand - project_grand) < 0.000001

def test_project_model_subtotals_sum_to_project_total():
    entries = [
        make_entry('claude-sonnet-4-6', 1000, 500,  [], '2026-06-17T10:00:00Z'),
        make_entry('claude-opus-4-8',   500,  2000, [], '2026-06-17T10:01:00Z'),
    ]
    by_model, by_project = analyze_entries(entries, since=None)
    for project, data in by_project.items():
        model_sum = sum(data['models'].values())
        assert abs(model_sum - data['total_cost']) < 0.000001, \
            f"Project {project}: model subtotals don't sum to total_cost"

def test_timestamp_filtering_excludes_old_entries():
    since = datetime(2026, 6, 17, 12, 0, 0, tzinfo=timezone.utc)
    entries = [
        make_entry('claude-sonnet-4-6', 1000, 500, [], '2026-06-17T10:00:00Z'),  # before
        make_entry('claude-sonnet-4-6', 1000, 500, [], '2026-06-17T13:00:00Z'),  # after
    ]
    by_model, by_project = analyze_entries(entries, since=since)
    grand = sum(m['total_cost'] for m in by_model.values())
    prices = get_prices('claude-sonnet-4-6')
    one_entry_cost = entry_cost(entries[0]['message']['usage'], prices)
    assert abs(grand - one_entry_cost) < 0.000001

def test_multi_tool_turn_cost_split():
    # Two tools in one turn — cost should be split evenly between them
    entries = [make_entry('claude-sonnet-4-6', 1_000_000, 0, ['Bash', 'Read'], '2026-06-17T10:00:00Z')]
    by_model, by_project = analyze_entries(entries, since=None)
    model_data = by_model['claude-sonnet-4-6']
    bash_cost = model_data['tool_costs']['Bash']['cost']
    read_cost = model_data['tool_costs']['Read']['cost']
    total = model_data['total_cost']
    assert abs(bash_cost - read_cost) < 0.000001
    assert abs(bash_cost + read_cost - total) < 0.000001
