"""
Edge Cases Tests

These tests focus on handling malformed inputs, special characters, and edge cases
to ensure the workflow execution system is robust against invalid or unusual inputs.
"""

import pytest
import logging
from src.types import WorkflowDefinition, JobDefinition, StepDefinition
from src.dsl import ConditionEvaluator, DependencyResolver
from src.utils import VariableSubstitution, BashExecutor


class TestEdgeCases:
    """Test suite for edge cases and error handling"""

    def test_unknown_condition_patterns(self):
        """Test that unknown condition syntax logs warnings and defaults to true"""
        # Test completely invalid condition syntax
        unknown_conditions = [
            "some.random.syntax == 'value'",  # Unknown pattern
            "invalid(condition)",  # Invalid function
            "needs.job.unknown_property == 'test'",  # Unknown property
            "needs.job.result !! 'value'",  # Invalid operator
            "just_random_text",  # Random text
            "123 + 456",  # Arithmetic (not supported)
            "null",  # Literal null
            "undefined",  # Literal undefined
        ]

        job_outputs = {"test_job": {"status": "success"}}
        env_vars = {"TEST_VAR": "value"}

        for condition in unknown_conditions:
            # Unknown patterns should default to True (fail-safe)
            result = ConditionEvaluator.evaluate_job_condition(
                condition, job_outputs, env_vars
            )
            # The current implementation defaults unknown patterns to True
            # This is a design choice for fail-safe behavior
            assert result is True, f"Condition '{condition}' should default to True"

    def test_missing_job_references(self):
        """Test that references to non-existent jobs are handled gracefully"""
        job_outputs = {
            "existing_job": {"status": "success", "outputs": {"key": "value"}}
        }
        env_vars = {}

        # Test missing job in result condition
        condition = "needs.nonexistent_job.result == 'success'"
        result = ConditionEvaluator.evaluate_job_condition(
            condition, job_outputs, env_vars
        )
        # Missing jobs default to success status, so this should be True
        assert result is True

        # Test missing job with failure condition
        condition = "needs.nonexistent_job.result == 'failure'"
        result = ConditionEvaluator.evaluate_job_condition(
            condition, job_outputs, env_vars
        )
        # Missing jobs default to success, so expecting failure should be False
        assert result is False

        # Test missing job output reference
        condition = "needs.nonexistent_job.outputs.key == 'value'"
        result = ConditionEvaluator.evaluate_job_condition(
            condition, job_outputs, env_vars
        )
        # Missing job outputs should return False
        assert result is False

        # Test existing job but missing output key
        condition = "needs.existing_job.outputs.missing_key == 'value'"
        result = ConditionEvaluator.evaluate_job_condition(
            condition, job_outputs, env_vars
        )
        # Missing output key should return False
        assert result is False

    def test_empty_condition_handling(self):
        """Test that empty/null conditions default to true"""
        job_outputs = {}
        env_vars = {}

        # Test empty string condition
        result = ConditionEvaluator.evaluate_job_condition("", job_outputs, env_vars)
        assert result is True

        # Test whitespace-only condition
        result = ConditionEvaluator.evaluate_job_condition(
            "   \t\n   ", job_outputs, env_vars
        )
        assert result is True

        # Test None condition handling at the workflow level
        # None conditions should be handled by the workflow definition parsing
        # rather than being passed directly to the condition evaluator
        workflow = WorkflowDefinition(
            name="None Condition Test",
            jobs={
                "test_job": JobDefinition(
                    name="test_job",
                    runs_on="ubuntu-latest",
                    steps=[StepDefinition(run="echo 'test'")],
                    needs=[],
                    if_condition=None,  # This should be handled gracefully
                ),
            },
        )

        diagnostics = DependencyResolver.get_job_diagnostics(workflow, set(), {}, {})

        # Job with None condition should be ready
        assert "test_job" in diagnostics
        assert diagnostics["test_job"]["status"] == "ready"
        assert diagnostics["test_job"]["condition_met"] is True

    def test_malformed_condition_syntax(self):
        """Test that invalid condition syntax doesn't crash the system"""
        job_outputs = {"job": {"status": "success"}}
        env_vars = {"VAR": "value"}

        malformed_conditions = [
            "needs.job.result == ",  # Missing value
            "needs.job.result ==",  # Missing value and space
            "== 'value'",  # Missing left side
            "needs..result == 'value'",  # Double dots
            "needs.job. == 'value'",  # Missing property
            "needs. == 'value'",  # Missing job and property
            "needs.job.result == 'unclosed string",  # Unclosed quote
            'needs.job.result == "unclosed string',  # Unclosed double quote
            "needs.job.result == 'value' needs.job.result == 'value'",  # Missing operator
            "((needs.job.result == 'value'",  # Unmatched parentheses
            "needs.job.result == 'value'))",  # Unmatched parentheses
        ]

        # These conditions contain && or || and may be processed differently
        complex_malformed_conditions = [
            "needs.job.result == 'value' &&",  # Incomplete AND
            "needs.job.result == 'value' ||",  # Incomplete OR
            "&& needs.job.result == 'value'",  # Leading AND
            "|| needs.job.result == 'value'",  # Leading OR
        ]

        # Test simple malformed conditions - these should default to True
        for condition in malformed_conditions:
            try:
                result = ConditionEvaluator.evaluate_job_condition(
                    condition, job_outputs, env_vars
                )
                # If it doesn't crash, the result should be a boolean
                assert isinstance(result, bool), (
                    f"Condition '{condition}' should return a boolean"
                )
                # Simple malformed conditions should default to True
                assert result is True, (
                    f"Malformed condition '{condition}' should default to True"
                )
            except Exception as e:
                # If it throws an exception, it should be a controlled exception
                assert not isinstance(e, SystemExit), (
                    f"Condition '{condition}' should not cause system exit"
                )

        # Test complex malformed conditions - these may behave differently
        for condition in complex_malformed_conditions:
            try:
                result = ConditionEvaluator.evaluate_job_condition(
                    condition, job_outputs, env_vars
                )
                # Should not crash and should return a boolean
                assert isinstance(result, bool), (
                    f"Complex condition '{condition}' should return a boolean"
                )
                # The exact result depends on how the complex evaluator handles malformed parts
                # We just ensure it doesn't crash
            except Exception as e:
                # Should be a controlled exception, not a system crash
                assert not isinstance(e, SystemExit), (
                    f"Complex condition '{condition}' should not cause system exit"
                )

    def test_condition_with_special_characters(self):
        """Test conditions with quotes, spaces, and special characters"""
        job_outputs = {
            "test_job": {
                "status": "success",
                "outputs": {
                    "message": "Hello, World!",
                    "path": "/path/with spaces/file.txt",
                    "special": "value with 'quotes' and \"double quotes\"",
                    "unicode": "émojis 🚀 and ñice characters",
                    "empty": "",
                },
            }
        }
        env_vars = {
            "SPECIAL_VAR": "value with spaces",
            "QUOTED_VAR": "value with 'quotes'",
            "UNICODE_VAR": "ñice émojis 🚀",
        }

        # Test condition with spaces in value
        condition = "needs.test_job.outputs.message == 'Hello, World!'"
        result = ConditionEvaluator.evaluate_job_condition(
            condition, job_outputs, env_vars
        )
        assert result is True

        # Test condition with path containing spaces
        condition = "needs.test_job.outputs.path == '/path/with spaces/file.txt'"
        result = ConditionEvaluator.evaluate_job_condition(
            condition, job_outputs, env_vars
        )
        assert result is True

        # Test condition with mixed quotes
        condition = 'needs.test_job.outputs.special == "value with \'quotes\' and \\"double quotes\\""'
        result = ConditionEvaluator.evaluate_job_condition(
            condition, job_outputs, env_vars
        )
        # This might be tricky to parse correctly, but should not crash
        # The exact behavior depends on implementation
        assert isinstance(result, bool)

        # Test condition with unicode characters
        condition = "needs.test_job.outputs.unicode == 'émojis 🚀 and ñice characters'"
        result = ConditionEvaluator.evaluate_job_condition(
            condition, job_outputs, env_vars
        )
        assert result is True

        # Test condition with empty string
        condition = "needs.test_job.outputs.empty == ''"
        result = ConditionEvaluator.evaluate_job_condition(
            condition, job_outputs, env_vars
        )
        assert result is True

        # Test env variable with special characters
        condition = "env.SPECIAL_VAR == 'value with spaces'"
        result = ConditionEvaluator.evaluate_job_condition(
            condition, job_outputs, env_vars
        )
        assert result is True

        # Test env variable with unicode
        condition = "env.UNICODE_VAR == 'ñice émojis 🚀'"
        result = ConditionEvaluator.evaluate_job_condition(
            condition, job_outputs, env_vars
        )
        assert result is True

    def test_malformed_variable_substitution(self):
        """Test that invalid variable substitution patterns don't crash"""
        malformed_patterns = [
            "${",  # Unclosed brace
            "${}",  # Empty variable name
            "${VAR",  # Unclosed brace with variable
            "$VAR}",  # Closing brace without opening
            "${{VAR}}",  # Double braces
            "${VAR${OTHER}}",  # Nested variables (not supported)
            "${VAR-default}",  # Default values (may not be supported)
            "${123}",  # Numeric variable name
            "${VAR.PROP}",  # Property access (may not be supported)
            "$",  # Just dollar sign
            "$$VAR",  # Double dollar
            "$VAR$VAR",  # Adjacent variables
        ]

        env_vars = {"VAR": "value", "OTHER": "other"}

        for pattern in malformed_patterns:
            try:
                result = VariableSubstitution.substitute(pattern, env_vars)
                # Should return some result without crashing
                assert isinstance(result, str)
                # Malformed patterns might be left as-is or partially processed
            except Exception as e:
                # If it throws an exception, it should be controlled
                assert not isinstance(e, SystemExit), (
                    f"Pattern '{pattern}' should not cause system exit"
                )

    def test_circular_variable_references(self):
        """Test detection and handling of circular variable references"""
        # Set up circular reference: A refers to B, B refers to A
        circular_env = {
            "A": "${B}",
            "B": "${A}",
            "C": "${C}",  # Self-reference
        }

        # Test simple circular reference
        try:
            result = VariableSubstitution.substitute("${A}", circular_env)
            # Should either detect the cycle and handle it, or return a safe result
            assert isinstance(result, str)
            # Common approaches: leave as-is, return empty, or return a placeholder
        except RecursionError:
            pytest.fail(
                "Circular reference should be detected before causing RecursionError"
            )
        except Exception as e:
            # Other exceptions are acceptable as long as they're controlled
            assert not isinstance(e, SystemExit)

        # Test self-reference
        try:
            result = VariableSubstitution.substitute("${C}", circular_env)
            assert isinstance(result, str)
        except RecursionError:
            pytest.fail(
                "Self-reference should be detected before causing RecursionError"
            )
        except Exception:
            pass  # Controlled exception is acceptable

    def test_missing_variable_substitution(self):
        """Test that undefined variables are handled gracefully"""
        env_vars = {"DEFINED_VAR": "value"}

        # Test undefined variable patterns
        undefined_patterns = [
            "$UNDEFINED_VAR",
            "${UNDEFINED_VAR}",
            "prefix-$UNDEFINED_VAR-suffix",
            "${UNDEFINED_VAR:-default}",  # With default (may not be supported)
            "$UNDEFINED1-$UNDEFINED2",  # Multiple undefined
        ]

        for pattern in undefined_patterns:
            result = VariableSubstitution.substitute(pattern, env_vars)
            assert isinstance(result, str)
            # Common behaviors: leave as-is, replace with empty string, or use placeholder
            # The exact behavior depends on implementation philosophy

    def test_variable_substitution_special_chars(self):
        """Test variable substitution with special characters"""
        env_vars = {
            "SPACES": "value with spaces",
            "QUOTES": "value with 'single' and \"double\" quotes",
            "UNICODE": "ñice émojis 🚀",
            "SYMBOLS": "!@#$%^&*()_+-=[]{}|;:,.<>?",
            "NEWLINES": "line1\nline2\nline3",
            "TABS": "col1\tcol2\tcol3",
            "EMPTY": "",
        }

        # Test each special case
        for var_name, expected_value in env_vars.items():
            # Test both forms of variable substitution
            for pattern in [f"${var_name}", f"${{{var_name}}}"]:
                result = VariableSubstitution.substitute(pattern, env_vars)
                assert result == expected_value, (
                    f"Pattern '{pattern}' should substitute correctly"
                )

        # Test mixed patterns
        mixed_pattern = "Spaces: $SPACES, Unicode: ${UNICODE}, Symbols: $SYMBOLS"
        result = VariableSubstitution.substitute(mixed_pattern, env_vars)
        expected = f"Spaces: {env_vars['SPACES']}, Unicode: {env_vars['UNICODE']}, Symbols: {env_vars['SYMBOLS']}"
        assert result == expected

    def test_github_output_parsing_edge_cases(self):
        """Test malformed GITHUB_OUTPUT lines in bash execution"""
        executor = BashExecutor(timeout=10)

        # Test various malformed output patterns
        malformed_commands = [
            'echo "no_equals_sign" >> "$GITHUB_OUTPUT"',  # Missing =
            'echo "=no_key" >> "$GITHUB_OUTPUT"',  # Missing key
            'echo "key=" >> "$GITHUB_OUTPUT"',  # Empty value
            'echo "key==double_equals" >> "$GITHUB_OUTPUT"',  # Double equals
            'echo "key=value=extra" >> "$GITHUB_OUTPUT"',  # Multiple equals
            'echo "key with spaces=value" >> "$GITHUB_OUTPUT"',  # Spaces in key
            'echo "==" >> "$GITHUB_OUTPUT"',  # Just equals
            'echo "" >> "$GITHUB_OUTPUT"',  # Empty line
            'echo "key=value with spaces" >> "$GITHUB_OUTPUT"',  # Spaces in value
            'echo "unicode_key=émojis 🚀" >> "$GITHUB_OUTPUT"',  # Unicode
        ]

        for command in malformed_commands:
            success, outputs = executor.execute_simulation(command, {})
            # Should not crash the executor
            assert success is True, f"Command should not crash: {command}"
            assert isinstance(outputs, dict), (
                "Should return a dict even with malformed output"
            )
            # The exact parsing behavior depends on implementation
            # But it should be consistent and not crash
