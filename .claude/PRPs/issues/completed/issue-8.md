# Investigation: Improve GitHub Actions variable substitution robustness

**Issue**: #8 (https://github.com/tbrandenburg/flowrite/issues/8)
**Type**: REFACTOR
**Investigated**: 2026-02-25T22:15:00Z

### Assessment

| Metric     | Value  | Reasoning                                                                                    |
| ---------- | ------ | -------------------------------------------------------------------------------------------- |
| Priority   | LOW    | Issue explicitly marked as "Low Priority" and describes non-blocking code quality improvements |
| Complexity | MEDIUM | Affects 2-3 files with regex patterns and code consolidation, but has comprehensive test coverage |
| Confidence | HIGH   | Clear evidence from codebase exploration with specific line numbers and well-documented problems |

---

## Problem Statement

The current GitHub Actions variable substitution implementation has fragile pattern reconstruction, potential spacing variations not handled, and duplicate/orphaned code that needs consolidation for better maintainability.

---

## Analysis

### Change Rationale

This refactoring addresses three code quality issues identified after the successful fix in PR #7:

**Issue 1**: Pattern reconstruction in `src/utils.py:69,77` rebuilds patterns instead of using original matched text, making it fragile to spacing variations.

**Issue 2**: The current regex patterns may not handle all spacing combinations robustly, though they already use `\s*` for flexible spacing.

**Issue 3**: Duplicate GitHub Actions resolution logic exists between `src/utils.py` and `src/main.py`, with the main.py version being completely unused (orphaned code).

### Evidence Chain

WHY: Pattern replacement might miss spacing variations
↓ BECAUSE: Code rebuilds patterns instead of using original matches
Evidence: `src/utils.py:69` - `pattern = f"${{{{ needs.{job_id}.outputs.{output_key} }}}}"`

↓ BECAUSE: This assumes exact spacing format
Evidence: `src/utils.py:77` - `pattern = f"${{{{ steps.{step_id}.outputs.{output_key} }}}}"`

↓ ROOT CAUSE: Using `re.findall()` loses the original matched text
Evidence: `src/utils.py:65-66` - `needs_matches = re.findall(needs_pattern, result)`

### Affected Files

| File              | Lines   | Action | Description                     |
| ----------------- | ------- | ------ | ------------------------------- |
| `src/utils.py`    | 65-80   | UPDATE | Improve pattern reconstruction  |
| `src/main.py`     | 640-661 | DELETE | Remove orphaned duplicate function |
| `tests/test_github_actions_variables.py` | NEW | UPDATE | Add spacing variation tests |

### Integration Points

- `src/utils.py:34` - `_resolve_github_actions_patterns()` called from `VariableSubstitution.substitute()`
- `src/main.py:640-661` - `_resolve_github_actions_reference()` is **NEVER CALLED** (orphaned)
- Test coverage exists in `tests/test_github_actions_variables.py`

### Git History

- **Introduced**: 0672bd8 - 2026-02-25 - "Fix: Variable substitution failing for GitHub Actions syntax (#6)"
- **Last modified**: 0672bd8 - Today
- **Implication**: Recently introduced code that can be improved while fresh

---

## Implementation Plan

### Step 1: Improve Pattern Reconstruction Robustness

**File**: `src/utils.py`
**Lines**: 65-80
**Action**: UPDATE

**Current code:**

```python
def _resolve_github_actions_patterns(text: str, context: Dict[str, Any]) -> str:
    """Resolve GitHub Actions patterns like ${{ needs.setup.outputs.build_id }}"""
    import re

    result = text

    # Handle needs.* patterns
    needs_pattern = r"\$\{\{\s*needs\.(\w+)\.outputs\.(\w+)\s*\}\}"
    needs_matches = re.findall(needs_pattern, result)
    for job_id, output_key in needs_matches:
        value = context.get("job_outputs", {}).get(job_id, {}).get(output_key, "")
        pattern = f"${{{{ needs.{job_id}.outputs.{output_key} }}}}"
        result = result.replace(pattern, str(value))

    # Handle steps.* patterns
    step_pattern = r"\$\{\{\s*steps\.(\w+)\.outputs\.(\w+)\s*\}\}"
    step_matches = re.findall(step_pattern, result)
    for step_id, output_key in step_matches:
        value = context.get("step_outputs", {}).get(output_key, "")
        pattern = f"${{{{ steps.{step_id}.outputs.{output_key} }}}}"
        result = result.replace(pattern, str(value))

    return result
```

**Required change:**

```python
def _resolve_github_actions_patterns(text: str, context: Dict[str, Any]) -> str:
    """Resolve GitHub Actions patterns like ${{ needs.setup.outputs.build_id }}"""
    import re

    result = text

    # Handle needs.* patterns - use original matched pattern
    needs_pattern = r"\$\{\{\s*needs\.(\w+)\.outputs\.(\w+)\s*\}\}"
    for match in re.finditer(needs_pattern, result):
        original_pattern = match.group(0)  # Full match including exact spacing
        job_id = match.group(1)
        output_key = match.group(2)
        value = context.get("job_outputs", {}).get(job_id, {}).get(output_key, "")
        result = result.replace(original_pattern, str(value))

    # Handle steps.* patterns - use original matched pattern
    step_pattern = r"\$\{\{\s*steps\.(\w+)\.outputs\.(\w+)\s*\}\}"
    for match in re.finditer(step_pattern, result):
        original_pattern = match.group(0)  # Full match including exact spacing
        step_id = match.group(1)
        output_key = match.group(2)
        value = context.get("step_outputs", {}).get(output_key, "")
        result = result.replace(original_pattern, str(value))

    return result
```

**Why**: Uses `re.finditer()` to preserve original matched text instead of rebuilding patterns, making it robust to any spacing variations.

---

### Step 2: Remove Orphaned Duplicate Code

**File**: `src/main.py`
**Lines**: 640-661
**Action**: DELETE

**Current code:**

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
            return context.get("job_outputs", {}).get(job_id, {}).get(output_key, "")

        # Handle steps.* patterns (existing logic)
        step_pattern = r"\$\{\{\s*steps\.(\w+)\.outputs\.(\w+)\s*\}\}"
        step_match = re.search(step_pattern, expression)
        if step_match:
            step_id = step_match.group(1)
            output_key = step_match.group(2)
            return context.get("step_outputs", {}).get(output_key, "")

        return None
```

**Required change:**

```python
# DELETE entire function - it's never called
```

**Why**: This function is completely unused (orphaned code) and duplicates functionality already properly implemented in `src/utils.py`.

---

### Step 3: Add Test Cases for Spacing Variations

**File**: `tests/test_github_actions_variables.py`
**Action**: UPDATE

**Test cases to add:**

```python
def test_github_actions_spacing_variations(variable_substitution):
    """Test that GitHub Actions patterns work with various spacing combinations."""
    context = {
        "job_outputs": {"setup": {"build_id": "12345"}},
        "step_outputs": {"version": "1.2.3"}
    }
    
    # Test various spacing combinations
    test_cases = [
        "${{ needs.setup.outputs.build_id }}",      # Standard spacing
        "${{needs.setup.outputs.build_id}}",        # No spaces
        "${{  needs.setup.outputs.build_id  }}",    # Extra spaces
        "${{ needs.setup.outputs.build_id}}",       # Mixed spacing
        "${{needs.setup.outputs.build_id }}",       # Mixed spacing
    ]
    
    for pattern in test_cases:
        result = variable_substitution.substitute(
            f"Build ID: {pattern}",
            {},
            context
        )
        assert result == "Build ID: 12345", f"Failed for pattern: {pattern}"

def test_github_actions_multiple_patterns_different_spacing(variable_substitution):
    """Test multiple patterns with different spacing in same text."""
    context = {
        "job_outputs": {"setup": {"build_id": "12345"}},
        "step_outputs": {"version": "1.2.3"}
    }
    
    text = "Build: ${{ needs.setup.outputs.build_id }} Version: ${{steps.test.outputs.version}}"
    result = variable_substitution.substitute(text, {}, context)
    assert result == "Build: 12345 Version: 1.2.3"
```

---

## Patterns to Follow

**From codebase - mirror these exactly:**

```python
# SOURCE: src/utils.py:47
# Pattern for regex with negative lookahead to avoid conflicts
env_pattern = r"\$\{(?!\{)([^}]+)\}"

# SOURCE: tests/test_github_actions_variables.py:15-25  
# Pattern for comprehensive test structure with context
def test_github_actions_needs_pattern(variable_substitution):
    context = {
        "job_outputs": {"setup": {"build_id": "12345"}}
    }
    text = "Build ID: ${{ needs.setup.outputs.build_id }}"
    result = variable_substitution.substitute(text, {}, context)
    assert result == "Build ID: 12345"
```

---

## Edge Cases & Risks

| Risk/Edge Case                 | Mitigation                                              |
| ------------------------------ | ------------------------------------------------------- |
| Multiple identical patterns    | `re.finditer()` processes each match individually      |
| Nested or malformed patterns   | Existing regex patterns already handle this correctly  |
| Performance impact             | Minimal - `finditer()` vs `findall()` has similar cost |
| Breaking existing functionality | Comprehensive test suite will catch any regressions   |

---

## Validation

### Automated Checks

```bash
make test                    # Run full test suite including new spacing tests
python -m pytest tests/test_github_actions_variables.py -v  # Specific GitHub Actions tests
python -m pytest tests/ -k "github_actions" -v             # All GitHub Actions related tests
```

### Manual Verification

1. Run existing tests to ensure no regression in GitHub Actions variable substitution
2. Verify that spacing variation test cases cover edge cases mentioned in issue
3. Confirm orphaned function removal doesn't break any functionality (grep for usage)

---

## Scope Boundaries

**IN SCOPE:**

- Improve pattern reconstruction robustness in `src/utils.py`
- Remove orphaned duplicate code in `src/main.py`
- Add comprehensive spacing variation tests
- Maintain existing functionality and API

**OUT OF SCOPE (do not touch):**

- Changing the regex patterns themselves (they already handle spacing with `\s*`)
- Modifying the `VariableSubstitution` class interface
- Adding new GitHub Actions pattern types
- Performance optimization beyond the robustness improvement

---

## Metadata

- **Investigated by**: Claude
- **Timestamp**: 2026-02-25T22:15:00Z
- **Artifact**: `.claude/PRPs/issues/issue-8.md`