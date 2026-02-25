# Flowrite Workflow Executor Makefile
# Using uv for modern Python project management

.PHONY: help install install-deps test pytest run clean worker local dev-setup temporal-server temporal-stop temporal-clean temporal-dev temporal-status build installdirs
.DEFAULT_GOAL := help

# Check if uv is installed
UV := $(shell command -v uv 2> /dev/null)
ifdef UV
    PY = uv run python
    PYTEST = uv run pytest
    SYNC_CMD = uv sync
    FLOWRITE_CMD = uv run flowrite
else
    PY = python
    PYTEST = python -m pytest
    SYNC_CMD = pip install -r requirements.txt
    FLOWRITE_CMD = python -m src.main
endif

# GNU Make Directory Variables
prefix = /usr/local
bindir = $(prefix)/bin

# Default target
help:
	@echo "Flowrite Workflow Executor (uv-optimized)"
	@echo "========================================="
	@echo ""
	@echo "Available targets:"
	@echo ""
	@echo "🔧 DEVELOPMENT:"
	@echo "  install-deps- Install dependencies using uv sync"
	@echo "  dev-setup   - Set up development environment"
	@echo "  test        - Run complete test suite (unit tests + integration tests)"
	@echo "  pytest      - Run unit tests only"
	@echo "  demo        - Quick demo with local mode"
	@echo ""
	@echo "📦 SYSTEM INSTALLATION (GNU Make compliant):"
	@echo "  build       - Build distributable package (wheel + sdist)"
	@echo "  install     - Install flowrite system-wide executable (use: sudo make install)"
	@echo "  install-strip- Install system executable (same as install)"
	@echo "  uninstall   - Remove system installation (use: sudo make uninstall)"
	@echo "  installdirs - Create installation directories"
	@echo ""
	@echo "🏃 WORKFLOW EXECUTION:"
	@echo "  local       - Run workflow in local mode (use YAML=file.yaml)"
	@echo "  run         - Run workflow with Temporal (use YAML=file.yaml)"
	@echo ""
	@echo "⚡ TEMPORAL MODE (Distributed Execution):"
	@echo "  temporal-dev   - Start Temporal server + worker (all-in-one)"
	@echo "  temporal-server- Start only Temporal server"
	@echo "  worker         - Start only Temporal worker"
	@echo "  temporal-status- Check Temporal server status"
	@echo "  temporal-stop  - Stop Temporal server"
	@echo "  temporal-clean - Stop and remove Temporal containers"
	@echo ""
	@echo "🛠️ UTILITIES:"
	@echo "  sample      - Create sample workflow"
	@echo "  clean       - Clean temporary files and cache"
	@echo "  lint        - Run code linting"
	@echo "  lines       - Verify LOC requirements"
	@echo "  structure   - Show project structure"
	@echo "  check-env   - Show environment information"
	@echo ""
	@echo "📖 EXAMPLES:"
	@echo "  make demo                              # Quick local demo"
	@echo "  make local YAML=examples/01_basic_workflow.yaml"
	@echo "  make temporal-dev                      # Start server + worker"
	@echo "  make run YAML=examples/01_basic_workflow.yaml"

# Installation using proper uv project management
install-deps:
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
dev-setup: install-deps
	@echo "✅ Development environment ready!"

# Test workflows and unit tests
test:
	@echo "Running complete test suite..."
	@echo "==============================="
	@echo "1. Running unit tests..."
	@$(PYTEST) tests/ -v
	@echo ""
	@echo "2. Running integration workflow tests..."
	@$(PY) -m src.main run test_workflow.yaml --local
	@$(PY) -m src.main run flow_blueprint.yaml --local
	@$(PY) -m src.main run echo_test.yaml --local
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
	@$(FLOWRITE_CMD) run $(YAML)

# Run in local mode (real bash execution)
local:
ifndef YAML
	@echo "Error: Please specify YAML file with YAML=filename.yaml"
	@exit 1
endif
	@echo "Running workflow in local mode: $(YAML)"
	@$(FLOWRITE_CMD) run $(YAML) --local

# Start Temporal worker
worker:
	@echo "Starting Temporal worker..."
	@echo "💡 Make sure Temporal server is running first with 'make temporal-server'"
	@$(FLOWRITE_CMD) worker

# 🚀 TEMPORAL ORCHESTRATION TARGETS

# Start Temporal development server
temporal-server:
	@echo "🚀 Starting Temporal Development Server..."
	@echo "========================================"
	@if [ -n "$$(docker ps -q -f name=temporal-flowrite)" ]; then \
		echo "⚠️  Temporal server already running!"; \
		echo "   Use 'make temporal-status' to check or 'make temporal-stop' to stop"; \
	else \
		echo "Starting server on ports 7233 (gRPC) and 8233 (Web UI)..."; \
		docker run -d --name temporal-flowrite --rm \
			-p 7233:7233 -p 8233:8233 \
			temporalio/temporal server start-dev --ip 0.0.0.0; \
		sleep 3; \
		echo ""; \
		echo "✅ Temporal Server started!"; \
		echo "   📊 Web UI: http://localhost:8233"; \
		echo "   🔌 gRPC:   localhost:7233"; \
		echo ""; \
		echo "💡 Next steps:"; \
		echo "   1. Run 'make worker' in another terminal, OR"; \
		echo "   2. Use 'make temporal-dev' to start server + worker together"; \
		echo "   3. Then run workflows with 'make run YAML=examples/01_basic_workflow.yaml'"; \
	fi

# Start Temporal server + worker in background (all-in-one development mode)
temporal-dev:
	@echo "🚀 Starting Temporal Development Environment..."
	@echo "=============================================="
	@echo "This will start both server and worker for you!"
	@echo ""
	@$(MAKE) temporal-server
	@if [ -n "$$(docker ps -q -f name=temporal-flowrite)" ]; then \
		echo "⏳ Waiting for server to be ready..."; \
		sleep 5; \
		echo "🔧 Starting worker in background..."; \
		$(PY) -m src.main worker > temporal-worker.log 2>&1 & \
		echo $$! > temporal-worker.pid; \
		sleep 2; \
		echo ""; \
		echo "🎉 Temporal Development Environment Ready!"; \
		echo "   📊 Web UI: http://localhost:8233"; \
		echo "   📝 Worker logs: temporal-worker.log"; \
		echo ""; \
		echo "▶️  Run workflows with:"; \
		echo "   make run YAML=examples/01_basic_workflow.yaml"; \
		echo "   make run YAML=examples/03_parallel_execution.yaml"; \
		echo ""; \
		echo "⏹️  Stop with: make temporal-stop"; \
	fi

# Check Temporal server status
temporal-status:
	@echo "🔍 Temporal Status Check..."
	@echo "=========================="
	@if [ -n "$$(docker ps -q -f name=temporal-flowrite)" ]; then \
		echo "✅ Server: Running"; \
		echo "   📊 Web UI: http://localhost:8233"; \
		echo "   🔌 gRPC:   localhost:7233"; \
		if [ -f temporal-worker.pid ] && kill -0 `cat temporal-worker.pid` 2>/dev/null; then \
			echo "✅ Worker: Running (PID: `cat temporal-worker.pid`)"; \
			echo "   📝 Logs: temporal-worker.log"; \
		else \
			echo "❌ Worker: Not running"; \
			echo "   💡 Start with 'make worker' or 'make temporal-dev'"; \
		fi; \
	else \
		echo "❌ Server: Not running"; \
		echo "   💡 Start with 'make temporal-server' or 'make temporal-dev'"; \
	fi

# Stop Temporal server (and worker if started with temporal-dev)
temporal-stop:
	@echo "⏹️  Stopping Temporal Environment..."
	@echo "=================================="
	@if [ -f temporal-worker.pid ]; then \
		if kill -0 `cat temporal-worker.pid` 2>/dev/null; then \
			echo "🔧 Stopping worker (PID: `cat temporal-worker.pid`)..."; \
			kill `cat temporal-worker.pid` 2>/dev/null || true; \
		fi; \
		rm -f temporal-worker.pid; \
	fi
	@if [ -n "$$(docker ps -q -f name=temporal-flowrite)" ]; then \
		echo "🔧 Stopping Temporal server..."; \
		docker stop temporal-flowrite >/dev/null 2>&1 || true; \
	fi
	@echo "✅ Temporal environment stopped"

# Clean up all Temporal containers and files
temporal-clean: temporal-stop
	@echo "🧹 Cleaning up Temporal resources..."
	@docker rm temporal-flowrite >/dev/null 2>&1 || true
	@rm -f temporal-worker.log temporal-worker.pid
	@echo "✅ Temporal cleanup completed"

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
	@$(MAKE) local YAML=sample_workflow.yaml

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

# Build distribution packages
build:
	@echo "Building distribution packages..."
ifdef UV
	@echo "Using uv build for package creation..."
	@uv build
else
	@echo "Using python -m build (uv not available)..."
	@$(PY) -m build
endif
	@echo "✅ Build artifacts created in dist/"

# Create installation directories
installdirs:
	@echo "Creating installation directories..."
ifeq ($(DESTDIR),)
	@echo "Using sudo for system directory creation..."
	@sudo mkdir -p $(bindir)
	@sudo mkdir -p $(prefix)/lib/python/site-packages
else
	@mkdir -p $(DESTDIR)$(bindir)
	@mkdir -p $(DESTDIR)$(prefix)/lib/python/site-packages
endif
	@echo "✅ Installation directories created"

# Install system executable  
install: build installdirs
	@echo "Installing flowrite system executable..."
	@echo "Preparing package installation to temporary location..."
	@rm -rf /tmp/flowrite-install
	@mkdir -p /tmp/flowrite-install
ifdef UV
	@echo "Installing package using uv pip..."
	@uv pip install --force-reinstall --target /tmp/flowrite-install dist/flowrite_executor-0.1.0-py3-none-any.whl
else
	@echo "Installing package using pip..."
	@$(PY) -m pip install --force-reinstall --target /tmp/flowrite-install dist/flowrite_executor-0.1.0-py3-none-any.whl
endif
	@echo "Creating executable script..."
	@echo '#!/usr/bin/env python3' > /tmp/flowrite-install/flowrite
	@echo 'import sys; sys.path.insert(0, "$(prefix)/lib/python/site-packages")' >> /tmp/flowrite-install/flowrite
	@echo 'from src.main import main' >> /tmp/flowrite-install/flowrite
	@echo 'if __name__ == "__main__": main()' >> /tmp/flowrite-install/flowrite
	@chmod +x /tmp/flowrite-install/flowrite
	@echo "Installing to system directories..."
ifeq ($(DESTDIR),)
	@echo "Using sudo for system installation..."
	@sudo mkdir -p $(prefix)/lib/python/site-packages
	@sudo cp -r /tmp/flowrite-install/* $(prefix)/lib/python/site-packages/
	@sudo mv $(prefix)/lib/python/site-packages/flowrite $(bindir)/flowrite
	@sudo chmod +x $(bindir)/flowrite
	@echo "✅ flowrite installed to $(bindir)/flowrite"
else
	@mkdir -p $(DESTDIR)$(prefix)/lib/python/site-packages
	@cp -r /tmp/flowrite-install/* $(DESTDIR)$(prefix)/lib/python/site-packages/
	@mv $(DESTDIR)$(prefix)/lib/python/site-packages/flowrite $(DESTDIR)$(bindir)/flowrite
	@chmod +x $(DESTDIR)$(bindir)/flowrite
	@echo "✅ flowrite installed to $(DESTDIR)$(bindir)/flowrite"
endif
	@rm -rf /tmp/flowrite-install

# Install stripped executable (same as install for Python)
install-strip: install
	@echo "✅ flowrite installed (Python executable - no stripping needed)"

# Uninstall system executable
uninstall:
	@echo "Uninstalling flowrite system executable..."
ifeq ($(DESTDIR),)
	@echo "Using sudo for system file removal..."
	@sudo rm -f $(bindir)/flowrite
	@sudo rm -rf $(prefix)/lib/python/site-packages/flowrite_executor*
	@sudo rm -rf $(prefix)/lib/python/site-packages/src
	@echo "✅ flowrite uninstalled from $(bindir)/flowrite"
else
	@rm -f $(DESTDIR)$(bindir)/flowrite
	@rm -rf $(DESTDIR)$(prefix)/lib/python/site-packages/flowrite_executor*
	@rm -rf $(DESTDIR)$(prefix)/lib/python/site-packages/src
	@echo "✅ flowrite uninstalled from $(DESTDIR)$(bindir)/flowrite"
endif