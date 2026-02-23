# Contributing to SenseBase

Thanks for your interest in contributing! Here's how to get started.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/your-org/contextpedia.git
cd contextpedia

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install with all features + dev tools
pip install -e ".[full,dev]"
```

## Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src

# Run a specific test file
pytest tests/test_search.py -v
```

## Linting

We use [Ruff](https://docs.astral.sh/ruff/) for linting.

```bash
# Check for issues
ruff check src/ tests/

# Auto-fix what's possible
ruff check --fix src/ tests/
```

## Submitting Changes

1. Fork the repository
2. Create a feature branch (`git checkout -b my-feature`)
3. Make your changes
4. Run tests and linting (`pytest tests/ && ruff check src/ tests/`)
5. Commit with a clear message
6. Open a Pull Request

## Adding a New Language Analyzer

See the [CLAUDE.md](CLAUDE.md) section on adding analyzers. In short:

1. Create a new file in `src/analyzers/` or `src/extractors/`
2. Implement the `Analyzer` base class from `src/analyzers/base.py`
3. Register it in `src/analyzers/registry.py` via `create_default_registry()`
4. Add tests in `tests/`

## Questions?

Open an issue and we'll be happy to help.
