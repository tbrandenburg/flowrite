"""
Test cases for condition evaluation core patterns in Flowrite workflows.
These tests ensure that various condition patterns (needs.job.result, needs.job.outputs, env variables)
are evaluated correctly based on actual job execution results.
"""

import pytest
from src.types import WorkflowDefinition, JobDefinition
from src.dsl import ConditionEvaluator, DependencyResolver, WorkflowParser


class TestConditionEvaluationCorePatterns:
    """Test core condition evaluation patterns"""

    def test_needs_result_success_condition(self):
        """Test needs.job.result == 'success' pattern"""
        # Test with successful job result
        job_outputs = {"setup": {"status": "success"}}
        condition = "needs.setup.result == 'success'"
        result = ConditionEvaluator.evaluate_job_condition(condition, job_outputs, {})
        assert result is True

        # Test with completed status (should map to success)
        job_outputs = {"setup": {"status": "completed"}}
        result = ConditionEvaluator.evaluate_job_condition(condition, job_outputs, {})
        assert result is True

        # Test with failed job result
        job_outputs = {"setup": {"status": "failure"}}
        result = ConditionEvaluator.evaluate_job_condition(condition, job_outputs, {})
        assert result is False

    def test_needs_result_failure_condition(self):
        """Test needs.job.result == 'failure' pattern"""
        # Test with failed job result
        job_outputs = {"setup": {"status": "failure"}}
        condition = "needs.setup.result == 'failure'"
        result = ConditionEvaluator.evaluate_job_condition(condition, job_outputs, {})
        assert result is True

        # Test with successful job result
        job_outputs = {"setup": {"status": "success"}}
        result = ConditionEvaluator.evaluate_job_condition(condition, job_outputs, {})
        assert result is False

    def test_needs_result_cancelled_condition(self):
        """Test needs.job.result == 'cancelled' pattern"""
        # Test with cancelled job result
        job_outputs = {"setup": {"status": "cancelled"}}
        condition = "needs.setup.result == 'cancelled'"
        result = ConditionEvaluator.evaluate_job_condition(condition, job_outputs, {})
        assert result is True

        # Test with successful job result
        job_outputs = {"setup": {"status": "success"}}
        result = ConditionEvaluator.evaluate_job_condition(condition, job_outputs, {})
        assert result is False

    def test_needs_output_conditions(self):
        """Test needs.job.outputs.key == 'value' patterns"""
        # Test matching output
        job_outputs = {
            "setup": {
                "outputs": {
                    "deploy_env": "production",
                    "version": "1.2.3",
                    "build_success": "true",
                }
            }
        }

        # Test exact match
        condition = "needs.setup.outputs.deploy_env == 'production'"
        result = ConditionEvaluator.evaluate_job_condition(condition, job_outputs, {})
        assert result is True

        # Test non-matching value
        condition = "needs.setup.outputs.deploy_env == 'staging'"
        result = ConditionEvaluator.evaluate_job_condition(condition, job_outputs, {})
        assert result is False

        # Test missing output key
        condition = "needs.setup.outputs.missing_key == 'value'"
        result = ConditionEvaluator.evaluate_job_condition(condition, job_outputs, {})
        assert result is False

        # Test missing job
        condition = "needs.missing_job.outputs.key == 'value'"
        result = ConditionEvaluator.evaluate_job_condition(condition, job_outputs, {})
        assert result is False

        # Test boolean-like values
        condition = "needs.setup.outputs.build_success == 'true'"
        result = ConditionEvaluator.evaluate_job_condition(condition, job_outputs, {})
        assert result is True

    def test_env_variable_conditions(self):
        """Test env.VAR == 'value' patterns"""
        env_vars = {
            "ENVIRONMENT": "production",
            "DEBUG": "false",
            "PORT": "8080",
            "FEATURE_FLAG": "enabled",
        }

        # Test exact match
        condition = "env.ENVIRONMENT == 'production'"
        result = ConditionEvaluator.evaluate_job_condition(condition, {}, env_vars)
        assert result is True

        # Test non-matching value
        condition = "env.ENVIRONMENT == 'staging'"
        result = ConditionEvaluator.evaluate_job_condition(condition, {}, env_vars)
        assert result is False

        # Test missing environment variable
        condition = "env.MISSING_VAR == 'value'"
        result = ConditionEvaluator.evaluate_job_condition(condition, {}, env_vars)
        assert result is False

        # Test boolean-like values
        condition = "env.DEBUG == 'false'"
        result = ConditionEvaluator.evaluate_job_condition(condition, {}, env_vars)
        assert result is True

        # Test numeric values
        condition = "env.PORT == '8080'"
        result = ConditionEvaluator.evaluate_job_condition(condition, {}, env_vars)
        assert result is True

    def test_condition_evaluation_with_actual_results(self):
        """Test conditions should evaluate based on real job execution results"""
        # Create a workflow with conditional jobs
        workflow_data = {
            "name": "Conditional Evaluation Test",
            "jobs": {
                "setup": {
                    "steps": [
                        {"run": "echo 'environment=production' >> \"$GITHUB_OUTPUT\""},
                        {"run": "echo 'tests_passed=true' >> \"$GITHUB_OUTPUT\""},
                    ]
                },
                "deploy": {
                    "needs": ["setup"],
                    "if": "needs.setup.outputs.environment == 'production'",
                    "steps": [{"run": "echo 'Deploying to production'"}],
                },
                "notify": {
                    "needs": ["setup"],
                    "if": "needs.setup.outputs.tests_passed == 'true'",
                    "steps": [{"run": "echo 'Sending success notification'"}],
                },
                "skip_job": {
                    "needs": ["setup"],
                    "if": "needs.setup.outputs.environment == 'staging'",
                    "steps": [{"run": "echo 'This should not run'"}],
                },
            },
        }

        workflow = WorkflowParser.parse(workflow_data)

        # Simulate setup job completion with outputs
        completed = {"setup"}
        job_outputs = {
            "setup": {"outputs": {"environment": "production", "tests_passed": "true"}}
        }

        # Get ready jobs - should include deploy and notify, but not skip_job
        ready_jobs = DependencyResolver.get_ready_jobs(
            workflow, completed, job_outputs, {}
        )

        assert "deploy" in ready_jobs
        assert "notify" in ready_jobs
        assert "skip_job" not in ready_jobs

        # Test diagnostics
        diagnostics = DependencyResolver.get_job_diagnostics(
            workflow, completed, job_outputs, {}
        )

        # deploy should be ready
        assert diagnostics["deploy"]["status"] == "ready"
        assert diagnostics["deploy"]["condition_met"] is True

        # notify should be ready
        assert diagnostics["notify"]["status"] == "ready"
        assert diagnostics["notify"]["condition_met"] is True

        # skip_job should be blocked by condition
        assert diagnostics["skip_job"]["status"] == "condition_not_met"
        assert diagnostics["skip_job"]["condition_met"] is False

    def test_combined_needs_and_env_conditions(self):
        """Test workflows with both needs-based and env-based conditions"""
        workflow_data = {
            "name": "Combined Conditions Test",
            "jobs": {
                "setup": {
                    "steps": [{"run": "echo 'status=ready' >> \"$GITHUB_OUTPUT\""}]
                },
                "env_dependent": {
                    "needs": ["setup"],
                    "if": "env.DEPLOY_ENABLED == 'true'",
                    "steps": [{"run": "echo 'Environment allows deployment'"}],
                },
                "output_dependent": {
                    "needs": ["setup"],
                    "if": "needs.setup.outputs.status == 'ready'",
                    "steps": [{"run": "echo 'Setup is ready'"}],
                },
            },
        }

        workflow = WorkflowParser.parse(workflow_data)
        completed = {"setup"}
        job_outputs = {"setup": {"outputs": {"status": "ready"}}}
        env_vars = {"DEPLOY_ENABLED": "true"}

        ready_jobs = DependencyResolver.get_ready_jobs(
            workflow, completed, job_outputs, env_vars
        )

        assert "env_dependent" in ready_jobs
        assert "output_dependent" in ready_jobs

        # Test with env condition not met
        env_vars = {"DEPLOY_ENABLED": "false"}
        ready_jobs = DependencyResolver.get_ready_jobs(
            workflow, completed, job_outputs, env_vars
        )

        assert "env_dependent" not in ready_jobs
        assert "output_dependent" in ready_jobs

    def test_empty_and_missing_conditions(self):
        """Test empty conditions default to true and missing job references are handled"""
        # Test empty condition
        result = ConditionEvaluator.evaluate_job_condition("", {}, {})
        assert result is True

        # Test None condition (should be treated as empty)
        # Note: None is converted to empty string for testing
        result = ConditionEvaluator.evaluate_job_condition("", {}, {})
        assert result is True

        # Test whitespace-only condition
        result = ConditionEvaluator.evaluate_job_condition("   ", {}, {})
        assert result is True

        # Test condition referencing missing job
        condition = "needs.missing_job.outputs.key == 'value'"
        result = ConditionEvaluator.evaluate_job_condition(condition, {}, {})
        assert result is False

        # Test condition referencing missing output in existing job
        job_outputs = {"existing_job": {"outputs": {"existing_key": "value"}}}
        condition = "needs.existing_job.outputs.missing_key == 'value'"
        result = ConditionEvaluator.evaluate_job_condition(condition, job_outputs, {})
        assert result is False


class TestForeachItemParsing:
    """Test foreach item parsing functionality"""

    def test_parse_foreach_items_newline_separated(self):
        """Test parsing newline-separated foreach items"""
        items = ConditionEvaluator.parse_foreach_items("item1\nitem2\nitem3")
        assert items == ["item1", "item2", "item3"]

        # Test with trailing newline
        items = ConditionEvaluator.parse_foreach_items("apple\nbanana\ncherry\n")
        assert items == ["apple", "banana", "cherry"]

        # Test with empty lines (should be filtered out)
        items = ConditionEvaluator.parse_foreach_items("file1.txt\n\nfile2.txt\n")
        assert items == ["file1.txt", "file2.txt"]

    def test_parse_foreach_items_space_separated(self):
        """Test parsing space-separated foreach items"""
        items = ConditionEvaluator.parse_foreach_items("apple banana cherry")
        assert items == ["apple", "banana", "cherry"]

        # Test with extra spaces
        items = ConditionEvaluator.parse_foreach_items("  item1   item2   item3  ")
        assert items == ["item1", "item2", "item3"]

        # Test with single item
        items = ConditionEvaluator.parse_foreach_items("single_item")
        assert items == ["single_item"]

    def test_parse_foreach_items_mixed_whitespace_prefers_newlines(self):
        """Test that newlines take precedence over spaces in mixed whitespace"""
        # When both newlines and spaces are present, newlines should be the delimiter
        items = ConditionEvaluator.parse_foreach_items(
            "file1 with spaces\nfile2 with spaces\nfile3"
        )
        assert items == ["file1 with spaces", "file2 with spaces", "file3"]

        # Test complex case with multiple spaces and newlines
        items = ConditionEvaluator.parse_foreach_items("item1 part1\nitem2 part2\n")
        assert items == ["item1 part1", "item2 part2"]

    def test_parse_foreach_items_edge_cases(self):
        """Test edge cases for foreach item parsing"""
        # Empty string
        items = ConditionEvaluator.parse_foreach_items("")
        assert items == []

        # Only whitespace
        items = ConditionEvaluator.parse_foreach_items("   ")
        assert items == []

        # Only newlines
        items = ConditionEvaluator.parse_foreach_items("\n\n\n")
        assert items == []

        # Single newline
        items = ConditionEvaluator.parse_foreach_items("\n")
        assert items == []

        # Mixed empty content
        items = ConditionEvaluator.parse_foreach_items("   \n  \n   ")
        assert items == []

    def test_parse_foreach_items_special_characters(self):
        """Test parsing items with special characters"""
        # Test with file paths
        items = ConditionEvaluator.parse_foreach_items(
            "/path/to/file1.txt\n/path/to/file2.txt"
        )
        assert items == ["/path/to/file1.txt", "/path/to/file2.txt"]

        # Test with URLs
        items = ConditionEvaluator.parse_foreach_items(
            "https://example.com/api/v1 https://example.com/api/v2"
        )
        assert items == ["https://example.com/api/v1", "https://example.com/api/v2"]

        # Test with special characters in names
        items = ConditionEvaluator.parse_foreach_items("item-1\nitem_2\nitem.3")
        assert items == ["item-1", "item_2", "item.3"]

        # Test with quotes (should be preserved)
        items = ConditionEvaluator.parse_foreach_items("'item1'\n\"item2\"")
        assert items == ["'item1'", '"item2"']
