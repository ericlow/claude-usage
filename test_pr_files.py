"""
Tests for documentation files added in the PR:
- README.md
- .github/PULL_REQUEST_TEMPLATE.md
- Screenshot.png

Run with:
    python3 -m pytest test_pr_files.py -v
"""

import os

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
README_PATH = os.path.join(REPO_ROOT, 'README.md')
PR_TEMPLATE_PATH = os.path.join(REPO_ROOT, '.github', 'PULL_REQUEST_TEMPLATE.md')
SCREENSHOT_PATH = os.path.join(REPO_ROOT, 'Screenshot.png')


def _readme() -> str:
    with open(README_PATH, encoding='utf-8') as f:
        return f.read()


def _pr_template() -> str:
    with open(PR_TEMPLATE_PATH, encoding='utf-8') as f:
        return f.read()


# ── README.md — file presence ─────────────────────────────────────────────────

def test_readme_exists():
    assert os.path.isfile(README_PATH), "README.md must exist at repo root"


def test_readme_is_nonempty():
    assert os.path.getsize(README_PATH) > 0, "README.md must not be empty"


# ── README.md — top-level sections ───────────────────────────────────────────

def test_readme_has_installation_section():
    assert '## Installation' in _readme()


def test_readme_has_usage_section():
    assert '## Usage' in _readme()


def test_readme_has_output_section():
    assert '## Output' in _readme()


def test_readme_has_requirements_section():
    assert '## Requirements' in _readme()


# ── README.md — title ────────────────────────────────────────────────────────

def test_readme_title_is_claude_usage_tool():
    content = _readme()
    assert content.startswith('# claude-usage-tool'), \
        "README.md must start with '# claude-usage-tool'"


# ── README.md — screenshot reference ─────────────────────────────────────────

def test_readme_references_screenshot():
    assert 'Screenshot.png' in _readme(), \
        "README.md must reference Screenshot.png"


# ── README.md — all periods documented ───────────────────────────────────────

def test_readme_documents_period_today():
    assert '`today`' in _readme()


def test_readme_documents_period_week():
    assert '`week`' in _readme()


def test_readme_documents_period_month():
    assert '`month`' in _readme()


def test_readme_documents_period_3months():
    assert '`3months`' in _readme()


def test_readme_documents_period_session():
    assert '`session`' in _readme()


# ── README.md — all views documented ────────────────────────────────────────

def test_readme_documents_view_model():
    assert '`model`' in _readme()


def test_readme_documents_view_project():
    assert '`project`' in _readme()


# ── README.md — usage syntax forms ───────────────────────────────────────────

def test_readme_documents_period_usage_form():
    assert 'claude-usage-tool <period> [view]' in _readme()


def test_readme_documents_file_path_usage_form():
    assert 'claude-usage-tool <path/to/session.jsonl>' in _readme()


# ── README.md — concrete examples ────────────────────────────────────────────

def test_readme_has_week_example():
    assert 'claude-usage-tool week' in _readme()


def test_readme_has_month_project_example():
    assert 'claude-usage-tool month project' in _readme()


def test_readme_has_session_example():
    assert 'claude-usage-tool session' in _readme()


# ── README.md — requirements ──────────────────────────────────────────────────

def test_readme_specifies_python_310():
    assert 'Python 3.10+' in _readme(), \
        "README.md must specify Python 3.10+ requirement"


def test_readme_states_no_external_dependencies():
    content = _readme()
    assert 'standard library' in content, \
        "README.md must state that no external dependencies are needed"


# ── README.md — install command ───────────────────────────────────────────────

def test_readme_documents_install_sh():
    assert './install.sh' in _readme()


# ── README.md — output description mentions overview ─────────────────────────

def test_readme_output_mentions_overview():
    assert 'Overview' in _readme()


def test_readme_output_mentions_detail_blocks():
    assert 'Detail blocks' in _readme() or 'detail blocks' in _readme()


# ── README.md — MCP tool marking mentioned ───────────────────────────────────

def test_readme_mentions_mcp_tools():
    assert 'MCP' in _readme(), \
        "README.md must mention MCP tool marking"


# ── .github/PULL_REQUEST_TEMPLATE.md — file presence ────────────────────────

def test_pr_template_exists():
    assert os.path.isfile(PR_TEMPLATE_PATH), \
        ".github/PULL_REQUEST_TEMPLATE.md must exist"


def test_pr_template_is_nonempty():
    assert os.path.getsize(PR_TEMPLATE_PATH) > 0


# ── .github/PULL_REQUEST_TEMPLATE.md — sections ──────────────────────────────

def test_pr_template_has_summary_section():
    assert '## Summary' in _pr_template()


def test_pr_template_has_changes_section():
    assert '## Changes' in _pr_template()


def test_pr_template_has_test_plan_section():
    assert '## Test plan' in _pr_template()


def test_pr_template_has_notes_section():
    assert '## Notes' in _pr_template()


# ── .github/PULL_REQUEST_TEMPLATE.md — test plan checklist items ─────────────

def test_pr_template_checklist_week_command():
    assert 'claude-usage-tool week' in _pr_template(), \
        "Test plan must include 'claude-usage-tool week' check"


def test_pr_template_checklist_month_project_command():
    assert 'claude-usage-tool month project' in _pr_template(), \
        "Test plan must include 'claude-usage-tool month project' check"


def test_pr_template_checklist_pytest_command():
    assert 'python3 -m pytest' in _pr_template(), \
        "Test plan must include pytest run instruction"


def test_pr_template_checklist_items_are_unchecked():
    # All checklist items should ship as unchecked: "- [ ]"
    content = _pr_template()
    assert '- [ ]' in content, \
        "Test plan checklist items must use '- [ ]' (unchecked) syntax"


def test_pr_template_has_no_checked_items():
    # Template should not pre-check any boxes
    assert '- [x]' not in _pr_template() and '- [X]' not in _pr_template(), \
        "PR template must not contain pre-checked checklist items"


# ── .github/PULL_REQUEST_TEMPLATE.md — HTML comments as placeholders ─────────

def test_pr_template_summary_has_placeholder_comment():
    content = _pr_template()
    assert '<!-- What does this PR do? -->' in content, \
        "Summary section must contain a placeholder HTML comment"


def test_pr_template_notes_has_placeholder_comment():
    content = _pr_template()
    assert '<!--' in content.split('## Notes')[-1], \
        "Notes section must contain a placeholder HTML comment"


# ── Screenshot.png — file presence and validity ───────────────────────────────

def test_screenshot_exists():
    assert os.path.isfile(SCREENSHOT_PATH), \
        "Screenshot.png must exist at repo root"


def test_screenshot_is_nonempty():
    assert os.path.getsize(SCREENSHOT_PATH) > 0, \
        "Screenshot.png must not be empty"


def test_screenshot_has_png_signature():
    """PNG files begin with the 8-byte magic signature \x89PNG\r\n\x1a\n."""
    with open(SCREENSHOT_PATH, 'rb') as f:
        header = f.read(8)
    assert header == b'\x89PNG\r\n\x1a\n', \
        "Screenshot.png must be a valid PNG file"


def test_screenshot_is_reasonably_sized():
    """Guard against an accidentally committed zero-byte or placeholder file."""
    size = os.path.getsize(SCREENSHOT_PATH)
    assert size >= 1024, \
        f"Screenshot.png is suspiciously small ({size} bytes); expected at least 1 KB"
