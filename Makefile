# Flowrite Workflow Executor Makefile

.PHONY: help install test run clean worker simulation

# Default target
help:
	@echo "Flowrite Workflow Executor"
	@echo "=========================="
	@echo ""
	@echo "Available targets:"
	@echo "  install     - Install dependencies"
	@echo "  test        - Run test workflows"
	@echo "  run         - Run workflow (use YAML=file.yaml)"
	@echo "  simulation  - Run workflow in simulation mode"
	@echo "  worker      - Start Temporal worker"
	@echo "  sample      - Create sample workflow"
	@echo "  clean       - Clean temporary files"
	@echo "  lint        - Run code linting"
	@echo ""
	@echo "Examples:"
	@echo "  make run YAML=flow_blueprint.yaml"
	@echo "  make simulation YAML=test_workflow.yaml"
	@echo "  make test"

# Installation
install:
	@echo "Installing dependencies..."
	pip install -r requirements.txt || echo "No requirements.txt found, install manually: pyyaml temporalio"

# Test workflows
test:
	@echo "Testing workflow executor..."
	python -m src.main run test_workflow.yaml --simulation
	python -m src.main run flow_blueprint.yaml --simulation
	python -m src.main run echo_test.yaml --simulation
	@echo "✅ All tests completed successfully!"

# Run workflow (requires YAML parameter)
run:
ifndef YAML
	@echo "Error: Please specify YAML file with YAML=filename.yaml"
	@exit 1
endif
	@echo "Running workflow: $(YAML)"
	python -m src.main run $(YAML)

# Run in simulation mode
simulation:
ifndef YAML
	@echo "Error: Please specify YAML file with YAML=filename.yaml"
	@exit 1
endif
	@echo "Running workflow in simulation: $(YAML)"
	python -m src.main run $(YAML) --simulation

# Start Temporal worker
worker:
	@echo "Starting Temporal worker..."
	python -m src.main worker

# Create sample workflow
sample:
	@echo "Creating sample workflow..."
	python -m src.main create-sample
	@echo "✅ Created sample_workflow.yaml"

# Clean temporary files
clean:
	@echo "Cleaning temporary files..."
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} + || true
	find . -name "*.tmp" -delete
	find . -name "*.log" -delete
	@echo "✅ Cleanup completed"

# Code linting (basic checks)
lint:
	@echo "Running basic code checks..."
	python -m py_compile src/*.py
	@echo "✅ Python syntax check passed"

# Development targets
dev-setup: install sample
	@echo "Development environment ready!"

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
	@find . -name "*.py" -not -path "./.venv/*" | xargs wc -l | tail -1

# Show project structure
structure:
	@echo "Project Structure:"
	@echo "=================="
	@tree . -I '__pycache__|.venv|*.pyc' || find . -type f -name "*.py" -o -name "*.yaml" -o -name "*.md" | grep -v __pycache__ | sort

# Quick demo
demo: sample
	@echo "🚀 Running Flowrite Demo"
	@echo "======================="
	make simulation YAML=sample_workflow.yaml