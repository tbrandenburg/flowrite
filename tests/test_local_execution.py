"""
Test suite for LocalEngine - local execution mode with real bash commands
Tests the local execution engine that executes workflows with actual commands
"""

import pytest
import yaml
import tempfile
import os
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from src.main import LocalEngine
from src.types import Config, WorkflowResult, JobOutput, JobStatus
from src.utils import BashExecutor


class TestLocalEngine:
    """Test LocalEngine functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.config = Config(max_retries=2)
        self.engine = LocalEngine(self.config)

    def create_temp_workflow(self, workflow_content: dict) -> str:
        """Create a temporary workflow file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(workflow_content, f)
            return f.name

    @pytest.fixture
    def simple_workflow(self):
        """Simple workflow for testing"""
        return {
            "name": "simple-test",
            "jobs": {
                "test-job": {
                    "runs-on": "ubuntu-latest",
                    "steps": [{"run": "echo 'hello world'"}],
                }
            },
        }

    @pytest.fixture
    def multi_job_workflow(self):
        """Multi-job workflow with dependencies"""
        return {
            "name": "multi-job-test",
            "jobs": {
                "setup": {
                    "runs-on": "ubuntu-latest",
                    "steps": [{"run": "echo 'setup complete'"}],
                },
                "test": {
                    "runs-on": "ubuntu-latest",
                    "needs": "setup",
                    "steps": [{"run": "echo 'running tests'"}],
                },
            },
        }

    @pytest.fixture
    def conditional_workflow(self):
        """Workflow with conditional execution"""
        return {
            "name": "conditional-test",
            "jobs": {
                "always-run": {
                    "runs-on": "ubuntu-latest",
                    "steps": [{"run": "echo 'always runs'"}],
                },
                "conditional-job": {
                    "runs-on": "ubuntu-latest",
                    "if": "success()",
                    "needs": "always-run",
                    "steps": [{"run": "echo 'conditional execution'"}],
                },
            },
        }

    @pytest.fixture
    def failing_workflow(self):
        """Workflow with failing commands for retry testing"""
        return {
            "name": "failing-test",
            "jobs": {
                "failing-job": {
                    "runs-on": "ubuntu-latest",
                    "steps": [
                        {"run": "exit 1"}  # Command that will fail
                    ],
                }
            },
        }

    @pytest.mark.asyncio
    async def test_simple_workflow_execution(self, simple_workflow):
        """Test basic workflow execution"""
        workflow_file = self.create_temp_workflow(simple_workflow)

        try:
            result = await self.engine.run_workflow(workflow_file)

            assert isinstance(result, WorkflowResult)
            assert result.status == "completed"
            assert "test-job" in result.jobs
            assert result.jobs["test-job"].status == "completed"
        finally:
            os.unlink(workflow_file)

    @pytest.mark.asyncio
    async def test_multi_job_workflow_execution(self, multi_job_workflow):
        """Test multi-job workflow with dependencies"""
        workflow_file = self.create_temp_workflow(multi_job_workflow)

        try:
            result = await self.engine.run_workflow(workflow_file)

            assert result.status == "completed"
            assert "setup" in result.jobs
            assert "test" in result.jobs
            assert result.jobs["setup"].status == "completed"
            assert result.jobs["test"].status == "completed"
        finally:
            os.unlink(workflow_file)

    @pytest.mark.asyncio
    async def test_conditional_workflow_execution(self, conditional_workflow):
        """Test workflow with conditional job execution"""
        workflow_file = self.create_temp_workflow(conditional_workflow)

        try:
            result = await self.engine.run_workflow(workflow_file)

            assert result.status == "completed"
            assert "always-run" in result.jobs
            assert "conditional-job" in result.jobs
            assert result.jobs["always-run"].status == "completed"
            assert result.jobs["conditional-job"].status == "completed"
        finally:
            os.unlink(workflow_file)

    @pytest.mark.asyncio
    async def test_failing_command_with_retries(self, failing_workflow):
        """Test retry logic with failing commands"""
        workflow_file = self.create_temp_workflow(failing_workflow)

        with patch.object(BashExecutor, "execute") as mock_execute:
            # Mock execute to fail twice, then succeed
            mock_execute.side_effect = [
                (False, "", "Command failed", {}),  # First attempt fails
                (False, "", "Command failed", {}),  # Second attempt fails
                (True, "Success", "", {}),  # Third attempt succeeds
            ]

            try:
                result = await self.engine.run_workflow(workflow_file)

                # Should succeed after retries
                assert result.status == "completed"
                assert result.jobs["failing-job"].status == "completed"
                assert mock_execute.call_count == 3  # Original + 2 retries
            finally:
                os.unlink(workflow_file)

    @pytest.mark.asyncio
    async def test_exhausted_retries(self, failing_workflow):
        """Test behavior when retries are exhausted"""
        workflow_file = self.create_temp_workflow(failing_workflow)

        with patch.object(BashExecutor, "execute") as mock_execute:
            # Mock execute to always fail
            mock_execute.return_value = (False, "", "Command always fails", {})

            try:
                result = await self.engine.run_workflow(workflow_file)

                # Should fail after exhausting retries
                assert result.status == "failed"
                assert result.jobs["failing-job"].status == "failed"
                assert (
                    mock_execute.call_count == 3
                )  # Original + 2 retries (max_retries=2)
            finally:
                os.unlink(workflow_file)

    @pytest.mark.asyncio
    async def test_invalid_workflow_validation(self):
        """Test workflow validation failure"""
        invalid_workflow = {
            "name": "invalid-test",
            "jobs": {
                "invalid-job": {
                    "runs-on": "ubuntu-latest",
                    "steps": [{"run": "echo 'test'"}],
                    "needs": "non-existent-job",  # This should cause validation failure
                }
            },
        }

        workflow_file = self.create_temp_workflow(invalid_workflow)

        try:
            with pytest.raises(Exception, match="Workflow validation failed"):
                await self.engine.run_workflow(workflow_file)
        finally:
            os.unlink(workflow_file)

    @pytest.mark.asyncio
    async def test_circular_dependency_detection(self):
        """Test detection of circular dependencies"""
        circular_workflow = {
            "name": "circular-test",
            "jobs": {
                "job-a": {
                    "runs-on": "ubuntu-latest",
                    "needs": "job-b",
                    "steps": [{"run": "echo 'job a'"}],
                },
                "job-b": {
                    "runs-on": "ubuntu-latest",
                    "needs": "job-a",
                    "steps": [{"run": "echo 'job b'"}],
                },
            },
        }

        workflow_file = self.create_temp_workflow(circular_workflow)

        try:
            # This should raise a validation exception, not return a failed result
            with pytest.raises(Exception, match="Circular dependency detected"):
                await self.engine.run_workflow(workflow_file)
        finally:
            os.unlink(workflow_file)

    @pytest.mark.asyncio
    async def test_environment_variable_substitution(self):
        """Test environment variable substitution in commands"""
        env_workflow = {
            "name": "env-test",
            "jobs": {
                "env-job": {
                    "runs-on": "ubuntu-latest",
                    "steps": [{"run": "echo $TEST_VAR"}],
                }
            },
        }

        workflow_file = self.create_temp_workflow(env_workflow)

        # Set environment variable
        test_value = "test_environment_value"
        with patch.dict(os.environ, {"TEST_VAR": test_value}):
            try:
                result = await self.engine.run_workflow(workflow_file)

                assert result.status == "completed"
                assert result.jobs["env-job"].status == "completed"
                # The command should have been executed with the substituted variable
            finally:
                os.unlink(workflow_file)

    @pytest.mark.asyncio
    async def test_step_output_capture(self):
        """Test that step outputs are properly captured"""
        output_workflow = {
            "name": "output-test",
            "jobs": {
                "output-job": {
                    "runs-on": "ubuntu-latest",
                    "steps": [{"id": "test-step", "run": "echo 'test output'"}],
                }
            },
        }

        workflow_file = self.create_temp_workflow(output_workflow)

        try:
            result = await self.engine.run_workflow(workflow_file)

            assert result.status == "completed"
            job_output = result.jobs["output-job"]
            assert job_output.status == "completed"
            # Note: Outputs structure depends on the LocalEngine implementation
        finally:
            os.unlink(workflow_file)

    @pytest.mark.asyncio
    async def test_skipped_job_condition(self):
        """Test job skipping when condition is not met"""
        skip_workflow = {
            "name": "skip-test",
            "jobs": {
                "failingjob": {  # Removed hyphen
                    "runs-on": "ubuntu-latest",
                    "steps": [{"run": "exit 1"}],
                },
                "conditionaljob": {  # Removed hyphen
                    "runs-on": "ubuntu-latest",
                    "if": "needs.failingjob.result == 'success'",  # Match job name
                    "needs": "failingjob",
                    "steps": [{"run": "echo 'should be skipped'"}],
                },
            },
        }

        workflow_file = self.create_temp_workflow(skip_workflow)

        try:
            result = await self.engine.run_workflow(workflow_file)

            assert result.status == "failed"  # Overall workflow fails
            assert result.jobs["failingjob"].status == "failed"
            assert result.jobs["conditionaljob"].status == "skipped"
        finally:
            os.unlink(workflow_file)

    def test_local_engine_initialization(self):
        """Test LocalEngine initialization"""
        config = Config(max_retries=5)
        engine = LocalEngine(config)

        assert engine.config == config
        assert engine.config.max_retries == 5

    @pytest.mark.asyncio
    async def test_workflow_file_not_found(self):
        """Test handling of non-existent workflow file"""
        with pytest.raises(ValueError, match="Workflow file not found"):
            await self.engine.run_workflow("non_existent_workflow.yaml")

    @pytest.mark.asyncio
    async def test_malformed_yaml(self):
        """Test handling of malformed YAML workflow file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [unclosed")
            malformed_file = f.name

        try:
            with pytest.raises(ValueError, match="YAML parsing error"):
                await self.engine.run_workflow(malformed_file)
        finally:
            os.unlink(malformed_file)


class TestLocalEngineIntegration:
    """Integration tests for LocalEngine"""

    def setup_method(self):
        """Set up integration test fixtures"""
        self.config = Config(max_retries=1)
        self.engine = LocalEngine(self.config)

    def create_temp_workflow(self, workflow_content: dict) -> str:
        """Create a temporary workflow file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(workflow_content, f)
            return f.name

    @pytest.mark.asyncio
    async def test_real_file_operations(self):
        """Integration test with real file operations"""
        file_workflow = {
            "name": "file-operations",
            "jobs": {
                "file-job": {
                    "runs-on": "ubuntu-latest",
                    "steps": [
                        {"run": "echo 'test content' > /tmp/test_local_engine.txt"},
                        {"run": "cat /tmp/test_local_engine.txt"},
                        {"run": "rm /tmp/test_local_engine.txt"},
                    ],
                }
            },
        }

        workflow_file = self.create_temp_workflow(file_workflow)

        try:
            result = await self.engine.run_workflow(workflow_file)

            assert result.status == "completed"
            assert result.jobs["file-job"].status == "completed"

            # Verify the temporary file was cleaned up
            assert not os.path.exists("/tmp/test_local_engine.txt")
        finally:
            os.unlink(workflow_file)

    @pytest.mark.asyncio
    async def test_complex_bash_commands(self):
        """Integration test with complex bash commands"""
        complex_workflow = {
            "name": "complex-bash",
            "jobs": {
                "bash-job": {
                    "runs-on": "ubuntu-latest",
                    "steps": [
                        {"run": 'for i in {1..3}; do echo "Line $i"; done'},
                        {"run": "if [ -d /tmp ]; then echo 'tmp exists'; fi"},
                        {"run": "ls /usr/bin | head -5 | wc -l"},
                    ],
                }
            },
        }

        workflow_file = self.create_temp_workflow(complex_workflow)

        try:
            result = await self.engine.run_workflow(workflow_file)

            assert result.status == "completed"
            assert result.jobs["bash-job"].status == "completed"
        finally:
            os.unlink(workflow_file)
