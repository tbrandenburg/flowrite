# Agent Guidelines

## Rules

* **ALWAYS** Keep it simple
* **ALWAYS** Apply smart state-of-the-art library usage for keeping this project only on glue code level
* **AVOID** Writing own code - all own code needs to be laboriously maintained and introduces new bugs - we want to avoid that

## Testing Protocol

* **MANDATORY** Run `make test` after any code changes to ensure no regressions
* **MANDATORY** All tests must pass before committing changes
* The test suite includes both unit tests (pytest) and integration tests (workflow simulations)
* Any new functionality must include corresponding test coverage

## Repository Cleanliness

### Root Directory Rules
**MANDATORY** Keep the repository root clean and organized:

* **ALLOWED in root**: Only essential project files
  - Configuration files: `pyproject.toml`, `Makefile`, `uv.lock`, `.gitignore`
  - Documentation: `README.md`, `LICENSE`, `AGENTS.md`
  - Core workflow files: `flow_blueprint.yaml`, `test_workflow.yaml`, `echo_test.yaml`
  - Sample files: `sample_workflow.yaml`, `loop_test.yaml`

* **FORBIDDEN in root**: Temporary, build, or development-specific files
  - Build artifacts: `build/`, `dist/`, `.coverage`
  - Cache directories: `.pytest_cache/`, `.ruff_cache/`, `__pycache__/`
  - Log files: `*.log`, `worker.log`, `temporal-worker.log`
  - Temporary test files: `*_debug.py`, `*_corrected.yaml`, `simple_*.yaml`
  - Development documentation: `*-matrix-patterns.md`, draft files

### Organized Folder Structure
```
flowrite/
├── src/                    # Core application code
├── tests/                  # Test suite
├── examples/               # Example workflows
├── docs/                   # Project documentation
├── dev/                    # Development tools and artifacts
├── .github/                # GitHub workflows and templates
├── .claude/                # AI assistant context and plans
└── .venv/                  # Virtual environment (gitignored)
```

### Cleanup Protocol
* **Before committing**: Run `make clean` to remove temporary files
* **After development**: Clean up any debug/test files created during development
* **Regular maintenance**: Use `git status` to identify untracked files that should be cleaned or gitignored

## Specifications

* [Workflow Blueprint](docs/flow_blueprint.md) to be supported in all cases