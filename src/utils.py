"""
Flowrite Utilities - Bash execution, variable substitution, and utility functions
"""

import os
import re
import subprocess
import tempfile
from typing import Any, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class VariableSubstitution:
    """Handles variable substitution in commands and expressions"""

    @staticmethod
    def substitute(
        text: str,
        variables: Dict[str, Any],
        github_actions_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Substitute variables in text with GitHub Actions support"""
        if not text:
            return text

        result = text

        # First, handle GitHub Actions patterns if context provided
        if github_actions_context:
            result = VariableSubstitution._resolve_github_actions_patterns(
                result, github_actions_context
            )

        # Then handle regular variable substitution (existing logic)
        if variables:
            # Handle ${VAR} patterns first (more specific)
            for var_name, value in variables.items():
                patterns = [f"${{{var_name}}}", f"${var_name}"]
                str_value = str(value) if value is not None else ""

                for pattern in patterns:
                    result = result.replace(pattern, str_value)

        # Handle environment variables that aren't in our dict (skip GitHub Actions patterns)
        env_pattern = r"\$\{(?!\{)([^}]+)\}"  # Negative lookahead to avoid ${{ patterns
        matches = re.findall(env_pattern, result)
        for var_name in matches:
            if var_name not in variables:
                env_value = os.environ.get(var_name)
                if env_value is not None:
                    result = result.replace(f"${{{var_name}}}", env_value)

        return result

    @staticmethod
    def _resolve_github_actions_patterns(text: str, context: Dict[str, Any]) -> str:
        """Resolve GitHub Actions patterns like ${{ needs.setup.outputs.build_id }}"""
        import re

        result = text

        # Handle needs.* patterns
        needs_pattern = r"\$\{\{\s*needs\.(\w+)\.outputs\.(\w+)\s*\}\}"
        needs_matches = re.findall(needs_pattern, result)
        for job_id, output_key in needs_matches:
            value = context.get("job_outputs", {}).get(job_id, {}).get(output_key, "")
            pattern = f"${{{{ needs.{job_id}.outputs.{output_key} }}}}"
            result = result.replace(pattern, str(value))

        # Handle steps.* patterns
        step_pattern = r"\$\{\{\s*steps\.(\w+)\.outputs\.(\w+)\s*\}\}"
        step_matches = re.findall(step_pattern, result)
        for step_id, output_key in step_matches:
            value = context.get("step_outputs", {}).get(output_key, "")
            pattern = f"${{{{ steps.{step_id}.outputs.{output_key} }}}}"
            result = result.replace(pattern, str(value))

        return result

    @staticmethod
    def extract_variables(text: str) -> list:
        """Extract variable names from text"""
        variables = []

        # Find ${VAR} patterns
        pattern1 = r"\$\{([^}]+)\}"
        variables.extend(re.findall(pattern1, text))

        # Find $VAR patterns (alphanumeric and underscore)
        pattern2 = r"\$([A-Za-z_][A-Za-z0-9_]*)"
        variables.extend(re.findall(pattern2, text))

        return list(set(variables))  # Remove duplicates


class BashExecutor:
    """Executes bash commands with proper error handling and output capture"""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def execute(
        self,
        command: str,
        env_vars: Optional[Dict[str, str]] = None,
        working_dir: Optional[str] = None,
    ) -> Tuple[bool, str, str, Dict[str, str]]:
        """
        Execute bash command and return (success, stdout, stderr, env_updates)
        """
        if not command.strip():
            return True, "", "", {}

        # Use empty dict if env_vars is None
        env_vars = env_vars or {}

        # Substitute variables
        if env_vars:
            command = VariableSubstitution.substitute(command, env_vars)

        try:
            # Create temporary script
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".sh", delete=False, dir=working_dir or None
            ) as f:
                script_content = f"""#!/bin/bash
set -e
export GITHUB_OUTPUT=$(mktemp)
export GITHUB_ENV=$(mktemp)
export GITHUB_STEP_SUMMARY=$(mktemp)

{command}

# Output file contents for parsing
echo "=== GITHUB_OUTPUT ==="
cat "$GITHUB_OUTPUT" 2>/dev/null || true
echo "=== GITHUB_ENV ==="
cat "$GITHUB_ENV" 2>/dev/null || true
echo "=== END ==="
"""
                f.write(script_content)
                script_path = f.name

            # Make executable
            os.chmod(script_path, 0o755)

            # Prepare environment
            exec_env = os.environ.copy()
            if env_vars:
                exec_env.update({k: str(v) for k, v in env_vars.items()})

            # Execute
            result = subprocess.run(
                [script_path],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=exec_env,
                cwd=working_dir or os.getcwd(),
            )

            # Parse outputs and env updates
            env_updates = self._parse_special_outputs(result.stdout)

            # Cleanup
            os.unlink(script_path)

            success = result.returncode == 0
            return success, result.stdout, result.stderr, env_updates

        except subprocess.TimeoutExpired:
            logger.error(f"Command timeout after {self.timeout}s: {command[:100]}...")
            return False, "", f"Timeout after {self.timeout}s", {}

        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return False, "", str(e), {}

    def _parse_special_outputs(self, stdout: str) -> Dict[str, str]:
        """Parse GITHUB_OUTPUT and GITHUB_ENV from command output"""
        outputs = {}

        lines = stdout.split("\n")
        in_output_section = False
        in_env_section = False

        for line in lines:
            line = line.strip()

            if line == "=== GITHUB_OUTPUT ===":
                in_output_section = True
                in_env_section = False
                continue
            elif line == "=== GITHUB_ENV ===":
                in_output_section = False
                in_env_section = True
                continue
            elif line == "=== END ===":
                in_output_section = False
                in_env_section = False
                continue

            if (in_output_section or in_env_section) and "=" in line:
                try:
                    key, value = line.split("=", 1)
                    outputs[key.strip()] = value.strip()
                except:
                    pass

        return outputs


class FileUtils:
    """File system utilities"""

    @staticmethod
    def ensure_dir(path: str) -> None:
        """Ensure directory exists"""
        os.makedirs(path, exist_ok=True)

    @staticmethod
    def write_text(path: str, content: str) -> None:
        """Write text to file"""
        FileUtils.ensure_dir(os.path.dirname(path))
        with open(path, "w") as f:
            f.write(content)

    @staticmethod
    def read_text(path: str) -> str:
        """Read text from file"""
        with open(path, "r") as f:
            return f.read()


class ConfigLoader:
    """Configuration loading utilities"""

    @staticmethod
    def from_dict(
        config_dict: Dict[str, Any], defaults: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Merge config with defaults"""
        result = defaults.copy() if defaults else {}
        result.update(config_dict or {})
        return result

    @staticmethod
    def from_env(prefix: str = "FLOWRITE_") -> Dict[str, Any]:
        """Load configuration from environment variables"""
        config = {}
        for key, value in os.environ.items():
            if key.startswith(prefix):
                config_key = key[len(prefix) :].lower()

                # Try to convert to appropriate type
                if value.lower() in ["true", "false"]:
                    config[config_key] = value.lower() == "true"
                elif value.isdigit():
                    config[config_key] = int(value)
                else:
                    try:
                        config[config_key] = float(value)
                    except ValueError:
                        config[config_key] = value

        return config
