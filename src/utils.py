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
    def substitute(text: str, variables: Dict[str, Any]) -> str:
        """Substitute variables in text using ${VAR} or $VAR patterns"""
        if not text or not variables:
            return text

        result = text

        # Handle ${VAR} patterns first (more specific)
        for var_name, value in variables.items():
            patterns = [f"${{{var_name}}}", f"${var_name}"]
            str_value = str(value) if value is not None else ""

            for pattern in patterns:
                result = result.replace(pattern, str_value)

        # Handle environment variables that aren't in our dict
        env_pattern = r"\$\{([^}]+)\}"
        matches = re.findall(env_pattern, result)
        for var_name in matches:
            if var_name not in variables:
                env_value = os.environ.get(var_name, "")
                result = result.replace(f"${{{var_name}}}", env_value)

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

    def execute_simulation(
        self, command: str, env_vars: Optional[Dict[str, str]] = None
    ) -> Tuple[bool, Dict[str, str]]:
        """
        Simulate command execution for testing with proper variable expansion
        """
        if not command.strip():
            return True, {}

        # Use empty dict if env_vars is None
        env_vars = env_vars or {}

        # Substitute variables for simulation
        if env_vars:
            command = VariableSubstitution.substitute(command, env_vars)

        logger.info(f"SIMULATION: {command}")

        # Simulate bash variable expansion and command execution
        sim_env = dict(env_vars)  # Copy the environment
        outputs = {}

        # Process commands line by line to simulate bash execution
        lines = command.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            i += 1

            if not line or line.startswith("#"):
                continue

            # Handle simple if statements
            if line.startswith("if ") and line.endswith("; then"):
                # Extract condition and find matching fi
                condition = line[3:-6].strip()  # Remove 'if ' and '; then'
                then_lines = []
                else_lines = []
                in_else = False
                nesting_level = 1  # Track nested if statements

                # Collect lines until matching 'fi'
                while i < len(lines):
                    current_line = lines[i].strip()
                    i += 1

                    if current_line.startswith("if ") and current_line.endswith(
                        "; then"
                    ):
                        nesting_level += 1
                    elif current_line == "fi":
                        nesting_level -= 1
                        if nesting_level == 0:
                            break
                    elif current_line == "else" and nesting_level == 1:
                        # Only switch to else block for the outer if statement
                        in_else = True
                        continue

                    if in_else:
                        else_lines.append(current_line)
                    else:
                        then_lines.append(current_line)

                # Evaluate condition (simple pattern matching)
                condition_met = self._evaluate_bash_condition(condition, sim_env)

                # Execute appropriate block
                block_to_execute = then_lines if condition_met else else_lines
                for block_line in block_to_execute:
                    if (
                        "=" in block_line
                        and not block_line.startswith("echo")
                        and ">>" not in block_line
                    ):
                        # Process variable assignment
                        self._process_variable_assignment(block_line, sim_env)
                    elif (
                        "GITHUB_OUTPUT" in block_line
                        or (
                            ">>" in block_line
                            and 'echo "' in block_line
                            and "=" in block_line
                        )
                    ) and 'echo "' in block_line:
                        # Process GitHub output
                        self._process_github_output(block_line, sim_env, outputs)
                    elif "GITHUB_ENV" in block_line and 'echo "' in block_line:
                        # Process GitHub env
                        self._process_github_env(block_line, sim_env, outputs)
                continue

            # Simulate variable assignments (VAR=value or VAR="value")
            if "=" in line and not line.startswith("echo") and ">>" not in line:
                self._process_variable_assignment(line, sim_env)

            # Parse GITHUB_OUTPUT patterns with variable expansion
            elif (
                "GITHUB_OUTPUT" in line
                or (">>" in line and 'echo "' in line and "=" in line)
            ) and 'echo "' in line:
                self._process_github_output(line, sim_env, outputs)

            # Parse GITHUB_ENV patterns with variable expansion
            elif "GITHUB_ENV" in line and 'echo "' in line:
                self._process_github_env(line, sim_env, outputs)

        return True, outputs

    def _evaluate_bash_condition(self, condition: str, sim_env: Dict[str, str]) -> bool:
        """Evaluate simple bash conditions"""
        # Expand variables in condition
        expanded_condition = VariableSubstitution.substitute(condition, sim_env)

        # Handle pattern matching like [[ "$VAR" =~ ^(val1|val2)$ ]]
        if "=~" in expanded_condition:
            # Simple regex pattern matching
            import re

            # Try to match [[ "value" =~ pattern ]] format
            bracket_match = re.search(
                r'\[\[\s*"([^"]*)"\s*=~\s*(.+?)\s*\]\]', expanded_condition
            )
            if bracket_match:
                left = bracket_match.group(1)
                pattern = bracket_match.group(2).strip()
                try:
                    return bool(re.match(pattern, left))
                except Exception as e:
                    pass

            # Fallback to simple split approach
            parts = expanded_condition.split("=~", 1)
            if len(parts) == 2:
                left = parts[0].strip().strip("\"'[]")
                right = parts[1].strip().strip("\"'[]")

                try:
                    return bool(re.match(right, left))
                except Exception as e:
                    pass

            # Fallback to simple split approach
            parts = condition.split("=~", 1)
            if len(parts) == 2:
                left = parts[0].strip().strip("\"'[]")
                right = parts[1].strip().strip("\"'[]")

                try:
                    return bool(re.match(right, left))
                except:
                    pass

        # Handle equality checks with proper bracket parsing
        if "==" in condition:
            import re

            # Try to match [[ "value" == "value" ]] pattern
            bracket_match = re.search(
                r'\[\[\s*["\']?([^"\']*?)["\']?\s*==\s*["\']?([^"\']*?)["\']?\s*\]\]',
                condition,
            )
            if bracket_match:
                left = bracket_match.group(1)
                right = bracket_match.group(2)
                return left == right

            # Fallback to simple split for other patterns
            parts = condition.split("==", 1)
            if len(parts) == 2:
                left = parts[0].strip().strip("\"'[]")
                right = parts[1].strip().strip("\"'[]")
                return left == right

        # Default to true for unknown conditions
        return True

    def _process_variable_assignment(self, line: str, sim_env: Dict[str, str]):
        """Process a variable assignment line"""
        try:
            # Handle variable assignment
            if line.startswith("export "):
                line = line[7:]  # Remove 'export '

            var_name, value = line.split("=", 1)
            var_name = var_name.strip()

            # Remove quotes if present
            if (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            ):
                value = value[1:-1]

            # Expand variables in the value using current sim_env
            value = VariableSubstitution.substitute(value, sim_env)

            # Handle command substitution like $(date +%s)
            if "$(" in value:
                # Simple simulation of common commands
                import time
                import hashlib

                replacements = {
                    "$(date +%s)": str(int(time.time())),
                    "$(date +%Y%m%d_%H%M%S)": time.strftime("%Y%m%d_%H%M%S"),
                    "$(date +%Y%m%d)": time.strftime("%Y%m%d"),
                    "$(date +%H)": time.strftime("%H"),  # Hour in 24-hour format
                    "$(date +%H%M)": time.strftime("%H%M"),
                    "$(date -Iseconds)": time.strftime("%Y-%m-%dT%H:%M:%S%z")
                    or time.strftime("%Y-%m-%dT%H:%M:%S"),
                }

                # Handle simple hash commands
                import re

                hash_pattern = r'\$\(echo "([^"]*)" \| sha256sum \| cut -d\' \' -f1 \| head -c (\d+)\)'
                match = re.search(hash_pattern, value)
                if match:
                    text_to_hash = match.group(1)
                    # Expand variables in the text to hash
                    text_to_hash = VariableSubstitution.substitute(
                        text_to_hash, sim_env
                    )
                    hash_length = int(match.group(2))
                    hash_value = hashlib.sha256(text_to_hash.encode()).hexdigest()[
                        :hash_length
                    ]
                    value = re.sub(hash_pattern, hash_value, value)

                # Apply other replacements
                for pattern, replacement in replacements.items():
                    value = value.replace(pattern, replacement)

            sim_env[var_name] = value
        except:
            pass

    def _process_github_output(
        self, line: str, sim_env: Dict[str, str], outputs: Dict[str, str]
    ):
        """Process GITHUB_OUTPUT line"""
        try:
            start = line.find('echo "') + 6
            end = line.find('"', start)
            if start > 5 and end > start:
                content = line[start:end]
                # Expand variables in the content
                content = VariableSubstitution.substitute(content, sim_env)
                if "=" in content:
                    key, value = content.split("=", 1)
                    outputs[key.strip()] = value.strip()
        except:
            pass

    def _process_github_env(
        self, line: str, sim_env: Dict[str, str], outputs: Dict[str, str]
    ):
        """Process GITHUB_ENV line"""
        try:
            start = line.find('echo "') + 6
            end = line.find('"', start)
            if start > 5 and end > start:
                content = line[start:end]
                # Expand variables in the content
                content = VariableSubstitution.substitute(content, sim_env)
                if "=" in content:
                    key, value = content.split("=", 1)
                    outputs[key.strip()] = value.strip()
                    sim_env[key.strip()] = value.strip()  # Also update sim environment
        except:
            pass

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
