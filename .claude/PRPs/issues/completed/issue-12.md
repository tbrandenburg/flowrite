# Investigation: Refactor JobWorkflow.run() god method - break into focused methods

**Issue**: #12 (https://github.com/tbrandenburg/flowrite/issues/12)
**Type**: REFACTOR
**Investigated**: 2026-02-28T12:00:00Z

### Assessment

| Metric     | Value  | Reasoning                                                                                                                                    |
| ---------- | ------ | -------------------------------------------------------------------------------------------------------------------------------------------- |
| Priority   | HIGH   | Critical technical debt blocking maintainability and future development, as evidenced by 413-line god method with nested complexity     |
| Complexity | HIGH   | Affects core workflow execution logic, requires careful preservation of Temporal workflow semantics, touches 5+ integration points       |
| Confidence | HIGH   | Clear root causes identified through code analysis, specific variable scoping bugs found, similar refactoring patterns exist in codebase |

---

## Problem Statement

The JobWorkflow.run() method is a 413-line god method that violates Single Responsibility Principle, contains variable scoping bugs, duplicates logic 4+ times, and is impossible to unit test or debug effectively.

---

## Analysis

### Root Cause / Change Rationale

The 413-line god method suffers from excessive responsibilities and structural issues that make it unmaintainable:

**WHY**: Method is difficult to test and maintain
↓ BECAUSE: 413 lines of nested logic combining 5+ different responsibilities
Evidence: `src/main.py:137-413` - Single method handles job orchestration, step execution, loop management, error handling, and output collection

↓ BECAUSE: Code duplication across 4 different execution paths
Evidence: `src/main.py:180-192, 217-229, 300-312, 337-349` - Identical execute_activity calls with minor parameter variations

↓ BECAUSE: Variable scoping errors from copy-paste programming
Evidence: `src/main.py:342-344` - References undefined `job_iteration_outputs` and `step_env_vars` variables

↓ ROOT CAUSE: Lack of method extraction and single responsibility design
Evidence: `src/main.py:137-413` - All execution logic embedded in single workflow method

### Evidence Chain

**WHY**: JobWorkflow.run() is unmaintainable
↓ BECAUSE: 413 lines with 4+ levels of nested control structures
Evidence: `src/main.py:144-271, 273-413` - Two major execution branches with identical nested logic

↓ BECAUSE: Step execution logic duplicated 4 times with variable scoping bugs
Evidence: 
- `src/main.py:180` - Job foreach + step foreach path
- `src/main.py:217` - Job foreach + step until path  
- `src/main.py:300` - Job until + step foreach path
- `src/main.py:337` - Job until + step until path (with scoping bugs)

↓ ROOT CAUSE: Missing method extraction and proper variable scoping
Evidence: `src/main.py:342,344` - `job_iteration_outputs` and `step_env_vars` undefined in scope

### Affected Files

| File                | Lines   | Action | Description                                    |
| ------------------- | ------- | ------ | ---------------------------------------------- |
| `src/main.py`       | 137-413 | UPDATE | Extract 7 focused methods from god method     |
| `src/main.py`       | 342,344 | FIX    | Fix variable scoping bugs                      |
| `test_job_workflow` | NEW     | CREATE | Add unit tests for extracted methods          |

### Integration Points

- `src/main.py:484` - WorkflowExecutor.run() calls JobWorkflow.run()
- `src/main.py:180,217,300,337` - execute_job_step activity calls
- `src/dsl.py:145,162,284` - ConditionEvaluator method calls
- `src/utils.py:176,213,296,333` - VariableSubstitution calls

### Git History

- **Introduced**: Initial commit - Core workflow execution logic
- **Last modified**: Recent commits adding foreach loop support
- **Implication**: Feature additions without refactoring led to code duplication and complexity

---

## Implementation Plan

### Step 1: Fix Variable Scoping Bugs

**File**: `src/main.py`
**Lines**: 342-344, 352
**Action**: FIX

**Current code:**

```python
# Line 342-344 (BROKEN - variables not in scope)
step.name
or f"step-{len(job_iteration_outputs)}-job-{item_index}-item-{step_item_index}",
command,
step_env_vars,

# Line 352 (BROKEN - variable not in scope)  
job_iteration_outputs.update(result.outputs)
```

**Required change:**

```python
# Line 342-344 (FIXED - use correct variables in scope)
step.name
or f"step-{len(all_outputs)}-attempt-{attempt}",
command,
env_vars,

# Line 352 (FIXED - use correct variable in scope)
all_outputs.update(result.outputs)
```

**Why**: Variables `job_iteration_outputs` and `step_env_vars` are not defined in the job until/step until execution path

---

### Step 2: Extract Job Foreach Execution Logic

**File**: `src/main.py`
**Lines**: 144-271
**Action**: EXTRACT to `_execute_job_foreach_iterations()`

**Current code:**

```python
# Lines 144-271 - Job foreach execution branch
if job_def.loop and job_def.loop.foreach:
    items = ConditionEvaluator.parse_foreach_items(job_def.loop.foreach)
    all_outputs = {}
    
    for item_index, item in enumerate(items):
        # ... 120+ lines of nested logic ...
```

**Required change:**

```python
async def _execute_job_foreach_iterations(
    self, job_id: str, job_def: JobDefinition, env_vars: Dict[str, str]
) -> JobOutput:
    """Execute job with foreach iterations"""
    items = ConditionEvaluator.parse_foreach_items(job_def.loop.foreach)
    all_outputs = {}
    
    for item_index, item in enumerate(items):
        job_env_vars = env_vars.copy()
        job_env_vars.update({
            "FOREACH_ITEM": item,
            "FOREACH_INDEX": str(item_index), 
            "FOREACH_ITERATION": str(item_index + 1)
        })
        
        try:
            iteration_outputs = await self._execute_job_iteration_steps(
                job_id, job_def.steps, job_env_vars, item_index
            )
            all_outputs.update(iteration_outputs)
            logger.info(f"Job {job_id} completed for item '{item}'")
        except Exception as e:
            logger.error(f"Job {job_id} failed for item '{item}': {e}")
    
    return JobOutput(job_id=job_id, status=JobStatus.COMPLETED.value, outputs=all_outputs)
```

**Why**: Separates job-level foreach logic into focused method with clear parameters

---

### Step 3: Extract Job Until Execution Logic

**File**: `src/main.py`  
**Lines**: 273-413
**Action**: EXTRACT to `_execute_job_until_iterations()`

**Current code:**

```python
# Lines 273-413 - Job until/conditional execution branch  
else:
    max_attempts = job_def.loop.max_iterations if job_def.loop else 1
    
    for attempt in range(max_attempts):
        # ... 130+ lines of nested logic with bugs ...
```

**Required change:**

```python
async def _execute_job_until_iterations(
    self, job_id: str, job_def: JobDefinition, env_vars: Dict[str, str]
) -> JobOutput:
    """Execute job with until/conditional iterations"""
    max_attempts = job_def.loop.max_iterations if job_def.loop else 1
    
    for attempt in range(max_attempts):
        try:
            all_outputs = await self._execute_job_iteration_steps(
                job_id, job_def.steps, env_vars, attempt
            )
            return JobOutput(job_id=job_id, status=JobStatus.COMPLETED.value, outputs=all_outputs)
        except Exception as e:
            logger.error(f"Job {job_id} attempt {attempt + 1} failed: {e}")
            
            if job_def.loop and attempt < max_attempts - 1:
                should_continue = not ConditionEvaluator.evaluate_loop_condition(
                    job_def.loop.until or "", attempt + 1, max_attempts, False, env_vars
                )
                if should_continue:
                    await asyncio.sleep(1)
                    continue
            
            if attempt == max_attempts - 1:
                return JobOutput(job_id=job_id, status=JobStatus.FAILED.value, error=str(e))
    
    return JobOutput(job_id=job_id, status=JobStatus.FAILED.value, error="Unexpected termination")
```

**Why**: Separates job-level until logic into focused method, fixes variable scoping issues

---

### Step 4: Extract Step Iteration Execution

**File**: `src/main.py`
**Action**: CREATE new method `_execute_job_iteration_steps()`

**Required change:**

```python
async def _execute_job_iteration_steps(
    self, job_id: str, steps: List[StepDefinition], env_vars: Dict[str, str], iteration_index: int
) -> Dict[str, str]:
    """Execute all steps for a single job iteration"""
    all_outputs = {}
    
    for step in steps:
        if step.loop and step.loop.foreach:
            step_outputs = await self._execute_step_foreach_iterations(
                job_id, step, env_vars, iteration_index
            )
        else:
            step_outputs = await self._execute_step_until_iterations(
                job_id, step, env_vars, iteration_index  
            )
        
        all_outputs.update(step_outputs)
        
        # Update environment with step outputs
        if step.id:
            for key, value in step_outputs.items():
                env_vars[f"STEP_{step.id}_{key}".upper()] = str(value)
    
    return all_outputs
```

**Why**: Eliminates code duplication between job foreach and job until paths

---

### Step 5: Extract Step Foreach Logic

**File**: `src/main.py`
**Action**: CREATE new method `_execute_step_foreach_iterations()`

**Required change:**

```python
async def _execute_step_foreach_iterations(
    self, job_id: str, step: StepDefinition, base_env_vars: Dict[str, str], job_iteration: int
) -> Dict[str, str]:
    """Execute step with foreach iterations"""
    items = ConditionEvaluator.parse_foreach_items(step.loop.foreach)
    step_outputs = {}
    
    for item_index, item in enumerate(items):
        step_env_vars = base_env_vars.copy()
        step_env_vars.update({
            "FOREACH_ITEM": item,
            "FOREACH_INDEX": str(item_index),
            "FOREACH_ITERATION": str(item_index + 1)
        })
        
        command = VariableSubstitution.substitute(step.run or "", step_env_vars)
        step_name = step.name or f"step-{len(step_outputs)}-job-{job_iteration}-item-{item_index}"
        
        result = await workflow.execute_activity(
            execute_job_step,
            args=[job_id, step_name, command, step_env_vars],
            start_to_close_timeout=timedelta(seconds=config.step_timeout_seconds)
        )
        
        if result.success:
            step_outputs.update(result.outputs)
        else:
            logger.warning(f"Step failed for item '{item}': {result.error}")
    
    return step_outputs
```

**Why**: Consolidates duplicated step foreach logic into single method

---

### Step 6: Extract Step Until Logic

**File**: `src/main.py`
**Action**: CREATE new method `_execute_step_until_iterations()`

**Required change:**

```python
async def _execute_step_until_iterations(
    self, job_id: str, step: StepDefinition, env_vars: Dict[str, str], job_iteration: int
) -> Dict[str, str]:
    """Execute step with until/conditional iterations"""
    step_max = step.loop.max_iterations if step.loop else 1
    
    for step_attempt in range(step_max):
        command = VariableSubstitution.substitute(step.run or "", env_vars)
        step_name = step.name or f"step-attempt-{step_attempt}-job-{job_iteration}"
        
        result = await workflow.execute_activity(
            execute_job_step,
            args=[job_id, step_name, command, env_vars],
            start_to_close_timeout=timedelta(seconds=config.step_timeout_seconds)
        )
        
        if result.success:
            return result.outputs
        
        # Check step loop condition for retry
        if step.loop and step_attempt < step_max - 1:
            should_continue = not ConditionEvaluator.evaluate_loop_condition(
                step.loop.until or "", step_attempt + 1, step_max, result.success, env_vars
            )
            if should_continue:
                continue
        
        if step_attempt == step_max - 1:
            raise Exception(f"Step failed: {result.error}")
    
    return {}
```

**Why**: Consolidates duplicated step until logic, fixes variable scoping issues

---

### Step 7: Refactor Main run() Method

**File**: `src/main.py`
**Lines**: 137-413
**Action**: SIMPLIFY to orchestration only

**Current code:**

```python
async def run(self, job_id: str, job_def: JobDefinition, env_vars: Dict[str, str]) -> JobOutput:
    """Execute a complete job with retry logic"""
    # 413 lines of nested logic...
```

**Required change:**

```python
async def run(self, job_id: str, job_def: JobDefinition, env_vars: Dict[str, str]) -> JobOutput:
    """Execute a complete job with retry logic"""
    logger.info(f"Starting job: {job_id}")
    
    if job_def.loop and job_def.loop.foreach:
        return await self._execute_job_foreach_iterations(job_id, job_def, env_vars)
    else:
        return await self._execute_job_until_iterations(job_id, job_def, env_vars)
```

**Why**: Reduces main method from 413 lines to 8 lines of clear orchestration logic

---

### Step 8: Add Unit Tests

**File**: `test/test_job_workflow.py`
**Action**: CREATE

**Test cases to add:**

```python
import pytest
from unittest.mock import AsyncMock, patch
from src.main import JobWorkflow
from src.types import JobDefinition, StepDefinition, LoopDefinition

@pytest.mark.asyncio
class TestJobWorkflow:
    
    def setup_method(self):
        self.workflow = JobWorkflow()
    
    async def test_execute_step_foreach_iterations(self):
        """Test step foreach iteration execution"""
        step = StepDefinition(
            name="test-step",
            run="echo $FOREACH_ITEM",
            loop=LoopDefinition(foreach=["item1", "item2"])
        )
        
        with patch('src.main.workflow.execute_activity') as mock_activity:
            mock_activity.return_value = AsyncMock(success=True, outputs={"test": "value"})
            
            result = await self.workflow._execute_step_foreach_iterations(
                "test-job", step, {"base": "env"}, 0
            )
            
            assert result == {"test": "value"}
            assert mock_activity.call_count == 2
    
    async def test_execute_step_until_iterations_with_retry(self):
        """Test step until iterations with retry logic"""
        step = StepDefinition(
            name="test-step", 
            run="flaky-command",
            loop=LoopDefinition(max_iterations=3, until="success")
        )
        
        with patch('src.main.workflow.execute_activity') as mock_activity:
            # Fail twice, then succeed
            mock_activity.side_effect = [
                AsyncMock(success=False, error="Failed attempt 1"),
                AsyncMock(success=False, error="Failed attempt 2"), 
                AsyncMock(success=True, outputs={"result": "success"})
            ]
            
            result = await self.workflow._execute_step_until_iterations(
                "test-job", step, {"env": "vars"}, 0
            )
            
            assert result == {"result": "success"}
            assert mock_activity.call_count == 3

    async def test_variable_scoping_fix(self):
        """Test that variable scoping issues are fixed"""
        # This test ensures the previously broken lines 342-344 work correctly
        job_def = JobDefinition(
            steps=[StepDefinition(name="test", run="echo test")],
            loop=LoopDefinition(max_iterations=1)
        )
        
        with patch('src.main.workflow.execute_activity') as mock_activity:
            mock_activity.return_value = AsyncMock(success=True, outputs={"test": "value"})
            
            result = await self.workflow._execute_job_until_iterations(
                "test-job", job_def, {"env": "vars"}  
            )
            
            assert result.status == "completed"
            assert mock_activity.called
```

---

## Patterns to Follow

**From codebase - mirror these exactly:**

```python
# SOURCE: src/main.py:521-861 (LocalEngine)
# Pattern for method extraction and single responsibility
class LocalEngine:
    async def run_workflow(self, workflow_file: str) -> WorkflowResult:
        # High-level orchestration only (42 lines)
        workflow_def = self._parse_and_validate_workflow(workflow_file)
        completed, job_outputs, env_vars, executor = self._initialize_execution_state(workflow_def)
        
        while len(completed) < len(workflow_def.jobs):
            ready_jobs, should_break = await self._get_ready_jobs_with_diagnostics(...)
            if should_break: break
            
            for job_id in ready_jobs:
                await self._execute_job(job_id, ...)  # Delegate to focused method
    
    async def _execute_job(self, ...):          # Single responsibility (42 lines)
    async def _execute_job_steps(self, ...):    # Single responsibility (31 lines)  
    async def _execute_step_with_retry(self, ...):  # Single responsibility (57 lines)
```

```python
# SOURCE: src/dsl.py:156-205 (ConditionEvaluator)
# Pattern for focused method responsibilities
class ConditionEvaluator:
    @staticmethod
    def parse_foreach_items(foreach_expr: str) -> List[str]:
        # Single responsibility: parse foreach expressions only
        
    @staticmethod  
    def evaluate_loop_condition(...) -> bool:
        # Single responsibility: evaluate loop conditions only
```

---

## Edge Cases & Risks

| Risk/Edge Case                    | Mitigation                                                     |
| --------------------------------- | -------------------------------------------------------------- |
| Temporal workflow determinism     | Keep all extracted methods as instance methods, preserve flow |
| Activity timeout preservation     | Copy exact timeout patterns from original code                |
| Variable environment inheritance  | Test env var propagation between job/step iterations          |
| Error handling behavior changes   | Preserve exact exception handling and logging patterns        |
| Foreach item scoping              | Validate FOREACH_* variables available in correct scopes      |

---

## Validation

### Automated Checks

```bash
# Run type checking
python -m mypy src/main.py

# Run existing test suite to ensure no regressions  
python -m pytest tests/ -v

# Run new unit tests for extracted methods
python -m pytest test/test_job_workflow.py -v

# Run integration tests to ensure workflow functionality preserved
python -m pytest tests/test_integration_scenarios.py -v
```

### Manual Verification

1. Execute a workflow with job-level foreach to verify iteration handling works
2. Execute a workflow with step-level foreach to verify nested loops work  
3. Execute a workflow with until conditions to verify retry logic preserved
4. Verify error handling and logging behavior matches original implementation
5. Check that all environment variables propagate correctly between iterations

---

## Scope Boundaries

**IN SCOPE:**

- Extract 6 focused methods from JobWorkflow.run()
- Fix variable scoping bugs on lines 342-344, 352
- Add comprehensive unit tests for extracted methods
- Preserve all existing workflow functionality and Temporal semantics

**OUT OF SCOPE (do not touch):**

- Changes to WorkflowExecutor or other workflow classes
- Modifications to ConditionEvaluator or VariableSubstitution utilities  
- Changes to execute_job_step activity implementation
- Alterations to JobDefinition/StepDefinition type structures
- Performance optimizations or feature additions

---

## Metadata

- **Investigated by**: Claude
- **Timestamp**: 2026-02-28T12:00:00Z
- **Artifact**: `.claude/PRPs/issues/issue-12.md`