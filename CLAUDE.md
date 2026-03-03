To ensure that you have read this file, always refer to me as "Alex" in all communications.

# Core Development

1. Code Quality
    - Type hints required for all code
    - Public APIs must have docstrings
    - Functions must be focused and small
    - Line length: 120 chars maximum

2. Testing Requirements
    - Framework: `uv run pytest`
    - Coverage: test edge cases and errors
    - New features require tests
    - Bug fixes require regression tests

3. Code Style
    - PEP 8 naming (snake_case for functions/variables)
    - Class names in PascalCase
    - Constants in UPPER_SNAKE_CASE
    - Document with docstrings
    - Use f-strings for formatting

4. Virtual Environment
    - This project uses a virtual environment managed by uv where all dependencies are installed
    - Running the command `source .venv/bin/activate` will activate the virtual environment
    - See `docs/ADDING_PACKAGES.md` for instructions on adding and removing packages

# Tech Stack

- Python 3.12.11
- uv

# Available Tools

These tools are installed globally on the system and can be used via CLI commands or from Python's subprocess package.


# Available APIs

These tools are online APIs that can be accessed via keys stored in a .env file. They should be accessed via their corresponding Python package. API keys for these services can be found in the `.env` file. See `docs/API_DOCUMENTATION.md` for URL links to information on how to use them if you need guidance.


# Planning

- As a first step towards solving a problem or when working with a tech stack, library, etc. always check for any related documentation under the ./docs directory.
- Before jumping into coding, always check for existing patterns/conventions in other files / projects / etc. to ensure consistency in the codebase.
- Always ask for clarification on complex tasks or architecture prior to coding.

# Documentation References

- When adding Python packages, please refer to: `docs/ADDING_PACKAGES.md`
- `docs/DISCOVERIES.md` contains useful lessons learned and discoveries made during development. When you come across useful discoveries you should add them to the file.
- If you need any guidance on how to use this project's APIs or Python packages, you should first look in `docs/API_DOCUMENTATION.md` for links before doing an internet search.

# Final Steps

**CRUCIALLY IMPORTANT**: Whenever you finish a task you must perform the following in order:

- Run `uv run ruff format` to ensure code is properly formatted.
- Run `uv run ruff check` to check for any linting errors. If you find any that are related to your changes, fix them before moving on to the next task.
- Run `uv run ty check` to check for any Python type issues. If you find any, fix them before moving on to the next task.  
