# Flowrite Workflow Examples

This directory contains simplified example workflows demonstrating the various features and capabilities of the Flowrite workflow executor.

## ⚡ Simplified for Local Execution

These examples are **intentionally simplified** for educational purposes and reliable local execution:

- **Echo-based operations**: Complex file operations, API calls, and deployments are replaced with descriptive echo statements
- **No external dependencies**: Examples run without requiring external services, databases, or network access  
- **Instant execution**: Sleep commands and delays are removed for immediate feedback
- **Predictable behavior**: Random failures and timing-dependent operations are replaced with consistent demonstrations
- **Educational focus**: Each example clearly demonstrates workflow concepts while remaining lightweight and maintainable

**Purpose**: Learn workflow patterns, job dependencies, parallel execution, loops, and complex DAGs through simplified demonstrations that focus on the workflow orchestration rather than the implementation details.

## Example Workflows

### 1. Basic Workflow (`01_basic_workflow.yaml`)
**Features Demonstrated:**
- Simple job dependencies (`needs`)
- Output propagation between jobs (`${{ needs.job.outputs.key }}`)
- Environment variable usage (`$GITHUB_ENV`, `$GITHUB_OUTPUT`)
- Conditional execution (`if: always()`)
- Variable substitution

**Use Case:** Standard CI/CD pipeline with setup → build → package → notify flow.

### 2. Step Sequences (`02_step_sequences.yaml`)
**Features Demonstrated:**
- Sequential step execution within jobs
- Complex multi-phase workflows (preparation → build → testing → deployment)
- Input parameters (`workflow_dispatch`)
- Environment-specific configurations
- Step-by-step state management

**Use Case:** Deployment pipeline with multiple sequential phases and input validation.

### 3. Parallel Execution (`03_parallel_execution.yaml`)
**Features Demonstrated:**
- True parallel job execution
- Fan-out patterns (multiple jobs from single setup)
- Fan-in patterns (aggregation job depending on multiple parallel jobs)
- Conditional parallel execution based on detected changes
- Cross-job coordination and synchronization

**Use Case:** Modern CI/CD with parallel builds, tests, and quality checks.

### 4. Loop Execution (`04_loop_execution.yaml`)
**Features Demonstrated:**
- **Job-level loops:** Retry entire jobs with `loop: { until: success(), max_iterations: N }`
- **Step-level loops:** Retry individual steps with polling semantics
- Multiple loop conditions (`success()`, `env.VAR == 'value'`)
- Parallel jobs with individual retry policies
- Complex retry logic and error handling

**Use Case:** Resilient workflows that handle flaky services and external dependencies.

### 5. Complex DAG (`05_complex_dag.yaml`)
**Features Demonstrated:**
- Multi-level dependency chains
- Complex conditional execution paths
- Fan-out and fan-in patterns
- Cross-cutting concerns (security, monitoring)
- Environment-specific deployment flows
- Canary deployment patterns
- Comprehensive result aggregation

**Use Case:** Enterprise deployment pipeline with multiple environments, security gates, and sophisticated deployment strategies.

## Testing the Examples

### Prerequisites
Ensure you have Flowrite installed and configured:

```bash
# Install dependencies
uv install

# Verify installation
make help
```

**Note**: These simplified examples require no external services, databases, or complex setup - they work immediately with just the basic Flowrite installation.

### Running Individual Examples

#### 1. Basic Workflow
```bash
# Simulation mode (no Temporal required)
make simulation YAML=examples/01_basic_workflow.yaml

# With Temporal server
make run YAML=examples/01_basic_workflow.yaml
```

#### 2. Step Sequences
```bash
# Simulation mode
make simulation YAML=examples/02_step_sequences.yaml

# With custom input parameters (Temporal mode)
make run YAML=examples/02_step_sequences.yaml
```

#### 3. Parallel Execution
```bash
# Simulation mode
make simulation YAML=examples/03_parallel_execution.yaml

# Watch parallel execution in real-time
make run YAML=examples/03_parallel_execution.yaml
```

#### 4. Loop Execution
```bash
# Simulation mode
make simulation YAML=examples/04_loop_execution.yaml

# With custom retry parameters
make run YAML=examples/04_loop_execution.yaml
```

#### 5. Complex DAG
```bash
# Simulation mode
make simulation YAML=examples/05_complex_dag.yaml

# Full production deployment simulation
make run YAML=examples/05_complex_dag.yaml
```

### Running All Examples (Test Suite)

```bash
# Run all examples in simulation mode
for example in examples/*.yaml; do
  echo "Testing $example..."
  make simulation YAML="$example"
  echo "---"
done
```

### Expected Output

Each workflow will demonstrate:

1. **Parsing Success**: YAML structure validation
2. **Dependency Resolution**: Correct job ordering
3. **Conditional Logic**: Proper if/when evaluation  
4. **Variable Substitution**: Output and environment variable propagation
5. **Loop Execution**: Retry and polling behavior demonstrations (where applicable)
6. **Error Handling**: Graceful failure management patterns

**Note**: Outputs are simplified echo statements with emoji indicators (✅ 🚀 ⭐ 🔄 🏁) that clearly show workflow progression and state changes.

### Advanced Testing

#### Performance Testing
```bash
# Measure execution time for complex workflows
time make simulation YAML=examples/05_complex_dag.yaml
```

#### Validation Testing
```bash
# Validate YAML syntax
for example in examples/*.yaml; do
  python -c "import yaml; yaml.safe_load(open('$example'))"
done
```

#### Integration Testing
```bash
# Test with local execution (no Temporal server required)
make local YAML=examples/05_complex_dag.yaml

# All examples work in both simulation and local modes
make simulation YAML=examples/01_basic_workflow.yaml
make local YAML=examples/01_basic_workflow.yaml
```

## Key Learning Points

### 1. Job Dependencies
- Use `needs: [job1, job2]` for dependency management
- Access outputs with `${{ needs.job.outputs.key }}`
- Use `if: always()` to run regardless of dependency failures

### 2. Parallel Execution
- Jobs without dependencies run in parallel
- Use fan-out/fan-in patterns for efficient resource utilization
- Coordinate parallel jobs with shared outputs

### 3. Loop Semantics
- **Job-level loops**: Retry entire jobs (good for flaky infrastructure)
- **Step-level loops**: Polling and incremental operations
- Configure appropriate `max_iterations` to prevent infinite loops

### 4. Complex Workflows
- Break down complex processes into logical job units
- Use conditional execution for environment-specific flows
- Implement proper error handling and rollback procedures

### 5. Best Practices
- Keep job outputs minimal and focused
- Use descriptive job and step names
- Implement comprehensive error reporting
- Design for both success and failure scenarios

## Troubleshooting

### Common Issues

1. **YAML Syntax Errors**: Validate with `python -c "import yaml; yaml.safe_load(open('file.yaml'))"`
2. **Dependency Cycles**: Review job `needs` relationships
3. **Output Access Errors**: Ensure source jobs completed successfully
4. **Infinite Loops**: Check loop conditions and `max_iterations`

### Debug Mode
```bash
# Enable debug logging
FLOWRITE_DEBUG=1 make simulation YAML=examples/01_basic_workflow.yaml
```

---

**Note**: These examples are designed to work in both simulation mode and local execution mode for immediate educational value. They use echo-based operations to demonstrate workflow concepts without requiring external dependencies or complex setup.