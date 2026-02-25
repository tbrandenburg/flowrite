import pytest
from src.utils import VariableSubstitution


class TestGitHubActionsVariables:
    def test_needs_pattern_substitution(self):
        """Test ${{ needs.job.outputs.key }} substitution"""
        text = "Build ID: ${{ needs.setup.outputs.build_id }}"
        context = {"job_outputs": {"setup": {"build_id": "build-12345"}}}
        result = VariableSubstitution.substitute(text, {}, context)
        assert result == "Build ID: build-12345"

    def test_mixed_variable_patterns(self):
        """Test mixing GitHub Actions and regular variables"""
        text = "Build ${{ needs.setup.outputs.build_id }} on ${ENVIRONMENT}"
        variables = {"ENVIRONMENT": "production"}
        context = {"job_outputs": {"setup": {"build_id": "build-12345"}}}
        result = VariableSubstitution.substitute(text, variables, context)
        assert result == "Build build-12345 on production"

    def test_no_leftover_braces(self):
        """Test that no '}' characters are left after substitution"""
        text = "Env: ${{ needs.setup.outputs.environment }}"
        context = {"job_outputs": {"setup": {"environment": "development"}}}
        result = VariableSubstitution.substitute(text, {}, context)
        assert "}" not in result
        assert result == "Env: development"

    def test_steps_pattern_substitution(self):
        """Test ${{ steps.step.outputs.key }} substitution"""
        text = "Output: ${{ steps.build.outputs.artifact }}"
        context = {"step_outputs": {"artifact": "dist/app.zip"}}
        result = VariableSubstitution.substitute(text, {}, context)
        assert result == "Output: dist/app.zip"

    def test_multiple_github_actions_patterns(self):
        """Test multiple GitHub Actions patterns in one string"""
        text = "Job ${{ needs.setup.outputs.job_id }}, Step ${{ steps.build.outputs.status }}"
        context = {
            "job_outputs": {"setup": {"job_id": "job-456"}},
            "step_outputs": {"status": "success"},
        }
        result = VariableSubstitution.substitute(text, {}, context)
        assert result == "Job job-456, Step success"

    def test_regex_avoids_github_actions_patterns(self):
        """Test that the fixed regex doesn't interfere with GitHub Actions syntax"""
        # This should NOT be processed by the env variable regex
        text = "Value: ${{ needs.setup.outputs.value }}, Env: ${HOME}"
        variables = {"HOME": "/home/user"}
        context = {"job_outputs": {"setup": {"value": "test-value"}}}
        result = VariableSubstitution.substitute(text, variables, context)
        # GitHub Actions pattern should be resolved, regular ${} should be resolved
        assert result == "Value: test-value, Env: /home/user"

    def test_missing_context_returns_empty_string(self):
        """Test that missing job/step outputs return empty strings"""
        text = "Missing: ${{ needs.nonexistent.outputs.missing }}"
        context = {"job_outputs": {}}
        result = VariableSubstitution.substitute(text, {}, context)
        assert result == "Missing: "
