import pytest
from unittest.mock import AsyncMock, patch
from src.main import JobWorkflow
from src.types import JobDefinition, StepDefinition, LoopConfig


@pytest.mark.asyncio
class TestJobWorkflow:
    def setup_method(self):
        self.workflow = JobWorkflow()

    async def test_execute_step_foreach_iterations(self):
        """Test step foreach iteration execution"""
        step = StepDefinition(
            name="test-step",
            run="echo $FOREACH_ITEM",
            loop=LoopConfig(foreach="item1 item2"),
        )

        with patch("src.main.workflow.execute_activity") as mock_activity:
            mock_activity.return_value = AsyncMock(
                success=True, outputs={"test": "value"}
            )

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
            loop=LoopConfig(max_iterations=3, until="success"),
        )

        with patch("src.main.workflow.execute_activity") as mock_activity:
            # Fail twice, then succeed
            mock_activity.side_effect = [
                AsyncMock(success=False, error="Failed attempt 1"),
                AsyncMock(success=False, error="Failed attempt 2"),
                AsyncMock(success=True, outputs={"result": "success"}),
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
            loop=LoopConfig(max_iterations=1),
        )

        with patch("src.main.workflow.execute_activity") as mock_activity:
            mock_activity.return_value = AsyncMock(
                success=True, outputs={"test": "value"}
            )

            result = await self.workflow._execute_job_until_iterations(
                "test-job", job_def, {"env": "vars"}
            )

            assert result.status == "completed"
            assert mock_activity.called
