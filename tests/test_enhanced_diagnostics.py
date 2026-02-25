"""
Enhanced Diagnostics Tests

These tests focus on testing the diagnostic capabilities of the workflow execution system,
ensuring that users get clear, categorized information about why jobs are blocked.
"""

import pytest
from src.types import WorkflowDefinition, JobDefinition, StepDefinition
from src.dsl import DependencyResolver
from src.types import JobStatus


class TestEnhancedDiagnostics:
    """Test suite for enhanced diagnostic capabilities"""

    def test_diagnostic_categorization(self):
        """Test that get_job_diagnostics() correctly categorizes blocking reasons"""
        # Create a workflow with various blocking scenarios
        workflow = WorkflowDefinition(
            name="Diagnostic Test Workflow",
            jobs={
                "ready_job": JobDefinition(
                    name="ready_job",
                    runs_on="ubuntu-latest",
                    steps=[StepDefinition(run="echo 'Ready to run'")],
                    needs=[],
                    if_condition=None,
                ),
                "dependency_blocked": JobDefinition(
                    name="dependency_blocked",
                    runs_on="ubuntu-latest",
                    steps=[StepDefinition(run="echo 'Waiting for deps'")],
                    needs=["missing_job"],  # Non-existent dependency
                    if_condition=None,
                ),
                "condition_blocked": JobDefinition(
                    name="condition_blocked",
                    runs_on="ubuntu-latest",
                    steps=[StepDefinition(run="echo 'Condition not met'")],
                    needs=[],
                    if_condition="needs.nonexistent.result == 'failure'",  # Should be False (nonexistent defaults to 'success')
                ),
                "both_blocked": JobDefinition(
                    name="both_blocked",
                    runs_on="ubuntu-latest",
                    steps=[StepDefinition(run="echo 'Both issues'")],
                    needs=["missing_job"],
                    if_condition="needs.nonexistent.result == 'success'",
                ),
                "completed_job": JobDefinition(
                    name="completed_job",
                    runs_on="ubuntu-latest",
                    steps=[StepDefinition(run="echo 'Already done'")],
                    needs=[],
                    if_condition=None,
                ),
            },
        )

        # Simulate that some jobs are already completed
        completed = {"completed_job"}
        job_outputs = {"completed_job": {}}
        env_vars = {}

        # Get diagnostics
        diagnostics = DependencyResolver.get_job_diagnostics(
            workflow, completed, job_outputs, env_vars
        )

        # Test ready job
        assert "ready_job" in diagnostics
        ready_diag = diagnostics["ready_job"]
        assert ready_diag["status"] == "ready"
        assert ready_diag["dependencies_met"] is True
        assert ready_diag["condition_met"] is True
        assert ready_diag["missing_dependencies"] == []

        # Test dependency blocked job
        assert "dependency_blocked" in diagnostics
        dep_diag = diagnostics["dependency_blocked"]
        assert dep_diag["status"] == "waiting_for_dependencies"
        assert dep_diag["dependencies_met"] is False
        assert dep_diag["condition_met"] is True  # Condition not even checked yet
        assert "missing_job" in dep_diag["missing_dependencies"]

        # Test condition blocked job
        assert "condition_blocked" in diagnostics
        cond_diag = diagnostics["condition_blocked"]
        assert cond_diag["status"] == "condition_not_met"
        assert cond_diag["dependencies_met"] is True  # Dependencies are met
        assert cond_diag["condition_met"] is False
        assert cond_diag["condition_details"] is not None
        assert cond_diag["condition_details"]["evaluated_to"] is False

        # Test job blocked by both dependencies and conditions
        assert "both_blocked" in diagnostics
        both_diag = diagnostics["both_blocked"]
        # Should show dependency issue first (conditions not checked when deps missing)
        assert both_diag["status"] == "waiting_for_dependencies"
        assert both_diag["dependencies_met"] is False
        assert "missing_job" in both_diag["missing_dependencies"]

        # Completed job should not appear in diagnostics
        assert "completed_job" not in diagnostics

    def test_mixed_blocking_scenarios(self):
        """Test jobs blocked by both dependencies AND conditions"""
        workflow = WorkflowDefinition(
            name="Mixed Blocking Test",
            jobs={
                "base_job": JobDefinition(
                    name="base_job",
                    runs_on="ubuntu-latest",
                    steps=[StepDefinition(run="echo 'Base job'")],
                    needs=[],
                    if_condition=None,
                ),
                "complex_job": JobDefinition(
                    name="complex_job",
                    runs_on="ubuntu-latest",
                    steps=[StepDefinition(run="echo 'Complex job'")],
                    needs=["base_job", "missing_dependency"],
                    if_condition="env.ENABLE_COMPLEX == 'true'",
                ),
            },
        )

        # Test when base_job is completed but missing_dependency is not
        completed = {"base_job"}
        job_outputs = {"base_job": {}}
        env_vars = {"ENABLE_COMPLEX": "false"}  # Condition will be false

        diagnostics = DependencyResolver.get_job_diagnostics(
            workflow, completed, job_outputs, env_vars
        )

        # Complex job should show dependency blocking first
        assert "complex_job" in diagnostics
        complex_diag = diagnostics["complex_job"]
        assert complex_diag["status"] == "waiting_for_dependencies"
        assert complex_diag["dependencies_met"] is False
        assert "missing_dependency" in complex_diag["missing_dependencies"]
        assert "base_job" not in complex_diag["missing_dependencies"]  # This one is met

        # Now test when dependencies are met but condition is false
        completed_both = {"base_job", "missing_dependency"}
        job_outputs_both = {"base_job": {}, "missing_dependency": {}}

        diagnostics_both = DependencyResolver.get_job_diagnostics(
            workflow, completed_both, job_outputs_both, env_vars
        )

        complex_diag_both = diagnostics_both["complex_job"]
        assert complex_diag_both["status"] == "condition_not_met"
        assert complex_diag_both["dependencies_met"] is True
        assert complex_diag_both["condition_met"] is False
        assert complex_diag_both["missing_dependencies"] == []

    def test_dependency_diagnostic_messages(self):
        """Test clear error messages for dependency issues"""
        workflow = WorkflowDefinition(
            name="Dependency Message Test",
            jobs={
                "job_a": JobDefinition(
                    name="job_a",
                    runs_on="ubuntu-latest",
                    steps=[StepDefinition(run="echo 'Job A'")],
                    needs=["job_b", "job_c", "nonexistent_job"],
                    if_condition=None,
                ),
                "job_b": JobDefinition(
                    name="job_b",
                    runs_on="ubuntu-latest",
                    steps=[StepDefinition(run="echo 'Job B'")],
                    needs=[],
                    if_condition=None,
                ),
            },
        )

        completed = {"job_b"}  # Only job_b is completed
        job_outputs = {"job_b": {}}
        env_vars = {}

        diagnostics = DependencyResolver.get_job_diagnostics(
            workflow, completed, job_outputs, env_vars
        )

        job_a_diag = diagnostics["job_a"]
        assert job_a_diag["status"] == "waiting_for_dependencies"
        assert job_a_diag["dependencies_met"] is False

        # Should list all missing dependencies
        missing_deps = job_a_diag["missing_dependencies"]
        assert "job_c" in missing_deps
        assert "nonexistent_job" in missing_deps
        assert "job_b" not in missing_deps  # This one is completed

        # Should have exactly 2 missing dependencies
        assert len(missing_deps) == 2

    def test_condition_diagnostic_messages(self):
        """Test clear error messages for condition issues"""
        workflow = WorkflowDefinition(
            name="Condition Message Test",
            jobs={
                "job_a": JobDefinition(
                    name="job_a",
                    runs_on="ubuntu-latest",
                    steps=[StepDefinition(run="echo 'Base job'")],
                    needs=[],
                    if_condition=None,
                ),
                "conditional_job": JobDefinition(
                    name="conditional_job",
                    runs_on="ubuntu-latest",
                    steps=[StepDefinition(run="echo 'Conditional job'")],
                    needs=["job_a"],
                    if_condition="needs.job_a.outputs.status == 'success' && env.DEPLOY_ENV == 'production'",
                ),
            },
        )

        # Set up scenario where dependencies are met but condition fails
        completed = {"job_a"}
        job_outputs = {"job_a": {"status": "failure"}}  # This will make condition false
        env_vars = {"DEPLOY_ENV": "staging"}  # This will also make condition false

        diagnostics = DependencyResolver.get_job_diagnostics(
            workflow, completed, job_outputs, env_vars
        )

        cond_diag = diagnostics["conditional_job"]
        assert cond_diag["status"] == "condition_not_met"
        assert cond_diag["dependencies_met"] is True
        assert cond_diag["condition_met"] is False

        # Should have detailed condition information
        condition_details = cond_diag["condition_details"]
        assert condition_details is not None
        assert "expression" in condition_details
        assert "evaluated_to" in condition_details
        assert (
            condition_details["expression"]
            == "needs.job_a.outputs.status == 'success' && env.DEPLOY_ENV == 'production'"
        )
        assert condition_details["evaluated_to"] is False

    def test_unknown_blocking_diagnostic(self):
        """Test handling of edge cases with unknown blocking reasons"""
        # Test an edge case where a job might be in an unusual state
        workflow = WorkflowDefinition(
            name="Edge Case Test",
            jobs={
                "normal_job": JobDefinition(
                    name="normal_job",
                    runs_on="ubuntu-latest",
                    steps=[StepDefinition(run="echo 'Normal'")],
                    needs=[],
                    if_condition=None,
                ),
                "edge_case_job": JobDefinition(
                    name="edge_case_job",
                    runs_on="ubuntu-latest",
                    steps=[StepDefinition(run="echo 'Edge case'")],
                    needs=[],
                    # Test with an empty string condition (edge case)
                    if_condition="",
                ),
            },
        )

        completed = set()
        job_outputs = {}
        env_vars = {}

        diagnostics = DependencyResolver.get_job_diagnostics(
            workflow, completed, job_outputs, env_vars
        )

        # Normal job should be ready
        normal_diag = diagnostics["normal_job"]
        assert normal_diag["status"] == "ready"

        # Edge case job with empty condition should still work
        # (empty condition should default to True)
        edge_diag = diagnostics["edge_case_job"]
        assert edge_diag["status"] == "ready"
        assert edge_diag["dependencies_met"] is True
        assert edge_diag["condition_met"] is True

        # Test with a null/None condition explicitly
        workflow.jobs["edge_case_job"].if_condition = None
        diagnostics_null = DependencyResolver.get_job_diagnostics(
            workflow, completed, job_outputs, env_vars
        )

        edge_diag_null = diagnostics_null["edge_case_job"]
        assert edge_diag_null["status"] == "ready"
        assert edge_diag_null["condition_met"] is True
