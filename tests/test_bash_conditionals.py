"""
Test cases for bash conditional execution in workflow steps.

This module tests the BashExecutor's ability to handle various bash conditional
constructs like if/else statements, pattern matching, and nested conditions.
"""

from src.utils import BashExecutor


class TestBashConditionalExecution:
    """Test bash conditional execution capabilities"""

    def test_bash_if_else_simulation(self):
        """Test if [[ "$VAR" == "value" ]]; then ... else ... fi"""
        executor = BashExecutor()

        # Test basic if-then-else with equality check
        script = """
if [[ "$ENVIRONMENT" == "production" ]]; then
  DEPLOY_FLAG=enabled
else
  DEPLOY_FLAG=disabled
fi
echo "deploy_flag=$DEPLOY_FLAG" >> "$GITHUB_OUTPUT"
"""

        # Test production environment
        env_vars = {"ENVIRONMENT": "production"}
        success, stdout, stderr, outputs = executor.execute(script, env_vars)
        assert success
        assert outputs.get("deploy_flag") == "enabled"

        # Test non-production environment
        env_vars = {"ENVIRONMENT": "staging"}
        success, stdout, stderr, outputs = executor.execute(script, env_vars)
        assert success
        assert outputs.get("deploy_flag") == "disabled"

    def test_bash_pattern_matching(self):
        """Test if [[ "$VAR" =~ ^(staging|production)$ ]]; then"""
        executor = BashExecutor()

        # Test regex pattern matching with alternation
        script = """
if [[ "$ENVIRONMENT" =~ ^(staging|production)$ ]]; then
  VALID_ENV=true
  echo "env_valid=true" >> "$GITHUB_OUTPUT"
else
  VALID_ENV=false
  echo "env_valid=false" >> "$GITHUB_OUTPUT"
fi
"""

        # Test valid environments
        for valid_env in ["staging", "production"]:
            env_vars = {"ENVIRONMENT": valid_env}
            success, stdout, stderr, outputs = executor.execute(script, env_vars)
            assert success
            assert outputs.get("env_valid") == "true"

        # Test invalid environments
        for invalid_env in ["development", "testing"]:
            env_vars = {"ENVIRONMENT": invalid_env}
            success, stdout, stderr, outputs = executor.execute(script, env_vars)
            assert success
            assert outputs.get("env_valid") == "false"

    def test_bash_nested_conditionals(self):
        """Test multiple sequential if statements with conditional logic"""
        executor = BashExecutor()

        # Test multiple sequential if statements to test conditional logic
        script = """
# First check environment
if [[ "$DEPLOY_ENVIRONMENT" == "production" ]]; then
  DEPLOY_ENABLED=true
else
  DEPLOY_ENABLED=false
fi

# Then check deployment type for production environments  
if [[ "$DEPLOY_TIME" == "maintenance" ]]; then
  MAINTENANCE_MODE=true
else
  MAINTENANCE_MODE=false
fi

echo "enabled=$DEPLOY_ENABLED" >> "$GITHUB_OUTPUT"
echo "maintenance=$MAINTENANCE_MODE" >> "$GITHUB_OUTPUT"
"""

        # Test production + maintenance window
        env_vars = {
            "DEPLOY_ENVIRONMENT": "production",
            "DEPLOY_TIME": "maintenance",
        }
        success, stdout, stderr, outputs = executor.execute(script, env_vars)
        assert success
        assert outputs.get("enabled") == "true"
        assert outputs.get("maintenance") == "true"

        # Test production + regular time
        env_vars = {
            "DEPLOY_ENVIRONMENT": "production",
            "DEPLOY_TIME": "regular",
        }
        success, stdout, stderr, outputs = executor.execute(script, env_vars)
        assert success
        assert outputs.get("enabled") == "true"
        assert outputs.get("maintenance") == "false"

        # Test non-production environment
        env_vars = {
            "DEPLOY_ENVIRONMENT": "staging",
            "DEPLOY_TIME": "maintenance",
        }
        success, stdout, stderr, outputs = executor.execute(script, env_vars)
        assert success
        assert outputs.get("enabled") == "false"
        assert outputs.get("maintenance") == "true"

    def test_bash_equality_checks(self):
        """Test [ "$VAR" == "value" ] vs [[ "$VAR" == "value" ]]"""
        executor = BashExecutor()

        # Test double bracket syntax
        script = """
if [[ "$BUILD_MODE" == "release" ]]; then
  echo "mode=release" >> "$GITHUB_OUTPUT"
else
  echo "mode=debug" >> "$GITHUB_OUTPUT"
fi
"""

        # Test release mode
        env_vars = {"BUILD_MODE": "release"}
        success, stdout, stderr, outputs = executor.execute(script, env_vars)
        assert success
        assert outputs.get("mode") == "release"

        # Test debug mode
        env_vars = {"BUILD_MODE": "debug"}
        success, stdout, stderr, outputs = executor.execute(script, env_vars)
        assert success
        assert outputs.get("mode") == "debug"
