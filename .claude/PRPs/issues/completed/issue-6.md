# Investigation: Variable substitution failing for GitHub Actions syntax - shows '}' instead of values

**Issue**: #6 (https://github.com/tbrandenburg/flowrite/issues/6)
**Type**: BUG
**Investigated**: 2026-02-25T10:30:00Z

### Assessment

| Metric     | Value  | Reasoning                                                                                                                                                                 |
| ---------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Severity   | HIGH   | Major feature broken - GitHub Actions variable substitution completely fails, making workflow debugging impossible and confusing users with misleading output            |
| Complexity | MEDIUM | 2-3 files affected with straightforward regex fix, but requires understanding GitHub Actions syntax patterns and integration with existing variable substitution system |
| Confidence | HIGH   | Clear root cause identified with exact regex pattern causing the issue, strong evidence from code exploration shows precise line where malformed substitution occurs     |

---

## Problem Statement

GitHub Actions-style variable references like `${{ needs.setup.outputs.build_id }}` fail during variable substitution, displaying only the closing curly bracket `}` instead of actual values. This breaks workflow visibility and makes debugging impossible.

---

## Analysis

### Root Cause Analysis

**WHY**: Echo statements show `}` instead of variable values
↓ **BECAUSE**: Variable substitution regex incorrectly matches GitHub Actions syntax
**Evidence**: `src/utils.py:35` - `env_pattern = r"\$\{([^}]+)\}"`

↓ **BECAUSE**: Regex `([^}]+)` captures everything until first `}`, not accounting for double braces
**Evidence**: Pattern `${{ needs.setup.outputs.build_id }}` matches `${{ needs.setup.outputs.build_id }` and captures `{ needs.setup.outputs.build_id `

↓ **BECAUSE**: Replacement removes the matched portion but leaves the final `}`
**Evidence**: `src/utils.py:40` - `result.replace(f"${{{var_name}}}", env_value)` where `var_name = "{ needs.setup.outputs.build_id "` 

↓ **ROOT CAUSE**: Single-brace regex pattern conflicts with double-brace GitHub Actions syntax
**Evidence**: `src/utils.py:35` - `r"\$\{([^}]+)\}"` should not match `${{ }}` patterns at all

### Evidence Chain

**WHY**: `${{ needs.setup.outputs.build_id }}` becomes `}`
↓ **BECAUSE**: Regex `r"\$\{([^}]+)\}"` matches `${{ needs.setup.outputs.build_id }`
**Evidence**: `src/utils.py:35-36` - Pattern finds first `}` and captures `{ needs.setup.outputs.build_id `

↓ **BECAUSE**: `replace(f"${{{ needs.setup.outputs.build_id }}", "")` removes most but not all
**Evidence**: `src/utils.py:40` - Only replaces the matched portion, final `}` remains

↓ **ROOT CAUSE**: Need to either skip GitHub Actions patterns or handle them separately
**Evidence**: `src/main.py:626` - GitHub Actions patterns already handled elsewhere with `r"\$\{\{\s*steps\.(\w+)\.outputs\.(\w+)\s*\}\}"`

### Affected Files

| File            | Lines  | Action | Description                                          |
| --------------- | ------ | ------ | ---------------------------------------------------- |
| `src/utils.py`  | 35-40  | UPDATE | Fix regex to avoid GitHub Actions patterns          |
| `src/main.py`   | 608    | UPDATE | Extend GitHub Actions support to handle `needs.*`   |
| `tests/test_*`  | NEW    | CREATE | Add tests for GitHub Actions variable substitution  |

### Integration Points

- `src/main.py:521` - LocalEngine calls VariableSubstitution.substitute()
- `src/main.py:155` - Temporal workflow calls same method
- `src/utils.py:83` - BashExecutor also uses variable substitution
- `src/main.py:626` - Existing GitHub Actions handling for `steps.*` patterns only

### Git History

- **Introduced**: cbf3c48 - 2026-02-24 - "feat: implement <750 LOC YAML workflow executor with temporal orchestration"
- **Last modified**: cbf3c48 - Initial implementation
- **Implication**: Original bug in initial implementation, regex designed for simple ${VAR} patterns only

---

## Implementation Plan

### Step 1: Fix regex pattern to avoid GitHub Actions conflicts

**File**: `src/utils.py`
**Lines**: 35-40
**Action**: UPDATE

**Current code:**

```python
# Handle environment variables that aren't in our dict
env_pattern = r"\$\{([^}]+)\}"
matches = re.findall(env_pattern, result)
for var_name in matches:
    if var_name not in variables:
        env_value = os.environ.get(var_name, "")
        result = result.replace(f"${{{var_name}}}", env_value)
```

**Required change:**

```python
# Handle environment variables that aren't in our dict (skip GitHub Actions patterns)
env_pattern = r"\$\{(?!\{)([^}]+)\}"  # Negative lookahead to avoid ${{ patterns
matches = re.findall(env_pattern, result)
for var_name in matches:
    if var_name not in variables:
        env_value = os.environ.get(var_name, "")
        result = result.replace(f"${{{var_name}}}", env_value)
```

**Why**: Negative lookahead `(?!\{)` prevents matching when `${` is followed by another `{`, avoiding GitHub Actions patterns entirely.

---

### Step 2: Extend GitHub Actions support in main.py

**File**: `src/main.py`
**Lines**: 608-634
**Action**: UPDATE

**Current code:**

```python
# Only handles steps.* patterns in _process_job_level_outputs
step_pattern = r"\$\{\{\s*steps\.(\w+)\.outputs\.(\w+)\s*\}\}"
```

**Required change:**

```python
def _resolve_github_actions_reference(self, expression, context):
    """Resolve GitHub Actions patterns like ${{ needs.setup.outputs.build_id }}"""
    import re
    
    # Handle needs.* patterns
    needs_pattern = r"\$\{\{\s*needs\.(\w+)\.outputs\.(\w+)\s*\}\}"
    needs_match = re.search(needs_pattern, expression)
    if needs_match:
        job_id = needs_match.group(1)
        output_key = needs_match.group(2)
        # Return from context or workflow state
        return context.get('job_outputs', {}).get(job_id, {}).get(output_key, '')
    
    # Handle steps.* patterns (existing logic)
    step_pattern = r"\$\{\{\s*steps\.(\w+)\.outputs\.(\w+)\s*\}\}"
    step_match = re.search(step_pattern, expression)
    if step_match:
        step_id = step_match.group(1)
        output_key = step_match.group(2)
        return context.get('step_outputs', {}).get(output_key, '')
    
    return None
```

**Why**: Adds support for `needs.*` patterns that the issue specifically mentions are failing.

---

### Step 3: Update VariableSubstitution to handle GitHub Actions patterns

**File**: `src/utils.py`  
**Lines**: 15-42
**Action**: UPDATE

**Add GitHub Actions preprocessing:**

```python
@staticmethod
def substitute(text: str, variables: dict, github_actions_context: dict = None) -> str:
    """Substitute variables in text with GitHub Actions support"""
    if not text:
        return text
    
    result = text
    
    # First, handle GitHub Actions patterns if context provided
    if github_actions_context:
        result = VariableSubstitution._resolve_github_actions_patterns(result, github_actions_context)
    
    # Then handle regular variable substitution (existing logic)
    # ... rest of existing code ...
```

**Why**: Provides proper GitHub Actions support before falling back to regular variable substitution.

---

### Step 4: Add comprehensive tests

**File**: `tests/test_github_actions_variables.py`
**Action**: CREATE

**Test cases to add:**

```python
import pytest
from src.utils import VariableSubstitution

class TestGitHubActionsVariables:
    def test_needs_pattern_substitution(self):
        """Test ${{ needs.job.outputs.key }} substitution"""
        text = "Build ID: ${{ needs.setup.outputs.build_id }}"
        context = {
            'job_outputs': {
                'setup': {'build_id': 'build-12345'}
            }
        }
        result = VariableSubstitution.substitute(text, {}, context)
        assert result == "Build ID: build-12345"
    
    def test_mixed_variable_patterns(self):
        """Test mixing GitHub Actions and regular variables"""
        text = "Build ${{ needs.setup.outputs.build_id }} on ${ENVIRONMENT}"
        variables = {'ENVIRONMENT': 'production'}
        context = {
            'job_outputs': {
                'setup': {'build_id': 'build-12345'}
            }
        }
        result = VariableSubstitution.substitute(text, variables, context)
        assert result == "Build build-12345 on production"
    
    def test_no_leftover_braces(self):
        """Test that no '}' characters are left after substitution"""
        text = "Env: ${{ needs.setup.outputs.environment }}"
        context = {
            'job_outputs': {
                'setup': {'environment': 'development'}
            }
        }
        result = VariableSubstitution.substitute(text, {}, context)
        assert '}' not in result
        assert result == "Env: development"
```

---

## Patterns to Follow

**From codebase - mirror these exactly:**

```python
# SOURCE: src/main.py:626-630
# Pattern for GitHub Actions regex matching
step_pattern = r"\$\{\{\s*steps\.(\w+)\.outputs\.(\w+)\s*\}\}"
match = re.search(step_pattern, output_expression)
if match:
    step_id = match.group(1)
    output_key = match.group(2)
```

```python
# SOURCE: src/utils.py:31-32
# Pattern for variable replacement
for pattern in patterns:
    result = result.replace(pattern, str_value)
```

---

## Edge Cases & Risks

| Risk/Edge Case                        | Mitigation                                                       |
| ------------------------------------- | ---------------------------------------------------------------- |
| Nested braces in variable values      | Test with complex variable values containing braces             |
| Missing job outputs in context        | Return empty string and log warning, don't crash               |
| Malformed GitHub Actions syntax       | Validate pattern matching and handle gracefully                 |
| Performance with large text blocks    | Regex optimization with compiled patterns                       |
| Backwards compatibility               | Make github_actions_context optional parameter                  |

---

## Validation

### Automated Checks

```bash
# Run the project's validation pipeline
make test                                    # Run full test suite
python -m pytest tests/test_github_actions_variables.py -v  # New tests
make run YAML=examples/01_basic_workflow.yaml  # Integration test
cat temporal-worker.log | grep -a "TEMPORAL:" # Check actual output
```

### Manual Verification

1. Run basic workflow and verify echo statements show actual values instead of `}`
2. Test both local mode (`make local`) and temporal mode (`make temporal-dev`)  
3. Verify existing variable substitution still works for `${VAR}` patterns
4. Check that job outputs work correctly in workflow summary

---

## Scope Boundaries

**IN SCOPE:**

- Fix regex pattern to avoid GitHub Actions conflicts
- Add support for `needs.*` patterns in GitHub Actions syntax
- Ensure no leftover `}` characters in output
- Maintain backwards compatibility

**OUT OF SCOPE (do not touch):**

- Other GitHub Actions features (contexts, expressions, functions)
- Workflow parsing or YAML structure changes  
- Temporal orchestration logic changes
- Performance optimizations beyond basic regex fixes

---

## Metadata

- **Investigated by**: Claude
- **Timestamp**: 2026-02-25T10:30:00Z  
- **Artifact**: `.claude/PRPs/issues/issue-6.md`