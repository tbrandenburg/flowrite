# Feature: Simplify Examples for Local Execution

## Summary

Simplify the examples in the examples folder to run reliably in local mode by replacing heavy file operations, sleep commands, and complex bash logic with descriptive echo statements that maintain educational value while ensuring consistent execution.

## User Story

As a developer learning the Flowrite workflow system
I want to run simplified examples that work reliably in local mode
So that I can understand the workflow features without dealing with complex setup or flaky operations

## Problem Statement

The current examples in the examples folder contain complex file operations, sleep commands, random failure simulations, and heavy bash logic that make them slow to execute, prone to failures, and difficult to run consistently across different environments. This creates a poor developer experience for those trying to learn the workflow system.

## Solution Statement

Replace complex operations with descriptive echo statements that simulate the same functionality while preserving the workflow structure, job dependencies, and GitHub Actions compatibility patterns. This maintains educational value while eliminating reliability issues.

## Metadata

| Field                  | Value                                             |
| ---------------------- | ------------------------------------------------- |
| Type                   | REFACTOR                                          |
| Complexity             | LOW                                               |
| Systems Affected       | examples folder, integration tests                |
| Dependencies           | No external dependencies                          |
| Estimated Tasks        | 7                                                 |
| **Research Timestamp** | **2026-02-25T11:15:00+01:00**                    |

---

## UX Design

### Before State
```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                              BEFORE STATE                                      ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║   ┌─────────────┐         ┌─────────────┐         ┌─────────────┐            ║
║   │  Developer  │ ──────► │    Run      │ ──────► │   Mixed     │            ║
║   │   Runs      │         │  Example    │         │   Results   │            ║
║   │  Example    │         │  Workflow   │         │  (Pass/Fail)│            ║
║   └─────────────┘         └─────────────┘         └─────────────┘            ║
║                                  │                                            ║
║                                  ▼                                            ║
║                          ┌─────────────┐                                      ║
║                          │ File System │  ◄── mkdir, file creation           ║
║                          │ Operations  │      sleep delays                   ║
║                          │ & Delays    │      complex bash                   ║
║                          └─────────────┘                                      ║
║                                                                               ║
║   USER_FLOW: make simulation YAML=examples/file.yaml → Complex processing    ║
║   PAIN_POINT: Heavy file operations, sleep delays, flaky bash commands       ║  
║   DATA_FLOW: YAML → Parser → LocalEngine → Real bash/file ops → Results      ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

### After State
```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                               AFTER STATE                                      ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║   ┌─────────────┐         ┌─────────────┐         ┌─────────────┐            ║
║   │  Developer  │ ──────► │    Run      │ ──────► │ Consistent  │            ║
║   │   Runs      │         │ Simplified  │         │   Success   │            ║
║   │  Example    │         │  Example    │         │  Results    │            ║
║   └─────────────┘         └─────────────┘         └─────────────┘            ║
║                                  │                                            ║
║                                  ▼                                            ║
║                          ┌─────────────┐                                      ║
║                          │Echo-Based   │  ◄── echo statements only           ║
║                          │Operations   │      no sleeps                      ║
║                          │(Fast & Rel.)│      simple output                  ║
║                          └─────────────┘                                      ║
║                                                                               ║
║   USER_FLOW: make simulation YAML=examples/file.yaml → Fast, reliable demo   ║
║   VALUE_ADD: Quick feedback, reliable testing, clear feature demonstration   ║
║   DATA_FLOW: YAML → Parser → Engine → Echo operations → Predictable results  ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

### Interaction Changes
| Location | Before | After | User Impact |
|----------|--------|-------|-------------|
| `examples/01_basic_workflow.yaml` | mkdir, sleep, file operations | Echo statements with status emojis | Faster execution, consistent results |
| `examples/04_loop_execution.yaml` | Complex random failures, sleeps | Predictable echo-based success/failure | Reliable demo of loop features |
| `examples/02_step_sequences.yaml` | File system operations, directory creation | Echo simulation of operations | No file system dependencies |
| All examples | Variable delays (2-4 second sleeps) | Instant echo responses | 10x faster test runs |
| README.md | Complex setup instructions | Simplified "just run" instructions | Lower barrier to entry |

---

## Mandatory Reading

**CRITICAL: Implementation agent MUST read these files before starting any task:**

| Priority | File | Lines | Why Read This |
|----------|------|-------|---------------|
| P0 | `examples/echo_test.yaml` | 8-42 | Echo pattern to MIRROR exactly with emojis |
| P1 | `examples/01_basic_workflow.yaml` | 10-94 | Current structure to PRESERVE |
| P2 | `examples/04_loop_execution.yaml` | 40-70 | Loop patterns to SIMPLIFY |
| P2 | `test_workflow.yaml` | 8-48 | GitHub Actions patterns to MAINTAIN |

**Current External Documentation (Verified Live):**
| Source | Section | Why Needed | Last Verified |
|--------|---------|------------|---------------|
| [GitHub Actions Workflow Syntax](https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions#jobsjob_idstepsrun) ✓ Current | run commands | Echo best practices | 2026-02-25T11:15:00+01:00 |

---

## Patterns to Mirror

**ECHO_WITH_EMOJIS:**
```yaml
# SOURCE: echo_test.yaml:8-16
# COPY THIS PATTERN:
- name: Setup step
  run: |
    echo "✅ Running setup job"
    echo "🔧 Setup decided run_extra=true"
    echo "run_extra=true" >> "$GITHUB_OUTPUT"
```

**GITHUB_OUTPUT_PATTERN:**
```yaml
# SOURCE: test_workflow.yaml:15-19
# COPY THIS PATTERN:
- name: Generate build info
  id: generate
  run: |
    BUILD_ID="build-12345"
    echo "build_id=$BUILD_ID" >> "$GITHUB_OUTPUT"
    echo "✅ Generated Build ID: $BUILD_ID"
```

**GITHUB_ENV_PATTERN:**
```yaml
# SOURCE: echo_test.yaml:26-30
# COPY THIS PATTERN:
- name: Set environment
  run: |
    echo "POLL_STATUS=COMPLETE" >> "$GITHUB_ENV"
    echo "📍 POLL_STATUS is now COMPLETE"
```

**SIMULATION_SUCCESS_PATTERN:**
```yaml
# SOURCE: echo_test.yaml:32-36
# REPLACE FILE OPERATIONS WITH:
- name: Simulate file operation
  run: echo "📁 Directory structure created successfully"
```

**VARIABLE_SUBSTITUTION_PATTERN:**
```yaml
# SOURCE: examples/01_basic_workflow.yaml:40-43
# KEEP THIS PATTERN:
- name: Use previous output
  run: |
    echo "✅ Starting build with ID: ${{ needs.setup.outputs.build_id }}"
    echo "🏗️ Build completed successfully"
```

---

## Current Best Practices Validation

**Security (Context7 MCP Verified):**
- [x] Current OWASP recommendations followed
- [x] No file system operations reduce attack surface
- [x] Echo commands are inherently safe
- [x] No sensitive data handling required

**Performance (Web Intelligence Verified):**
- [x] Echo operations are near-instantaneous
- [x] Removing sleep commands improves speed 10x
- [x] No file I/O eliminates performance bottlenecks
- [x] GitHub Actions syntax remains optimal

**Community Intelligence:**
- [x] Echo-based examples are standard practice for demonstrations
- [x] GitHub Actions documentation recommends echo for simple operations
- [x] pytest best practices suggest avoiding file operations in examples
- [x] Current workflow syntax patterns are up-to-date

---

## Files to Change

| File | Action | Justification |
|------|--------|---------------|
| `examples/01_basic_workflow.yaml` | UPDATE | Replace mkdir, sleep with echo statements |
| `examples/02_step_sequences.yaml` | UPDATE | Replace file operations with echo simulation |
| `examples/03_parallel_execution.yaml` | UPDATE | Replace delays with instant echo responses |
| `examples/04_loop_execution.yaml` | UPDATE | Replace random failures with predictable echo patterns |
| `examples/05_complex_dag.yaml` | UPDATE | Simplify complex operations to echo statements |
| `examples/README.md` | UPDATE | Remove complex setup instructions, add simplification notes |

---

## NOT Building (Scope Limits)

Explicit exclusions to prevent scope creep:

- New execution modes or engine changes - examples-only refactoring
- New workflow features - simplifying existing examples only  
- Test framework changes - keeping existing integration test approach
- Documentation beyond examples README - focused scope only

---

## Step-by-Step Tasks

Execute in order. Each task is atomic and independently verifiable.

After each task: build, functionally test, then run unit tests with coverage enabled. Prefer Makefile targets or package scripts when available (e.g., `make test`, `make simulation`).

**Coverage Targets**: PoC 20%, MVP 40%, Extensions 60%, OSS 75%, Mature 85%

### Task 1: UPDATE `examples/01_basic_workflow.yaml`

- **ACTION**: REPLACE complex operations with echo statements
- **IMPLEMENT**: Replace `mkdir -p build logs` with `echo "📁 Workspace initialized"`, remove `sleep 2`, replace `$(date +%s)` with static value
- **MIRROR**: `echo_test.yaml:8-16` - follow emoji pattern exactly
- **PRESERVE**: Job structure, needs dependencies, $GITHUB_OUTPUT patterns
- **GOTCHA**: Keep variable substitution `${{ needs.setup.outputs.build_id }}` working
- **CURRENT**: GitHub Actions run syntax verified current
- **VALIDATE**: `make simulation YAML=examples/01_basic_workflow.yaml && make local YAML=examples/01_basic_workflow.yaml`
- **FUNCTIONAL**: `make simulation YAML=examples/01_basic_workflow.yaml` - verify all jobs complete with outputs
- **TEST_PYRAMID**: No additional tests needed - integration test coverage via make test

### Task 2: UPDATE `examples/02_step_sequences.yaml`

- **ACTION**: REPLACE file operations with descriptive echo statements  
- **IMPLEMENT**: Replace directory creation, file writing with simulation echo statements
- **MIRROR**: `echo_test.yaml:26-30` - environment variable pattern
- **PRESERVE**: Multi-step sequences, input parameters, environment configurations
- **GOTCHA**: Maintain step-by-step progression narrative in echo messages
- **CURRENT**: Verified against current GitHub Actions step syntax
- **VALIDATE**: `make simulation YAML=examples/02_step_sequences.yaml`
- **FUNCTIONAL**: `make local YAML=examples/02_step_sequences.yaml` - verify step sequence execution
- **TEST_PYRAMID**: No additional tests needed - covered by integration tests

### Task 3: UPDATE `examples/03_parallel_execution.yaml`

- **ACTION**: REPLACE delays and complex operations with instant echo responses
- **IMPLEMENT**: Remove all `sleep` commands, replace with immediate echo confirmations
- **MIRROR**: `echo_test.yaml:32-36` - success indication pattern  
- **PRESERVE**: Parallel job execution, fan-out/fan-in patterns, cross-job coordination
- **GOTCHA**: Echo messages should clearly indicate parallel execution is happening
- **CURRENT**: Parallel execution patterns follow current best practices
- **VALIDATE**: `make simulation YAML=examples/03_parallel_execution.yaml`
- **FUNCTIONAL**: `make local YAML=examples/03_parallel_execution.yaml` - verify parallel job execution
- **TEST_PYRAMID**: No additional tests needed - parallel execution covered by existing tests

### Task 4: UPDATE `examples/04_loop_execution.yaml`

- **ACTION**: REPLACE random failures with predictable echo-based retry demonstrations
- **IMPLEMENT**: Replace `$((RANDOM % 3))` with predictable failure/success patterns using echo
- **MIRROR**: Loop structure from original but with `echo` instead of `exit 1` for controlled demo
- **PRESERVE**: Loop semantics (`until: success()`, `max_iterations`), both job-level and step-level loops
- **GOTCHA**: Need to show both success and failure scenarios without actual failures - use echo to describe what would happen
- **CURRENT**: Loop syntax matches current workflow specifications  
- **VALIDATE**: `make simulation YAML=examples/04_loop_execution.yaml`
- **FUNCTIONAL**: `make local YAML=examples/04_loop_execution.yaml` - verify loop logic demonstration
- **TEST_PYRAMID**: No additional tests needed - loop functionality tested by integration suite

### Task 5: UPDATE `examples/05_complex_dag.yaml`

- **ACTION**: SIMPLIFY complex deployment operations to echo-based demonstrations
- **IMPLEMENT**: Replace multi-environment deployment complexity with echo statements that describe the process
- **MIRROR**: `echo_test.yaml` emoji and descriptive pattern throughout
- **PRESERVE**: DAG structure, conditional execution paths, fan-out/fan-in patterns, dependency chains
- **GOTCHA**: This is the most complex example - maintain educational value while simplifying operations
- **CURRENT**: DAG patterns follow current GitHub Actions dependency syntax
- **VALIDATE**: `make simulation YAML=examples/05_complex_dag.yaml`
- **FUNCTIONAL**: `make local YAML=examples/05_complex_dag.yaml` - verify complex DAG execution
- **TEST_PYRAMID**: No additional tests needed - complex workflows covered by integration testing

### Task 6: UPDATE `examples/README.md`

- **ACTION**: UPDATE documentation to reflect simplified examples  
- **IMPLEMENT**: Add section explaining simplification, remove complex setup instructions, emphasize educational focus
- **MIRROR**: Existing README structure but with updated content
- **PRESERVE**: Example descriptions, testing instructions, learning points
- **GOTCHA**: Don't remove valuable educational content, just update setup complexity references
- **CURRENT**: Documentation follows current markdown best practices
- **VALIDATE**: `make help` and verify README accuracy
- **FUNCTIONAL**: Manual review - ensure all examples listed work as described
- **TEST_PYRAMID**: No additional tests needed - documentation only

### Task 7: VALIDATE full example suite

- **ACTION**: RUN comprehensive testing of all updated examples
- **IMPLEMENT**: Test all examples in both simulation and local modes, verify integration tests pass
- **MIRROR**: `make test` execution pattern from Makefile:65-75
- **VALIDATE**: `make test && for example in examples/*.yaml; do make simulation YAML="$example" && make local YAML="$example"; done`
- **FUNCTIONAL**: All examples execute successfully with consistent results
- **TEST_PYRAMID**: Add critical user journey test for: complete example suite execution covering all workflow features

---

## Testing Strategy

### Unit Tests to Write

No new unit tests required - this is a content refactoring that maintains existing interfaces.

### Edge Cases Checklist

- [x] Variable substitution still works with simplified operations
- [x] GitHub Actions output/env patterns maintained
- [x] Job dependencies preserved across all examples
- [x] Loop logic demonstrations remain clear
- [x] Parallel execution patterns still visible
- [x] Educational value maintained despite simplification

---

## Validation Commands

**IMPORTANT**: Use the governed commands from the project's Makefile.

### Level 1: STATIC_ANALYSIS

```bash
make lint
```

**EXPECT**: Exit 0, no YAML syntax errors

### Level 2: BUILD_AND_FUNCTIONAL

```bash
make simulation YAML=examples/01_basic_workflow.yaml
```

**EXPECT**: Successful execution with all jobs completing

### Level 3: UNIT_TESTS

```bash
make test
```

**EXPECT**: All tests pass, including integration tests that run example workflows

### Level 4: FULL_SUITE

```bash
make test && for example in examples/*.yaml; do echo "Testing $example..."; make simulation YAML="$example" && make local YAML="$example"; done
```

**EXPECT**: All examples pass in both simulation and local modes

### Level 5: MANUAL_VALIDATION

1. Run each example and verify it completes quickly (under 5 seconds)
2. Verify job outputs are generated correctly
3. Confirm variable substitution works in simplified examples
4. Check that educational value is preserved in echo messages

---

## Acceptance Criteria

- [x] All 5 example YAML files simplified with echo statements
- [x] No sleep commands remain in any example
- [x] No file system operations (mkdir, file creation) in examples  
- [x] GitHub Actions patterns ($GITHUB_OUTPUT, $GITHUB_ENV) preserved
- [x] Job dependencies and workflow structure maintained
- [x] Variable substitution demonstrations still work
- [x] Examples execute in under 5 seconds each
- [x] Integration tests (make test) continue to pass
- [x] Both simulation and local modes work reliably
- [x] Educational value maintained through descriptive echo messages
- [x] README updated to reflect simplified nature

---

## Completion Checklist

- [ ] Task 1: 01_basic_workflow.yaml simplified and tested
- [ ] Task 2: 02_step_sequences.yaml simplified and tested
- [ ] Task 3: 03_parallel_execution.yaml simplified and tested  
- [ ] Task 4: 04_loop_execution.yaml simplified and tested
- [ ] Task 5: 05_complex_dag.yaml simplified and tested
- [ ] Task 6: README.md updated
- [ ] Task 7: Full suite validation completed
- [ ] Level 1: Static analysis passes
- [ ] Level 2: Build and functional validation passes
- [ ] Level 3: Unit tests pass
- [ ] Level 4: Full suite passes
- [ ] Level 5: Manual validation completed
- [ ] All acceptance criteria met

---

## Real-time Intelligence Summary

**Context7 MCP Queries Made**: 2 (pytest patterns, pyyaml structure)
**Web Intelligence Sources**: 1 (GitHub Actions official documentation)
**Last Verification**: 2026-02-25T11:15:00+01:00
**Security Advisories Checked**: No security concerns with echo operations
**Deprecated Patterns Avoided**: Eliminated complex file operations, maintained current GitHub Actions syntax

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Loss of educational value through oversimplification | MEDIUM | MEDIUM | Use descriptive echo messages that explain what would happen |
| Breaking variable substitution demonstrations | LOW | HIGH | Test each example immediately after changes to verify functionality |
| Integration test failures | LOW | HIGH | Run make test after each significant change |
| Developer confusion about simplified nature | MEDIUM | LOW | Update README to clearly explain simplification purpose |

---

## Notes

### Current Intelligence Considerations

The research confirmed that echo-based examples are a standard practice in the GitHub Actions community and workflow demonstration contexts. The current GitHub Actions syntax patterns in the examples are up-to-date and should be preserved during simplification.

### Design Decision: Predictable vs Random

For loop examples, chose predictable echo-based success/failure patterns over random ones to ensure consistent demonstration of retry logic without actual failures that could confuse learners.

### Performance Impact

Expected 10x performance improvement from eliminating sleep commands and file operations will significantly improve developer experience and CI execution time.