# Contributing

## Setup

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/), Git

```bash
git clone https://github.com/project-sakai-mcp/sakai-tasks-mcp.git
cd sakai-tasks-mcp
uv sync
```

## Test

```bash
uv run pytest
uv run pytest --cov=src tests/   # with coverage
```

## Run

```bash
uv run python -m src.server
npx @modelcontextprotocol/inspector uv run python -m src.server   # MCP Inspector
```

## Build

```bash
uv run python scripts/build_windows.py   # Windows
uv run python scripts/build_macos.py     # macOS
```

## Workflow

- Open an issue to discuss large changes first.
- Branch names: `feat/<name>`, `fix/<name>`, `docs/<name>`
- Add tests under `tests/` for your changes.
- Run `uv run pytest` before opening a pull request.
- Describe the problem, the changes, and how to verify them in the pull request.

## Privacy

Never include passwords, cookies or session ids in code, tests, issues or pull requests. Remove the following from logs, test fixtures and screenshots:

- CSRF tokens
- Names, usernames, emails and user ids
- Your university's hostname and site ids (use `sakai.example.edu` and ids like `course-101`)
- Course titles and instructors' text
