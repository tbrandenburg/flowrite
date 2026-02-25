# Flowrite Workflow Executor Makefile
# Using uv for modern Python project management

.PHONY: help install test pytest run clean worker simulation local dev-setup
.DEFAULT_GOAL := help

# Check if uv is installed
UV := $(shell command -v uv 2> /dev/null)
ifdef UV
    PY = uv run python
    PYTEST = uv run pytest
    SYNC_CMD = uv sync
else
    PY = python
    PYTEST = python -m pytest
    SYNC_CMD = pip install -r requirements.txt
endif

# Default target
help:
	@echo "Flowrite Workflow Executor (uv-optimized)"
	@echo "========================================="
	@echo ""
	@echo "Available targets:"
	@echo "  install     - Install dependencies using uv sync"
	@echo "  dev-setup   - Set up development environment"
	@echo "  test        - Run complete test suite (unit tests + integration tests)"
	@echo "  pytest      - Run unit tests only"
	@echo "  run         - Run workflow (use YAML=file.yaml)"
	@echo "  local       - Run workflow in local mode (real bash execution)"
	@echo "  simulation  - Run workflow in simulation mode"
	@echo "  worker      - Start Temporal worker"
	@echo "  sample      - Create sample workflow"
	@echo "  clean       - Clean temporary files and cache"
	@echo "  lint        - Run code linting"
	@echo "  lines       - Verify LOC requirements"
	@echo "  structure   - Show project structure"
	@echo "  demo        - Quick demo"
	@echo "  check-env   - Show environment information"
	@echo ""
	@echo "Examples:"
	@echo "  make install"
	@echo "  make run YAML=flow_blueprint.yaml"
	@echo "  make local YAML=test_workflow.yaml"
	@echo "  make simulation YAML=test_workflow.yaml"
	@echo "  make test"

# Installation using proper uv project management
install:
	@echo "Installing dependencies..."
ifdef UV
	@echo "Using uv sync for dependency management..."
	@$(SYNC_CMD) --all-extras --dev
else
	@echo "Using pip (uv not available)..."
	@pip install temporalio>=1.6.0 pyyaml>=6.0.1 pytest>=7.4.0 pytest-asyncio>=0.21.0 pytest-cov>=4.1.0
endif
	@echo "✅ Dependencies installed successfully!"

# Development setup
dev-setup: install
	@echo "✅ Development environment ready!"

# Test workflows and unit tests
test:
	@echo "Running complete test suite..."
	@echo "==============================="
	@echo "1. Running unit tests..."
	@$(PYTEST) tests/ -v
	@echo ""
	@echo "2. Running integration workflow tests..."
	@$(PY) -m src.main run test_workflow.yaml --simulation
	@$(PY) -m src.main run flow_blueprint.yaml --simulation
	@$(PY) -m src.main run echo_test.yaml --simulation
	@echo "✅ All tests completed successfully!"

# Run unit tests only
pytest:
	@echo "Running unit test suite..."
	@$(PYTEST) tests/ -v
	@echo "✅ Unit tests completed!"

# Run workflow (requires YAML parameter)
run:
ifndef YAML
	@echo "Error: Please specify YAML file with YAML=filename.yaml"
	@exit 1
endif
	@echo "Running workflow: $(YAML)"
	@$(PY) -m src.main run $(YAML)

# Run in simulation mode
simulation:
ifndef YAML
	@echo "Error: Please specify YAML file with YAML=filename.yaml"
	@exit 1
endif
	@echo "Running workflow in simulation: $(YAML)"
	@$(PY) -m src.main run $(YAML) --simulation

# Run in local mode (real bash execution)
local:
ifndef YAML
	@echo "Error: Please specify YAML file with YAML=filename.yaml"
	@exit 1
endif
	@echo "Running workflow in local mode: $(YAML)"
	@$(PY) -m src.main run $(YAML) --local

# Start Temporal worker
worker:
	@echo "Starting Temporal worker..."
	@$(PY) -m src.main worker

# Create sample workflow
sample:
	@echo "Creating sample workflow..."
	@$(PY) -m src.main create-sample
	@echo "✅ Created sample_workflow.yaml"

# Clean temporary files and cache
clean:
	@echo "Cleaning temporary files and cache..."
	@find . -name "*.pyc" -delete
	@find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.tmp" -delete
	@find . -name "*.log" -delete
	@find . -name ".pytest_cache" -type d -exec rm -rf {} + 2>/dev/null || true
ifdef UV
	@uv cache clean 2>/dev/null || true
endif
	@echo "✅ Cleanup completed"

# Code linting
lint:
	@echo "Running code quality checks..."
	@$(PY) -m py_compile src/*.py
	@echo "✅ Python syntax check passed"
ifdef UV
	@echo "Running additional linting with uv..."
	@uv run --with ruff -- ruff check src/ tests/ 2>/dev/null || echo "⚠️  ruff not available, skipping advanced linting"
endif

# Line count verification
lines:
	@echo "Line count verification:"
	@echo "========================"
	@wc -l src/main.py
	@echo "Main file target: <750 lines"
	@echo ""
	@echo "All source files:"
	@wc -l src/*.py
	@echo ""
	@echo "Total project files:"
	@find . -name "*.py" -not -path "./.venv/*" -not -path "./.*" | xargs wc -l | tail -1

# Show project structure
structure:
	@echo "Project Structure:"
	@echo "=================="
	@tree . -I '__pycache__|.venv|*.pyc|.git|.pytest_cache' 2>/dev/null || \
		find . -type f \( -name "*.py" -o -name "*.yaml" -o -name "*.md" -o -name "*.toml" \) \
		! -path "./.venv/*" ! -path "./.git/*" ! -path "./__pycache__/*" | sort

# Quick demo
demo: sample
	@echo "🚀 Running Flowrite Demo"
ifdef UV
	@echo "============================ (uv-optimized)"
else
	@echo "============================"
endif
	@$(MAKE) simulation YAML=sample_workflow.yaml

# Environment information
check-env:
	@echo "Environment Information:"
	@echo "======================="
ifdef UV
	@echo "uv version: $(shell uv --version 2>/dev/null || echo 'not installed')"
else
	@echo "uv: not installed (using standard Python)"
endif
	@echo "Python version: $(shell $(PY) --version 2>/dev/null || echo 'not available')"
	@echo ""
	@echo "Key dependencies:"
	@$(PY) -c "import temporalio; print(f'✅ temporalio {temporalio.__version__}')" 2>/dev/null || echo "❌ temporalio not available"
	@$(PY) -c "import yaml; print('✅ pyyaml available')" 2>/dev/null || echo "❌ pyyaml not available"
	@$(PY) -c "import pytest; print(f'✅ pytest {pytest.__version__}')" 2>/dev/null || echo "❌ pytest not available"

# Run with coverage
test-cov:
	@echo "Running tests with coverage..."
	@$(PYTEST) tests/ --cov=src --cov-report=term-missing --cov-report=html
	@echo "✅ Coverage report generated!"

# Format code (if available)
format:
	@echo "Formatting code..."
ifdef UV
	@uv run --with black -- black src/ tests/ 2>/dev/null || echo "⚠️  black not available, skipping formatting"
	@uv run --with isort -- isort src/ tests/ 2>/dev/null || echo "⚠️  isort not available, skipping import sorting"
else
	@echo "⚠️  uv not available, skipping formatting"
endif

# Validate project configuration
validate:
	@echo "Validating project configuration..."
	@$(PY) -c "import tomllib; tomllib.load(open('pyproject.toml', 'rb')); print('✅ pyproject.toml is valid')" 2>/dev/null || \
		$(PY) -c "import tomli; tomli.load(open('pyproject.toml', 'rb')); print('✅ pyproject.toml is valid')" 2>/dev/null || \
		echo "⚠️  Could not validate pyproject.toml"
	@echo "Testing imports..."
	@$(PY) -c "from src.main import main; print('✅ Main module imports successfully')"