"""
High-signal unit tests for Flowrite Workflow Executor
Testing core functionality with maximum value, minimal bloat.
"""

import pytest
import yaml
import tempfile
import os
from unittest.mock import Mock, patch
from src.types import (
    WorkflowDefinition,
    JobDefinition,
    StepDefinition,
    LoopConfig,
    Config,
    JobStatus,
    StepResult,
    JobOutput,
)
from src.dsl import WorkflowParser, ConditionEvaluator, DependencyResolver, OutputParser
from src.utils import BashExecutor, VariableSubstitution, ConfigLoader


class TestWorkflowTypes:
    """Test core data structures"""

    def test_loop_config_creation(self):
        """Test LoopConfig instantiation and validation"""
        loop = LoopConfig(until="success()", max_iterations=3)
        assert loop.until == "success()"
        assert loop.max_iterations == 3

    def test_loop_config_foreach_creation(self):
        """Test LoopConfig with foreach field"""
        loop = LoopConfig(foreach="item1\nitem2\nitem3", max_iterations=3)
        assert loop.foreach == "item1\nitem2\nitem3"
        assert loop.until is None
        assert loop.max_iterations == 3

    def test_loop_config_foreach_space_separated(self):
        """Test LoopConfig with space-separated foreach values"""
        loop = LoopConfig(foreach="apple banana cherry", max_iterations=10)
        assert loop.foreach == "apple banana cherry"
        assert loop.until is None
        assert loop.max_iterations == 10

    def test_job_definition_needs_string_to_list(self):
        """Test JobDefinition converts needs string to list"""
        job = JobDefinition(needs="setup")
        assert job.needs == ["setup"]

        job = JobDefinition(needs=["setup", "prepare"])
        assert job.needs == ["setup", "prepare"]

    def test_workflow_definition_if_condition_mapping(self):
        """Test WorkflowDefinition maps 'if' to 'if_condition'"""
        workflow_data = {
            "name": "test",
            "jobs": {
                "test_job": {
                    "if": "always()",
                    "runs-on": "ubuntu-latest",
                    "steps": [{"run": "echo test"}],
                }
            },
        }
        workflow = WorkflowDefinition(**workflow_data)
        assert workflow.jobs["test_job"].if_condition == "always()"
        assert workflow.jobs["test_job"].runs_on == "ubuntu-latest"

    def test_config_default_values(self):
        """Test default configuration values are reasonable"""
        config = Config()
        assert config.step_timeout_seconds > 0
        assert config.activity_timeout_seconds > 0
        assert config.max_retries >= 1
        assert config.temporal_server is not None


class TestConditionEvaluator:
    """Test workflow condition evaluation logic"""

    def test_always_condition(self):
        """Test always() condition always returns True"""
        result = ConditionEvaluator.evaluate_job_condition("always()", {}, {})
        assert result is True

    def test_needs_output_condition_match(self):
        """Test needs.job.outputs.key == 'value' condition with match"""
        job_outputs = {"setup": {"outputs": {"status": "ready"}}}
        condition = "needs.setup.outputs.status == 'ready'"
        result = ConditionEvaluator.evaluate_job_condition(condition, job_outputs, {})
        assert result is True

    def test_needs_output_condition_no_match(self):
        """Test needs.job.outputs.key == 'value' condition with no match"""
        job_outputs = {"setup": {"outputs": {"status": "pending"}}}
        condition = "needs.setup.outputs.status == 'ready'"
        result = ConditionEvaluator.evaluate_job_condition(condition, job_outputs, {})
        assert result is False

    def test_env_variable_condition_match(self):
        """Test env.VARIABLE == 'value' condition with match"""
        env_vars = {"STATUS": "complete"}
        condition = "env.STATUS == 'complete'"
        result = ConditionEvaluator.evaluate_job_condition(condition, {}, env_vars)
        assert result is True

    def test_empty_condition_defaults_true(self):
        """Test empty condition defaults to True"""
        assert ConditionEvaluator.evaluate_job_condition("", {}, {}) is True

    def test_success_failure_cancelled_conditions(self):
        """Test basic success/failure/cancelled conditions"""
        assert ConditionEvaluator.evaluate_job_condition("success()", {}, {}) is True
        assert ConditionEvaluator.evaluate_job_condition("failure()", {}, {}) is True
        assert ConditionEvaluator.evaluate_job_condition("cancelled()", {}, {}) is True


class TestDependencyResolver:
    """Test job dependency resolution using actual API"""

    def test_get_ready_jobs_no_dependencies(self):
        """Test getting ready jobs when no dependencies exist"""
        workflow = WorkflowDefinition(
            jobs={
                "job1": JobDefinition(name="job1"),
                "job2": JobDefinition(name="job2"),
            }
        )

        ready = DependencyResolver.get_ready_jobs(workflow, set(), {}, {})
        assert "job1" in ready
        assert "job2" in ready
        assert len(ready) == 2

    def test_get_ready_jobs_with_dependencies(self):
        """Test getting ready jobs respects dependencies"""
        workflow = WorkflowDefinition(
            jobs={
                "setup": JobDefinition(name="setup"),
                "build": JobDefinition(name="build", needs=["setup"]),
                "test": JobDefinition(name="test", needs=["build"]),
            }
        )

        # Initially only setup should be ready
        ready = DependencyResolver.get_ready_jobs(workflow, set(), {}, {})
        assert ready == ["setup"]

        # After setup completes, build should be ready
        ready = DependencyResolver.get_ready_jobs(workflow, {"setup"}, {}, {})
        assert ready == ["build"]

        # After both complete, test should be ready
        ready = DependencyResolver.get_ready_jobs(workflow, {"setup", "build"}, {}, {})
        assert ready == ["test"]

    def test_get_ready_jobs_with_conditions(self):
        """Test getting ready jobs respects if conditions"""
        workflow = WorkflowDefinition(
            jobs={
                "setup": JobDefinition(name="setup"),
                "conditional": JobDefinition(
                    name="conditional",
                    needs=["setup"],
                    if_condition="needs.setup.outputs.run == 'true'",
                ),
            }
        )

        # Without matching condition, job shouldn't be ready
        job_outputs = {"setup": {"outputs": {"run": "false"}}}
        ready = DependencyResolver.get_ready_jobs(workflow, {"setup"}, job_outputs, {})
        assert "conditional" not in ready

        # With matching condition, job should be ready
        job_outputs = {"setup": {"outputs": {"run": "true"}}}
        ready = DependencyResolver.get_ready_jobs(workflow, {"setup"}, job_outputs, {})
        assert "conditional" in ready


class TestOutputParser:
    """Test GITHUB_OUTPUT and GITHUB_ENV parsing"""

    def test_parse_github_output_simple(self):
        """Test basic GITHUB_OUTPUT parsing"""
        command = 'echo "status=ready" >> "$GITHUB_OUTPUT"'
        outputs = OutputParser.parse_github_output(command)
        assert outputs == {"status": "ready"}

    def test_parse_github_env_simple(self):
        """Test basic GITHUB_ENV parsing"""
        command = 'echo "BUILD_STATUS=success" >> "$GITHUB_ENV"'
        env_vars = OutputParser.parse_github_env(command)
        assert env_vars == {"BUILD_STATUS": "success"}

    def test_parse_multiline_outputs(self):
        """Test parsing multiple output lines"""
        command = """
        echo "status=ready" >> "$GITHUB_OUTPUT"
        echo "version=1.0.0" >> "$GITHUB_OUTPUT"
        """
        outputs = OutputParser.parse_github_output(command)
        assert "status" in outputs
        assert "version" in outputs

    def test_parse_invalid_format_ignored(self):
        """Test invalid format lines are ignored gracefully"""
        command = """
        echo "invalid line"
        echo "status=ready" >> "$GITHUB_OUTPUT"
        echo "another invalid"
        """
        outputs = OutputParser.parse_github_output(command)
        assert outputs.get("status") == "ready"


class TestVariableSubstitution:
    """Test variable substitution in commands"""

    def test_substitute_simple_variable(self):
        """Test basic ${VAR} substitution"""
        text = "echo ${MESSAGE}"
        env_vars = {"MESSAGE": "hello world"}
        result = VariableSubstitution.substitute(text, env_vars)
        assert result == "echo hello world"

    def test_substitute_dollar_variable(self):
        """Test $VAR substitution"""
        text = "echo $USER is running"
        env_vars = {"USER": "testuser"}
        result = VariableSubstitution.substitute(text, env_vars)
        assert result == "echo testuser is running"

    def test_substitute_missing_variable(self):
        """Test missing variables remain unchanged"""
        text = "echo ${MISSING_VAR}"
        env_vars = {}
        result = VariableSubstitution.substitute(text, env_vars)
        assert result == "echo ${MISSING_VAR}"

    def test_substitute_mixed_formats(self):
        """Test mixed ${VAR} and $VAR in same text"""
        text = "echo ${MESSAGE} from $USER"
        env_vars = {"MESSAGE": "hello", "USER": "testuser"}
        result = VariableSubstitution.substitute(text, env_vars)
        assert result == "echo hello from testuser"


class TestWorkflowParser:
    """Test YAML workflow parsing"""

    def test_parse_minimal_workflow(self):
        """Test parsing minimal valid workflow"""
        yaml_data = {
            "name": "Test Workflow",
            "jobs": {"test": {"steps": [{"run": 'echo "hello"'}]}},
        }
        workflow = WorkflowParser.parse(yaml_data)
        assert workflow.name == "Test Workflow"
        assert "test" in workflow.jobs
        assert len(workflow.jobs["test"].steps) == 1
        assert workflow.jobs["test"].steps[0].run == 'echo "hello"'

    def test_parse_workflow_with_dependencies(self):
        """Test parsing workflow with job dependencies"""
        yaml_data = {
            "name": "Dependency Test",
            "jobs": {
                "setup": {"steps": [{"run": 'echo "setup"'}]},
                "build": {"needs": "setup", "steps": [{"run": 'echo "build"'}]},
            },
        }
        workflow = WorkflowParser.parse(yaml_data)
        assert workflow.jobs["build"].needs == ["setup"]

    def test_load_from_file(self):
        """Test loading workflow from YAML file"""
        yaml_content = """
        name: File Test Workflow
        jobs:
          test:
            steps:
              - run: echo "from file"
        """

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            temp_file = f.name

        try:
            workflow = WorkflowParser.load_from_file(temp_file)
            assert workflow.name == "File Test Workflow"
            assert "test" in workflow.jobs
        finally:
            os.unlink(temp_file)


class TestBashExecutor:
    """Test bash command execution"""

    def test_execute_simple_command_success(self):
        """Test successful command execution"""
        executor = BashExecutor(timeout=5)
        success, stdout, stderr, env_updates = executor.execute("echo 'test'", {})
        assert success is True
        assert "test" in stdout
        assert stderr == ""

    def test_execute_command_failure(self):
        """Test failed command execution"""
        executor = BashExecutor(timeout=5)
        success, stdout, stderr, env_updates = executor.execute("exit 1", {})
        assert success is False

    def test_execute_with_environment_variables(self):
        """Test command execution with custom environment"""
        executor = BashExecutor(timeout=5)
        env_vars = {"TEST_VAR": "test_value"}
        success, stdout, stderr, env_updates = executor.execute(
            "echo $TEST_VAR", env_vars
        )
        assert success is True
        assert "test_value" in stdout

    @patch("subprocess.run")
    def test_execute_timeout_handling(self, mock_run):
        """Test timeout handling in command execution"""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 5)

        executor = BashExecutor(timeout=5)
        success, stdout, stderr, env_updates = executor.execute("sleep 10", {})
        assert success is False
        assert "timeout" in stderr.lower()


class TestIntegrationScenarios:
    """Integration tests for complete workflow processing"""

    def test_complete_workflow_structure(self):
        """Test complete workflow parsing and validation"""
        workflow_data = {
            "name": "Integration Test",
            "jobs": {
                "setup": {
                    "name": "Setup job",
                    "steps": [
                        {
                            "name": "Initialize",
                            "id": "init",
                            "run": 'echo "status=ready" >> "$GITHUB_OUTPUT"',
                        }
                    ],
                },
                "parallel_job_a": {
                    "name": "Job A",
                    "needs": "setup",
                    "steps": [{"run": "echo 'Running job A'"}],
                },
                "parallel_job_b": {
                    "name": "Job B",
                    "needs": "setup",
                    "if": "needs.setup.outputs.status == 'ready'",
                    "steps": [{"run": "echo 'Running job B'"}],
                },
                "final": {
                    "name": "Cleanup",
                    "needs": ["parallel_job_a", "parallel_job_b"],
                    "if": "always()",
                    "steps": [{"run": "echo 'Workflow completed'"}],
                },
            },
        }

        # Test parsing
        workflow = WorkflowParser.parse(workflow_data)

        # Verify structure
        assert workflow.name == "Integration Test"
        assert len(workflow.jobs) == 4
        assert "setup" in workflow.jobs
        assert "parallel_job_a" in workflow.jobs
        assert "parallel_job_b" in workflow.jobs
        assert "final" in workflow.jobs

        # Test dependency resolution
        ready = DependencyResolver.get_ready_jobs(workflow, set(), {}, {})
        assert "setup" in ready
        assert "parallel_job_a" not in ready  # Depends on setup
        assert "parallel_job_b" not in ready  # Depends on setup
        assert "final" not in ready  # Depends on both parallel jobs

        # Test condition evaluation for conditional job
        job_outputs = {"setup": {"outputs": {"status": "ready"}}}
        condition = workflow.jobs["parallel_job_b"].if_condition
        if condition:  # Check condition exists before evaluation
            result = ConditionEvaluator.evaluate_job_condition(
                condition, job_outputs, {}
            )
            assert result is True

    def test_step_and_job_results(self):
        """Test result data structures work correctly"""
        step_result = StepResult(success=True, outputs={"key": "value"})
        assert step_result.success
        assert step_result.outputs["key"] == "value"
        assert step_result.error is None

        job_output = JobOutput(
            job_id="test_job", status=JobStatus.COMPLETED, outputs={"result": "success"}
        )
        assert job_output.job_id == "test_job"
        assert job_output.status == JobStatus.COMPLETED
        assert job_output.outputs["result"] == "success"

    def test_loop_configuration_handling(self):
        """Test loop configurations are properly handled"""
        # Test job with loop
        job_data = {
            "name": "retry_job",
            "loop": {"until": "success()", "max_iterations": 3},
            "steps": [{"run": "echo test"}],
        }
        job = JobDefinition(**job_data)
        assert job.loop is not None
        assert job.loop.until == "success()"
        assert job.loop.max_iterations == 3

        # Test step with loop
        step_data = {
            "name": "retry_step",
            "loop": {"until": "env.READY == 'true'", "max_iterations": 5},
            "run": "echo retrying",
        }
        step = StepDefinition(**step_data)
        assert step.loop is not None
        assert step.loop.until == "env.READY == 'true'"
        assert step.loop.max_iterations == 5

    def test_foreach_loop_configuration_handling(self):
        """Test foreach loop configurations are properly handled"""
        # Test job with foreach loop
        job_data = {
            "name": "foreach_job",
            "loop": {
                "foreach": "file1.txt\nfile2.txt\nfile3.txt",
                "max_iterations": 10,
            },
            "steps": [{"run": "echo processing $FOREACH_ITEM"}],
        }
        job = JobDefinition(**job_data)
        assert job.loop is not None
        assert job.loop.foreach == "file1.txt\nfile2.txt\nfile3.txt"
        assert job.loop.until is None
        assert job.loop.max_iterations == 10

        # Test step with foreach loop (space-separated)
        step_data = {
            "name": "foreach_step",
            "loop": {"foreach": "apple banana cherry", "max_iterations": 5},
            "run": "echo processing $FOREACH_ITEM ($FOREACH_INDEX of $FOREACH_ITERATION)",
        }
        step = StepDefinition(**step_data)
        assert step.loop is not None
        assert step.loop.foreach == "apple banana cherry"
        assert step.loop.until is None
        assert step.loop.max_iterations == 5

        # Test empty foreach string
        empty_foreach_data = {
            "name": "empty_foreach",
            "loop": {"foreach": "", "max_iterations": 1},
            "run": "echo should not iterate",
        }
        step = StepDefinition(**empty_foreach_data)
        assert step.loop is not None
        assert step.loop.foreach == ""
        assert step.loop.until is None


class TestErrorScenarios:
    """Test error handling and edge cases"""

    def test_invalid_condition_evaluation(self):
        """Test handling of malformed conditions"""
        # Should not crash on malformed condition
        result = ConditionEvaluator.evaluate_job_condition(
            "malformed condition", {}, {}
        )
        # Implementation should handle gracefully, exact behavior may vary
        assert isinstance(result, bool)

    def test_missing_job_outputs(self):
        """Test condition evaluation with missing job outputs"""
        condition = "needs.missing_job.outputs.key == 'value'"
        result = ConditionEvaluator.evaluate_job_condition(condition, {}, {})
        assert result is False  # Missing job should evaluate to False

    def test_bash_execution_error_handling(self):
        """Test bash executor handles command failures gracefully"""
        executor = BashExecutor(timeout=5)
        success, stdout, stderr, env_updates = executor.execute("false", {})
        assert success is False
        # Should not crash on command failure


if __name__ == "__main__":
    pytest.main([__file__])
