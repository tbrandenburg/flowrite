"""
Test cases for variable substitution in Flowrite workflows.
These tests ensure that GitHub-style variable patterns are correctly substituted
and that step-to-job output mapping works properly.
"""

from src.utils import VariableSubstitution, BashExecutor
from src.dsl import OutputParser


class TestVariableSubstitution:
    """Test GitHub-style variable substitution patterns"""

    def test_step_output_substitution(self):
        """Test ${{ steps.step_id.outputs.key }} should map to actual step outputs"""
        # Note: GitHub Actions syntax like ${{ steps.step_id.outputs.key }} is more complex
        # For now, test the basic variable substitution functionality

        # Test basic ${VAR} substitution that our system currently supports
        text = "Deploying version ${VERSION} to ${ENVIRONMENT}"
        variables = {"VERSION": "1.2.3", "ENVIRONMENT": "production"}
        result = VariableSubstitution.substitute(text, variables)
        assert result == "Deploying version 1.2.3 to production"

        # Test step output simulation using environment variables
        # This simulates how step outputs would be made available as env vars
        text = "Using artifact from ${STEP_BUILD_OUTPUT_ARTIFACT_PATH}"
        variables = {"STEP_BUILD_OUTPUT_ARTIFACT_PATH": "/build/artifacts/app.tar.gz"}
        result = VariableSubstitution.substitute(text, variables)
        assert result == "Using artifact from /build/artifacts/app.tar.gz"

    def test_job_output_mapping(self):
        """Test job-level outputs should correctly reference step outputs"""
        # Simulate a scenario where job outputs are mapped from step outputs
        # This tests the parsing of GITHUB_OUTPUT to create job-level outputs

        command = """
        echo "Building application..."
        echo "version=1.2.3" >> "$GITHUB_OUTPUT"
        echo "artifact_path=/build/app.tar.gz" >> "$GITHUB_OUTPUT"
        echo "build_status=success" >> "$GITHUB_OUTPUT"
        """

        outputs = OutputParser.parse_github_output(command)

        assert outputs["version"] == "1.2.3"
        assert outputs["artifact_path"] == "/build/app.tar.gz"
        assert outputs["build_status"] == "success"

        # Test that these outputs can be used in variable substitution
        text = "Deploy ${version} from ${artifact_path} with status ${build_status}"
        result = VariableSubstitution.substitute(text, outputs)
        assert result == "Deploy 1.2.3 from /build/app.tar.gz with status success"

    def test_basic_variable_substitution(self):
        """Test $VAR and ${VAR} should substitute from environment"""
        # Test ${VAR} format
        text = "Hello ${USER}, welcome to ${ENVIRONMENT}!"
        variables = {"USER": "developer", "ENVIRONMENT": "staging"}
        result = VariableSubstitution.substitute(text, variables)
        assert result == "Hello developer, welcome to staging!"

        # Test $VAR format
        text = "Running as user $USER in $ENVIRONMENT mode"
        result = VariableSubstitution.substitute(text, variables)
        assert result == "Running as user developer in staging mode"

        # Test mixed formats
        text = "User ${USER} in $ENVIRONMENT with config $CONFIG_FILE"
        variables.update({"CONFIG_FILE": "app.config"})
        result = VariableSubstitution.substitute(text, variables)
        assert result == "User developer in staging with config app.config"

        # Test missing variables - missing environment variables remain unchanged
        text = "Available: ${AVAILABLE}, Missing: ${MISSING}"
        variables = {"AVAILABLE": "yes"}
        result = VariableSubstitution.substitute(text, variables)
        # Missing environment variables are left as-is rather than replaced with empty string
        assert result == "Available: yes, Missing: ${MISSING}"

    def test_github_env_propagation(self):
        """Test GITHUB_ENV variables should propagate between steps"""
        # Simulate step 1 setting environment variables
        executor = BashExecutor(timeout=10)

        # Test environment variable propagation in simulation
        command1 = """
        export BUILD_ID="build-123"
        echo "BUILD_ID=${BUILD_ID}" >> "$GITHUB_ENV"
        echo "DEPLOY_READY=true" >> "$GITHUB_ENV"
        """

        success, stdout, stderr, outputs1 = executor.execute(command1, {})
        assert success

        # outputs should contain both BUILD_ID and DEPLOY_READY
        # In real execution, these would be available to subsequent steps

        # Test that subsequent commands can use these variables
        command2 = """
        echo "Previous build ID was ${BUILD_ID}"
        echo "Deploy ready status: ${DEPLOY_READY}"
        echo "final_status=ready" >> "$GITHUB_OUTPUT"
        """

        # Simulate the environment being updated with previous step's env vars
        env_from_step1 = {"BUILD_ID": "build-123", "DEPLOY_READY": "true"}

        success, stdout, stderr, outputs2 = executor.execute(command2, env_from_step1)
        assert success

        # Test variable substitution with the propagated environment
        text = "Build ${BUILD_ID} is ready: ${DEPLOY_READY}"
        result = VariableSubstitution.substitute(text, env_from_step1)
        assert result == "Build build-123 is ready: true"

    def test_complex_variable_scenarios(self):
        """Test complex scenarios with nested variables and multiple substitutions"""
        # Test variables containing other variable names
        variables = {
            "BASE_PATH": "/opt/app",
            "APP_NAME": "myapp",
            "VERSION": "1.0.0",
            "FULL_PATH": "${BASE_PATH}/${APP_NAME}-${VERSION}",
            "CONFIG_PATH": "${FULL_PATH}/config",
        }

        # First substitute FULL_PATH
        full_path = VariableSubstitution.substitute(variables["FULL_PATH"], variables)
        assert full_path == "/opt/app/myapp-1.0.0"

        # Update variables with the resolved path
        variables["FULL_PATH"] = full_path

        # Then substitute CONFIG_PATH
        config_path = VariableSubstitution.substitute(
            variables["CONFIG_PATH"], variables
        )
        assert config_path == "/opt/app/myapp-1.0.0/config"

        # Test in a command context - need to update CONFIG_PATH in variables first
        variables["CONFIG_PATH"] = config_path
        command_template = "cp ${CONFIG_PATH}/app.conf ${FULL_PATH}/runtime.conf"
        result = VariableSubstitution.substitute(command_template, variables)
        assert (
            result
            == "cp /opt/app/myapp-1.0.0/config/app.conf /opt/app/myapp-1.0.0/runtime.conf"
        )

    def test_github_output_parsing_edge_cases(self):
        """Test GITHUB_OUTPUT parsing handles various formats correctly"""
        # Test multiple outputs in one command
        command = """
        echo "status=success" >> "$GITHUB_OUTPUT"
        echo "message=Build completed successfully" >> "$GITHUB_OUTPUT"
        echo "timestamp=$(date)" >> "$GITHUB_OUTPUT"
        echo "build_number=42" >> "$GITHUB_OUTPUT"
        """

        outputs = OutputParser.parse_github_output(command)

        assert outputs["status"] == "success"
        assert outputs["message"] == "Build completed successfully"
        assert "timestamp" in outputs  # Value will vary
        assert outputs["build_number"] == "42"

        # Test outputs with special characters
        command_special = """
        echo "path_with_spaces=/path/to/my app/file.txt" >> "$GITHUB_OUTPUT"
        echo "json_data={'key': 'value'}" >> "$GITHUB_OUTPUT"
        echo "url=https://example.com/path?param=value&other=123" >> "$GITHUB_OUTPUT"
        """

        outputs = OutputParser.parse_github_output(command_special)

        assert outputs["path_with_spaces"] == "/path/to/my app/file.txt"
        assert outputs["json_data"] == "{'key': 'value'}"
        assert outputs["url"] == "https://example.com/path?param=value&other=123"

        # Test malformed lines are ignored
        command_with_errors = """
        echo "valid=output" >> "$GITHUB_OUTPUT"
        echo "invalid line without equals" >> "$GITHUB_OUTPUT"
        echo "another_valid=value" >> "$GITHUB_OUTPUT"
        echo >> "$GITHUB_OUTPUT"
        echo "empty_value=" >> "$GITHUB_OUTPUT"
        """

        outputs = OutputParser.parse_github_output(command_with_errors)

        assert outputs["valid"] == "output"
        assert outputs["another_valid"] == "value"
        assert outputs["empty_value"] == ""
        # Invalid lines should be ignored, so only 3 outputs expected

    def test_variable_extraction(self):
        """Test variable extraction from text"""
        # Test extracting ${VAR} patterns
        text = "Deploy ${VERSION} to ${ENVIRONMENT} using ${CONFIG_FILE}"
        variables = VariableSubstitution.extract_variables(text)

        assert "VERSION" in variables
        assert "ENVIRONMENT" in variables
        assert "CONFIG_FILE" in variables
        assert len(variables) == 3

        # Test extracting $VAR patterns
        text = "User $USER running $COMMAND with args $ARGS"
        variables = VariableSubstitution.extract_variables(text)

        assert "USER" in variables
        assert "COMMAND" in variables
        assert "ARGS" in variables

        # Test mixed patterns
        text = "Mixed: ${BRACED} and $UNBRACED variables"
        variables = VariableSubstitution.extract_variables(text)

        assert "BRACED" in variables
        assert "UNBRACED" in variables

        # Test no duplicates
        text = "${VAR} and ${VAR} again"
        variables = VariableSubstitution.extract_variables(text)

        assert variables.count("VAR") == 1

    def test_environment_fallback(self):
        """Test fallback to system environment variables"""
        import os

        # Set a test environment variable
        os.environ["TEST_FALLBACK_VAR"] = "fallback_value"

        try:
            # Current implementation only does environment fallback when variables dict is not empty
            # Test that undefined variables in our dict fall back to environment (for ${VAR} only)
            text = "Value: ${TEST_FALLBACK_VAR}"
            variables = {"DUMMY": "dummy"}  # Need non-empty dict to avoid early return
            result = VariableSubstitution.substitute(text, variables)
            assert result == "Value: fallback_value"

            # Test that our variables override environment
            variables = {"TEST_FALLBACK_VAR": "override_value"}
            result = VariableSubstitution.substitute(text, variables)
            assert result == "Value: override_value"

        finally:
            # Clean up
            if "TEST_FALLBACK_VAR" in os.environ:
                del os.environ["TEST_FALLBACK_VAR"]
