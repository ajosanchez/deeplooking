# Adding Python Packages

- ONLY use uv, NEVER pip
- Installation: `uv add package`
- Running tools: `uv run tool`
- Upgrading: `uv add --upgrade-package package`
- Removing: `uv remove package`
- FORBIDDEN: `uv pip install`, `@latest` syntax