# claude-usage-tool

A CLI for breaking down Claude Code API costs by tool call, model, and project. Reads the JSONL session files Claude Code writes to `~/.claude/projects/`.

## Installation

```bash
./install.sh
```

This symlinks `claude-usage-tool` into `~/.local/bin`. If that directory isn't in your `PATH`, the script will tell you what to add to `~/.zshrc`.

## Usage

```
claude-usage-tool <period> [view]
claude-usage-tool <path/to/session.jsonl> [view]
```

**Periods:**

| Argument  | Window          |
|-----------|-----------------|
| `today`   | Current day     |
| `week`    | Last 7 days     |
| `month`   | Last 30 days    |
| `3months` | Last 3 months   |
| `session` | Most recent session only |

**Views (optional second argument):**

| Argument  | Description |
|-----------|-------------|
| `model`   | Detail by model, with per-tool breakdown (default) |
| `project` | Detail by project, with per-project model + tool breakdown |

**Examples:**

```bash
claude-usage-tool week
claude-usage-tool month project
claude-usage-tool session
claude-usage-tool ~/.claude/projects/my-project/abc123.jsonl
```

## Output

Each run prints:

1. **Overview** — grand total, cost by model, cost by project (projects under 1% are hidden)
2. **Detail blocks** — per model or per project, showing each tool call's share of cost, call count, and cache tokens created. MCP tools are marked with `*`.

Costs are API-equivalent estimates based on published token pricing. Pro/Max subscribers pay a flat monthly fee — these numbers show what the equivalent API usage would cost.

## Requirements

- Python 3.10+
- No dependencies beyond the standard library
