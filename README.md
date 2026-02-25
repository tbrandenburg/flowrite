# Flowrite Workflow Executor

🚀 **A lightweight, <750 LOC YAML workflow executor with temporal orchestration**

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)
[![Lines of Code](https://img.shields.io/badge/LOC-536%2F750-green.svg)](src/main.py)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## 🎯 Overview

Flowrite is a production-ready workflow executor that supports GitHub Actions-compatible YAML syntax with advanced features like parallel execution, conditional logic, retry loops, and variable propagation. Built with a clean DSL architecture and staying under 750 lines in the main file.

**Two Execution Modes:**
- **🏃 Local Mode**: Immediate bash execution, perfect for development and testing
- **⚡ Temporal Mode**: Distributed orchestration with fault tolerance for production

## ✨ Features

### 🔄 **Workflow Execution**
- **Parallel job execution** with dependency resolution
- **Conditional job execution** (`if: always()`, `if: needs.*.outputs.*`)
- **Job-level and step-level retry loops** with configurable semantics
- **Variable substitution** (`${VAR}`, `$VAR`) and environment propagation
- **Output parsing** (`GITHUB_OUTPUT`, `GITHUB_ENV`) between jobs

### 🏗️ **Architecture**
- **DSL-based parser** with clean separation of concerns
- **Configuration-driven** execution (no hard-coded values)
- **Generic bash execution engine** with error handling
- **Dual execution modes**: Local and Temporal orchestration
- **Extensible type system** for easy feature additions

### 📊 **Code Quality**
- **Main file: 536 lines** (28% under 750 line requirement)
- **Total: 1,184 lines** across 4 well-organized modules
- **Strongly typed** with dataclasses and type hints
- **Comprehensive error handling** and validation

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/your-username/flowrite.git
cd flowrite

# Install dependencies (Python 3.8+)
pip install pyyaml temporalio

# Or use uv for faster dependency management
uv sync
```

### 🏃 Local Mode (Instant Start)

```bash
# Create and run a demo workflow
make demo

# Run any example workflow locally
make local YAML=examples/01_basic_workflow.yaml
make local YAML=examples/03_parallel_execution.yaml
```

### ⚡ Temporal Mode (Distributed Orchestration)

```bash
# Option 1: All-in-one development setup (recommended)
make temporal-dev

# Then run workflows
make run YAML=examples/01_basic_workflow.yaml

# Stop when done
make temporal-stop
```

```bash
# Option 2: Manual setup (for more control)
make temporal-server    # Terminal 1
make worker            # Terminal 2
make run YAML=examples/01_basic_workflow.yaml  # Terminal 3
```

## 📝 Workflow Syntax

Flowrite supports GitHub Actions-compatible YAML with additional loop semantics:

```yaml
name: Example Workflow

jobs:
  setup:
    name: Setup job
    steps:
      - name: Initialize
        id: init
        run: |
          echo "status=ready" >> "$GITHUB_OUTPUT"
          echo "Starting workflow..."

  parallel_job_a:
    name: Job A
    needs: setup
    steps:
      - run: echo "Running job A"

  parallel_job_b:
    name: Job B with loops
    needs: setup
    if: needs.setup.outputs.status == 'ready'
    loop:
      until: success()
      max_iterations: 3
    steps:
      - name: Retry operation
        loop:
          until: env.READY == 'true'
          max_iterations: 5
        run: |
          echo "READY=true" >> "$GITHUB_ENV"
          echo "Operation completed"

  final:
    name: Cleanup
    needs: [parallel_job_a, parallel_job_b]
    if: always()
    steps:
      - run: echo "Workflow completed"
```

### Supported Features

| Feature | Syntax | Description |
|---------|--------|-------------|
| **Job Dependencies** | `needs: [job1, job2]` | Wait for jobs to complete |
| **Conditions** | `if: always()` | Always run job |
| | `if: needs.job.outputs.key == 'value'` | Conditional execution |
| **Job Loops** | `loop: {until: success(), max_iterations: 3}` | Retry entire job |
| **Step Loops** | `loop: {until: env.VAR == 'value', max_iterations: 5}` | Retry individual step |
| **Outputs** | `echo "key=value" >> "$GITHUB_OUTPUT"` | Job outputs |
| **Environment** | `echo "VAR=value" >> "$GITHUB_ENV"` | Environment variables |
| **Variables** | `${VAR}` or `$VAR` | Variable substitution |

## 🛠️ Development

### Available Commands

```bash
make help          # Show all available commands

# Development
make install       # Install dependencies
make test          # Run complete test suite
make demo          # Quick demo

# Local Execution (No dependencies)
make local YAML=examples/01_basic_workflow.yaml

# Temporal Orchestration (Distributed)
make temporal-dev  # Start server + worker
make run YAML=examples/01_basic_workflow.yaml
make temporal-status  # Check status
make temporal-stop    # Stop everything

# Utilities  
make lint          # Code quality checks
make clean         # Clean temporary files
make lines         # Verify LOC requirements
```

### 📁 Example Workflows

The `examples/` folder contains 5 comprehensive workflow demonstrations:

1. **`01_basic_workflow.yaml`** - Simple CI/CD pipeline with job dependencies
2. **`02_step_sequences.yaml`** - Multi-phase deployment with step sequences  
3. **`03_parallel_execution.yaml`** - Modern CI/CD with parallel processing
4. **`04_loop_execution.yaml`** - Resilient workflows with retry mechanisms
5. **`05_complex_dag.yaml`** - Enterprise deployment with complex dependencies

```bash
# Try them all!
make local YAML=examples/01_basic_workflow.yaml
make local YAML=examples/03_parallel_execution.yaml
make local YAML=examples/04_loop_execution.yaml
```

### Project Structure

```
flowrite/
├── src/
│   ├── main.py      # Main orchestrator (536 lines)
│   ├── types.py     # Type definitions (139 lines)
│   ├── dsl.py       # YAML parser & DSL (230 lines)
│   └── utils.py     # Utilities & bash executor (279 lines)
├── examples/        # 5 comprehensive workflow examples
│   ├── 01_basic_workflow.yaml
│   ├── 02_step_sequences.yaml
│   ├── 03_parallel_execution.yaml
│   ├── 04_loop_execution.yaml
│   └── 05_complex_dag.yaml
├── docs/
│   └── flow_blueprint.md  # Workflow specification
├── tests/           # Comprehensive test suite (129 tests)
└── Makefile         # Development automation
```

## 🏗️ Execution Modes

### 🏃 Local Mode
- **Zero dependencies** - runs immediately
- **Real bash execution** with actual command processing
- **Perfect for**: Development, testing, CI/CD pipelines
- **Use when**: You want immediate results without setup

```bash
make local YAML=your_workflow.yaml
```

### ⚡ Temporal Mode  
- **Distributed orchestration** with fault tolerance
- **Requires**: Temporal server (auto-managed with Docker)
- **Perfect for**: Production workflows, long-running processes
- **Use when**: You need durability, retries, and distributed execution

```bash
make temporal-dev  # Starts everything for you
make run YAML=your_workflow.yaml
```

**Temporal Features:**
- 📊 **Web UI**: http://localhost:8233 (workflow monitoring)
- 🔄 **Auto-recovery**: Workflows survive server restarts
- 📈 **Scalability**: Distribute across multiple workers
- 🛡️ **Fault tolerance**: Built-in retry and error handling

## 🧪 Testing

The project includes comprehensive testing:

```bash
make test          # Run all tests (129 tests)
make pytest        # Unit tests only
make local YAML=examples/01_basic_workflow.yaml  # Integration test
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make changes (keep main.py under 750 lines!)
4. Run tests: `make test`
5. Submit a pull request

### Code Quality Standards

- **Main file limit**: 750 lines (currently 536)
- **Type hints**: Required for all functions
- **Error handling**: Comprehensive exception handling
- **Documentation**: Clear docstrings and comments

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🎉 Achievements

✅ **Sub-750 LOC**: Main engine is 536 lines (28% under limit)  
✅ **Full GitHub Actions compatibility**: Supports standard workflow syntax  
✅ **Advanced loop semantics**: Job-level and step-level retry logic  
✅ **Parallel execution**: True concurrent job processing  
✅ **Dual execution modes**: Local immediate + Temporal distributed
✅ **Production ready**: Temporal orchestration with fault tolerance  
✅ **Developer friendly**: One-command setup and comprehensive examples  

---

**Built with ❤️ for workflow automation**

*Flowrite: Simple, powerful, and under 750 lines!* 🚀