"""
Test cases for dependency cycle detection in Flowrite workflows.
These tests ensure that actual circular dependencies are detected while
condition-based or dependency-based waiting scenarios are correctly categorized.
"""

import pytest
from src.types import WorkflowDefinition, JobDefinition
from src.dsl import WorkflowParser, DependencyResolver


class TestDependencyCycleDetection:
    """Test detection of true dependency cycles vs false positives"""

    def test_true_dependency_cycle_simple(self):
        """Test A→B→A should be detected as actual cycle"""
        workflow_data = {
            "name": "Simple Cycle Test",
            "jobs": {
                "job_a": {"needs": ["job_b"], "steps": [{"run": "echo 'Job A'"}]},
                "job_b": {"needs": ["job_a"], "steps": [{"run": "echo 'Job B'"}]},
            },
        }

        workflow = WorkflowParser.parse(workflow_data)
        errors = WorkflowParser.validate(workflow)

        # Should detect circular dependency
        assert len(errors) > 0
        assert any("circular dependency" in error.lower() for error in errors)

        # Verify the cycle involves both jobs
        cycle_error = [e for e in errors if "circular dependency" in e.lower()][0]
        assert "job_a" in cycle_error or "job_b" in cycle_error

    def test_true_dependency_cycle_complex(self):
        """Test A→B→C→A should be detected as actual cycle"""
        workflow_data = {
            "name": "Complex Cycle Test",
            "jobs": {
                "job_a": {"needs": ["job_c"], "steps": [{"run": "echo 'Job A'"}]},
                "job_b": {"needs": ["job_a"], "steps": [{"run": "echo 'Job B'"}]},
                "job_c": {"needs": ["job_b"], "steps": [{"run": "echo 'Job C'"}]},
            },
        }

        workflow = WorkflowParser.parse(workflow_data)
        errors = WorkflowParser.validate(workflow)

        # Should detect circular dependency
        assert len(errors) > 0
        assert any("circular dependency" in error.lower() for error in errors)

    def test_self_dependency(self):
        """Test A→A should be detected as cycle"""
        workflow_data = {
            "name": "Self Dependency Test",
            "jobs": {"job_a": {"needs": ["job_a"], "steps": [{"run": "echo 'Job A'"}]}},
        }

        workflow = WorkflowParser.parse(workflow_data)
        errors = WorkflowParser.validate(workflow)

        # Should detect self-dependency cycle
        assert len(errors) > 0
        assert any("circular dependency" in error.lower() for error in errors)

    def test_condition_blocking_not_cycle(self):
        """Test jobs blocked by unmet conditions should show condition diagnostic, not cycle"""
        workflow_data = {
            "name": "Condition Blocking Test",
            "jobs": {
                "setup": {
                    "steps": [{"run": "echo 'status=pending' >> \"$GITHUB_OUTPUT\""}]
                },
                "conditional_job": {
                    "needs": ["setup"],
                    "if": "needs.setup.outputs.status == 'ready'",
                    "steps": [{"run": "echo 'Conditional job'"}],
                },
            },
        }

        workflow = WorkflowParser.parse(workflow_data)
        errors = WorkflowParser.validate(workflow)

        # Should not detect any cycles - this is a valid workflow
        assert len(errors) == 0

        # Test runtime diagnostics
        completed = {"setup"}
        job_outputs = {"setup": {"outputs": {"status": "pending"}}}
        diagnostics = DependencyResolver.get_job_diagnostics(
            workflow, completed, job_outputs, {}
        )

        # conditional_job should be blocked by condition, not dependency cycle
        assert "conditional_job" in diagnostics
        assert diagnostics["conditional_job"]["status"] == "condition_not_met"
        assert diagnostics["conditional_job"]["condition_met"] is False
        assert diagnostics["conditional_job"]["dependencies_met"] is True

    def test_dependency_waiting_not_cycle(self):
        """Test jobs waiting for dependencies should show dependency diagnostic, not cycle"""
        workflow_data = {
            "name": "Dependency Waiting Test",
            "jobs": {
                "setup": {"steps": [{"run": "echo 'Setup'"}]},
                "build": {"needs": ["setup"], "steps": [{"run": "echo 'Build'"}]},
                "test": {"needs": ["build"], "steps": [{"run": "echo 'Test'"}]},
            },
        }

        workflow = WorkflowParser.parse(workflow_data)
        errors = WorkflowParser.validate(workflow)

        # Should not detect any cycles - this is a linear dependency chain
        assert len(errors) == 0

        # Test runtime diagnostics - nothing completed yet
        completed = set()
        diagnostics = DependencyResolver.get_job_diagnostics(
            workflow, completed, {}, {}
        )

        # setup should be ready
        assert diagnostics["setup"]["status"] == "ready"

        # build should be waiting for setup
        assert diagnostics["build"]["status"] == "waiting_for_dependencies"
        assert diagnostics["build"]["dependencies_met"] is False
        assert "setup" in diagnostics["build"]["missing_dependencies"]

        # test should be waiting for build
        assert diagnostics["test"]["status"] == "waiting_for_dependencies"
        assert diagnostics["test"]["dependencies_met"] is False
        assert "build" in diagnostics["test"]["missing_dependencies"]

    def test_no_cycle_in_valid_dag(self):
        """Test that valid DAG workflows don't trigger false cycle warnings"""
        workflow_data = {
            "name": "Valid DAG Test",
            "jobs": {
                "init": {"steps": [{"run": "echo 'Initialize'"}]},
                "build_frontend": {
                    "needs": ["init"],
                    "steps": [{"run": "echo 'Build frontend'"}],
                },
                "build_backend": {
                    "needs": ["init"],
                    "steps": [{"run": "echo 'Build backend'"}],
                },
                "test_frontend": {
                    "needs": ["build_frontend"],
                    "steps": [{"run": "echo 'Test frontend'"}],
                },
                "test_backend": {
                    "needs": ["build_backend"],
                    "steps": [{"run": "echo 'Test backend'"}],
                },
                "deploy": {
                    "needs": ["test_frontend", "test_backend"],
                    "steps": [{"run": "echo 'Deploy'"}],
                },
            },
        }

        workflow = WorkflowParser.parse(workflow_data)
        errors = WorkflowParser.validate(workflow)

        # Should not detect any cycles
        assert len(errors) == 0

        # Test that jobs are properly scheduled
        completed = set()
        ready_jobs = DependencyResolver.get_ready_jobs(workflow, completed, {}, {})
        assert "init" in ready_jobs
        assert len(ready_jobs) == 1

        # After init completes
        completed.add("init")
        ready_jobs = DependencyResolver.get_ready_jobs(workflow, completed, {}, {})
        assert "build_frontend" in ready_jobs
        assert "build_backend" in ready_jobs
        assert len(ready_jobs) == 2
